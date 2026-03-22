"""
JPG Image Estimator v7
Optimizes JPEG images for target file size using binary search on qscale:v.
Quality 0-100 maps to qscale:v 31-2 (lower qscale = higher quality).

Changes from v6:
- Added progress_callback support (blue bar fills during probe phase + final encode)
  Estimation phase: 0.0 -> 0.70 (stepped per probe)
  Encode phase:     0.70 -> 1.0
"""
import os
import tempfile
import ffmpeg
from typing import Dict, Optional, Callable, Any

from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata, run_ffmpeg_skill_standard
from client.core.tool_registry import get_ffmpeg_path


def get_temp_filename(ext='jpg'): 
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name


class Estimator(EstimatorProtocol):
    """
    JPG quality binary search estimator v7.
    Strategy: Binary search across quality levels (and optionally resolution)
    to find the highest quality that fits within target size.
    Progress: stepped fractions emitted after each probe (0→0.70), 1.0 at encode done.
    """

    @property
    def version(self) -> str:
        return "v7"

    @property
    def description(self) -> str:
        return "JPG binary search quality optimization + progress bar"

    def get_output_extension(self) -> str:
        return "jpg"

    @staticmethod
    def _quality_to_qscale(q: int) -> int:
        """Quality 0 (worst) → qscale:v 31, Quality 100 (best) → qscale:v 2."""
        return 31 - int((q / 100.0) * 29)

    def estimate(
        self,
        input_path: str,
        target_size_bytes: int,
        **options
    ) -> Dict[str, Any]:
        """Find optimal quality/resolution for target size through binary search."""
        ffmpeg_bin = get_ffmpeg_path()
        allow_downscale = options.get('allow_downscale', False)
        override_w = options.get('override_width')
        override_h = options.get('override_height')
        stop_check = options.get('stop_check')
        progress_callback = options.get('progress_callback')
        print(f"[JPG_v7] Estimating for {target_size_bytes} bytes, downscale={allow_downscale}")

        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))

        meta = get_media_metadata(input_path)

        if override_w and override_h:
            meta['width'] = override_w
            meta['height'] = override_h

        scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
        best_res = None

        # Progress budget: each scale has up to 6 iterations; cap at 4 scales × 6 = 24 probes
        total_probes = len(scales) * 6
        completed_probes = 0

        for scale in scales:
            target_w = max(1, int(meta['width'] * scale))
            target_h = max(1, int(meta['height'] * scale))

            low, high, valid_q = 0, 100, -1

            for _ in range(6):
                if stop_check and stop_check():
                    break
                mid = (low + high) // 2
                tmp = get_temp_filename()
                qscale = self._quality_to_qscale(mid)

                try:
                    stream_tmp = ffmpeg.overwrite_output(
                        ffmpeg.input(input_path).filter('scale', target_w, target_h)
                        .output(tmp, **{'qscale:v': qscale}))
                    run_ffmpeg_skill_standard(
                        ffmpeg.compile(stream_tmp, cmd=ffmpeg_bin),
                        stop_check=stop_check,
                        log_target='estimator'
                    )

                    if os.path.exists(tmp):
                        size = os.path.getsize(tmp)
                        if size < target_size_bytes:
                            valid_q = mid
                            best_res = {
                                'quality': mid,
                                'scale_factor': scale,
                                'resolution_w': target_w,
                                'resolution_h': target_h,
                                'estimated_size': size,
                                'ffmpeg_out_args': {'qscale:v': qscale}
                            }
                            low = mid + 1
                        else:
                            high = mid - 1
                    else:
                        high = mid - 1
                except:
                    high = mid - 1
                finally:
                    if os.path.exists(tmp): os.remove(tmp)

                completed_probes += 1
                emit_progress(completed_probes / total_probes * 0.70)

            if valid_q >= 50:
                break

        # Pad remaining probe slots in progress
        emit_progress(0.70)

        if best_res is None:
            best_res = self._fallback_estimate(input_path, target_size_bytes, meta, allow_downscale, scales, stop_check)

        print(f"[JPG_v7] Estimated: Q{best_res['quality']}, scale {int(best_res['scale_factor']*100)}%")
        return best_res

    def _fallback_estimate(self, input_path, target_size_bytes, meta, allow_downscale, scales, stop_check=None):
        """Fallback estimation when binary search fails to find valid quality."""
        ffmpeg_bin = get_ffmpeg_path()
        if not allow_downscale:
            print("[JPG_v7] ⚠ Target unreachable, using max compression")
            qscale = self._quality_to_qscale(0)
            tmp = get_temp_filename()
            floor_size = 0
            try:
                stream_tmp = ffmpeg.overwrite_output(
                    ffmpeg.input(input_path).output(tmp, **{'qscale:v': qscale}))
                run_ffmpeg_skill_standard(ffmpeg.compile(stream_tmp, cmd=ffmpeg_bin), stop_check=stop_check, log_target='estimator')
                if os.path.exists(tmp): floor_size = os.path.getsize(tmp)
            except: pass
            finally:
                if os.path.exists(tmp): os.remove(tmp)

            return {
                'quality': 0,
                'scale_factor': 1.0,
                'resolution_w': meta['width'],
                'resolution_h': meta['height'],
                'estimated_size': floor_size,
                'ffmpeg_out_args': {'qscale:v': qscale}
            }
        else:
            print("[JPG_v7] ⚠ Emergency downscaling")
            current_scale = scales[-1]

            for _ in range(20):
                if stop_check and stop_check():
                    break
                current_scale *= 0.90
                current_w = max(1, int(meta['width'] * current_scale))
                current_h = max(1, int(meta['height'] * current_scale))

                tmp = get_temp_filename()
                test_q = 5
                qscale = self._quality_to_qscale(test_q)

                try:
                    stream_tmp = ffmpeg.overwrite_output(
                        ffmpeg.input(input_path).filter('scale', current_w, current_h)
                        .output(tmp, **{'qscale:v': qscale}))
                    run_ffmpeg_skill_standard(ffmpeg.compile(stream_tmp, cmd=ffmpeg_bin), stop_check=stop_check, log_target='estimator')

                    size = os.path.getsize(tmp)
                    if size < target_size_bytes or current_w < 16:
                        if os.path.exists(tmp): os.remove(tmp)
                        return {
                            'quality': test_q,
                            'scale_factor': current_scale,
                            'resolution_w': current_w,
                            'resolution_h': current_h,
                            'estimated_size': size,
                            'ffmpeg_out_args': {'qscale:v': qscale}
                        }
                except: pass
                finally:
                    if os.path.exists(tmp): os.remove(tmp)

            return {
                'quality': 0, 'scale_factor': 0.1, 'resolution_w': 16, 'resolution_h': 16,
                'estimated_size': 0, 'ffmpeg_out_args': {'qscale:v': 31}
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
        """Execute JPG encoding using estimated parameters."""
        self._current_stop_check = stop_check

        def emit(msg: str):
            if status_callback:
                status_callback(msg)

        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))

        try:
            ffmpeg_bin = get_ffmpeg_path()
            emit_progress(0.0)

            # Run estimation phase (fills 0 → 0.70)
            params = self.estimate(
                input_path, target_size_bytes,
                stop_check=stop_check,
                progress_callback=progress_callback,
                **options
            )

            emit(f"JPG Q{params['quality']}, scale {int(params['scale_factor']*100)}%")
            emit_progress(0.70)  # Estimation done

            if stop_check and stop_check():
                emit("Stopped by user")
                return False

            # Build FFmpeg command
            stream = ffmpeg.input(input_path)

            override_w = options.get('override_width')
            override_h = options.get('override_height')
            needs_scale = (override_w and override_h) or params['scale_factor'] < 1.0
            if needs_scale:
                stream = ffmpeg.filter(stream, 'scale', params['resolution_w'], params['resolution_h'])

            rotation = options.get('rotation')
            if rotation and rotation != "No rotation":
                if rotation == "90° clockwise":
                    stream = ffmpeg.filter(stream, 'transpose', 1)
                elif rotation == "180°":
                    stream = ffmpeg.filter(stream, 'transpose', 2)
                    stream = ffmpeg.filter(stream, 'transpose', 2)
                elif rotation == "270° clockwise":
                    stream = ffmpeg.filter(stream, 'transpose', 2)

            ffmpeg_args = params.get('ffmpeg_out_args', {})
            stream = ffmpeg.output(stream, output_path, **ffmpeg_args)
            stream = ffmpeg.overwrite_output(stream)

            emit("Encoding JPG...")
            run_ffmpeg_skill_standard(
                ffmpeg.compile(stream, cmd=ffmpeg_bin),
                stop_check=stop_check,
                log_target=output_path
            )

            if os.path.exists(output_path):
                actual_kb = os.path.getsize(output_path) / 1024
                emit(f"[OK] Complete: {actual_kb:.1f} KB")
                emit_progress(1.0)
                return True
            else:
                emit("[X] Output file not created")
                return False

        except Exception as e:
            emit(f"Error: {str(e)}")
            from client.utils.error_reporter import log_error
            log_error(e, context="jpg_estimator_v7 / execute")
            return False


# Backward compatibility
_estimator = Estimator()

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
