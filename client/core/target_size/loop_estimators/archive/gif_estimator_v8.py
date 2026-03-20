import os
import math
import time
import tempfile
import subprocess
import threading
import ffmpeg
from typing import Dict, Optional, Callable
from client.core.target_size._estimator_protocol import EstimatorProtocol
from client.core.target_size._common import get_ffmpeg_binary, run_ffmpeg_skill_standard

class Estimator(EstimatorProtocol):
    """
    GIF Estimator v7 - Content-Aware Solver
    
    Strategy: "Analyze -> Adapt -> Solve"
    1. Extracts a 1.5s sample.
    2. Runs TWO probes to determine 'Color Sensitivity' and 'Motion Complexity'.
    3. Selects the optimal Strategy (e.g., "Reduce Colors first" vs "Reduce FPS first").
    4. Solves for Resolution using the chosen strategy.
    """

    def get_output_extension(self) -> str:
        return 'gif'

    def get_media_metadata(self, file_path: str) -> dict:
        try:
            probe = ffmpeg.probe(file_path)
            video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            fmt = probe['format']
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

    def _run_encode(self, input_path, start, duration, w, h, fps, colors, dither, transform_filters=None) -> int:
        """Helper to encode a specific configuration and return size."""
        tmp = self._get_temp_filename()
        try:
            dither_type = dither.split(':')[0]
            dither_opts = f":bayer_scale={dither.split('=')[1]}" if 'scale=' in dither else ""
            
            # 1. Transforms
            chain = []
            if transform_filters and transform_filters.get('vf_filters'):
                chain.append(f"[0:v]{','.join(transform_filters['vf_filters'])}[t]")
                curr = "t"
            else:
                curr = "0:v"

            # 2. GIF Logic
            chain.append(
                f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];"
                f"[v]split[a][b];"
                f"[a]palettegen=max_colors={colors}[p];"
                f"[b][p]paletteuse=dither={dither_type}{dither_opts}"
            )
            
            filter_str = ";".join(chain)
            ffmpeg_bin = get_ffmpeg_binary()
            
            cmd = [
                ffmpeg_bin, '-y', '-hide_banner', '-loglevel', 'error',
                '-ss', str(start), '-t', str(duration),
                '-i', input_path,
                '-filter_complex', filter_str,
                tmp
            ]
            
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

        # --- 1. SETUP SAMPLE ---
        # 1.5s sample is enough for analysis
        sample_len = 1.5
        if meta['duration'] < 1.5: sample_len = meta['duration']
        start_time = min(meta['duration'] * 0.2, meta['duration'] - sample_len)
        
        # Calculate Budget Density (KB per second)
        # Safety buffer 15% for unsampled variation
        safe_target = target_size_bytes * 0.85
        kb_per_sec = (safe_target / meta['duration']) / 1024
        
        print(f"[GIF_v7] Analysis Budget: {kb_per_sec:.1f} KB/s")

        # --- 2. CONTENT ANALYSIS (The Smart Part) ---
        # We run two probes at a moderate resolution (e.g., 320p or 480p width)
        # to see how the video reacts to color reduction.
        
        test_w = min(480, meta['width'])
        test_h = int(meta['height'] * (test_w / meta['width']))
        
        # Probe A: High Fidelity (Is it complex?)
        size_hi = self._run_encode(input_path, start_time, sample_len, test_w, test_h, 15, 256, "bayer:bayer_scale=2", transform_filters)
        
        # Probe B: Low Color (Does reducing colors help?)
        size_lo = self._run_encode(input_path, start_time, sample_len, test_w, test_h, 15, 32, "none", transform_filters)
        
        # Color Sensitivity Index (0.0 to 1.0)
        # High value = Reducing colors saves A LOT of space (e.g. Flat UI, Cartoons)
        # Low value = Reducing colors barely helps (e.g. Noisy video, Real life footage)
        color_sensitivity = (size_hi - size_lo) / size_hi
        
        print(f"[GIF_v7] Sensitivity: {color_sensitivity:.2f} (Hi: {size_hi/1024:.0f}KB, Lo: {size_lo/1024:.0f}KB)")

        # --- 3. STRATEGY SELECTION ---
        # Based on sensitivity and budget, pick the "personality" of the settings.
        
        fps = 15
        dither = "bayer:bayer_scale=3"
        colors = 256
        
        # CASE A: Extreme Low Budget (< 50KB/s)
        if kb_per_sec < 50:
            fps = 10
            colors = 64
            dither = "none" # Desperate measures
            
        # CASE B: High Color Sensitivity (Cartoon/Logo)
        # We should reduce colors aggressively to keep resolution/fps high.
        elif color_sensitivity > 0.6:
            if kb_per_sec < 150: colors = 64
            elif kb_per_sec < 300: colors = 128
            else: colors = 256
            dither = "none" # Clean look for cartoons
            fps = 15
            
        # CASE C: Low Sensitivity (Real Video / Noise)
        # Reducing colors looks ugly and doesn't save space.
        # We must reduce Dither and FPS instead.
        elif color_sensitivity < 0.3:
            colors = 256 # Keep colors
            if kb_per_sec < 150:
                fps = 10
                dither = "bayer:bayer_scale=1" # Strong ordered dither
            elif kb_per_sec < 300:
                fps = 12
                dither = "bayer:bayer_scale=2"
            else:
                fps = 15
                dither = "floyd_steinberg" # Luxury
                
        # CASE D: Balanced (Standard)
        else:
            if kb_per_sec < 100: colors = 128; dither="bayer:bayer_scale=1"
            elif kb_per_sec < 250: colors = 256; dither="bayer:bayer_scale=3"
            else: colors = 256; dither="floyd_steinberg"

        # --- 4. RESOLUTION SOLVER ---
        # Now that we've tuned the "Texture" settings (FPS/Colors), 
        # we binary search the Scale to fit the budget.
        
        sample_target = (safe_target / meta['duration']) * sample_len
        best_scale = 0.1
        
        if not allow_downscale:
            best_scale = 1.0
        else:
            low, high = 0.1, 1.0
            orig_w, orig_h = meta['width'], meta['height']
            
            # 5 iterations
            for _ in range(5):
                mid = (low + high) / 2
                w = int(orig_w * mid)
                h = int(orig_h * mid)
                w -= w % 2
                h -= h % 2
                
                if w < 16: 
                    low = mid
                    continue
                
                sz = self._run_encode(input_path, start_time, sample_len, w, h, fps, colors, dither, transform_filters)
                
                if sz <= sample_target:
                    best_scale = mid
                    low = mid # Try bigger
                else:
                    high = mid # Too big
                    
        return {
            'fps': fps,
            'colors': colors,
            'dither': dither,
            'resolution_scale': best_scale,
            'resolution_w': int(meta['width'] * best_scale) & ~1,
            'resolution_h': int(meta['height'] * best_scale) & ~1
        }

    def execute(self, input_path, output_path, target_size_bytes, status_callback=None, stop_check=None, **options):
        self._current_stop_check = stop_check
        # ... (Standard Execute Logic same as v6) ...
        # Ensure you call self.estimate() first
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
        
        emit(f"Encoding GIF: {w}x{h}, {fps}fps, {colors}col, {dither}")

        # Parse Dither
        dither_type = dither.split(':')[0]
        dither_opts = f":bayer_scale={dither.split('=')[1]}" if 'scale=' in dither else ""
        
        # Transform chain
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
        cmd = [ffmpeg_bin, '-y', '-i', input_path, '-filter_complex', ";".join(chain), output_path]
        
        # Subprocess boilerplate
        try:
            # Drain pipe helper
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