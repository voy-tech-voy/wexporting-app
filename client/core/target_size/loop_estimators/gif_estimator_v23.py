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
    GIF Estimator v22 - Adaptive Hybrid Solver
    """

    # For Fixed Resolution: We go as low as needed
    DEEP_QUALITY_STEPS = [256, 128, 64, 32, 16] 
    
    # For Resize Enabled: We stop at this floor before downscaling
    QUALITY_FLOOR = {'fps': 12, 'colors': 128}

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

    def _calculate_effective_duration(self, meta_duration: float, options: dict) -> float:
        """
        Determines actual output duration after Trims and Retiming.
        """
        duration = meta_duration
        
        t_filters = options.get('transform_filters', {})
        inp_args = t_filters.get('input_args', {})
        
        # Normalize keys (handle '-t' vs 't', '-ss' vs 'ss')
        clean_args = {k.lstrip('-'): v for k, v in inp_args.items()}
        
        # Handle -ss (start) and -to (end) or -t (duration)
        if 'to' in clean_args and 'ss' in clean_args:
            # User set both start and end time
            try:
                start = float(clean_args['ss'])
                end = float(clean_args['to'])
                duration = max(0.1, end - start)
            except: pass
        elif 't' in clean_args:
            # Explicit duration trim
            try:
                duration = min(duration, float(clean_args['t']))
            except: pass
        elif 'ss' in clean_args:
            # Only start cut, duration = original - start
            try:
                start = float(clean_args['ss'])
                duration = max(0.1, duration - start)
            except: pass
        
        # Handle speed changes (atempo in vf_filters)
        vf = t_filters.get('vf_filters', [])
        for f in vf:
            if 'setpts=' in f:
                # setpts=0.5*PTS means 2x speed
                try:
                    factor = float(f.split('setpts=')[1].split('*')[0])
                    if factor > 0:
                        duration = duration * factor  # 0.5 factor = half duration
                except: pass
        
        return duration

    def _get_transformed_dimensions(self, orig_w: int, orig_h: int, options: dict) -> tuple:
        """
        Get dimensions after transform filters (resize, rotation) are applied.
        """
        t_filters = options.get('transform_filters', {})
        vf = t_filters.get('vf_filters', [])
        
        w, h = orig_w, orig_h
        
        # Check for rotation first (transpose swaps dimensions)
        for f in vf:
            if f.startswith('transpose='):
                # transpose=1 (90° CW) and transpose=2 (90° CCW) swap dimensions
                # Two transpose=2 filters for 180° don't swap
                transpose_count = sum(1 for flt in vf if flt.startswith('transpose='))
                if transpose_count == 1:
                    # 90° or 270° rotation - swap dimensions
                    w, h = h, w
                # 180° (two transposes) keeps same dimensions
                break
        
        # Check for explicit target_dimensions from transform builder
        target_dims = t_filters.get('target_dimensions')
        if target_dims:
            # If rotation swapped, we need to use target dims relative to rotated source
            if w != orig_w:  # Was rotated
                return target_dims  # Use as-is, transform builder should handle this
            return target_dims
        
        # Check vf_filters for scale filter
        for f in vf:
            if f.startswith('scale='):
                try:
                    parts = f.replace('scale=', '').split(':')
                    # Parse width
                    sw = parts[0].split('=')[-1] if '=' in parts[0] else parts[0]
                    # Parse height  
                    sh = parts[1].split(':')[0] if len(parts) > 1 else '-2'
                    
                    scale_w = int(sw) if sw not in ['-2', '-1'] else -2
                    scale_h = int(sh) if sh not in ['-2', '-1'] else -2
                    
                    if scale_w == -2 and scale_h > 0:
                        scale_w = int(w * (scale_h / h)) & ~1
                    elif scale_h == -2 and scale_w > 0:
                        scale_h = int(h * (scale_w / w)) & ~1
                    
                    if scale_w > 0 and scale_h > 0:
                        return (scale_w, scale_h)
                except: pass
        
        return (w, h)

    def _analyze_gradients(self, input_path: str, start: float) -> bool:
        """Detects if dither is needed. Flat colors (VAV < 18) get dither=none."""
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
            p_opts = f"max_colors={col}:stats_mode=diff"
            
            # Get vf_filters but remove scale since we apply our own w/h
            vf = filters.get('vf_filters', [])
            vf_no_scale = [f for f in vf if not f.startswith('scale=')]
            
            chain = []
            if vf_no_scale:
                chain.append(f"[0:v]{','.join(vf_no_scale)}[t]")
                curr = "t"
            else:
                curr = "0:v"
            
            chain.append(f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];[v]split[a][b];"
                         f"[a]palettegen={p_opts}[p];[b][p]paletteuse=dither={d_type}{d_opts}:diff_mode=rectangle")
            
            cmd = [get_ffmpeg_binary(), '-y', '-hide_banner', '-loglevel', 'error']
            for k, v in filters.get('input_args', {}).items(): cmd.extend([f'-{k.lstrip("-")}', str(v)])
            cmd.extend(['-ss', str(start), '-t', str(dur), '-i', input_path, '-filter_complex', ";".join(chain), tmp])
            
            subprocess.run(cmd, capture_output=True, creationflags=0x08000000 if os.name == 'nt' else 0)
            return os.path.getsize(tmp) if os.path.exists(tmp) else 999999999
        finally:
            if os.path.exists(tmp): os.remove(tmp)

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        meta = self.get_media_metadata(input_path)
        if not meta['duration']: return {}
        
        allow_downscale = options.get('allow_downscale', False)
        transform_filters = options.get('transform_filters', {})
        
        # Use effective duration (accounting for time trims)
        duration = self._calculate_effective_duration(meta['duration'], options)
        
        # Get dimensions after transform resize (if any)
        orig_w, orig_h = meta['width'], meta['height']
        base_w, base_h = self._get_transformed_dimensions(orig_w, orig_h, options)
        
        # 1. Start-of-logic Analysis: Do we have gradients?
        has_gradients = self._analyze_gradients(input_path, duration * 0.2)
        base_dither = "bayer:bayer_scale=3" if has_gradients else "none"
        
        usable_budget = target_size_bytes * 0.90 # 10% safety margin
        sample_dur, start_time = min(2.0, duration), duration * 0.2
        sample_target = (usable_budget / duration) * sample_dur
        
        best_cfg = None

        if not allow_downscale:
            # PATH A: FIXED RESOLUTION (v20 logic)
            # Prioritize fitting the budget by dropping quality as low as needed.
            for col in self.DEEP_QUALITY_STEPS:
                ref_fps = 10
                sz = self._run_sample(input_path, start_time, sample_dur, base_w, base_h, 
                                      ref_fps, col, base_dither, transform_filters)
                price_per_frame = sz / (ref_fps * sample_dur)
                max_fps = (usable_budget / duration) / price_per_frame
                
                if max_fps >= 5.0: # Even if it's a slideshow, make it fit
                    final_fps = min(int(max_fps), 24)
                    best_cfg = {'fps': final_fps, 'colors': col, 'dither': base_dither, 
                                'w': base_w, 'h': base_h, 'scale': 1.0, 'sz': price_per_frame * final_fps * sample_dur}
                    break
        else:
            # PATH B: AUTO-RESIZE (v21 logic)
            # Drop quality only to the "Floor", then resize to save the motion/colors.
            ladder = [{'c': 256, 'f': 24}, {'c': 256, 'f': 15}, {'c': 128, 'f': 12}]
            for tier in ladder:
                sz = self._run_sample(input_path, start_time, sample_dur, base_w, base_h, 
                                      tier['f'], tier['c'], base_dither, transform_filters)
                if sz <= sample_target:
                    best_cfg = {'fps': tier['f'], 'colors': tier['c'], 'dither': base_dither, 
                                'w': base_w, 'h': base_h, 'scale': 1.0, 'sz': sz}
                    break
            
            if not best_cfg:
                # Still too big at the floor? Lock floor and binary search for resolution.
                low_s, high_s = 0.1, 1.0
                found_scale = 0.1
                for _ in range(5):
                    mid_s = (low_s + high_s) / 2
                    tw, th = (int(base_w * mid_s) & ~1), (int(base_h * mid_s) & ~1)
                    sz = self._run_sample(input_path, start_time, sample_dur, tw, th, 
                                          self.QUALITY_FLOOR['fps'], self.QUALITY_FLOOR['colors'], base_dither, transform_filters)
                    if sz <= sample_target:
                        found_scale, low_s = mid_s, mid_s
                    else:
                        high_s = mid_s
                best_cfg = {'fps': self.QUALITY_FLOOR['fps'], 'colors': self.QUALITY_FLOOR['colors'], 
                            'dither': base_dither, 'scale': found_scale, 'sz': sz,
                            'w': int(base_w * found_scale) & ~1, 'h': int(base_h * found_scale) & ~1}

        if not best_cfg: return {}

        # 2. DITHER REFINEMENT: Analyze buffer to choose dither technique
        est_full = (best_cfg['sz'] / sample_dur) * duration
        buffer = (target_size_bytes - est_full) / target_size_bytes
        
        if has_gradients:
            if buffer > 0.18:
                best_cfg['dither'] = "sierra2_4a" # Quality upgrade
            elif buffer < 0.05:
                best_cfg['dither'] = "bayer:bayer_scale=5" # Size optimization
        else:
            best_cfg['dither'] = "none" # Keep flat colors sharp

        return {
            'fps': best_cfg['fps'], 'colors': best_cfg['colors'], 'dither': best_cfg['dither'],
            'resolution_w': best_cfg['w'], 'resolution_h': best_cfg['h'],
            'resolution_scale': round(best_cfg.get('scale', 1.0), 3),
            'has_gradients': has_gradients,
            'estimated_total_kb': round(est_full / 1024, 1)
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options):
        
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params: return False

        if status_callback:
            status_callback(f"Encoding: {params['resolution_w']}px, {params['fps']}fps, {params['dither']} dither")

        d_parts = params['dither'].split(':')
        d_type, d_opts = d_parts[0], f":{d_parts[1]}" if len(d_parts) > 1 else ""
        p_opts = f"max_colors={params['colors']}:stats_mode=diff"

        # Get transform filters, but remove any scale filter since we'll use our calculated resolution
        vf = options.get('transform_filters', {}).get('vf_filters', [])
        vf_no_scale = [f for f in vf if not f.startswith('scale=')]
        
        chain = []
        if vf_no_scale:
            chain.append(f"[0:v]{','.join(vf_no_scale)}[t]")
            curr = "t"
        else:
            curr = "0:v"
        chain.append(f"[{curr}]fps={params['fps']},scale={params['resolution_w']}:{params['resolution_h']}:flags=lanczos[v];"
                     f"[v]split[a][b];[a]palettegen={p_opts}[p];[b][p]paletteuse=dither={d_type}{d_opts}:diff_mode=rectangle")

        cmd = [get_ffmpeg_binary(), '-y']
        for k, v in options.get('transform_filters', {}).get('input_args', {}).items():
            cmd.extend([f'-{k.lstrip("-")}', str(v)])
        cmd.extend(['-i', input_path, '-filter_complex', ";".join(chain), output_path])
        
        try:
            proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL, creationflags=0x08000000 if os.name == 'nt' else 0)
            while proc.poll() is None:
                if stop_check and stop_check():
                    proc.terminate(); return False
                time.sleep(0.5)
            return proc.returncode == 0
        except: return False