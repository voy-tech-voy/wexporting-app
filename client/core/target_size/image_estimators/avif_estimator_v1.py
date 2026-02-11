"""
AVIF Image Estimator v1
Optimizes AVIF images for target file size using CRF parameter (0-63, lower=better quality).

Quality mapping: UI 0-100 → CRF 63-0 (inverted for user-friendly UX)
Heavy compression: Uses preset 4 (slower, better compression) vs default preset 6
"""
import os
import subprocess
import tempfile
from typing import Dict, Optional, Callable, Any

from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata


def get_temp_filename(ext='avif'): 
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name


def get_ffmpeg_binary():
    """Get the FFmpeg binary path from environment or use default."""
    ffmpeg_bin = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
    if ffmpeg_bin and os.path.exists(ffmpeg_bin):
        return ffmpeg_bin
    return 'ffmpeg'


def run_ffmpeg_cmd(cmd_args):
    """Run FFmpeg command with proper binary path and subprocess."""
    ffmpeg_bin = get_ffmpeg_binary()
    cmd = [ffmpeg_bin] + cmd_args
    
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    )
    return result


class Estimator(EstimatorProtocol):
    """AVIF CRF binary search estimator v1 - quality-optimized AV1 encoding."""
    
    @property
    def version(self) -> str:
        return "v1"
    
    @property
    def description(self) -> str:
        return "AVIF binary search CRF optimization"
    
    def get_output_extension(self) -> str:
        return "avif"
    
    def _encode_test(self, input_path: str, output_path: str, width: int, height: int, crf: int, preset: int = 6) -> Optional[int]:
        """Encode a test image and return file size, or None on failure."""
        cmd_args = [
            '-y',  # Overwrite
            '-i', input_path,
            '-vf', f'scale={width}:{height}',
            '-c:v', 'libsvtav1',
            '-crf', str(crf),
            '-preset', str(preset),
            '-still-picture', '1',  # Critical for single-frame optimization
            output_path
        ]
        
        result = run_ffmpeg_cmd(cmd_args)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return os.path.getsize(output_path)
        return None
    
    def estimate(
        self, 
        input_path: str, 
        target_size_bytes: int, 
        **options
    ) -> Dict[str, Any]:
        allow_downscale = options.get('allow_downscale', False)
        heavy_compression = options.get('heavy_compression', False)
        override_w = options.get('override_width')
        override_h = options.get('override_height')
        stop_check = options.get('stop_check')
        progress_callback = options.get('progress_callback')
        
        def should_stop() -> bool:
            return stop_check() if stop_check else False
        
        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))
        
        preset = 4 if heavy_compression else 6
        preset_name = "heavy (slower)" if heavy_compression else "balanced"
        
        print(f"[AVIF_v1] Estimating for {target_size_bytes} bytes ({target_size_bytes/1024:.1f} KB), downscale={allow_downscale}, preset={preset_name}")
        
        meta = get_media_metadata(input_path)
        
        # Use user override dimensions if provided
        original_w, original_h = meta['width'], meta['height']
        if override_w and override_h:
            meta['width'] = override_w
            meta['height'] = override_h
        
        scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
        best_res = None
        best_crf = 64  # Start with worst (higher CRF = worse quality)
        
        # Progress tracking: estimation phase is 0.0 → 0.8
        total_tests = len(scales) * 10  # max 10 iterations per scale
        completed_tests = 0
        
        for scale_idx, scale in enumerate(scales):
            if should_stop():
                print("[AVIF_v1] Stopped by user during estimation")
                return self._make_fallback_result(meta, preset)
            
            target_w = max(1, int(meta['width'] * scale))
            target_h = max(1, int(meta['height'] * scale))
            # Ensure even dimensions
            target_w = target_w - (target_w % 2) if target_w > 1 else target_w
            target_h = target_h - (target_h % 2) if target_h > 1 else target_h
            
            # Binary search for LOWEST CRF (best quality) that fits under target
            # CRF 0 = lossless, CRF 63 = worst quality
            low, high = 0, 63
            scale_best_crf = 64
            scale_best_size = 0
            
            # More iterations for better precision
            for iteration in range(10):
                if should_stop():
                    print("[AVIF_v1] Stopped by user during binary search")
                    return best_res if best_res else self._make_fallback_result(meta, preset)
                
                mid = (low + high) // 2
                tmp = get_temp_filename()
                
                try:
                    size = self._encode_test(input_path, tmp, target_w, target_h, mid, preset)
                    
                    if size is not None:
                        print(f"[AVIF_v1] Scale {int(scale*100)}%, CRF{mid}: {size/1024:.1f} KB (target: {target_size_bytes/1024:.1f} KB)")
                        
                        if size <= target_size_bytes:
                            # This CRF fits - try lower CRF (better quality)
                            if mid < scale_best_crf:
                                scale_best_crf = mid
                                scale_best_size = size
                            high = mid - 1
                        else:
                            # Too big - try higher CRF (worse quality)
                            low = mid + 1
                    else:
                        # Encoding failed - try higher CRF
                        low = mid + 1
                except Exception as e:
                    print(f"[AVIF_v1] Encode test failed: {e}")
                    low = mid + 1
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                
                # Update progress (estimation = 0.0 → 0.8)
                completed_tests += 1
                emit_progress(completed_tests / total_tests * 0.8)
                
                # Early exit if converged
                if low > high:
                    # Skip remaining iterations for this scale in progress
                    completed_tests += (9 - iteration)
                    break
            
            # Update best result if this scale found a valid CRF
            if scale_best_crf < best_crf:
                best_crf = scale_best_crf
                # Convert CRF to UI quality (0-100, higher=better)
                ui_quality = max(0, min(100, int(100 - (scale_best_crf / 63.0) * 100)))
                best_res = {
                    'quality': ui_quality,  # UI-friendly 0-100
                    'crf': scale_best_crf,  # Actual CRF for encoding
                    'preset': preset,
                    'scale_factor': scale,
                    'resolution_w': target_w,
                    'resolution_h': target_h,
                    'estimated_size': scale_best_size,
                    'original_width': original_w,
                    'original_height': original_h,
                    'ffmpeg_out_args': {
                        'c:v': 'libsvtav1',
                        'crf': scale_best_crf,
                        'preset': preset,
                        'still-picture': 1
                    }
                }
            
            # If we found a high quality solution (CRF ≤ 25), stop searching lower scales
            if scale_best_crf <= 25:
                print(f"[AVIF_v1] Found high quality CRF{scale_best_crf} at scale {int(scale*100)}%, stopping search")
                break
        
        if best_res is None:
            best_res = self._fallback_estimate(input_path, target_size_bytes, meta, allow_downscale, preset, should_stop, emit_progress)
        
        emit_progress(0.8)  # Estimation complete
        print(f"[AVIF_v1] Final: CRF{best_res['crf']} (Q{best_res['quality']}), scale {int(best_res['scale_factor']*100)}%, estimated {best_res['estimated_size']/1024:.1f} KB")
        return best_res
    
    def _make_fallback_result(self, meta, preset):
        """Create a minimal fallback result for when stopped early."""
        return {
            'quality': 0,
            'crf': 63,
            'preset': preset,
            'scale_factor': 1.0,
            'resolution_w': meta['width'],
            'resolution_h': meta['height'],
            'estimated_size': 0,
            'original_width': meta['width'],
            'original_height': meta['height'],
            'ffmpeg_out_args': {
                'c:v': 'libsvtav1',
                'crf': 63,
                'preset': preset,
                'still-picture': 1
            }
        }
    
    def _fallback_estimate(self, input_path, target_size_bytes, meta, allow_downscale, preset, should_stop, emit_progress):
        """Fallback when target is unreachable with normal CRF range."""
        print("[AVIF_v1] ⚠ Target unreachable with standard settings")
        
        if allow_downscale:
            # Try progressively smaller sizes with maximum CRF
            print("[AVIF_v1] Attempting emergency downscaling...")
            current_scale = 0.5
            
            for attempt in range(20):
                if should_stop():
                    print("[AVIF_v1] Stopped by user during fallback")
                    return self._make_fallback_result(meta, preset)
                
                current_w = max(16, int(meta['width'] * current_scale))
                current_h = max(16, int(meta['height'] * current_scale))
                current_w = current_w - (current_w % 2) if current_w > 1 else current_w
                current_h = current_h - (current_h % 2) if current_h > 1 else current_h
                
                tmp = get_temp_filename()
                try:
                    size = self._encode_test(input_path, tmp, current_w, current_h, 55, preset)
                    if size and size <= target_size_bytes:
                        print(f"[AVIF_v1] Emergency scale found: {int(current_scale*100)}% = {size/1024:.1f} KB")
                        ui_quality = max(0, min(100, int(100 - (55 / 63.0) * 100)))
                        return {
                            'quality': ui_quality,
                            'crf': 55,
                            'preset': preset,
                            'scale_factor': current_scale,
                            'resolution_w': current_w,
                            'resolution_h': current_h,
                            'estimated_size': size,
                            'original_width': meta['width'],
                            'original_height': meta['height'],
                            'ffmpeg_out_args': {
                                'c:v': 'libsvtav1',
                                'crf': 55,
                                'preset': preset,
                                'still-picture': 1
                            }
                        }
                except:
                    pass
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                
                current_scale *= 0.8
                if current_w <= 16:
                    break
        
        # Last resort: use maximum CRF at original size
        print("[AVIF_v1] Using maximum CRF fallback")
        tmp = get_temp_filename()
        floor_size = 0
        try:
            floor_size = self._encode_test(input_path, tmp, meta['width'], meta['height'], 63, preset) or 0
        except:
            pass
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        
        return self._make_fallback_result(meta, preset)
    
    def execute(
        self,
        input_path: str,
        output_path: str,
        target_size_bytes: int,
        status_callback: Optional[Callable[[str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        **options
    ) -> bool:
        def emit(msg: str):
            if status_callback:
                status_callback(msg)
        
        def should_stop() -> bool:
            return stop_check() if stop_check else False
        
        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))
        
        try:
            if should_stop():
                emit("Stopped by user")
                return False
            
            emit_progress(0.0)
            
            # Pass stop_check and progress into estimate for interruptibility
            params = self.estimate(
                input_path, target_size_bytes,
                stop_check=stop_check,
                progress_callback=progress_callback,
                **options
            )
            emit(f"AVIF CRF{params['crf']} (Q{params['quality']}), {params['resolution_w']}x{params['resolution_h']}")
            
            if should_stop():
                emit("Stopped by user")
                return False
            
            emit_progress(0.8)  # Estimation done, encoding starts
            
            # Build filter chain
            vf_filters = []
            
            # Get user override dimensions
            override_w = options.get('override_width')
            override_h = options.get('override_height')
            
            # Apply scale if: user provided override OR auto-resize reduced size
            needs_scale = (override_w and override_h) or params['scale_factor'] < 1.0
            if needs_scale:
                vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")
            
            # Handle rotation
            rotation = options.get('rotation')
            if rotation and rotation != "No rotation":
                if rotation == "90° clockwise":
                    vf_filters.append("transpose=1")
                elif rotation == "180°":
                    vf_filters.append("transpose=2,transpose=2")
                elif rotation == "270° clockwise":
                    vf_filters.append("transpose=2")
            
            # Build command
            cmd_args = ['-y', '-i', input_path]
            
            if vf_filters:
                cmd_args.extend(['-vf', ','.join(vf_filters)])
            
            cmd_args.extend([
                '-c:v', 'libsvtav1',
                '-crf', str(params['crf']),
                '-preset', str(params['preset']),
                '-still-picture', '1',
                output_path
            ])
            
            preset_name = "heavy (slower)" if params['preset'] == 4 else "balanced"
            emit(f"Encoding AVIF ({preset_name})...")
            
            ffmpeg_bin = get_ffmpeg_binary()
            cmd = [ffmpeg_bin] + cmd_args
            
            print(f"[AVIF_v1 DEBUG] Command: {' '.join(cmd)}")
            
            # Use Popen for interruptibility
            # DEVNULL for stdout; drain stderr in thread to avoid pipe deadlock
            import threading
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Drain stderr in background thread to prevent pipe buffer deadlock
            stderr_chunks = []
            def drain_stderr():
                try:
                    for line in process.stderr:
                        stderr_chunks.append(line)
                except:
                    pass
            stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
            stderr_thread.start()
            
            # Poll process while checking for stop
            while process.poll() is None:
                if should_stop():
                    process.kill()
                    process.wait()
                    emit("Stopped by user during encoding")
                    # Clean up partial output
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass
                    return False
                # Brief wait to avoid busy-spinning
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
                # Pulse progress between 0.8 and 0.95 during encoding
                emit_progress(0.9)
            
            stderr_thread.join(timeout=2.0)
            
            if process.returncode != 0:
                stderr_output = b''.join(stderr_chunks).decode('utf-8', errors='ignore') if stderr_chunks else 'No stderr'
                print(f"[AVIF_v1 FFMPEG ERROR] {stderr_output}")
                emit(f"FFmpeg error (code {process.returncode})")
                return False
            
            if os.path.exists(output_path):
                actual_kb = os.path.getsize(output_path) / 1024
                target_kb = target_size_bytes / 1024
                emit_progress(1.0)
                emit(f"[OK] Complete: {actual_kb:.1f} KB (target: {target_kb:.1f} KB)")
                return True
            
            emit("[X] Output file not created")
            return False
            
        except Exception as e:
            import traceback
            emit(f"Error: {str(e)}")
            print(f"[AVIF_v1 ERROR] {traceback.format_exc()}")
            return False


_estimator = Estimator()

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
