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
    GIF Estimator v10 - Cost-Per-Frame Solver
    
    Addresses the "Gradient Quality" issue by mathematically prioritizing 
    Color Depth over Frame Rate.
    
    Strategy:
    1. Sample the video at 'Reference Quality' (256 Colors) to find the 'Cost Per Frame'.
    2. Mathematically calculate the exact FPS that fits the budget:
       FPS = Budget / (CostPerFrame * Duration)
    3. If FPS > 8, use that exact FPS (e.g. 11, 13, 9) and KEEP full colors.
    4. Only degrade colors if the calculated FPS would be unwatchably low (<8).
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

    def _run_sample_encode(self, input_path, start, duration, w, h, fps, colors, dither, transform_filters) -> int:
        tmp = self._get_temp_filename()
        try:
            dither_type = dither.split(':')[0]
            dither_opts = f":bayer_scale={dither.split('=')[1]}" if 'scale=' in dither else ""
            
            chain = []
            # Transforms
            if transform_filters and transform_filters.get('vf_filters'):
                chain.append(f"[0:v]{','.join(transform_filters['vf_filters'])}[t]")
                curr = "t"
            else:
                curr = "0:v"

            # GIF Filter
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
        print(f"[GIF_v10] Target: {target_size_bytes} bytes. Strategy: Gradient Preservation.")
        
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0: return {}

        allow_downscale = options.get('allow_downscale', True)
        transform_filters = options.get('transform_filters', {})

        # Setup Sample
        sample_len = 2.0
        if meta['duration'] < 2.0: sample_len = meta['duration']
        start_time = min(meta['duration'] * 0.2, meta['duration'] - sample_len)
        
        # Projection Factor
        # GIF overhead is non-linear, but Cost-Per-Frame is a decent proxy.
        # We add 7% safety overhead.
        safety_factor = 0.93
        usable_budget = target_size_bytes * safety_factor
        
        orig_w, orig_h = meta['width'], meta['height']

        # =================================================================
        # TIER DEFINITIONS (Priority: Gradients > FPS)
        # =================================================================
        # We define tiers of "Visual Fidelity". We will stick to the highest tier 
        # possible and simply lower the FPS to make it fit.
        
        tiers = [
            # Tier 0: Perfect Gradients (Floyd-Steinberg + 256 Colors)
            {'colors': 256, 'dither': "floyd_steinberg"},
            # Tier 1: Clean Gradients (Bayer 2 + 256 Colors) - Less noise than Floyd
            {'colors': 256, 'dither': "bayer:bayer_scale=2"},
            # Tier 2: Standard (Bayer 3 + 256 Colors)
            {'colors': 256, 'dither': "bayer:bayer_scale=3"},
            # Tier 3: Compromise (128 Colors) - Gradients will start to band here
            {'colors': 128, 'dither': "bayer:bayer_scale=3"},
            # Tier 4: Starvation
            {'colors': 64,  'dither': "bayer:bayer_scale=4"},
        ]

        best_params = None
        
        # We iterate through Visual Quality tiers.
        # For each tier, we calculate the Max FPS allowed.
        
        for tier in tiers:
            # 1. Analyze "Cost Per Frame" for this visual quality
            # We encode the sample at a fixed reference FPS (e.g., 10fps) to get a baseline size.
            ref_fps = 10
            
            # Determine Resolution
            # If downscale is allowed, we might binary search here, but to keep v10 focused 
            # on the "Gradient vs FPS" trade-off, we'll assume native or simple downscale.
            # Let's try native resolution first.
            
            w, h = orig_w, orig_h
            if allow_downscale:
                # Heuristic: If 1080p, scale to 720p immediately for GIFs, they rarely need 1080p.
                if w > 1280: 
                    scale = 1280/w; w=int(w*scale); h=int(h*scale)
                    w-=w%2; h-=h%2

            sample_size = self._run_sample_encode(
                input_path, start_time, sample_len, w, h, ref_fps, 
                tier['colors'], tier['dither'], transform_filters
            )
            
            # 2. Calculate Cost Per Frame
            # This sample contained (ref_fps * sample_len) frames.
            frame_count_in_sample = ref_fps * sample_len
            cost_per_frame = sample_size / frame_count_in_sample
            
            # 3. Calculate Maximum Affordable FPS
            # Max_Frames = Budget / Cost_Per_Frame
            max_total_frames = usable_budget / cost_per_frame
            max_fps = max_total_frames / meta['duration']
            
            print(f"   [Tier {tier['colors']}col/{tier['dither'][:5]}] Cost/Frame: {cost_per_frame/1024:.1f}KB -> Max FPS: {max_fps:.2f}")

            # 4. Evaluate Viability
            # Can we run at a decent framerate with these colors?
            
            # GIF limit: Max 50fps (2cs), Min usually ~5fps (20cs)
            if max_fps >= 8.0:
                # YES! We can keep these rich colors and just use this calculated FPS.
                # Cap FPS at 25 to avoid waste.
                final_fps = min(max_fps, 25.0)
                
                # Snap to GIF-friendly delays (100/N) to avoid jitter, 
                # or just let FFmpeg handle rounding (it usually does a good job).
                # Let's round to nearest integer for clean logs, but passing float is fine.
                final_fps = int(final_fps)
                
                best_params = {
                    'fps': final_fps,
                    'colors': tier['colors'],
                    'dither': tier['dither'],
                    'resolution_w': w,
                    'resolution_h': h,
                    'resolution_scale': w / orig_w
                }
                break # STOP! We found the best quality (highest tier) that fits.
            
            # If Max FPS < 8, this tier is too expensive. We need to drop to the next Tier (fewer colors)
            # to afford a playable framerate.
        
        # Fallback: If even the lowest tier forces FPS < 8, we have two choices:
        # A. Accept low FPS (Slide show)
        # B. Downscale Resolution (if allowed)
        
        if best_params is None:
            # We are in the "Starvation" zone.
            if allow_downscale:
                print("[GIF_v10] Quality Starvation. Forcing Downscale to keep 10fps.")
                # Force 10fps, Tier 4 settings, and solve for Resolution
                # (Re-using binary search logic from v6/v9 roughly here for fallback)
                return self._emergency_resolution_solve(
                    input_path, target_size_bytes, meta, transform_filters
                )
            else:
                # Must accept low FPS
                print("[GIF_v10] Quality Starvation. Accepting low FPS.")
                best_params = {
                    'fps': max(5, int(max_fps)), # Floor at 5fps
                    'colors': tiers[-1]['colors'],
                    'dither': tiers[-1]['dither'],
                    'resolution_w': w,
                    'resolution_h': h,
                    'resolution_scale': w / orig_w
                }

        return best_params

    def _emergency_resolution_solve(self, input_path, target_size, meta, transform_filters):
        """Fallback to v9-style resolution solving if full resolution is impossible."""
        # Force decent settings
        fps = 10; colors = 64; dither = "bayer:bayer_scale=3"
        
        # Binary Search Scale
        sample_len = 2.0; start = 0.0
        sample_target = (target_size * 0.95 / meta['duration']) * sample_len
        
        low, high = 0.1, 1.0; best_scale = 0.1
        orig_w, orig_h = meta['width'], meta['height']
        
        for _ in range(5):
            mid = (low + high) / 2
            w = int(orig_w * mid); h = int(orig_h * mid)
            w -= w%2; h -= h%2
            if w<32: low=mid; continue
            
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