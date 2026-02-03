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
    GIF Estimator v14 - Content-Adaptive Balanced Solver
    
    Strategy: "Analyze -> Branch -> Solve"
    
    1. Analysis: Runs two probes (High Color vs Low Color) to calculate 'Color Sensitivity'.
    2. Branching: 
       - If Sensitive (Flat/Cartoon): Prioritizes dropping Colors, keeps FPS high.
       - If Insensitive (Gradients/Video): Prioritizes dropping FPS, keeps Colors high (256).
    3. Solving: Iterates through the selected Tier List to find the best fit.
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
        # ... (Reuse logic from v13 for accuracy) ...
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
            # Add input args from filters (e.g. trimming)
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
        
        # 1. Effective Duration
        eff_duration = self._calculate_effective_duration(meta['duration'], options)
        
        # 2. Sample Setup (2.0s)
        sample_len = min(2.0, eff_duration)
        start_time = 0.0
        if eff_duration > sample_len:
            # Offset sample 20% in, plus any input trim offset
            inp_args = transform_filters.get('input_args', {})
            base_offset = float(inp_args.get('-ss', inp_args.get('ss', 0)))
            start_time = min(eff_duration * 0.2, eff_duration - sample_len) + base_offset

        # 3. Budgeting
        # Safety Factor 0.90 to account for variability outside sample
        safe_target = target_size_bytes * 0.90
        kb_per_sec = (safe_target / eff_duration) / 1024
        
        print(f"[GIF_v14] Budget: {kb_per_sec:.1f} KB/s. Analyzing content type...")

        # 4. CONTENT ANALYSIS (Dual Probe)
        # Determine if we should prioritize Colors (Rich) or Resolution/Colors (Flat)
        
        # We test at a moderate resolution to be fast
        test_w = min(480, meta['width'])
        test_h = int(meta['height'] * (test_w / meta['width']))
        test_w -= test_w % 2; test_h -= test_h % 2

        # Probe A (Rich): 12fps, 256 Col, Bayer2 (Good baseline)
        size_rich = self._run_sample_encode(
            input_path, start_time, sample_len, test_w, test_h, 
            12, 256, "bayer:bayer_scale=2", transform_filters
        )
        
        # Probe B (Flat): 12fps, 32 Col, No Dither
        size_flat = self._run_sample_encode(
            input_path, start_time, sample_len, test_w, test_h, 
            12, 32, "none", transform_filters
        )
        
        # Sensitivity Index (0.0 - 1.0)
        # High (>0.5): Dropping colors saves HUGE space. (Cartoon/Logo)
        # Low (<0.3): Dropping colors doesn't help much. (Real Video/Gradients)
        sensitivity = (size_rich - size_flat) / size_rich if size_rich > 0 else 0
        print(f"[GIF_v14] Color Sensitivity: {sensitivity:.2f}")

        # 5. SELECT TIER LIST
        
        # === LIST A: RICH CONTENT (Gradients, Video) ===
        # Strategy: Protect 256 colors at all costs. Drop FPS first.
        # Dither: Bayer Scale 2 is cleaner than Floyd for gradients.
        TIERS_RICH = [
            {'fps': 15, 'colors': 256, 'dither': "bayer:bayer_scale=2"}, # Ideal
            {'fps': 12, 'colors': 256, 'dither': "bayer:bayer_scale=2"}, # Smooth enough
            {'fps': 10, 'colors': 256, 'dither': "bayer:bayer_scale=3"}, # Slight dither drop
            {'fps': 8,  'colors': 256, 'dither': "bayer:bayer_scale=3"}, # Low FPS, Rich Color
            {'fps': 12, 'colors': 128, 'dither': "bayer:bayer_scale=3"}, # Fallback: Drop colors
            {'fps': 10, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
            {'fps': 8,  'colors': 128, 'dither': "bayer:bayer_scale=3"},
        ]

        # === LIST B: FLAT CONTENT (Logos, Cartoons) ===
        # Strategy: Drop colors aggressively. Keep FPS higher if possible.
        TIERS_FLAT = [
            {'fps': 15, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
            {'fps': 15, 'colors': 64,  'dither': "none"}, # Clean look
            {'fps': 12, 'colors': 64,  'dither': "none"},
            {'fps': 15, 'colors': 32,  'dither': "none"},
            {'fps': 10, 'colors': 32,  'dither': "none"},
            {'fps': 8,  'colors': 16,  'dither': "none"}, # Retro style
        ]

        # Select List
        if sensitivity > 0.50:
            selected_tiers = TIERS_FLAT
            print("[GIF_v14] Mode: FLAT (Prioritizing clean lines, lower colors)")
        else:
            selected_tiers = TIERS_RICH
            print("[GIF_v14] Mode: RICH (Prioritizing 256 colors, lower FPS)")

        # 6. SOLVE (Iterate Tiers + Binary Search Resolution)
        
        orig_w, orig_h = meta['width'], meta['height']
        sample_target = (safe_target / eff_duration) * sample_len
        
        best_result = None

        # We iterate through tiers. For the first tier that looks "plausible", 
        # we try to solve resolution.
        
        for tier in selected_tiers:
            # Quick check at native resolution
            # If downscale is OFF, we verify native.
            # If downscale is ON, we verify if native is even close.
            
            w, h = orig_w, orig_h
            if allow_downscale and w > 1280: # Pre-scale big sources
                s = 1280/w; w=int(w*s); h=int(h*s); w-=w%2; h-=h%2

            tier_size = self._run_sample_encode(
                input_path, start_time, sample_len, w, h,
                tier['fps'], tier['colors'], tier['dither'], transform_filters
            )
            
            projected = (tier_size / sample_len) * eff_duration
            
            # Logic:
            # 1. If Native fits, USE IT.
            # 2. If Downscale allowed:
            #    - If projected is < 3.0x Target, we can probably scale down to fit.
            #    - If projected is > 3.0x Target, this tier is too heavy, skip to next.
            
            if projected <= target_size_bytes:
                # Perfect fit at native/high res
                best_result = {**tier, 'resolution_w': w, 'resolution_h': h, 'resolution_scale': w/orig_w}
                print(f"   ✓ Match found: Tier {tier['fps']}fps/{tier['colors']}col @ {w}x{h}")
                break
            
            elif allow_downscale and projected < (target_size_bytes * 3.0):
                # It's within striking distance via downscaling. Solve Resolution.
                print(f"   -> Solving Res for Tier {tier['fps']}fps/{tier['colors']}col (Est: {projected/1024:.0f}KB)...")
                
                low, high = 0.1, 1.0
                best_scale = 0.1
                
                for _ in range(5):
                    mid = (low + high) / 2
                    sw = int(orig_w * mid); sh = int(orig_h * mid); sw-=sw%2; sh-=sh%2
                    if sw < 32: low = mid; continue
                    
                    sz = self._run_sample_encode(
                        input_path, start_time, sample_len, sw, sh,
                        tier['fps'], tier['colors'], tier['dither'], transform_filters
                    )
                    
                    # Convert sample size to full size
                    full_sz = (sz / sample_len) * eff_duration
                    
                    if full_sz <= safe_target:
                        best_scale = mid
                        low = mid # Try bigger
                    else:
                        high = mid # Shrink
                
                # Found the best scale for this tier
                fw = int(orig_w * best_scale) & ~1
                fh = int(orig_h * best_scale) & ~1
                
                best_result = {**tier, 'resolution_w': fw, 'resolution_h': fh, 'resolution_scale': best_scale}
                break # Stop at the highest quality tier we could scale to fit
            
            else:
                print(f"   x Skipping Tier {tier['fps']}fps/{tier['colors']}col (Too heavy: {projected/1024:.0f}KB)")

        # Fallback if everything failed
        if not best_result:
            fallback = selected_tiers[-1]
            if allow_downscale:
                # Emergency tiny scale
                best_result = {**fallback, 'resolution_w': int(orig_w*0.2)&~1, 'resolution_h': int(orig_h*0.2)&~1, 'resolution_scale': 0.2}
            else:
                best_result = {**fallback, 'resolution_w': orig_w, 'resolution_h': orig_h, 'resolution_scale': 1.0}

        return best_result

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
                emit(f"✓ Done: {os.path.getsize(output_path)/1024:.1f} KB")
                return True
            else:
                emit(f"Error: {b''.join(errs).decode('utf-8', 'ignore')[-200:]}")
                return False
        except Exception as e:
            emit(f"Ex Error: {e}")
            return False