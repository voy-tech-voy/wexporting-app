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
    GIF Estimator v6 - The "Pessimistic" Solver
    
    Improvements over v5:
    1. Pessimistic Extrapolation: Adds a 15% safety buffer to account for unsampled complexity.
    2. Transform Awareness: Applies UI crops/rotations during estimation.
    3. Tuned Heuristics: Better FPS/Dither selection logic for modern web usage.
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
        except:
            return {'duration': 0, 'width': 0, 'height': 0}

    def _get_temp_filename(self, ext='gif'):
        f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
        f.close()
        return f.name

    def _build_filter_chain(self, w, h, fps, colors, dither, transform_filters=None):
        """
        Shared logic to build the FFmpeg filter complex string.
        Ensures Estimate and Execute uses IDENTICAL processing.
        """
        # 1. Parse Dither
        dither_type = dither.split(':')[0]
        dither_opts = ""
        if 'scale=' in dither:
            dither_opts = f":bayer_scale={dither.split('=')[1]}"

        # 2. Build Chain
        filter_parts = []
        current_label = "0:v"

        # A. Apply UI Transforms (Crop, etc) FIRST
        if transform_filters:
            vf_filters = transform_filters.get('vf_filters', [])
            if vf_filters:
                transform_chain = ','.join(vf_filters)
                filter_parts.append(f"[{current_label}]{transform_chain}[transformed]")
                current_label = "transformed"

        # B. Apply Resolution & FPS
        # We perform scaling here. 
        # Note: If transforms changed aspect ratio, w/h must allow for that.
        filter_parts.append(
            f"[{current_label}]fps={fps},scale={w}:{h}:flags=lanczos[v];"
            f"[v]split[a][b];"
            f"[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
            f"[b][p]paletteuse=dither={dither_type}{dither_opts}:diff_mode=rectangle"
        )
        
        return ';'.join(filter_parts)

    def _run_sample_encode(self, input_path, start_time, duration, w, h, fps, dither, colors, transform_filters, input_args) -> int:
        tmp = self._get_temp_filename()
        try:
            ffmpeg_bin = get_ffmpeg_binary()
            
            # Build the exact filter chain we would use in production
            filter_complex = self._build_filter_chain(w, h, fps, colors, dither, transform_filters)
            
            # Construct command
            # Note: We use -ss before -i for fast seeking
            cmd = [ffmpeg_bin, '-y', '-hide_banner', '-loglevel', 'error']
            
            # Input Args (e.g. hwaccel)
            for k, v in input_args.items():
                cmd.extend([f'-{k}', str(v)])

            cmd.extend([
                '-ss', str(start_time),
                '-t', str(duration),
                '-i', input_path,
                '-filter_complex', filter_complex,
                tmp
            ])

            subprocess.run(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if os.path.exists(tmp):
                return os.path.getsize(tmp)
            return 999999999 

        except Exception:
            return 999999999
        finally:
            if os.path.exists(tmp): os.remove(tmp)

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        print(f"[GIF_v6] Estimating for {target_size_bytes} bytes...")
        
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0: return {}

        allow_downscale = options.get('allow_downscale', True)
        transform_filters = options.get('transform_filters', {})
        input_args = transform_filters.get('input_args', {})

        # --- 1. SAFETY CALCULATIONS ---
        # GIF variance is high. We assume the full video is 15% harder to compress than the sample.
        # This prevents the "It fit the sample but failed the full export" issue.
        safety_margin = 0.85 
        safe_target_bytes = target_size_bytes * safety_margin
        
        # Calculate Budget Per Second
        bytes_per_second = safe_target_bytes / meta['duration']
        kb_per_second = bytes_per_second / 1024

        # --- 2. HEURISTIC CONFIGURATION ---
        # Tuned for "Internet Speed" reality.
        # Reducing Dither/FPS is much more effective than reducing resolution for GIF size.
        
        if kb_per_second > 400:     # > 400KB/s (Luxury)
            fps, colors, dither = 20, 256, "floyd_steinberg"
        elif kb_per_second > 150:   # > 150KB/s (Standard)
            fps, colors, dither = 15, 256, "bayer:bayer_scale=2"
        elif kb_per_second > 80:    # > 80KB/s (Tight)
            fps, colors, dither = 12, 128, "bayer:bayer_scale=3"
        elif kb_per_second > 40:    # > 40KB/s (Very Tight)
            fps, colors, dither = 10, 64,  "bayer:bayer_scale=5" # Ordered dither saves HUGE space
        else:                       # < 40KB/s (Starvation)
            fps, colors, dither = 8,  32,  "none"

        # --- 3. SAMPLE RESOLUTION SOLVER ---
        sample_len = 2.0
        if meta['duration'] < 2.0: sample_len = meta['duration']
        
        # Take sample from 20% mark to avoid static intros
        start_time = min(meta['duration'] * 0.2, meta['duration'] - sample_len)
        
        # We need the sample to fit into this slice of the budget
        sample_target_size = bytes_per_second * sample_len

        # Determine Aspect Ratio from Metadata
        # (Note: If UI crop changes aspect ratio, we should ideally use that, 
        # but estimating original AR is safer than crashing on invalid geometry)
        orig_w, orig_h = meta['width'], meta['height']
        
        low = 0.1
        high = 1.0
        best_scale = 0.1
        
        if not allow_downscale:
            best_scale = 1.0
        else:
            print(f"[GIF_v6] Budget: {kb_per_second:.1f} KB/s. solving resolution for sample target {sample_target_size/1024:.1f} KB...")
            
            # Binary Search for Resolution (5 iterations)
            for i in range(5):
                mid_scale = (low + high) / 2
                
                w = int(orig_w * mid_scale)
                h = int(orig_h * mid_scale)
                # Ensure even
                w -= w % 2
                h -= h % 2
                
                if w < 16 or h < 16: 
                    low = mid_scale
                    continue

                actual_sample = self._run_sample_encode(
                    input_path, start_time, sample_len, w, h, fps, dither, colors, transform_filters, input_args
                )
                
                print(f"   [Iter {i}] Scale {mid_scale:.2f} ({w}x{h}) -> {actual_sample/1024:.1f} KB")

                if actual_sample < sample_target_size:
                    best_scale = mid_scale
                    low = mid_scale # It fits! Try to go bigger.
                else:
                    high = mid_scale # Too big! Shrink.

        # Final Dimensions
        final_w = int(orig_w * best_scale)
        final_h = int(orig_h * best_scale)
        final_w -= final_w % 2
        final_h -= final_h % 2

        return {
            'fps': fps,
            'colors': colors,
            'dither': dither,
            'resolution_w': final_w,
            'resolution_h': final_h,
            'resolution_scale': best_scale
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options) -> bool:
        
        def emit(msg): 
            if status_callback: status_callback(msg)
        def should_stop(): 
            return stop_check() if stop_check else False

        # 1. ESTIMATE
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params:
            emit("Estimation failed")
            return False

        fps = params['fps']
        colors = params['colors']
        dither = params['dither']
        w, h = params['resolution_w'], params['resolution_h']

        emit(f"Encoding GIF: {w}x{h} @ {fps}fps (Dither: {dither})...")

        # 2. BUILD COMMAND
        # We reuse the exact same filter chain logic to ensure consistency
        transform_filters = options.get('transform_filters', {})
        input_args = transform_filters.get('input_args', {})
        
        filter_complex = self._build_filter_chain(w, h, fps, colors, dither, transform_filters)
        
        ffmpeg_bin = get_ffmpeg_binary()
        cmd = [ffmpeg_bin, '-y']
        
        for k, v in input_args.items():
            cmd.extend([f'-{k}', str(v)])
            
        cmd.extend([
            '-i', input_path,
            '-filter_complex', filter_complex,
            output_path
        ])

        # 3. RUN
        def drain_pipe(pipe, collected):
            try:
                while True:
                    chunk = pipe.read(4096)
                    if not chunk: break
                    collected.append(chunk)
            except: pass

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            stderr_chunks = []
            drain_thread = threading.Thread(target=drain_pipe, args=(process.stderr, stderr_chunks))
            drain_thread.daemon = True
            drain_thread.start()

            while process.poll() is None:
                if should_stop():
                    process.terminate()
                    try: process.wait(timeout=2)
                    except: process.kill()
                    emit("Stopped by user")
                    return False
                time.sleep(0.1)

            drain_thread.join(timeout=1)

            if process.returncode != 0:
                err = b''.join(stderr_chunks).decode('utf-8', errors='ignore')
                emit(f"FFmpeg Error: {err[-300:]}")
                return False

            if os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / (1024*1024)
                emit(f"✓ Complete: {size_mb:.2f} MB")
                return True
            return False

        except Exception as e:
            emit(f"Execution Error: {str(e)}")
            return False