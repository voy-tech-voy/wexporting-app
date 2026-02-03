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
    GIF Estimator v5 - Logic-Based Solver
    
    Strategy: "Sample & Solve"
    1. Extracts a 2-second representative sample.
    2. Calculates 'Budget Per Second'.
    3. Heuristically selects FPS and Dither based on budget.
    4. Binary Searches Resolution on the sample to hit exact size.
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

    def _run_sample_encode(self, input_path, start_time, duration, w, h, fps, dither, colors) -> int:
        """
        Runs a quick encoding on a slice of the video and returns the file size in bytes.
        """
        tmp = self._get_temp_filename()
        try:
            # Dither parsing
            dither_mode = dither.split(':')[0]
            bayer_scale = int(dither.split('=')[1]) if 'scale=' in dither else -1
            dither_opts = f":bayer_scale={bayer_scale}" if bayer_scale != -1 else ""

            # Filter chain: Crop time -> FPS -> Scale -> Split -> Palette -> GIF
            # Note: We use -ss and -t before input for fast seeking if possible, but filter trimming is more accurate for loops
            
            ffmpeg_bin = get_ffmpeg_binary()
            
            # Complex filter string
            # 1. Trim 2. FPS 3. Scale 4. PaletteGen 5. PaletteUse
            filter_str = (
                f"trim=start={start_time}:duration={duration},setpts=PTS-STARTPTS,"
                f"fps={fps},scale={w}:{h},split[s0][s1];"
                f"[s0]palettegen=max_colors={colors}[p];"
                f"[s1][p]paletteuse=dither={dither_mode}{dither_opts}"
            )
            
            cmd = [
                ffmpeg_bin, '-y', '-hide_banner', '-loglevel', 'error',
                '-i', input_path,
                '-filter_complex', filter_str,
                '-frames:v', int(fps * duration), # Cap frames just in case
                tmp
            ]

            subprocess.run(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if os.path.exists(tmp):
                return os.path.getsize(tmp)
            return 999999999 # Fail high

        except Exception:
            return 999999999
        finally:
            if os.path.exists(tmp): os.remove(tmp)

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        """
        Calculates params by solving the resolution for the target budget.
        """
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0: return {}

        allow_downscale = options.get('allow_downscale', True) # Default to true for GIF logic
        
        # 1. CALCULATE BUDGET
        # How many bytes do we have per second?
        # Safety buffer: GIF overhead is high, reserve 10%
        safe_target = target_size_bytes * 0.90
        bytes_per_second = safe_target / meta['duration']
        
        # 2. HEURISTIC CONFIGURATION (The "Logic" Step)
        # Based on available bandwidth, determine FPS and Dithering method.
        # Low bandwidth = Low FPS + Ordered Dither (Clean)
        # High bandwidth = High FPS + Error Diffusion Dither (Noisy but pretty)
        
        if bytes_per_second > 500 * 1024: # > 500KB/s (Huge budget)
            fps = 20
            dither = "floyd_steinberg" # Prettiest, heaviest
            colors = 256
        elif bytes_per_second > 200 * 1024: # > 200KB/s
            fps = 15
            dither = "bayer:bayer_scale=2" # Balanced
            colors = 256
        elif bytes_per_second > 50 * 1024: # > 50KB/s
            fps = 12
            dither = "bayer:bayer_scale=5" # Highly compressible ordered dither
            colors = 128
        else: # < 50KB/s (Starvation)
            fps = 10
            dither = "none" # Flat colors, maximum compression
            colors = 64

        # 3. SAMPLE CONFIGURATION
        sample_len = 2.0
        if meta['duration'] < 2.0: sample_len = meta['duration']
        start_time = min(meta['duration'] * 0.3, meta['duration'] - sample_len)
        
        # Target size for our 2s sample
        sample_target = bytes_per_second * sample_len

        # 4. RESOLUTION SOLVER (Binary Search)
        # Instead of guessing presets, we binary search the Scale Factor (0.1 to 1.0)
        # to find the maximum resolution that fits the sample_target.
        
        low = 0.1
        high = 1.0
        best_scale = 0.1
        
        if not allow_downscale:
            # If downscale not allowed, we just return scale 1.0 logic 
            # (but we might have lowered FPS/Dither in step 2 to compensate)
            best_scale = 1.0
        else:
            print(f"[GIF_v5] Solving Resolution... Budget: {bytes_per_second/1024:.2f} KB/s")
            
            # 5 Iterations of binary search is enough for precision
            for i in range(5):
                mid_scale = (low + high) / 2
                
                w = int(meta['width'] * mid_scale)
                h = int(meta['height'] * mid_scale)
                # Ensure even dimensions
                w -= w % 2
                h -= h % 2
                
                if w < 32 or h < 32: # Too small
                    low = mid_scale
                    continue

                actual_sample_size = self._run_sample_encode(
                    input_path, start_time, sample_len, w, h, fps, dither, colors
                )
                
                print(f"   Iter {i}: Scale {mid_scale:.2f} ({w}x{h}) -> {actual_sample_size/1024:.2f}KB (Target {sample_target/1024:.2f}KB)")

                if actual_sample_size < sample_target:
                    best_scale = mid_scale
                    low = mid_scale # Try bigger
                else:
                    high = mid_scale # Too big, shrink

        # Final Dimensions
        final_w = int(meta['width'] * best_scale)
        final_h = int(meta['height'] * best_scale)
        final_w -= final_w % 2
        final_h -= final_h % 2

        return {
            'fps': fps,
            'colors': colors,
            'dither': dither,
            'resolution_scale': best_scale,
            'resolution_w': final_w,
            'resolution_h': final_h
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

        # 2. GET TRANSFORM FILTERS (like v4)
        transform_filters = options.get('transform_filters', {})
        input_args = transform_filters.get('input_args', {})
        vf_filters = list(transform_filters.get('vf_filters', []))

        # 3. BUILD FILTER CHAIN
        # Parse dither parameters
        dither_type = dither.split(':')[0]
        dither_opts = f":bayer_scale={dither.split('=')[1]}" if 'scale=' in dither else ""

        # Build filter_complex chain with transforms
        # Order: transforms → fps → scale → palette generation → paletteuse
        filter_parts = []
        
        # Start with input
        current_label = "0:v"
        
        # Apply transform filters first
        if vf_filters:
            transform_chain = ','.join(vf_filters)
            filter_parts.append(f"[{current_label}]{transform_chain}[transformed]")
            current_label = "transformed"
        
        # Then apply GIF-specific filters (fps, scale, palette)
        filter_parts.append(
            f"[{current_label}]fps={fps},scale={w}:{h}[v];"
            f"[v]split[a][b];"
            f"[a]palettegen=max_colors={colors}[p];"
            f"[b][p]paletteuse=dither={dither_type}{dither_opts}"
        )
        
        filter_complex = ';'.join(filter_parts)
        
        # 4. BUILD COMMAND (like v4)
        ffmpeg_bin = get_ffmpeg_binary()
        cmd = [ffmpeg_bin, '-y']
        
        # Add input args if present
        for k, v in input_args.items():
            cmd.extend([f'-{k}', str(v)])
        
        cmd.extend([
            '-i', input_path,
            '-filter_complex', filter_complex,
            output_path
        ])
        
        # 5. RUN WITH INTERRUPTIBILITY (like v4)
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
                    try:
                        process.wait(timeout=2)
                    except:
                        process.kill()
                    emit("Stopped by user")
                    return False
                time.sleep(0.1)

            drain_thread.join(timeout=1)

            if process.returncode != 0:
                error_msg = b''.join(stderr_chunks).decode('utf-8', errors='ignore')
                print(f"[GIF_v5 ERROR] FFmpeg failed. Command: {' '.join(cmd)}\nError Output:\n{error_msg}")
                emit(f"FFmpeg Error: {error_msg[-300:]}")
                return False

            if os.path.exists(output_path):
                actual_size = os.path.getsize(output_path)
                emit(f"✓ Complete: {actual_size / 1024:.1f} KB")
                return True
            else:
                emit("✗ Output file not created")
                return False

        except Exception as e:
            emit(f"Error: {str(e)}")
            return False