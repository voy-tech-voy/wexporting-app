import os
import math
import time
import tempfile
import subprocess
import threading
import ffmpeg
import re
from typing import Dict, Optional, Callable
from client.core.target_size._estimator_protocol import EstimatorProtocol
from client.core.target_size._common import get_ffmpeg_binary

class Estimator(EstimatorProtocol):
    """
    GIF Estimator v18 - The Hybrid Cost-Visual Solver
    
    Combines v10's Cost-Per-Frame accuracy with v17's visual gradient analysis.
    """

    # Tiers define "Texture Quality" (Color depth). 
    # FPS is calculated dynamically based on the cost of these tiers.
    QUALITY_TIERS = [
        {'id': 0, 'colors': 256, 'label': 'High Fidelity'},
        {'id': 1, 'colors': 128, 'label': 'Standard'},
        {'id': 2, 'colors': 64,  'label': 'Compromise'},
        {'id': 3, 'colors': 32,  'label': 'Economy'},
    ]

    def get_output_extension(self) -> str:
        return 'gif'

    def get_media_metadata(self, file_path: str) -> dict:
        try:
            probe = ffmpeg.probe(file_path)
            fmt = probe['format']
            video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            duration = float(fmt.get('duration', 0))
            if duration == 0 and video: duration = float(video.get('duration', 0))
            return {'duration': duration, 'width': int(video['width']), 'height': int(video['height'])}
        except: return {'duration': 0, 'width': 0, 'height': 0}

    def _analyze_complexity(self, input_path: str, start: float) -> dict:
        """ Detects if the video is flat (UI/Text) or complex (Gradients). """
        try:
            ffmpeg_bin = get_ffmpeg_binary()
            cmd = [ffmpeg_bin, '-y', '-ss', str(start), '-t', '1', '-i', input_path,
                   '-vf', 'signalstats', '-f', 'null', '-']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            vav_values = re.findall(r"VAV=(\d+)", result.stderr)
            avg_vav = sum(int(v) for v in vav_values) / len(vav_values) if vav_values else 100
            return {'has_gradients': avg_vav > 18, 'score': avg_vav}
        except: return {'has_gradients': True, 'score': 100}

    def _run_sample_encode(self, input_path, start, duration, w, h, fps, colors, dither, transform_filters) -> int:
        tmp = tempfile.NamedTemporaryFile(suffix='.gif', delete=False).name
        try:
            d_parts = dither.split(':')
            d_type = d_parts[0]
            d_opts = f":{d_parts[1]}" if len(d_parts) > 1 else ""
            
            p_opts = f"max_colors={colors}:stats_mode=diff"
            if colors <= 4: p_opts += ":reserve_transparent=0"

            vf = transform_filters.get('vf_filters', [])
            chain = []
            curr = "0:v"
            if vf:
                chain.append(f"[0:v]{','.join(vf)}[t]"); curr = "t"
            
            chain.append(
                f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];"
                f"[v]split[a][b];"
                f"[a]palettegen={p_opts}[p];"
                f"[b][p]paletteuse=dither={d_type}{d_opts}:diff_mode=rectangle"
            )
            
            cmd = [get_ffmpeg_binary(), '-y', '-hide_banner', '-loglevel', 'error']
            for k, v in transform_filters.get('input_args', {}).items():
                cmd.extend([f'-{k.lstrip("-")}', str(v)])
            cmd.extend(['-ss', str(start), '-t', str(duration), '-i', input_path,
                        '-filter_complex', ";".join(chain), tmp])
            
            subprocess.run(cmd, capture_output=True, creationflags=0x08000000 if os.name == 'nt' else 0)
            return os.path.getsize(tmp) if os.path.exists(tmp) else 999999999
        finally:
            if os.path.exists(tmp) and os.access(tmp, os.F_OK): os.remove(tmp)

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0: return {}
        
        duration = meta['duration']
        orig_w, orig_h = meta['width'], meta['height']
        
        # 1. Visual Complexity Analysis
        analysis = self._analyze_complexity(input_path, duration * 0.2)
        has_gradients = analysis['has_gradients']
        
        # Base dither selection
        # If flat, no dither. If gradients, start with Bayer 3 for estimation.
        base_dither = "bayer:bayer_scale=3" if has_gradients else "none"

        # 2. Setup Budget and Samples
        usable_budget = target_size_bytes * 0.92 # 8% Safety buffer for GIF headers
        sample_len = min(2.0, duration)
        start_time = duration * 0.2
        
        # Extract transform filters
        transform_filters = options.get('transform_filters', {})
        
        # Reference resolution: 480p or native if smaller
        allow_downscale = options.get('allow_downscale', False)  # Default to no resize
        if allow_downscale:
            ref_w = min(480, orig_w)
            ref_h = int(orig_h * (ref_w / orig_w)) & ~1
        else:
            ref_w, ref_h = orig_w, orig_h

        best_params = None

        # 3. Cost-Per-Frame Search (v10 logic)
        for tier in self.QUALITY_TIERS:
            # We encode at a reference 10fps to find the "Price per frame"
            ref_fps = 10
            sz = self._run_sample_encode(input_path, start_time, sample_len, ref_w, ref_h,
                                         ref_fps, tier['colors'], base_dither, transform_filters)
            
            # Calculate Max FPS this budget can afford at this resolution/color
            cost_per_frame = sz / (ref_fps * sample_len)
            max_total_frames = usable_budget / cost_per_frame
            calculated_fps = max_total_frames / duration
            
            # If we can afford at least 10 FPS, we take this tier.
            if calculated_fps >= 10.0:
                # Cap FPS at 24 (user requested removal of 30/25)
                final_fps = min(calculated_fps, 24.0)
                best_params = {
                    'fps': int(final_fps),
                    'colors': tier['colors'],
                    'dither': base_dither,
                    'resolution_w': ref_w,
                    'resolution_h': ref_h,
                    'resolution_scale': ref_w / orig_w,
                    'estimated_size': int(cost_per_frame * final_fps * duration)
                }
                break

        # 4. Emergency Resolution Solver (If even low FPS is too big)
        if not best_params:
            # Re-solve using v17-style resolution binary search at 8fps/64colors
            if allow_downscale:
                low_scale, high_scale = 0.1, 1.0
                best_scale = 0.1
                for _ in range(4):
                    mid = (low_scale + high_scale) / 2
                    w, h = (int(orig_w * mid) & ~1), (int(orig_h * mid) & ~1)
                    sz = self._run_sample_encode(input_path, start_time, sample_len, w, h, 8, 64, base_dither, transform_filters)
                    full_est = (sz / sample_len) * duration
                    if full_est <= usable_budget:
                        best_scale, low_scale = mid, mid
                    else:
                        high_scale = mid
            else:
                # Use native resolution
                best_scale = 1.0
                w, h = orig_w, orig_h
            
            best_params = {
                'fps': 8, 'colors': 64, 'dither': base_dither,
                'resolution_w': int(orig_w * best_scale) & ~1,
                'resolution_h': int(orig_h * best_scale) & ~1,
                'resolution_scale': best_scale,
                'estimated_size': int(usable_budget) # Approximated
            }

        # 5. Dynamic Dither Upgrade (v17 refinement)
        # If we have a huge buffer (>20%) and gradients, use Floyd-Steinberg
        buffer_percent = (target_size_bytes - best_params.get('estimated_size', 0)) / target_size_bytes
        if has_gradients:
            if buffer_percent > 0.20:
                best_params['dither'] = "floyd_steinberg"
            elif buffer_percent < 0.05:
                best_params['dither'] = "bayer:bayer_scale=5" # Save size

        # Final Return Data
        best_params.update({
            'has_gradients': has_gradients,
            'complexity_score': round(analysis['score'], 1),
            'size_buffer_percent': round(buffer_percent * 100, 1)
        })
        
        return best_params

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options):
        
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params: return False

        if status_callback:
            status_callback(f"Encoding {params['resolution_w']}px @ {params['fps']}fps (Dither: {params['dither']})")

        d_parts = params['dither'].split(':')
        d_type = d_parts[0]
        d_opts = f":{d_parts[1]}" if len(d_parts) > 1 else ""
        
        p_opts = f"max_colors={params['colors']}:stats_mode=diff"
        if params['colors'] <= 4: p_opts += ":reserve_transparent=0"

        vf = options.get('transform_filters', {}).get('vf_filters', [])
        chain = []
        curr = "0:v"
        if vf:
            chain.append(f"[0:v]{','.join(vf)}[t]"); curr = "t"
        
        chain.append(
            f"[{curr}]fps={params['fps']},scale={params['resolution_w']}:{params['resolution_h']}:flags=lanczos[v];"
            f"[v]split[a][b];"
            f"[a]palettegen={p_opts}[p];"
            f"[b][p]paletteuse=dither={d_type}{d_opts}:diff_mode=rectangle"
        )

        # Build command with input args BEFORE -i flag
        cmd = [get_ffmpeg_binary(), '-y']
        in_args = options.get('transform_filters', {}).get('input_args', {})
        for k, v in in_args.items():
            cmd.extend([f'-{k.lstrip("-")}', str(v)])
        cmd.extend(['-i', input_path, '-filter_complex', ";".join(chain), output_path])
        
        try:
            proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL, creationflags=0x08000000 if os.name == 'nt' else 0)
            while proc.poll() is None:
                if stop_check and stop_check():
                    proc.terminate(); return False
                time.sleep(0.2)
            return proc.returncode == 0
        except: return False