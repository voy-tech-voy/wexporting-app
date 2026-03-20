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
    GIF Estimator v8 - Iterative Solver
    
    Strategy:
    1. If Downscale Allowed: Use 'Content-Aware' logic to pick optimal texture, then solve Resolution.
    2. If Downscale OFF: Use 'Iterative Degradation'. Loop through quality tiers (FPS/Colors/Dither)
       until the sample fits the target budget at native resolution.
    """

    # Ordered from Heaviest -> Lightest
    QUALITY_TIERS = [
        # Tier 0: Luxury
        {'fps': 25, 'colors': 256, 'dither': "floyd_steinberg"}, 
        # Tier 1: High
        {'fps': 20, 'colors': 256, 'dither': "bayer:bayer_scale=3"},
        # Tier 2: Standard (Reference)
        {'fps': 15, 'colors': 256, 'dither': "bayer:bayer_scale=2"},
        # Tier 3: Economical (Reduced colors helper)
        {'fps': 15, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
        # Tier 4: Low FPS (Motion sacrifice)
        {'fps': 12, 'colors': 128, 'dither': "bayer:bayer_scale=3"},
        # Tier 5: Tight Budget
        {'fps': 10, 'colors': 64,  'dither': "bayer:bayer_scale=4"},
        # Tier 6: Starvation (Flat colors, low fps)
        {'fps': 8,  'colors': 32,  'dither': "none"},
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
                f"[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
                f"[b][p]paletteuse=dither={dither_type}{dither_opts}:diff_mode=rectangle"
            )
            
            filter_str = ";".join(chain)
            ffmpeg_bin = get_ffmpeg_binary()
            
            # Use -ss before -i for fast seeking on input
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
        print(f"[GIF_v8] Estimating for {target_size_bytes} bytes...")
        
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0: return {}

        allow_downscale = options.get('allow_downscale', True)
        transform_filters = options.get('transform_filters', {})

        # Sample Setup
        sample_len = 1.5
        if meta['duration'] < 1.5: sample_len = meta['duration']
        start_time = min(meta['duration'] * 0.2, meta['duration'] - sample_len)
        
        # Projection Multiplier
        # (Full Duration / Sample Duration) + 10% Safety Buffer for header variance
        projection_factor = (meta['duration'] / sample_len) * 1.10
        
        # Determine base resolution (considering UI transforms if possible, otherwise native)
        # Note: Ideally we'd parse transform_filters to get crop dimensions, but using native w/h 
        # is a safe baseline.
        orig_w, orig_h = meta['width'], meta['height']

        # =================================================================
        # STRATEGY A: FIXED RESOLUTION (Iterative Degradation)
        # =================================================================
        if not allow_downscale:
            print("[GIF_v8] Mode: Fixed Resolution. Searching Quality Tiers...")
            
            best_tier = self.QUALITY_TIERS[-1] # Default to worst
            
            for i, tier in enumerate(self.QUALITY_TIERS):
                # Test this tier
                sample_size = self._run_encode(
                    input_path, start_time, sample_len, 
                    orig_w, orig_h, 
                    tier['fps'], tier['colors'], tier['dither'], 
                    transform_filters
                )
                
                projected_total = sample_size * projection_factor
                print(f"   Tier {i}: {tier['fps']}fps/{tier['colors']}col -> Est: {projected_total/1024:.1f} KB")
                
                if projected_total <= target_size_bytes:
                    print(f"   [OK] Found Match at Tier {i}")
                    best_tier = tier
                    break
            
            # If even the last tier failed, we use it (Best Effort)
            return {
                'fps': best_tier['fps'],
                'colors': best_tier['colors'],
                'dither': best_tier['dither'],
                'resolution_scale': 1.0,
                'resolution_w': orig_w,
                'resolution_h': orig_h
            }

        # =================================================================
        # STRATEGY B: DYNAMIC RESOLUTION (Content-Aware)
        # =================================================================
        else:
            print("[GIF_v8] Mode: Dynamic Resolution. Analyzing Complexity...")
            
            # 1. Budget density
            safe_target = target_size_bytes * 0.90
            kb_per_sec = (safe_target / meta['duration']) / 1024
            
            # 2. Heuristic selection (Fast Start)
            # We pick a "Personality" based on budget, then solve Resolution.
            if kb_per_sec > 200:
                base = self.QUALITY_TIERS[1] # High
            elif kb_per_sec > 100:
                base = self.QUALITY_TIERS[2] # Std
            elif kb_per_sec > 50:
                base = self.QUALITY_TIERS[4] # Low FPS
            else:
                base = self.QUALITY_TIERS[5] # Tight
                
            fps, colors, dither = base['fps'], base['colors'], base['dither']
            
            # 3. Solve Resolution (Binary Search)
            sample_target = (safe_target / meta['duration']) * sample_len
            
            low, high = 0.1, 1.0
            best_scale = 0.1
            
            for _ in range(5):
                mid = (low + high) / 2
                w = int(orig_w * mid)
                h = int(orig_h * mid)
                w -= w % 2
                h -= h % 2
                if w < 16: 
                    low = mid; continue
                
                sz = self._run_encode(input_path, start_time, sample_len, w, h, fps, colors, dither, transform_filters)
                
                if sz <= sample_target:
                    best_scale = mid
                    low = mid # Try bigger
                else:
                    high = mid # Shrink
            
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
        if not params:
            emit("Estimation failed")
            return False

        fps, colors, dither = params['fps'], params['colors'], params['dither']
        w, h = params['resolution_w'], params['resolution_h']
        
        emit(f"Encoding GIF: {w}x{h} @ {fps}fps, {colors} colors...")

        # Parse Dither
        dither_type = dither.split(':')[0]
        dither_opts = f":bayer_scale={dither.split('=')[1]}" if 'scale=' in dither else ""
        
        # Build Filter
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
        
        # Run
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