"""
WebP Image Estimator v9
Optimizes WebP images for target file size using quality parameter (0-100).

Changes from v8:
- Added progress_callback support (blue bar fills during probe phase + final encode)
  Estimation phase: 0.0 -> 0.70 (stepped per probe, up to 10 iterations per scale)
  Encode phase:     0.70 -> 1.0
"""
import os
import subprocess
import tempfile
import ffmpeg
from typing import Dict, Optional, Callable, Any

from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata, run_ffmpeg_skill_standard


# WebP quality above ~85 yields rapidly diminishing visual returns
# while inflating file size significantly. Cap here unless target is tight.
QUALITY_CEILING = 85


def get_temp_filename(ext='webp'):
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name


def get_ffmpeg_binary():
    """Get the FFmpeg binary path from environment or use default."""
    ffmpeg_bin = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
    if ffmpeg_bin and os.path.exists(ffmpeg_bin):
        return ffmpeg_bin
    return 'ffmpeg'


def run_ffmpeg_cmd(cmd_args, stop_check=None):
    rc = run_ffmpeg_skill_standard(cmd_args, stop_check=stop_check, log_target='estimator')
    class _R: pass
    r = _R(); r.returncode = rc; return r


class Estimator(EstimatorProtocol):
    """WebP quality binary search estimator v9 - skip + quality ceiling + progress bar."""

    @property
    def version(self) -> str:
        return "v9"

    @property
    def description(self) -> str:
        return "WebP binary search with skip logic, quality ceiling, and progress bar"

    def get_output_extension(self) -> str:
        return "webp"

    def _encode_test(self, input_path: str, output_path: str, width: int, height: int, quality: int) -> Optional[int]:
        """Encode a test image and return file size, or None on failure."""
        cmd_args = [
            '-y',
            '-i', input_path,
            '-vf', f'scale={width}:{height}',
            '-c:v', 'libwebp',
            '-quality', str(quality),
            output_path
        ]
        result = run_ffmpeg_cmd(cmd_args, stop_check=getattr(self, '_current_stop_check', None))
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
        override_w = options.get('override_width')
        override_h = options.get('override_height')
        stop_check = options.get('stop_check')
        progress_callback = options.get('progress_callback')
        print(f"[WebP_v9] Estimating for {target_size_bytes} bytes ({target_size_bytes/1024:.1f} KB), downscale={allow_downscale}")

        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))

        # Skip if input already fits under target
        input_size = os.path.getsize(input_path)
        if input_size <= target_size_bytes:
            print(f"[WebP_v9] Input ({input_size/1024:.1f} KB) already under target ({target_size_bytes/1024:.1f} KB) - skipping")
            meta = get_media_metadata(input_path)
            return {
                'skipped': True,
                'reason': 'input_already_under_target',
                'input_size': input_size,
                'quality': -1,
                'scale_factor': 1.0,
                'resolution_w': meta['width'],
                'resolution_h': meta['height'],
                'estimated_size': input_size,
                'original_width': meta['width'],
                'original_height': meta['height'],
                'ffmpeg_out_args': {}
            }

        meta = get_media_metadata(input_path)

        original_w, original_h = meta['width'], meta['height']
        if override_w and override_h:
            meta['width'] = override_w
            meta['height'] = override_h

        scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
        best_res = None
        best_quality = -1

        # Progress: each scale × 10 iterations. Max 4 × 10 = 40 probes.
        total_probes = len(scales) * 10
        completed_probes = 0

        for scale in scales:
            if stop_check and stop_check():
                break

            target_w = max(1, int(meta['width'] * scale))
            target_h = max(1, int(meta['height'] * scale))
            target_w = target_w - (target_w % 2) if target_w > 1 else target_w
            target_h = target_h - (target_h % 2) if target_h > 1 else target_h

            low, high = 0, QUALITY_CEILING
            scale_best_quality = -1
            scale_best_size = 0

            for iteration in range(10):
                if stop_check and stop_check():
                    break
                mid = (low + high) // 2
                tmp = get_temp_filename()

                try:
                    size = self._encode_test(input_path, tmp, target_w, target_h, mid)

                    if size is not None:
                        print(f"[WebP_v9] Scale {int(scale*100)}%, Q{mid}: {size/1024:.1f} KB (target: {target_size_bytes/1024:.1f} KB)")

                        if size <= target_size_bytes:
                            if mid > scale_best_quality:
                                scale_best_quality = mid
                                scale_best_size = size
                            low = mid + 1
                        else:
                            high = mid - 1
                    else:
                        high = mid - 1
                except Exception as e:
                    print(f"[WebP_v9] Encode test failed: {e}")
                    high = mid - 1
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)

                completed_probes += 1
                emit_progress(completed_probes / total_probes * 0.70)

                if low > high:
                    # Pad remaining iterations for this scale
                    remaining = 10 - iteration - 1
                    completed_probes += remaining
                    emit_progress(completed_probes / total_probes * 0.70)
                    break

            if scale_best_quality > best_quality:
                best_quality = scale_best_quality
                best_res = {
                    'quality': scale_best_quality,
                    'scale_factor': scale,
                    'resolution_w': target_w,
                    'resolution_h': target_h,
                    'estimated_size': scale_best_size,
                    'original_width': original_w,
                    'original_height': original_h,
                    'ffmpeg_out_args': {'c:v': 'libwebp', 'quality': scale_best_quality}
                }

            if scale_best_quality >= 75:
                print(f"[WebP_v9] Found high quality Q{scale_best_quality} at scale {int(scale*100)}%, stopping search")
                break

        emit_progress(0.70)  # Estimation complete

        if best_res is None:
            best_res = self._fallback_estimate(input_path, target_size_bytes, meta, allow_downscale, original_w, original_h)

        print(f"[WebP_v9] Final: Q{best_res['quality']}, scale {int(best_res['scale_factor']*100)}%, estimated {best_res['estimated_size']/1024:.1f} KB")
        return best_res

    def _fallback_estimate(self, input_path, target_size_bytes, meta, allow_downscale, original_w=None, original_h=None):
        """Fallback when target is unreachable with normal quality range."""
        print("[WebP_v9] Target unreachable with standard settings")
        ow = original_w or meta['width']
        oh = original_h or meta['height']

        if allow_downscale:
            print("[WebP_v9] Attempting emergency downscaling...")
            current_scale = 0.5

            for attempt in range(20):
                current_w = max(16, int(meta['width'] * current_scale))
                current_h = max(16, int(meta['height'] * current_scale))
                current_w = current_w - (current_w % 2) if current_w > 1 else current_w
                current_h = current_h - (current_h % 2) if current_h > 1 else current_h

                tmp = get_temp_filename()
                try:
                    size = self._encode_test(input_path, tmp, current_w, current_h, 10)
                    if size and size <= target_size_bytes:
                        print(f"[WebP_v9] Emergency scale found: {int(current_scale*100)}% = {size/1024:.1f} KB")
                        return {
                            'quality': 10,
                            'scale_factor': current_scale,
                            'resolution_w': current_w,
                            'resolution_h': current_h,
                            'estimated_size': size,
                            'original_width': ow,
                            'original_height': oh,
                            'ffmpeg_out_args': {'c:v': 'libwebp', 'quality': 10}
                        }
                except:
                    pass
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)

                current_scale *= 0.8
                if current_w <= 16:
                    break

        print("[WebP_v9] Using minimum quality fallback")
        tmp = get_temp_filename()
        floor_size = 0
        try:
            floor_size = self._encode_test(input_path, tmp, meta['width'], meta['height'], 0) or 0
        except:
            pass
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

        return {
            'quality': 0,
            'scale_factor': 1.0,
            'resolution_w': meta['width'],
            'resolution_h': meta['height'],
            'estimated_size': floor_size,
            'original_width': ow,
            'original_height': oh,
            'ffmpeg_out_args': {'c:v': 'libwebp', 'quality': 0}
        }

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
        self._current_stop_check = stop_check

        def emit(msg: str):
            if status_callback:
                status_callback(msg)

        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))

        try:
            if stop_check and stop_check():
                emit("Stopped by user")
                return False

            emit_progress(0.0)

            params = self.estimate(
                input_path, target_size_bytes,
                stop_check=stop_check,
                progress_callback=progress_callback,
                **options
            )

            # Handle skip: input already under target
            if params.get('skipped'):
                input_kb = params.get('input_size', 0) / 1024
                target_kb = target_size_bytes / 1024
                emit(f"[SKIP] Already under target ({input_kb:.1f} KB < {target_kb:.1f} KB)")
                return 'skipped'

            emit(f"WebP Q{params['quality']}, {params['resolution_w']}x{params['resolution_h']}")
            emit_progress(0.70)  # Estimation done

            if stop_check and stop_check():
                emit("Stopped by user")
                return False

            # Build filter chain
            vf_filters = []
            override_w = options.get('override_width')
            override_h = options.get('override_height')
            needs_scale = (override_w and override_h) or params['scale_factor'] < 1.0
            if needs_scale:
                vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")

            rotation = options.get('rotation')
            if rotation and rotation != "No rotation":
                if rotation == "90° clockwise":
                    vf_filters.append("transpose=1")
                elif rotation == "180°":
                    vf_filters.append("transpose=2,transpose=2")
                elif rotation == "270° clockwise":
                    vf_filters.append("transpose=2")

            cmd_args = ['-y', '-i', input_path]
            if vf_filters:
                cmd_args.extend(['-vf', ','.join(vf_filters)])
            cmd_args.extend([
                '-c:v', 'libwebp',
                '-quality', str(params['quality']),
                output_path
            ])

            emit("Encoding WebP...")
            ffmpeg_bin = get_ffmpeg_binary()
            cmd = [ffmpeg_bin] + cmd_args
            print(f"[WebP_v9 DEBUG] Command: {' '.join(cmd)}")

            rc = run_ffmpeg_skill_standard(cmd, stop_check=stop_check, log_target=output_path)

            if rc != 0:
                emit(f"FFmpeg error (code {rc})")
                from client.utils.error_reporter import log_error
                log_error(
                    Exception(f"FFmpeg WebP failed (rc={rc})"),
                    context="webp_estimator_v9",
                    additional_info={"command": cmd}
                )
                return False

            if os.path.exists(output_path):
                actual_kb = os.path.getsize(output_path) / 1024
                target_kb = target_size_bytes / 1024
                emit(f"[OK] Complete: {actual_kb:.1f} KB (target: {target_kb:.1f} KB)")
                emit_progress(1.0)
                return True

            emit("[X] Output file not created")
            return False

        except Exception as e:
            import traceback
            emit(f"Error: {str(e)}")
            print(f"[WebP_v9 ERROR] {traceback.format_exc()}")
            from client.utils.error_reporter import log_error
            log_error(e, context="webp_estimator_v9 / execute")
            return False


_estimator = Estimator()

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
