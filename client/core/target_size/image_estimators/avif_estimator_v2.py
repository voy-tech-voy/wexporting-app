"""
AVIF Image Estimator v2
Aggressive binary search: probes middle CRF first to narrow the search range,
then performs a targeted binary search in the relevant half. Fewer encode tests 
means faster convergence for AV1's slow encoding.

Strategy:
  Phase 1 (Probe):  Encode at CRF 32 (midpoint) to determine if target is in
                     the quality half (0-31) or compression half (33-63).
  Phase 2 (Search): Binary search only the relevant half (~5-6 iterations).

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
    """AVIF CRF estimator v2 - aggressive mid-probe + targeted binary search."""
    
    @property
    def version(self) -> str:
        return "v2"
    
    @property
    def description(self) -> str:
        return "AVIF aggressive mid-probe binary search"
    
    def get_output_extension(self) -> str:
        return "avif"
    
    def _encode_test(self, input_path: str, output_path: str, width: int, height: int, crf: int, preset: int = 6, stop_check: Optional[Callable[[], bool]] = None, progress_callback: Optional[Callable[[float], None]] = None) -> Optional[int]:
        """Encode a test image and return file size, or None on failure/stop.
        
        progress_callback here receives values in [0.0, 1.0] representing
        progress WITHIN this single encode test. The caller is responsible
        for mapping this to the overall progress range.
        """
        cmd_args = [
            '-y',
            '-i', input_path,
            '-vf', f'scale={width}:{height}',
            '-c:v', 'libsvtav1',
            '-crf', str(crf),
            '-preset', str(preset),
            '-still-picture', '1',
            output_path
        ]
        
        ffmpeg_bin = get_ffmpeg_binary()
        cmd = [ffmpeg_bin] + cmd_args
        
        # Use Popen for interruptibility
        # DEVNULL for stdout/stderr — we only need file size, not FFmpeg output.
        # Using PIPE would deadlock when FFmpeg fills the pipe buffer.
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Poll with stop_check and progress updates
        poll_count = 0
        while process.poll() is None:
            if stop_check and stop_check():
                process.kill()
                process.wait()
                # Clean up partial output
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                return None
            
            # Emit sub-progress within this encode test (0.0 → ~0.9)
            if progress_callback and poll_count % 3 == 0:
                # Asymptotic approach to 0.9 — never reaches 1.0 until done
                sub_progress = min(0.9, poll_count * 0.05)
                progress_callback(sub_progress)
            
            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
            poll_count += 1
        
        # Signal completion of this test
        if progress_callback:
            progress_callback(1.0)
        
        if process.returncode == 0 and os.path.exists(output_path):
            return os.path.getsize(output_path)
        return None
    
    def _safe_encode_test(self, input_path, width, height, crf, preset, stop_check=None, progress_callback=None):
        """Encode test with automatic temp file cleanup. Returns size or None."""
        tmp = get_temp_filename()
        try:
            return self._encode_test(input_path, tmp, width, height, crf, preset, stop_check=stop_check, progress_callback=progress_callback)
        except Exception as e:
            print(f"[AVIF_v2] Encode test failed at CRF {crf}: {e}")
            return None
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    
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
        
        print(f"[AVIF_v2] Estimating for {target_size_bytes} bytes ({target_size_bytes/1024:.1f} KB), downscale={allow_downscale}, preset={preset_name}")
        
        meta = get_media_metadata(input_path)
        
        # Use user override dimensions if provided
        original_w, original_h = meta['width'], meta['height']
        if override_w and override_h:
            meta['width'] = override_w
            meta['height'] = override_h
        
        scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
        best_res = None
        best_crf = 64
        
        # Progress: estimation = 0.0 → 0.65
        # Each scale: 1 probe + up to 6 binary search iterations = ~7 tests
        total_tests = len(scales) * 7
        completed_tests = 0
        
        def make_sub_progress(test_index):
            """Create a scoped callback that maps [0,1] within one encode test
            to the correct slice of the overall [0.0, 0.65] estimation range."""
            start = test_index / total_tests * 0.65
            end = (test_index + 1) / total_tests * 0.65
            def sub_cb(fraction):
                # fraction is 0.0→1.0 within this single test
                overall = start + (end - start) * fraction
                emit_progress(overall)
            return sub_cb
        
        for scale_idx, scale in enumerate(scales):
            if should_stop():
                print("[AVIF_v2] Stopped by user during estimation")
                return self._make_fallback_result(meta, preset)
            
            target_w = max(2, int(meta['width'] * scale))
            target_h = max(2, int(meta['height'] * scale))
            # Ensure even dimensions
            target_w = target_w - (target_w % 2)
            target_h = target_h - (target_h % 2)
            
            # ── Phase 1: Mid-probe to determine search half ──
            mid_crf = 32
            print(f"[AVIF_v2] Scale {int(scale*100)}% ({target_w}x{target_h}): probing CRF {mid_crf}...")
            
            mid_size = self._safe_encode_test(input_path, target_w, target_h, mid_crf, preset, stop_check=should_stop, progress_callback=make_sub_progress(completed_tests))
            completed_tests += 1
            emit_progress(completed_tests / total_tests * 0.65)
            
            if should_stop():
                return best_res if best_res else self._make_fallback_result(meta, preset)
            
            if mid_size is None:
                # Probe failed — skip this scale
                print(f"[AVIF_v2] Mid-probe failed at scale {int(scale*100)}%, skipping")
                completed_tests += 6  # skip remaining iterations
                emit_progress(completed_tests / total_tests * 0.65)
                continue
            
            print(f"[AVIF_v2] Mid-probe CRF{mid_crf}: {mid_size/1024:.1f} KB (target: {target_size_bytes/1024:.1f} KB)")
            
            # ── Phase 2: Narrow binary search ──
            if mid_size <= target_size_bytes:
                # Target is larger than mid — search QUALITY half (CRF 0-32, lower CRF = better)
                low, high = 0, mid_crf
                scale_best_crf = mid_crf
                scale_best_size = mid_size
                print(f"[AVIF_v2] Searching quality half CRF [{low}-{high}]")
            else:
                # Target is smaller than mid — search COMPRESSION half (CRF 32-63)
                low, high = mid_crf + 1, 63
                scale_best_crf = 64  # no valid result yet
                scale_best_size = 0
                print(f"[AVIF_v2] Searching compression half CRF [{low}-{high}]")
            
            for iteration in range(6):
                if should_stop():
                    print("[AVIF_v2] Stopped by user during binary search")
                    return best_res if best_res else self._make_fallback_result(meta, preset)
                
                if low > high:
                    completed_tests += (5 - iteration)
                    break
                
                mid = (low + high) // 2
                size = self._safe_encode_test(input_path, target_w, target_h, mid, preset, stop_check=should_stop, progress_callback=make_sub_progress(completed_tests))
                completed_tests += 1
                emit_progress(completed_tests / total_tests * 0.65)
                
                if size is not None:
                    print(f"[AVIF_v2] Scale {int(scale*100)}%, CRF{mid}: {size/1024:.1f} KB (target: {target_size_bytes/1024:.1f} KB)")
                    
                    if size <= target_size_bytes:
                        # Fits — record and try better quality (lower CRF)
                        if mid < scale_best_crf:
                            scale_best_crf = mid
                            scale_best_size = size
                        high = mid - 1
                    else:
                        # Too big — try worse quality (higher CRF)
                        low = mid + 1
                else:
                    # Encode failed — move to higher CRF
                    low = mid + 1
            
            # Update best result if this scale found a valid CRF
            if scale_best_crf < best_crf:
                best_crf = scale_best_crf
                ui_quality = max(0, min(100, int(100 - (scale_best_crf / 63.0) * 100)))
                best_res = {
                    'quality': ui_quality,
                    'crf': scale_best_crf,
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
            
            # If we found a high quality solution, stop searching lower scales
            if scale_best_crf <= 20:
                print(f"[AVIF_v2] Found high quality CRF{scale_best_crf} at scale {int(scale*100)}%, stopping search")
                break
        
        if best_res is None:
            best_res = self._fallback_estimate(input_path, target_size_bytes, meta, allow_downscale, preset, should_stop, emit_progress)
        
        emit_progress(0.65)  # Estimation complete
        print(f"[AVIF_v2] Final: CRF{best_res['crf']} (Q{best_res['quality']}), scale {int(best_res['scale_factor']*100)}%, estimated {best_res['estimated_size']/1024:.1f} KB")
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
        print("[AVIF_v2] ⚠ Target unreachable with standard settings")
        
        if allow_downscale:
            print("[AVIF_v2] Attempting emergency downscaling...")
            current_scale = 0.5
            
            for attempt in range(20):
                if should_stop():
                    print("[AVIF_v2] Stopped by user during fallback")
                    return self._make_fallback_result(meta, preset)
                
                current_w = max(16, int(meta['width'] * current_scale))
                current_h = max(16, int(meta['height'] * current_scale))
                current_w = current_w - (current_w % 2) if current_w > 1 else current_w
                current_h = current_h - (current_h % 2) if current_h > 1 else current_h
                
                size = self._safe_encode_test(input_path, current_w, current_h, 55, preset, stop_check=should_stop, progress_callback=emit_progress)
                if size and size <= target_size_bytes:
                    print(f"[AVIF_v2] Emergency scale found: {int(current_scale*100)}% = {size/1024:.1f} KB")
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
                
                current_scale *= 0.8
                if current_w <= 16:
                    break
        
        # Last resort: use maximum CRF at original size
        print("[AVIF_v2] Using maximum CRF fallback")
        self._safe_encode_test(input_path, meta['width'], meta['height'], 63, preset, stop_check=should_stop, progress_callback=emit_progress)
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
            
            emit_progress(0.65)  # Estimation done, encoding starts
            
            # Build filter chain
            vf_filters = []
            
            override_w = options.get('override_width')
            override_h = options.get('override_height')
            
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
            
            print(f"[AVIF_v2 DEBUG] Command: {' '.join(cmd)}")
            
            # Use Popen for interruptibility
            # DEVNULL for stdout; drain stderr in a thread to avoid pipe deadlock
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
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass
                    return False
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
                # Progress pulses between 0.65 and 0.95 during encoding
                emit_progress(0.85)
            
            stderr_thread.join(timeout=2.0)
            
            if process.returncode != 0:
                stderr_output = b''.join(stderr_chunks).decode('utf-8', errors='ignore') if stderr_chunks else 'No stderr'
                print(f"[AVIF_v2 FFMPEG ERROR] {stderr_output}")
                emit(f"FFmpeg error (code {process.returncode})")
                from client.utils.error_reporter import log_error
                log_error(
                    Exception(f"FFmpeg avif failed (returncode={process.returncode})"),
                    context="avif_estimator_v2",
                    additional_info={"stderr_tail": stderr_output[-2000:]}
                )
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
            print(f"[AVIF_v2 ERROR] {traceback.format_exc()}")
            from client.utils.error_reporter import log_error
            log_error(e, context="avif_estimator_v2 / execute")
            return False


_estimator = Estimator()

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
