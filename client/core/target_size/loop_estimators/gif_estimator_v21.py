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
    GIF Estimator v21 - The Quality-First Hybrid
    
    Strategy:
    1. Define a 'Quality Floor' (e.g., 12fps, 128 colors).
    2. Try to fit the video at Native Resolution by lowering quality down to the floor.
    3. If still too large at the floor, lock the floor settings and start 
       downscaling Resolution until the target is met.
    """

    # Quality targets from High to the 'Floor'
    QUALITY_LADDER = [
        {'colors': 256, 'fps': 24, 'label': 'Cinema'},
        {'colors': 256, 'fps': 18, 'label': 'Smooth'},
        {'colors': 128, 'fps': 15, 'label': 'Standard'},
        {'colors': 128, 'fps': 12, 'label': 'Quality Floor'}, # The limit before we resize
    ]

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
        try:
            cmd = [get_ffmpeg_binary(), '-y', '-ss', str(start), '-t', '1', '-i', input_path,
                   '-vf', 'signalstats', '-f', 'null', '-']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            vavs = re.findall(r"VAV=(\d+)", res.stderr)
            avg_vav = sum(int(v) for v in vavs) / len(vavs) if vavs else 100
            return avg_vav > 18
        except: return True

    def _run_sample(self, input_path, start, dur, w, h, fps, col, dither, filters) -> int:
        tmp = tempfile.NamedTemporaryFile(suffix='.gif', delete=False).name
        try:
            d_parts = dither.split(':')
            d_type, d_opts = d_parts[0], f":{d_parts[1]}" if len(d_parts) > 1 else ""
            
            # stats_mode=diff is better for 'rich motion' (prioritizes moving colors)
            p_opts = f"max_colors={col}:stats_mode=diff"
            
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
        
        allow_downscale = options.get('allow_downscale', True)
        duration, orig_w, orig_h = meta['duration'], meta['width'], meta['height']
        has_gradients = self._analyze_gradients(input_path, duration * 0.2)
        base_dither = "bayer:bayer_scale=3" if has_gradients else "none"
        
        usable_budget = target_size_bytes * 0.88 # 12% safety for LZW spikes
        sample_dur, start_time = min(2.0, duration), duration * 0.2
        sample_target = (usable_budget / duration) * sample_dur

        best_cfg = None

        # PHASE 1: Quality Degradation (Native Resolution)
        # Try to fit the target by only lowering FPS and Colors down to the 'Floor'
        for tier in self.QUALITY_LADDER:
            sz = self._run_sample(input_path, start_time, sample_dur, orig_w, orig_h, 
                                  tier['fps'], tier['colors'], base_dither, options.get('transform_filters', {}))
            if sz <= sample_target:
                best_cfg = {**tier, 'dither': base_dither, 'w': orig_w, 'h': orig_h, 'scale': 1.0, 'sz': sz}
                break

        # PHASE 2: Resolution Scaling (If Quality Floor wasn't enough)
        if not best_cfg and allow_downscale:
            floor = self.QUALITY_LADDER[-1]
            low_s, high_s = 0.1, 1.0
            found_scale = 0.1
            
            # Binary search for resolution while KEEPING the Floor's FPS/Colors
            for _ in range(5):
                mid_s = (low_s + high_s) / 2
                w, h = (int(orig_w * mid_s) & ~1), (int(orig_h * mid_s) & ~1)
                sz = self._run_sample(input_path, start_time, sample_dur, w, h, 
                                      floor['fps'], floor['colors'], base_dither, options.get('transform_filters', {}))
                
                if sz <= sample_target:
                    found_scale, low_s = mid_s, mid_s
                else:
                    high_s = mid_s
            
            best_cfg = {**floor, 'dither': base_dither, 'scale': found_scale, 'sz': sz,
                        'w': int(orig_w * found_scale) & ~1, 'h': int(orig_h * found_scale) & ~1}

        # Final Fallback (If scaling disabled or target is impossible)
        if not best_cfg:
            best_cfg = {**self.QUALITY_LADDER[-1], 'dither': 'none', 'w': orig_w, 'h': orig_h, 'scale': 1.0}

        # DITHER UPGRADE: If we have >15% buffer, use better dither (sierra2_4a is great for motion)
        est_full = (best_cfg.get('sz', sample_target) / sample_dur) * duration
        buffer = (target_size_bytes - est_full) / target_size_bytes
        
        if has_gradients:
            if buffer > 0.18: best_cfg['dither'] = "sierra2_4a"
            elif buffer < 0.05: best_cfg['dither'] = "bayer:bayer_scale=5"

        return {
            'fps': best_cfg['fps'], 'colors': best_cfg['colors'], 'dither': best_cfg['dither'],
            'resolution_w': best_cfg['w'], 'resolution_h': best_cfg['h'],
            'resolution_scale': round(best_cfg['scale'], 3),
            'has_gradients': has_gradients, 'est_size_mb': round(est_full/1024/1024, 2)
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options):
        
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params: return False

        if status_callback:
            status_callback(f"Encoding: {params['resolution_w']}px, {params['fps']}fps, {params['colors']} colors")

        d_type = params['dither'].split(':')[0]
        d_opts = f":{params['dither'].split(':')[1]}" if ':' in params['dither'] else ""
        p_opts = f"max_colors={params['colors']}:stats_mode=diff" # diff is best for motion

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