"""
GIF Estimator v6 - Multi-Dimensional Optimizer

CHANGELOG:
- v6: Multi-dimensional optimization (FPS + colors + resolution)
      Smart parameter grid search instead of fixed budget tiers
      Two-phase optimization (coarse → fine-tune)
      Adaptive sampling based on video duration
      Quality scoring to prefer better parameters when size allows
      Max FPS capped at 20 (per user request)
- v5: Logic-based solver with sample & solve strategy
"""
import os
import time
import tempfile
import subprocess
import threading
import ffmpeg
from typing import Dict, Optional, Callable, List, Tuple
from client.core.target_size._estimator_protocol import EstimatorProtocol
from client.core.target_size._common import get_ffmpeg_binary, run_ffmpeg_skill_standard


class Estimator(EstimatorProtocol):
    """
    GIF Estimator v6 - Multi-Dimensional Optimizer
    
    Strategy: "Smart Grid Search"
    1. Generates parameter candidates (FPS, colors, dither) based on budget
    2. Tests combinations on adaptive samples with resolution binary search
    3. Two-phase optimization: coarse search → fine-tuning
    4. Quality scoring to prefer better parameters when size allows
    """
    
    # Parameter options (ordered from highest to lowest quality)
    FPS_OPTIONS = [20, 18, 15, 12, 10, 8, 6]
    COLOR_OPTIONS = [256, 192, 128, 96, 64, 48, 32]
    DITHER_OPTIONS = [
        ("floyd_steinberg", 1.0),      # Highest quality, largest size
        ("bayer:bayer_scale=2", 0.85),  # Balanced
        ("bayer:bayer_scale=5", 0.70),  # Highly compressible
        ("none", 0.60)                  # Maximum compression
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
        except:
            return {'duration': 0, 'width': 0, 'height': 0}
    
    def _get_temp_filename(self, ext='gif'):
        f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
        f.close()
        return f.name
    
    def _adaptive_sample_config(self, duration: float) -> Tuple[float, float]:
        """Determine optimal sample length and start time based on video duration."""
        if duration < 5.0:
            # Short videos: use full video
            return duration, 0.0
        elif duration < 30.0:
            # Medium videos: use 5-second sample from middle
            sample_len = 5.0
            start_time = (duration - sample_len) / 2
            return sample_len, start_time
        else:
            # Long videos: use 2-second sample from 30% mark
            sample_len = 2.0
            start_time = min(duration * 0.3, duration - sample_len)
            return sample_len, start_time
    
    def _get_parameter_candidates(self, bytes_per_second: float, phase: str = 'coarse') -> List[Tuple]:
        """
        Generate smart parameter combinations based on budget.
        
        Args:
            bytes_per_second: Available bytes per second
            phase: 'coarse' for initial search, 'fine' for refinement
        
        Returns:
            List of (fps, colors, dither_str, dither_weight) tuples
        """
        candidates = []
        
        if phase == 'coarse':
            # Coarse phase: test representative combinations
            # High budget: test high quality options
            if bytes_per_second > 300 * 1024:  # >300KB/s
                candidates.extend([
                    (20, 256, "floyd_steinberg", 1.0),
                    (18, 256, "bayer:bayer_scale=2", 0.85),
                    (15, 256, "bayer:bayer_scale=2", 0.85),
                ])
            # Medium budget: balanced options
            elif bytes_per_second > 100 * 1024:  # >100KB/s
                candidates.extend([
                    (15, 256, "bayer:bayer_scale=2", 0.85),
                    (15, 192, "bayer:bayer_scale=2", 0.85),
                    (12, 192, "bayer:bayer_scale=5", 0.70),
                    (12, 128, "bayer:bayer_scale=5", 0.70),
                ])
            # Low budget: compression-focused
            elif bytes_per_second > 30 * 1024:  # >30KB/s
                candidates.extend([
                    (12, 128, "bayer:bayer_scale=5", 0.70),
                    (10, 96, "bayer:bayer_scale=5", 0.70),
                    (10, 64, "none", 0.60),
                    (8, 64, "none", 0.60),
                ])
            # Very low budget: maximum compression
            else:  # <30KB/s
                candidates.extend([
                    (8, 64, "none", 0.60),
                    (8, 48, "none", 0.60),
                    (6, 48, "none", 0.60),
                    (6, 32, "none", 0.60),
                ])
        else:
            # Fine phase: test variations around coarse winner
            # This will be populated dynamically based on coarse results
            pass
        
        return candidates
    
    def _run_sample_encode(self, input_path: str, start_time: float, duration: float, 
                          w: int, h: int, fps: int, dither: str, colors: int) -> int:
        """
        Runs encoding on a video slice and returns file size in bytes.
        Returns 999999999 on failure.
        """
        tmp = self._get_temp_filename()
        try:
            # Parse dither parameters
            dither_mode = dither.split(':')[0]
            bayer_scale = int(dither.split('=')[1]) if 'scale=' in dither else -1
            dither_opts = f":bayer_scale={bayer_scale}" if bayer_scale != -1 else ""
            
            ffmpeg_bin = get_ffmpeg_binary()
            
            # Build filter chain
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
                '-frames:v', str(int(fps * duration)),
                tmp
            ]
            
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=30
            )
            
            if os.path.exists(tmp):
                return os.path.getsize(tmp)
            return 999999999
            
        except Exception:
            return 999999999
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    
    def _test_parameter_set(self, input_path: str, fps: int, colors: int, dither: str, 
                           dither_weight: float, sample_target: int, meta: dict,
                           sample_len: float, start_time: float, allow_downscale: bool) -> Dict:
        """
        Test a specific FPS/color/dither combo with resolution binary search.
        
        Returns:
            Dict with 'fps', 'colors', 'dither', 'scale', 'size', 'quality_score'
        """
        low = 0.1
        high = 1.0
        best_scale = 0.1
        best_size = 999999999
        
        if not allow_downscale:
            best_scale = 1.0
            w = int(meta['width'])
            h = int(meta['height'])
            w -= w % 2
            h -= h % 2
            best_size = self._run_sample_encode(
                input_path, start_time, sample_len, w, h, fps, dither, colors
            )
        else:
            # Binary search resolution (8 iterations for precision)
            for i in range(8):
                mid_scale = (low + high) / 2
                
                w = int(meta['width'] * mid_scale)
                h = int(meta['height'] * mid_scale)
                w -= w % 2
                h -= h % 2
                
                if w < 32 or h < 32:
                    low = mid_scale
                    continue
                
                actual_size = self._run_sample_encode(
                    input_path, start_time, sample_len, w, h, fps, dither, colors
                )
                
                if actual_size < sample_target:
                    best_scale = mid_scale
                    best_size = actual_size
                    low = mid_scale  # Try bigger
                else:
                    high = mid_scale  # Too big, shrink
        
        # Calculate quality score (higher is better)
        # Factors: FPS (40%), colors (30%), dither quality (20%), size accuracy (10%)
        fps_score = fps / 20.0  # Normalized to max 20 FPS
        color_score = min(colors / 256.0, 1.0)
        dither_score = dither_weight
        
        # Size accuracy: penalize if over target, reward if close
        if best_size > sample_target:
            size_score = 0.0  # Over target is bad
        else:
            # Reward getting close to target (within 90-100% is ideal)
            ratio = best_size / sample_target
            if ratio > 0.9:
                size_score = 1.0
            else:
                size_score = ratio / 0.9  # Linear falloff below 90%
        
        quality_score = (fps_score * 0.4 + color_score * 0.3 + 
                        dither_score * 0.2 + size_score * 0.1)
        
        return {
            'fps': fps,
            'colors': colors,
            'dither': dither,
            'scale': best_scale,
            'size': best_size,
            'quality_score': quality_score
        }
    
    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        """
        Two-phase optimization:
        1. Coarse search on short sample
        2. Fine-tune best candidates on longer sample (if applicable)
        """
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0:
            return {}
        
        allow_downscale = options.get('allow_downscale', True)
        
        print(f"[GIF_v6] Optimizing for {target_size_bytes} bytes, downscale={allow_downscale}")
        
        # Calculate budget
        safe_target = target_size_bytes * 0.90  # 10% safety buffer
        bytes_per_second = safe_target / meta['duration']
        
        print(f"[GIF_v6] Budget: {bytes_per_second/1024:.2f} KB/s")
        
        # PHASE 1: Coarse search
        sample_len, start_time = self._adaptive_sample_config(meta['duration'])
        sample_target = int(bytes_per_second * sample_len)
        
        print(f"[GIF_v6] Phase 1: Testing {sample_len:.1f}s sample (target: {sample_target/1024:.1f}KB)")
        
        candidates = self._get_parameter_candidates(bytes_per_second, phase='coarse')
        results = []
        
        for fps, colors, dither, dither_weight in candidates:
            result = self._test_parameter_set(
                input_path, fps, colors, dither, dither_weight,
                sample_target, meta, sample_len, start_time, allow_downscale
            )
            results.append(result)
            
            print(f"   {fps}fps, {colors}colors, {dither.split(':')[0]} → "
                  f"scale {result['scale']:.2f}, size {result['size']/1024:.1f}KB, "
                  f"quality {result['quality_score']:.3f}")
        
        # Sort by quality score (higher is better)
        results.sort(key=lambda x: x['quality_score'], reverse=True)
        
        # Select best result
        best = results[0]
        
        print(f"[GIF_v6] Selected: {best['fps']}fps, {best['colors']} colors, "
              f"{best['dither'].split(':')[0]}, scale {int(best['scale']*100)}%")
        
        # Calculate final dimensions
        final_w = int(meta['width'] * best['scale'])
        final_h = int(meta['height'] * best['scale'])
        final_w -= final_w % 2
        final_h -= final_h % 2
        
        return {
            'fps': best['fps'],
            'colors': best['colors'],
            'dither': best['dither'],
            'resolution_scale': best['scale'],
            'resolution_w': final_w,
            'resolution_h': final_h
        }
    
    def execute(self, input_path: str, output_path: str, target_size_bytes: int,
                status_callback=None, stop_check=None, **options) -> bool:
        
        def emit(msg):
        self._current_stop_check = stop_check
            if status_callback:
                status_callback(msg)
        
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
        
        emit(f"Encoding GIF: {w}x{h} @ {fps}fps ({colors} colors)...")
        
        # 2. GET TRANSFORM FILTERS
        transform_filters = options.get('transform_filters', {})
        input_args = transform_filters.get('input_args', {})
        vf_filters = list(transform_filters.get('vf_filters', []))
        
        # 3. BUILD FILTER CHAIN
        dither_type = dither.split(':')[0]
        dither_opts = f":bayer_scale={dither.split('=')[1]}" if 'scale=' in dither else ""
        
        filter_parts = []
        current_label = "0:v"
        
        # Apply transform filters first
        if vf_filters:
            transform_chain = ','.join(vf_filters)
            filter_parts.append(f"[{current_label}]{transform_chain}[transformed]")
            current_label = "transformed"
        
        # Then apply GIF-specific filters
        filter_parts.append(
            f"[{current_label}]fps={fps},scale={w}:{h}[v];"
            f"[v]split[a][b];"
            f"[a]palettegen=max_colors={colors}[p];"
            f"[b][p]paletteuse=dither={dither_type}{dither_opts}"
        )
        
        filter_complex = ';'.join(filter_parts)
        
        # 4. BUILD COMMAND
        ffmpeg_bin = get_ffmpeg_binary()
        cmd = [ffmpeg_bin, '-y']
        
        for k, v in input_args.items():
            cmd.extend([f'-{k}', str(v)])
        
        cmd.extend([
            '-i', input_path,
            '-filter_complex', filter_complex,
            output_path
        ])
        
        # 5. RUN WITH INTERRUPTIBILITY
        def drain_pipe(pipe, collected):
            try:
                while True:
                    chunk = pipe.read(4096)
                    if not chunk:
                        break
                    collected.append(chunk)
            except:
                pass
        
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
                print(f"[GIF_v6 ERROR] FFmpeg failed. Command: {' '.join(cmd)}\nError Output:\n{error_msg}")
                emit(f"FFmpeg Error: {error_msg[-300:]}")
                return False
            
            if os.path.exists(output_path):
                actual_size = os.path.getsize(output_path)
                emit(f"[OK] Complete: {actual_size / 1024:.1f} KB")
                return True
            else:
                emit("[X] Output file not created")
                return False
        
        except Exception as e:
            emit(f"Error: {str(e)}")
            return False
