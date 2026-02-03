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
    GIF Estimator v12 - The Extreme Spectrum Solver
    
    Changes from v11:
    - Expanded Tiers from 5 to 10.
    - Added "Logo/Icon" tiers (16, 8, 4, 2 colors).
    - Adjusted Cost Ratios to reflect the massive savings of disabling dither.
    
    Strategy:
    1. Lighthouse Probe at Tier 2 (Standard Video).
    2. Prediction & Pruning based on extended ratio curve.
    3. Iterative verification starting from highest plausible quality.
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
        print(f"[GIF_v12] Target: {target_size_bytes} bytes. Strategy: Extreme Spectrum.")
        
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0: return {}

        allow_downscale = options.get('allow_downscale', True)
        transform_filters = options.get('transform_filters', {})

        # Setup Sample
        sample_len = 2.0
        if meta['duration'] < 2.0: sample_len = meta['duration']
        start_time = min(meta['duration'] * 0.2, meta['duration'] - sample_len)
        
        # Safety Factor
        safety_factor = 0.93
        usable_budget = target_size_bytes * safety_factor
        
        orig_w, orig_h = meta['width'], meta['height']

        # =================================================================
        # EXTENDED TIER DEFINITIONS
        # =================================================================
        # Ratios are estimated relative to Tier 2 (Standard Bayer).
        # Note how ratios drop significantly when 'dither' becomes 'none'.
        
        tiers = [
            # --- PHOTOGRAPHIC / HIGH DETAIL ---
            # 0: Luxury (Floyd) - Heavy noise
            {'id': 0, 'colors': 256, 'dither': "floyd_steinberg",     'ratio': 1.35},
            # 1: High (Bayer 2)
            {'id': 1, 'colors': 256, 'dither': "bayer:bayer_scale=2", 'ratio': 1.15},
            # 2: REFERENCE (Standard Bayer 3)
            {'id': 2, 'colors': 256, 'dither': "bayer:bayer_scale=3", 'ratio': 1.00},
            
            # --- COMPROMISE ---
            # 3: Reduced Colors (128)
            {'id': 3, 'colors': 128, 'dither': "bayer:bayer_scale=3", 'ratio': 0.85},
            # 4: Low Colors (64)
            {'id': 4, 'colors': 64,  'dither': "bayer:bayer_scale=3", 'ratio': 0.70},
            # 5: Flat 64 (No Dither starts here - Huge savings)
            {'id': 5, 'colors': 64,  'dither': "none",                'ratio': 0.50},
            
            # --- LOGO / ICON / EXTREME ---
            # 6: Retro 32
            {'id': 6, 'colors': 32,  'dither': "none",                'ratio': 0.40},
            # 7: Icon 16
            {'id': 7, 'colors': 16,  'dither': "none",                'ratio': 0.30},
            # 8: Simple 8
            {'id': 8, 'colors': 8,   'dither': "none",                'ratio': 0.22},
            # 9: Binary/Duotone 2
            {'id': 9, 'colors': 2,   'dither': "none",                'ratio': 0.15},
        ]

        # Resolution Pre-check
        w, h = orig_w, orig_h
        if allow_downscale and w > 1280:
            scale = 1280/w; w=int(w*scale); h=int(h*scale)
            w-=w%2; h-=h%2

        # =================================================================
        # STEP 1: THE LIGHTHOUSE PROBE
        # =================================================================
        # Run ONE encode at the Reference Tier (Tier 2) to get baseline cost.
        ref_tier = tiers[2]
        ref_fps = 10
        
        print("[GIF_v12] Running Lighthouse Probe (Tier 2)...")
        sample_size = self._run_sample_encode(
            input_path, start_time, sample_len, w, h, ref_fps, 
            ref_tier['colors'], ref_tier['dither'], transform_filters
        )
        
        # Calculate Base Cost Per Frame
        frame_count_sample = ref_fps * sample_len
        base_cost_per_frame = sample_size / frame_count_sample
        print(f"[GIF_v12] Base Cost Per Frame: {base_cost_per_frame/1024:.2f} KB")

        # =================================================================
        # STEP 2: PREDICT & PRUNE
        # =================================================================
        valid_candidates = []
        
        for tier in tiers:
            # Predict cost for this tier using ratios
            predicted_cost = base_cost_per_frame * tier['ratio']
            
            # How many frames can we afford total?
            max_frames = usable_budget / predicted_cost
            
            # What FPS does that give us?
            projected_fps = max_frames / meta['duration']
            
            # Cutoff Rule: 
            # For high tiers (video), we need > 7 FPS.
            # For low tiers (logos/extreme), we accept down to 5 FPS.
            min_fps_threshold = 5.0 if tier['id'] >= 5 else 7.5
            
            if projected_fps >= min_fps_threshold:
                # Calculate likely final FPS (cap at 25)
                final_fps = min(int(projected_fps), 25)
                valid_candidates.append({
                    'tier': tier,
                    'fps': final_fps,
                    'cost': predicted_cost
                })
            else:
                pass # Pruning

        # =================================================================
        # STEP 3: VERIFY & SELECT
        # =================================================================
        
        if not valid_candidates:
            if allow_downscale:
                print("[GIF_v12] All tiers failed. Engaging Emergency Resolution Solver.")
                # Force Tier 6 (32 colors) and shrink
                return self._emergency_resolution_solve(input_path, target_size_bytes, meta, transform_filters)
            else:
                # If native res required, take the absolute lowest setting possible
                print("[GIF_v12] All tiers failed. Forcing 2-Color mode at 5 FPS.")
                worst = tiers[-1]
                return {
                    'fps': 5, 'colors': worst['colors'], 'dither': worst['dither'],
                    'resolution_w': w, 'resolution_h': h, 'resolution_scale': w/orig_w
                }

        # Test candidates starting from HIGHEST quality
        for candidate in valid_candidates:
            tier = candidate['tier']
            fps = candidate['fps']
            
            # VERIFICATION PROBE
            real_size = self._run_sample_encode(
                input_path, start_time, sample_len, w, h, fps,
                tier['colors'], tier['dither'], transform_filters
            )
            
            projected_total = (real_size / sample_len) * meta['duration'] * 1.05 
            
            if projected_total <= target_size_bytes:
                print(f"[GIF_v12] ✓ Winner: Tier {tier['id']} ({tier['colors']}col) @ {fps} FPS")
                return {
                    'fps': fps,
                    'colors': tier['colors'],
                    'dither': tier['dither'],
                    'resolution_w': w,
                    'resolution_h': h,
                    'resolution_scale': w/orig_w
                }
            else:
                print(f"   Tier {tier['id']} verification failed. Trying next...")

        # Fallback to lowest candidate
        fallback = valid_candidates[-1]
        print("[GIF_v12] Verification missed. Falling back to lowest candidate.")
        return {
            'fps': fallback['fps'],
            'colors': fallback['tier']['colors'],
            'dither': fallback['tier']['dither'],
            'resolution_w': w,
            'resolution_h': h,
            'resolution_scale': w/orig_w
        }

    def _emergency_resolution_solve(self, input_path, target_size, meta, transform_filters):
        """Fallback: Force 10fps/32colors and shrink resolution until it fits."""
        fps = 10; colors = 32; dither = "none"
        sample_len = 2.0; start = 0.0
        sample_target = (target_size * 0.95 / meta['duration']) * sample_len
        
        low, high = 0.1, 1.0; best_scale = 0.1
        orig_w, orig_h = meta['width'], meta['height']
        
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
            