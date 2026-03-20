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
    GIF Estimator v15 - The Binary-Binary Solver
    
    Strategy: Two-Stage Binary Search (O(log n) complexity)
    
    1. Tier Search: Binary searches through 30+ quality tiers (FPS/Colors) at a 
       Reference Resolution to find the best 'Texture Quality' that fits the budget neighborhood.
    2. Scale Search: Binary searches Resolution (Scale) using the selected Tier 
       to hit the exact byte target.
       
    Improvements:
    - Speed: Drastically faster due to logarithmic searching (skips steps intelligently).
    - Accuracy: Uses "Effective Duration" and Dynamic Overhead logic to reduce estimation error.
    """

    # Sorted strictly by "Cost" (High to Low)
    SORTED_TIERS = [
        # --- LUXURY (High FPS) ---
        {'id': 0,  'fps': 30, 'colors': 256, 'dither': "floyd_steinberg"},
        {'id': 1,  'fps': 25, 'colors': 256, 'dither': "bayer:bayer_scale=3"},
        {'id': 2,  'fps': 20, 'colors': 256, 'dither': "bayer:bayer_scale=3"},
        
        # --- STANDARD (15 FPS - Various Dithers) ---
        {'id': 3,  'fps': 15, 'colors': 256, 'dither': "floyd_steinberg"},
        {'id': 4,  'fps': 15, 'colors': 256, 'dither': "bayer:bayer_scale=2"},
        {'id': 5,  'fps': 15, 'colors': 256, 'dither': "bayer:bayer_scale=3"}, # Benchmark
        {'id': 6,  'fps': 15, 'colors': 192, 'dither': "bayer:bayer_scale=3"},
        {'id': 7,  'fps': 15, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
        {'id': 8,  'fps': 15, 'colors': 128, 'dither': "bayer:bayer_scale=5"}, # Clean ordered
        
        # --- SMOOTH ECONOMY (12 FPS) ---
        {'id': 9,  'fps': 12, 'colors': 256, 'dither': "bayer:bayer_scale=3"},
        {'id': 10, 'fps': 12, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
        {'id': 11, 'fps': 12, 'colors': 64,  'dither': "bayer:bayer_scale=3"},
        
        # --- COMPROMISE (10 FPS) ---
        {'id': 12, 'fps': 10, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
        {'id': 13, 'fps': 10, 'colors': 64,  'dither': "bayer:bayer_scale=3"},
        {'id': 14, 'fps': 10, 'colors': 64,  'dither': "bayer:bayer_scale=5"},
        {'id': 15, 'fps': 10, 'colors': 64,  'dither': "none"},
        
        # --- STARVATION (Low FPS / Low Color) ---
        {'id': 16, 'fps': 8,  'colors': 64,  'dither': "bayer:bayer_scale=3"},
        {'id': 17, 'fps': 8,  'colors': 48,  'dither': "none"},
        {'id': 18, 'fps': 8,  'colors': 32,  'dither': "none"},
        {'id': 19, 'fps': 6,  'colors': 32,  'dither': "none"},
        {'id': 20, 'fps': 5,  'colors': 16,  'dither': "none"},
        {'id': 21, 'fps': 5,  'colors': 8,   'dither': "none"},
    ]

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
        # Calculate duration based on trims and speed multipliers
        duration = meta_duration
        t_filters = options.get('transform_filters', {})
        inp_args = t_filters.get('input_args', {})
        clean_args = {k.lstrip('-'): v for k, v in inp_args.items()}
        
        if 't' in clean_args:
            try: duration = min(duration, float(clean_args['t']))
            except: pass
        elif 'ss' in clean_args:
            try: duration = max(0.1, duration - float(clean_args['ss']))
            except: pass

        speed_factor = options.get('speed_factor', 1.0)
        if speed_factor > 0: duration = duration / speed_factor
        return duration

    def _run_sample_encode(self, input_path, start, duration, w, h, fps, colors, dither, transform_filters) -> int:
        tmp = self._get_temp_filename()
        try:
            dither_type = dither.split(':')[0]
            dither_opts = f":bayer_scale={dither.split('=')[1]}" if 'scale=' in dither else ""
            
            chain = []
            if transform_filters and transform_filters.get('vf_filters'):
                chain.append(f"[0:v]{','.join(transform_filters['vf_filters'])}[t]")
                curr = "t"
            else:
                curr = "0:v"

            chain.append(
                f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];"
                f"[v]split[a][b];"
                f"[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
                f"[b][p]paletteuse=dither={dither_type}{dither_opts}:diff_mode=rectangle"
            )
            
            ffmpeg_bin = get_ffmpeg_binary()
            # Handle input args (HWAccel, trims)
            input_args = transform_filters.get('input_args', {})
            cmd = [ffmpeg_bin, '-y', '-hide_banner', '-loglevel', 'error']
            
            for k, v in input_args.items():
                cmd.extend([f'-{k.lstrip("-")}', str(v)])
            
            cmd.extend([
                '-ss', str(start), '-t', str(duration),
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
        
        eff_duration = self._calculate_effective_duration(meta['duration'], options)
        
        # Sample Setup (2.0s)
        sample_len = min(2.0, eff_duration)
        start_time = 0.0
        if eff_duration > sample_len:
            inp_args = transform_filters.get('input_args', {})
            base_offset = float(inp_args.get('-ss', inp_args.get('ss', 0)))
            start_time = min(eff_duration * 0.2, eff_duration - sample_len) + base_offset

        # Target Calculation
        # GIF overhead is tricky. We define a sample target.
        # We assume the sample represents the whole video linearly + 5% variance buffer.
        sample_target = (target_size_bytes / eff_duration) * sample_len * 0.95
        
        orig_w, orig_h = meta['width'], meta['height']

        # =================================================================
        # PHASE 1: TIER SELECTION (Binary Search)
        # =================================================================
        # We search for the Tier that fits closest to the budget at a "Reference Resolution".
        # Reference Resolution: 480p width (Standard GIF size)
        # This keeps the test fast and realistic.
        
        ref_w = min(480, orig_w)
        ref_h = int(orig_h * (ref_w / orig_w))
        ref_w -= ref_w % 2; ref_h -= ref_h % 2
        
        # If we can't downscale, we MUST test at Native resolution
        if not allow_downscale:
            ref_w, ref_h = orig_w, orig_h

        print(f"[GIF_v15] Searching {len(self.SORTED_TIERS)} Tiers for {target_size_bytes/1024:.0f}KB target...")
        
        low_idx = 0
        high_idx = len(self.SORTED_TIERS) - 1
        best_tier_idx = high_idx # Default to worst
        
        # Optimization: Don't search everything. 
        # Check median first.
        
        while low_idx <= high_idx:
            mid = (low_idx + high_idx) // 2
            tier = self.SORTED_TIERS[mid]
            
            # Encode Sample
            sz = self._run_sample_encode(
                input_path, start_time, sample_len, ref_w, ref_h,
                tier['fps'], tier['colors'], tier['dither'], transform_filters
            )
            
            print(f"   Tier {mid} ({tier['fps']}fps/{tier['colors']}col): {sz/1024:.1f}KB vs Target {sample_target/1024:.1f}KB")
            
            if sz <= sample_target:
                # This fits! But is it too small? 
                # If we are way under budget (< 50%), we are sacrificing too much quality.
                # Try to find a higher quality tier (Lower Index) that also fits.
                best_tier_idx = mid
                high_idx = mid - 1
            else:
                # Too big! We must go lower quality (Higher Index)
                low_idx = mid + 1

        selected_tier = self.SORTED_TIERS[best_tier_idx]
        print(f"[GIF_v15] Selected Tier {best_tier_idx}: {selected_tier}")

        # =================================================================
        # PHASE 2: RESOLUTION SOLVER (Binary Search)
        # =================================================================
        # Now we lock the Tier (FPS/Color) and scale the Geometry to fill the budget.
        
        if not allow_downscale:
            return {
                'fps': selected_tier['fps'],
                'colors': selected_tier['colors'],
                'dither': selected_tier['dither'],
                'resolution_scale': 1.0,
                'resolution_w': orig_w,
                'resolution_h': orig_h
            }
        
        print("[GIF_v15] Fine-tuning Resolution...")
        low_scale, high_scale = 0.1, 1.0
        final_scale = 0.1
        
        # 5 Iterations to hone in on size
        for _ in range(5):
            mid_scale = (low_scale + high_scale) / 2
            w = int(orig_w * mid_scale); h = int(orig_h * mid_scale)
            w -= w % 2; h -= h % 2
            if w < 16: low_scale = mid_scale; continue
            
            sz = self._run_sample_encode(
                input_path, start_time, sample_len, w, h,
                selected_tier['fps'], selected_tier['colors'], selected_tier['dither'], transform_filters
            )
            
            # Project full size
            full_est = (sz / sample_len) * eff_duration
            
            # We want to be as close to target as possible without going over
            if full_est <= target_size_bytes * 0.98: # 98% cap for safety
                final_scale = mid_scale
                low_scale = mid_scale # Try bigger
            else:
                high_scale = mid_scale # Too big, shrink

        final_w = int(orig_w * final_scale) & ~1
        final_h = int(orig_h * final_scale) & ~1
        
        return {
            'fps': selected_tier['fps'],
            'colors': selected_tier['colors'],
            'dither': selected_tier['dither'],
            'resolution_scale': final_scale,
            'resolution_w': final_w,
            'resolution_h': final_h
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options):
        
        def emit(msg): 
            if status_callback: status_callback(msg)
        def should_stop(): 
            return stop_check() if stop_check else False

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
        
        chain.append(
            f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];"
            f"[v]split[a][b];"
            f"[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
            f"[b][p]paletteuse=dither={dither_type}{dither_opts}:diff_mode=rectangle"
        )
        
        ffmpeg_bin = get_ffmpeg_binary()
        cmd = [ffmpeg_bin, '-y', '-i', input_path]
        
        # Input args
        input_args = options.get('transform_filters', {}).get('input_args', {})
        for k, v in input_args.items():
            cmd.extend([f'-{k.lstrip("-")}', str(v)])
            
        cmd.extend(['-filter_complex', ";".join(chain), output_path])
        
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
            
            if proc.returncode == 0 and os.path.exists(output_path):
                emit(f"[OK] Done: {os.path.getsize(output_path)/1024:.1f} KB")
                return True
            else:
                emit(f"Error: {b''.join(errs).decode('utf-8', 'ignore')[-200:]}")
                return False
        except Exception as e:
            emit(f"Ex Error: {e}")
            return False