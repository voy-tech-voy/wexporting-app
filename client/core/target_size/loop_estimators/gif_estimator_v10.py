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
    GIF Estimator v9 - Granular Binary Solver
    
    Strategy:
    1. Defines 30+ 'Micro-Tiers' of quality (gradual reduction of FPS/Colors/Dither).
    2. Performs a Binary Search on these tiers using a 2s sample.
    3. Finds the highest quality tier that is projected to be <= 95% of target.
    """

    # Ordered strictly by "Heaviness" (Estimated Bitrate)
    # FPS: High impact
    # Dither: Floyd > Bayer2 > Bayer3 > Bayer5 > None
    # Colors: 256 > 192 > 128 > 96 > 64 > 32
    MICRO_TIERS = [
        # --- Luxury (High FPS, Full Color) ---
        {'id': 0, 'fps': 30, 'colors': 256, 'dither': "floyd_steinberg"},
        {'id': 1, 'fps': 25, 'colors': 256, 'dither': "floyd_steinberg"},
        {'id': 2, 'fps': 24, 'colors': 256, 'dither': "bayer:bayer_scale=3"},
        {'id': 3, 'fps': 20, 'colors': 256, 'dither': "bayer:bayer_scale=3"},
        {'id': 4, 'fps': 18, 'colors': 256, 'dither': "bayer:bayer_scale=3"},
        
        # --- Standard (15 FPS, Various Dithers) ---
        {'id': 5, 'fps': 15, 'colors': 256, 'dither': "floyd_steinberg"},
        {'id': 6, 'fps': 15, 'colors': 256, 'dither': "bayer:bayer_scale=2"},
        {'id': 7, 'fps': 15, 'colors': 256, 'dither': "bayer:bayer_scale=3"}, # Ref
        {'id': 8, 'fps': 15, 'colors': 192, 'dither': "bayer:bayer_scale=3"},
        {'id': 9, 'fps': 15, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
        {'id': 10, 'fps': 15, 'colors': 128, 'dither': "bayer:bayer_scale=5"}, # Clean ordered dither
        
        # --- Economy (12 FPS) ---
        {'id': 11, 'fps': 12, 'colors': 256, 'dither': "bayer:bayer_scale=3"},
        {'id': 12, 'fps': 12, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
        {'id': 13, 'fps': 12, 'colors': 96,  'dither': "bayer:bayer_scale=4"},
        {'id': 14, 'fps': 12, 'colors': 64,  'dither': "bayer:bayer_scale=4"},
        
        # --- Tight (10 FPS) ---
        {'id': 15, 'fps': 10, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
        {'id': 16, 'fps': 10, 'colors': 64,  'dither': "bayer:bayer_scale=3"},
        {'id': 17, 'fps': 10, 'colors': 64,  'dither': "bayer:bayer_scale=5"},
        {'id': 18, 'fps': 10, 'colors': 64,  'dither': "none"},
        
        # --- Starvation (Low FPS / Low Color) ---
        {'id': 19, 'fps': 8,  'colors': 64,  'dither': "bayer:bayer_scale=3"},
        {'id': 20, 'fps': 8,  'colors': 48,  'dither': "none"},
        {'id': 21, 'fps': 8,  'colors': 32,  'dither': "none"},
        {'id': 22, 'fps': 6,  'colors': 32,  'dither': "none"},
        {'id': 23, 'fps': 5,  'colors': 16,  'dither': "none"},
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

    def _run_encode(self, input_path, start, duration, w, h, fps, colors, dither, transform_filters=None) -> int:
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
            cmd = [
                ffmpeg_bin, '-y', '-hide_banner', '-loglevel', 'error',
                '-ss', str(start), '-t', str(duration),
                '-i', input_path,
                '-filter_complex', ";".join(chain),
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
        print(f"[GIF_v9] Target: {target_size_bytes} bytes. Mode: Granular Search.")
        
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0: return {}

        allow_downscale = options.get('allow_downscale', True)
        transform_filters = options.get('transform_filters', {})

        # Setup Sample
        sample_len = 2.0
        if meta['duration'] < 2.0: sample_len = meta['duration']
        start_time = min(meta['duration'] * 0.2, meta['duration'] - sample_len)
        
        # Projection: We want to hug the line. 
        # Reducing safety buffer to 5% (1.05) to avoid over-compression (1.2MB vs 2MB issue).
        projection_factor = (meta['duration'] / sample_len) * 1.05
        
        orig_w, orig_h = meta['width'], meta['height']

        # =================================================================
        # STRATEGY A: FIXED RESOLUTION (Search Micro-Tiers)
        # =================================================================
        if not allow_downscale:
            print("[GIF_v9] Auto-Resize OFF. Optimizing via Tier Binary Search.")
            
            # Binary Search through the 24 Tiers
            low_idx = 0
            high_idx = len(self.MICRO_TIERS) - 1
            best_tier = self.MICRO_TIERS[-1] # Fallback to worst
            
            # We want the *lowest index* (Highest Quality) that fits.
            
            while low_idx <= high_idx:
                mid = (low_idx + high_idx) // 2
                tier = self.MICRO_TIERS[mid]
                
                sz = self._run_encode(
                    input_path, start_time, sample_len, orig_w, orig_h,
                    tier['fps'], tier['colors'], tier['dither'], transform_filters
                )
                
                est_total = sz * projection_factor
                print(f"   Tier {mid} ({tier['fps']}fps/{tier['colors']}col): Est {est_total/1024:.0f} KB")
                
                if est_total <= target_size_bytes:
                    best_tier = tier
                    # This fits, but can we get better? Try lower indices (higher quality)
                    high_idx = mid - 1
                else:
                    # Too big, need simpler tier (higher index)
                    low_idx = mid + 1
            
            return {
                'fps': best_tier['fps'],
                'colors': best_tier['colors'],
                'dither': best_tier['dither'],
                'resolution_scale': 1.0,
                'resolution_w': orig_w,
                'resolution_h': orig_h
            }

        # =================================================================
        # STRATEGY B: DYNAMIC RESOLUTION
        # =================================================================
        else:
            # Similar to v8, but using the granular list to pick a better starting point
            safe_target = target_size_bytes * 0.95
            kb_per_sec = (safe_target / meta['duration']) / 1024
            
            # Select "Personality" based on budget
            if kb_per_sec > 250:   base = self.MICRO_TIERS[3]  # Luxury
            elif kb_per_sec > 150: base = self.MICRO_TIERS[6]  # Std
            elif kb_per_sec > 80:  base = self.MICRO_TIERS[11] # Econ
            elif kb_per_sec > 40:  base = self.MICRO_TIERS[16] # Tight
            else:                  base = self.MICRO_TIERS[20] # Starvation
            
            fps, colors, dither = base['fps'], base['colors'], base['dither']
            
            # Binary Search Scale
            sample_target = (safe_target / meta['duration']) * sample_len
            low, high = 0.1, 1.0
            best_scale = 0.1
            
            for _ in range(6):
                mid = (low + high) / 2
                w = int(orig_w * mid)
                h = int(orig_h * mid)
                w -= w % 2; h -= h % 2
                if w < 16: low = mid; continue
                
                sz = self._run_encode(input_path, start_time, sample_len, w, h, fps, colors, dither, transform_filters)
                
                if sz <= sample_target:
                    best_scale = mid
                    low = mid # Fits, try bigger
                else:
                    high = mid # Too big
            
            return {
                'fps': fps, 'colors': colors, 'dither': dither,
                'resolution_scale': best_scale,
                'resolution_w': int(orig_w * best_scale) & ~1,
                'resolution_h': int(orig_h * best_scale) & ~1
            }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options):
        
        def emit(msg): 
            if status_callback: status_callback(msg)
        def should_stop(): 
            return stop_check() if stop_check else False

        params = self.estimate(input_path, target_size_bytes, **options)
        if not params: return False

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
        cmd = [ffmpeg_bin, '-y', '-i', input_path, '-filter_complex', ";".join(chain), output_path]
        
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