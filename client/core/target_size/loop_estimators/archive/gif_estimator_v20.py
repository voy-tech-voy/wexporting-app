import os
import time
import tempfile
import subprocess
import threading
import ffmpeg
import re
from typing import Dict
from client.core.target_size._estimator_protocol import EstimatorProtocol
from client.core.target_size._common import get_ffmpeg_binary

class Estimator(EstimatorProtocol):
    """
    GIF Estimator v20 - The Constraint Solver (No-Scale Focus)
    
    Strategy: 
    1. Analyze video complexity (Gradients vs Flat).
    2. Calculate "Byte Price" per frame at various color depths.
    3. Solve for the highest possible FPS/Color combo within the target.
    4. Refine Dither based on remaining byte-buffer.
    """

    # We prioritize Colors (Gradient Quality) over FPS. 
    # The algorithm will try these color depths in order.
    COLOR_STEPS = [256, 128, 64, 32, 16]

    def get_output_extension(self) -> str:
        return 'gif'

    def get_media_metadata(self, file_path: str) -> dict:
        try:
            probe = ffmpeg.probe(file_path)
            v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            return {
                'duration': float(probe['format'].get('duration', v.get('duration', 0))),
                'width': int(v['width']), 'height': int(v['height'])
            }
        except: return {'duration': 0, 'width': 0, 'height': 0}

    def _analyze_gradients(self, input_path: str, start: float) -> bool:
        """Detects if the video has gradients (requires dither) or is flat (UI/Text)."""
        try:
            cmd = [get_ffmpeg_binary(), '-y', '-ss', str(start), '-t', '1', '-i', input_path,
                   '-vf', 'signalstats', '-f', 'null', '-']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            vavs = re.findall(r"VAV=(\d+)", res.stderr)
            avg_vav = sum(int(v) for v in vavs) / len(vavs) if vavs else 100
            # VAV > 18 usually indicates natural footage or gradients.
            return avg_vav > 18
        except: return True

    def _run_sample(self, input_path, start, dur, w, h, fps, col, dither, filters) -> int:
        tmp = tempfile.NamedTemporaryFile(suffix='.gif', delete=False).name
        try:
            d_parts = dither.split(':')
            d_type = d_parts[0]
            d_opts = f":{d_parts[1]}" if len(d_parts) > 1 else ""
            p_opts = f"max_colors={col}:stats_mode=diff" + (":reserve_transparent=0" if col <= 4 else "")
            
            vf = filters.get('vf_filters', [])
            chain = [f"[0:v]{','.join(vf)}[t]"] if vf else []
            curr = "t" if vf else "0:v"
            chain.append(f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];[v]split[a][b];"
                         f"[a]palettegen={p_opts}[p];[b][p]paletteuse=dither={d_type}{d_opts}:diff_mode=rectangle")
            
            cmd = [get_ffmpeg_binary(), '-y', '-hide_banner', '-loglevel', 'error']
            for k, v in filters.get('input_args', {}).items(): cmd.extend([f'-{k.lstrip("-")}', str(v)])
            cmd.extend(['-ss', str(start), '-t', str(dur), '-i', input_path, '-filter_complex', ";".join(chain), tmp])
            
            subprocess.run(cmd, capture_output=True, creationflags=0x08000000 if os.name == 'nt' else 0)
            return os.path.getsize(tmp) if os.path.exists(tmp) else 999999999
        finally:
            if os.path.exists(tmp) and os.access(tmp, os.F_OK): os.remove(tmp)

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        meta = self.get_media_metadata(input_path)
        if not meta['duration']: return {}
        
        allow_downscale = options.get('allow_downscale', False)
        duration = meta['duration']
        orig_w, orig_h = meta['width'], meta['height']
        
        # 1. ANALYSIS: Determine if we actually need dither
        has_gradients = self._analyze_gradients(input_path, duration * 0.2)
        base_dither = "bayer:bayer_scale=3" if has_gradients else "none"
        
        # 2. BUDGET: Use a 0.90 safety factor to avoid the "stuck" size issue
        usable_budget = target_size_bytes * 0.90
        sample_dur = min(2.0, duration)
        start_time = duration * 0.2
        
        # Resolution decision
        w, h = orig_w, orig_h
        if allow_downscale and w > 640:
            scale = 640/w; w=int(w*scale); h=int(h*scale)
        w, h = w&~1, h&~1

        best_params = None

        # 3. SEARCH: Find the best Color Depth and calculate exact FPS
        for col in self.COLOR_STEPS:
            # We test at 10 FPS to find the "Price Per Frame"
            ref_fps = 10
            sz = self._run_sample(input_path, start_time, sample_dur, w, h, ref_fps, col, base_dither, options.get('transform_filters', {}))
            
            # Price Per Frame = (Sample Size) / (Frames in Sample)
            price_per_frame = sz / (ref_fps * sample_dur)
            
            # Max FPS = (Budget per second) / (Price Per Frame)
            max_fps = (usable_budget / duration) / price_per_frame
            
            # If we can afford a watchable framerate (>= 8fps), we take this color depth
            if max_fps >= 8.0:
                final_fps = min(int(max_fps), 24) # Cap at 24fps
                best_params = {
                    'fps': final_fps,
                    'colors': col,
                    'dither': base_dither,
                    'resolution_w': w,
                    'resolution_h': h,
                    'est_size': price_per_frame * final_fps * duration
                }
                break

        # Fallback if the video is too heavy for the resolution at any color depth
        if not best_params:
            best_params = {'fps': 5, 'colors': 16, 'dither': 'none', 'resolution_w': w, 'resolution_h': h, 'est_size': usable_budget}

        # 4. DITHER REFINEMENT: Utilize the leftover buffer
        buffer_pct = (target_size_bytes - best_params['est_size']) / target_size_bytes
        
        if has_gradients:
            if buffer_pct > 0.15:
                best_params['dither'] = "floyd_steinberg" # Use elaborate dither
            elif buffer_pct < 0.05:
                best_params['dither'] = "bayer:bayer_scale=5" # Use least size impact dither
        else:
            best_params['dither'] = "none" # Keep it clean for flat colors

        return {
            **best_params,
            'resolution_scale': w / orig_w,
            'has_gradients': has_gradients,
            'buffer_pct': round(buffer_pct * 100, 2),
            'estimated_total_kb': round(best_params['est_size'] / 1024, 1)
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options):
        
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params: return False

        if status_callback:
            status_callback(f"Encoding: {params['resolution_w']}px, {params['fps']}fps, {params['colors']} colors ({params['dither']} dither)")

        d_parts = params['dither'].split(':')
        d_type = d_parts[0]
        d_opts = f":{d_parts[1]}" if len(d_parts) > 1 else ""
        p_opts = f"max_colors={params['colors']}:stats_mode=diff" + (":reserve_transparent=0" if params['colors'] <= 4 else "")

        vf = options.get('transform_filters', {}).get('vf_filters', [])
        chain = [f"[0:v]{','.join(vf)}[t]"] if vf else []
        curr = "t" if vf else "0:v"
        chain.append(f"[{curr}]fps={params['fps']},scale={params['resolution_w']}:{params['resolution_h']}:flags=lanczos[v];"
                     f"[v]split[a][b];[a]palettegen={p_opts}[p];[b][p]paletteuse=dither={d_type}{d_opts}:diff_mode=rectangle")

        cmd = [get_ffmpeg_binary(), '-y', '-i', input_path]
        in_args = options.get('transform_filters', {}).get('input_args', {})
        for k, v in in_args.items(): cmd.extend([f'-{k.lstrip("-")}', str(v)])
        cmd.extend(['-filter_complex', ";".join(chain), output_path])
        
        try:
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, creationflags=0x08000000 if os.name == 'nt' else 0)
            while proc.poll() is None:
                if stop_check and stop_check():
                    proc.terminate(); return False
                time.sleep(0.5)
            return proc.returncode == 0
        except: return False