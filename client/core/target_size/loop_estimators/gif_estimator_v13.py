import os
import math
import time
import tempfile
import subprocess
import threading
import ffmpeg
from typing import Dict, Optional, Callable
from client.core.target_size._estimator_protocol import EstimatorProtocol
from client.core.target_size._common import get_ffmpeg_binary

class Estimator(EstimatorProtocol):
    """
    GIF Estimator v13 - Duration Aware Solver
    
    Changes from v12:
    - Calculates 'Effective Duration' considering Trims (-t) and Speed changes.
    - Prevents quality starvation when a long video is trimmed to a short loop.
    
    Strategy: Lighthouse Probe (Tier 2) + Ratio Prediction + Iterative Verification.
    """

    def get_output_extension(self) -> str:
        return 'gif'

    def get_media_metadata(self, file_path: str) -> dict:
        try:
            probe = ffmpeg.probe(file_path)
            fmt = probe['format']
            video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            duration = float(fmt.get('duration', 0))
            if duration == 0 and video:
                duration = float(video.get('duration', 0))
            return {
                'duration': duration,
                'width': int(video['width']),
                'height': int(video['height'])
            }
        except: return {'duration': 0, 'width': 0, 'height': 0}

    def _get_temp_filename(self, ext='gif'):
        f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
        f.close()
        return f.name

    def _calculate_effective_duration(self, meta_duration, options):
        """
        Determines the actual output duration after Trims and Retiming.
        """
        # 1. Start with full duration
        duration = meta_duration
        
        # 2. Check for Input Trims (-t or -ss) in input_args
        #    Format expected: {'-t': '5.0'} or {'t': 5.0}
        t_filters = options.get('transform_filters', {})
        inp_args = t_filters.get('input_args', {})
        
        # Normalize keys to handle '-t' vs 't'
        clean_args = {k.lstrip('-'): v for k, v in inp_args.items()}
        
        if 't' in clean_args:
            # User explicitly trimmed duration (e.g. "5.0")
            try:
                trim_duration = float(clean_args['t'])
                # Duration is the lesser of the trim or the remaining file
                duration = min(duration, trim_duration)
            except: pass
        
        elif 'ss' in clean_args:
            # User cut the start, but didn't set duration. 
            # Duration is Original - Start
            try:
                start = float(clean_args['ss'])
                duration = max(0.1, duration - start)
            except: pass

        # 3. Check for Speed Changes (Retiming)
        # Assuming the UI passes a 'speed_factor' (e.g., 2.0 = 2x fast forward)
        # If speed is doubled, duration is halved.
        speed_factor = options.get('speed_factor', 1.0)
        if speed_factor > 0:
            duration = duration / speed_factor
            
        print(f"[GIF_v13] Raw Duration: {meta_duration:.2f}s -> Effective: {duration:.2f}s")
        return duration

    def _run_sample_encode(self, input_path, start, duration, w, h, fps, colors, dither, transform_filters) -> int:
        tmp = self._get_temp_filename()
        try:
            dither_type = dither.split(':')[0]
            dither_opts = f":bayer_scale={dither.split('=')[1]}" if 'scale=' in dither else ""
            
            chain = []
            
            # Apply Pre-transforms (Resize, Speed, etc)
            # IMPORTANT: The probe must include the transforms to measure complexity correctly.
            if transform_filters and transform_filters.get('vf_filters'):
                chain.append(f"[0:v]{','.join(transform_filters['vf_filters'])}[t]")
                curr = "t"
            else:
                curr = "0:v"

            # For low color counts (<=3), disable transparent color slot reservation
            palette_opts = f"max_colors={colors}:stats_mode=diff"
            if colors <= 3:
                palette_opts += ":reserve_transparent=0"

            # Apply GIF Encoding Logic
            chain.append(
                f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];"
                f"[v]split[a][b];"
                f"[a]palettegen={palette_opts}[p];"
                f"[b][p]paletteuse=dither={dither_type}{dither_opts}:diff_mode=rectangle"
            )
            
            ffmpeg_bin = get_ffmpeg_binary()
            
            # Input args (seek, hwaccel)
            input_args = transform_filters.get('input_args', {})
            cmd = [ffmpeg_bin, '-y', '-hide_banner', '-loglevel', 'error']
            
            for k, v in input_args.items():
                cmd.extend([f'-{k.lstrip("-")}', str(v)])
            
            # We add explicit seeking for the sample probe here
            # Note: This might conflict if input_args already has -ss. 
            # For probing a sample, we usually override input args seeking logic
            # to target the specific sample window.
            
            cmd.extend([
                '-ss', str(start), 
                '-t', str(duration),
                '-i', input_path,
                '-filter_complex', ";".join(chain),
                tmp
            ])
            
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            if os.path.exists(tmp): return os.path.getsize(tmp)
            return 999999999
        except: return 999999999
        finally: 
            if os.path.exists(tmp): os.remove(tmp)

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0: return {}

        allow_downscale = options.get('allow_downscale', True)
        transform_filters = options.get('transform_filters', {})

        # --- 1. CALCULATE EFFECTIVE DURATION ---
        # This fixes the bug where trimming a long video resulted in starvation mode
        eff_duration = self._calculate_effective_duration(meta['duration'], options)
        
        # Setup Sample Window
        # We try to scan 2.0s. If the effective video is shorter, we scan the whole thing.
        sample_len = min(2.0, eff_duration)
        
        # Calculate start time (try to hit 20% mark, unless video is too short)
        start_time = 0.0
        if eff_duration > sample_len:
            start_time = min(eff_duration * 0.2, eff_duration - sample_len)
            # Add input offset if trimming via -ss
            inp_args = transform_filters.get('input_args', {})
            base_offset = float(inp_args.get('-ss', inp_args.get('ss', 0)))
            start_time += base_offset

        # Safety Factor (Overhead is higher on short loops)
        safety_factor = 0.90
        usable_budget = target_size_bytes * safety_factor
        
        print(f"[GIF_v13] Target: {target_size_bytes}B. Eff Duration: {eff_duration:.2f}s. Sample: {sample_len}s")

        orig_w, orig_h = meta['width'], meta['height']

        # --- 2. TIER DEFINITIONS ---
        tiers = [
            {'id': 0, 'colors': 256, 'dither': "floyd_steinberg",     'ratio': 1.35},
            {'id': 1, 'colors': 256, 'dither': "bayer:bayer_scale=2", 'ratio': 1.15},
            {'id': 2, 'colors': 256, 'dither': "bayer:bayer_scale=3", 'ratio': 1.00}, # Ref
            {'id': 3, 'colors': 128, 'dither': "bayer:bayer_scale=3", 'ratio': 0.85},
            {'id': 4, 'colors': 64,  'dither': "bayer:bayer_scale=3", 'ratio': 0.70},
            {'id': 5, 'colors': 64,  'dither': "none",                'ratio': 0.50},
            {'id': 6, 'colors': 32,  'dither': "none",                'ratio': 0.40},
            {'id': 7, 'colors': 16,  'dither': "none",                'ratio': 0.30},
            {'id': 8, 'colors': 8,   'dither': "none",                'ratio': 0.22},
            {'id': 9, 'colors': 2,   'dither': "none",                'ratio': 0.15},
        ]

        # Resolution Pre-check
        w, h = orig_w, orig_h
        if allow_downscale and w > 1280:
            scale = 1280/w; w=int(w*scale); h=int(h*scale); w-=w%2; h-=h%2

        # --- 3. LIGHTHOUSE PROBE ---
        ref_tier = tiers[2] # Standard Bayer 3
        ref_fps = 10
        
        sample_size = self._run_sample_encode(
            input_path, start_time, sample_len, w, h, ref_fps, 
            ref_tier['colors'], ref_tier['dither'], transform_filters
        )
        
        frame_count_sample = ref_fps * sample_len
        base_cost_per_frame = sample_size / frame_count_sample
        print(f"[GIF_v13] Base Cost/Frame: {base_cost_per_frame/1024:.2f} KB")

        # --- 4. PREDICT & PRUNE ---
        valid_candidates = []
        
        for tier in tiers:
            predicted_cost = base_cost_per_frame * tier['ratio']
            
            # Use EFFECTIVE duration for total frames calculation
            max_frames = usable_budget / predicted_cost
            projected_fps = max_frames / eff_duration 
            
            min_fps = 5.0 if tier['id'] >= 5 else 7.5
            
            if projected_fps >= min_fps:
                final_fps = min(int(projected_fps), 25)
                valid_candidates.append({'tier': tier, 'fps': final_fps})
            # else: pruned

        # --- 5. VERIFY & SELECT ---
        if not valid_candidates:
            if allow_downscale:
                print("[GIF_v13] All failed. Solving Resolution...")
                return self._emergency_resolution_solve(input_path, target_size_bytes, eff_duration, transform_filters)
            else:
                return {'fps': 5, 'colors': tiers[-1]['colors'], 'dither': tiers[-1]['dither'], 
                        'resolution_w': w, 'resolution_h': h, 'resolution_scale': w/orig_w}

        for candidate in valid_candidates:
            tier = candidate['tier']
            fps = candidate['fps']
            
            real_size = self._run_sample_encode(
                input_path, start_time, sample_len, w, h, fps,
                tier['colors'], tier['dither'], transform_filters
            )
            
            # Projection uses Effective Duration
            projected_total = (real_size / sample_len) * eff_duration * 1.05 
            
            if projected_total <= target_size_bytes:
                print(f"[GIF_v13] ✓ Winner: Tier {tier['id']} @ {fps} FPS")
                return {
                    'fps': fps, 'colors': tier['colors'], 'dither': tier['dither'],
                    'resolution_w': w, 'resolution_h': h, 'resolution_scale': w/orig_w
                }

        # Fallback
        fallback = valid_candidates[-1]
        return {
            'fps': fallback['fps'],
            'colors': fallback['tier']['colors'],
            'dither': fallback['tier']['dither'],
            'resolution_w': w, 'resolution_h': h, 'resolution_scale': w/orig_w
        }

    def _emergency_resolution_solve(self, input_path, target_size, eff_duration, transform_filters):
        """Binary search resolution for fixed 10fps/32colors."""
        fps = 10; colors = 32; dither = "none"
        sample_len = min(2.0, eff_duration); start = 0.0
        
        # Calculate sample target based on effective duration ratio
        sample_target = (target_size * 0.90 / eff_duration) * sample_len
        
        # Get metadata again to be sure of original dims
        meta = self.get_media_metadata(input_path)
        orig_w, orig_h = meta['width'], meta['height']
        
        low, high = 0.1, 1.0; best_scale = 0.1
        
        for _ in range(5):
            mid = (low + high) / 2
            w = int(orig_w * mid); h = int(orig_h * mid)
            w -= w%2; h -= h%2
            if w<16: low=mid; continue
            
            sz = self._run_sample_encode(input_path, start, sample_len, w, h, fps, colors, dither, transform_filters)
            if sz <= sample_target: best_scale=mid; low=mid
            else: high=mid
            
        return {
            'fps': fps, 'colors': colors, 'dither': dither,
            'resolution_w': int(orig_w * best_scale)&~1,
            'resolution_h': int(orig_h * best_scale)&~1,
            'resolution_scale': best_scale
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options):
        
        def emit(msg): 
            print(f"[GIF v13] {msg}")
            if status_callback: status_callback(msg)
        def should_stop(): 
            return stop_check() if stop_check else False

        print(f"[GIF v13] Starting export:")
        print(f"  Input: {input_path}")
        print(f"  Output: {output_path}")
        print(f"  Target size: {target_size_bytes} bytes")

        params = self.estimate(input_path, target_size_bytes, **options)
        if not params:
            emit("Estimation failed")
            return False

        fps, colors, dither = params['fps'], params['colors'], params['dither']
        w, h = params['resolution_w'], params['resolution_h']
        
        emit(f"Encoding GIF: {w}x{h} @ {fps}fps, {colors} colors...")

        dither_type = dither.split(':')[0]
        dither_opts = f":bayer_scale={dither.split('=')[1]}" if 'scale=' in dither else ""
        
        t_filters = options.get('transform_filters', {}).get('vf_filters', [])
        chain = []
        if t_filters: chain.append(f"[0:v]{','.join(t_filters)}[t]")
        curr = "t" if t_filters else "0:v"
        
        # For low color counts (<=3), disable transparent color slot reservation
        palette_opts = f"max_colors={colors}:stats_mode=diff"
        if colors <= 3:
            palette_opts += ":reserve_transparent=0"
        
        chain.append(
            f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];"
            f"[v]split[a][b];"
            f"[a]palettegen={palette_opts}[p];"
            f"[b][p]paletteuse=dither={dither_type}{dither_opts}:diff_mode=rectangle"
        )
        
        ffmpeg_bin = get_ffmpeg_binary()
        cmd = [ffmpeg_bin, '-y']
        
        # Add Input Args (Trims, etc) - MUST come BEFORE -i
        input_args = options.get('transform_filters', {}).get('input_args', {})
        for k, v in input_args.items():
            cmd.extend([f'-{k.lstrip("-")}', str(v)])
            
        cmd.extend(['-i', input_path, '-filter_complex', ";".join(chain), output_path])
        
        print(f"[GIF v13] FFmpeg command: {' '.join(cmd)}")
        
        try:
            def drain(p, l):
                while True:
                    c = p.read(4096)
                    if not c: break
                    l.append(c)

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            errs = []
            t = threading.Thread(target=drain, args=(proc.stderr, errs))
            t.daemon = True; t.start()
            
            while proc.poll() is None:
                if should_stop(): 
                    proc.terminate()
                    emit("Stopped")
                    return False
                time.sleep(0.1)
            t.join()
            
            print(f"[GIF v13] FFmpeg exit code: {proc.returncode}")
            print(f"[GIF v13] Output exists: {os.path.exists(output_path)}")
            if os.path.exists(output_path):
                print(f"[GIF v13] Output size: {os.path.getsize(output_path)} bytes")
            
            if proc.returncode == 0 and os.path.exists(output_path):
                emit(f"✓ Done: {os.path.getsize(output_path)/1024:.1f} KB")
                return True
            else:
                stderr_output = b''.join(errs).decode('utf-8', 'ignore')
                print(f"[GIF v13] FFmpeg stderr:\n{stderr_output}")
                emit(f"Error: {stderr_output[-200:]}")
                return False
        except Exception as e:
            print(f"[GIF v13] Exception: {e}")
            import traceback
            traceback.print_exc()
            emit(f"Ex Error: {e}")
            return False