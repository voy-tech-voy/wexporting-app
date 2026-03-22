"""
PNG Image Estimator v7
Optimizes PNG images for target file size using compression_level (0-9).
Quality 0-100 maps to compression_level 9-0 (higher compression = smaller file).

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


def get_temp_filename(ext='png'): 
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name


class Estimator(EstimatorProtocol):
    """PNG compression level binary search estimator v7 + progress bar."""

    @property
    def version(self) -> str:
        return "v7"

    @property
    def description(self) -> str:
        return "PNG binary search compression optimization + progress bar"

    def get_output_extension(self) -> str:
        return "png"

    @staticmethod
    def _quality_to_compression(q: int) -> int:
        """Quality 0 → compression 9, Quality 100 → compression 0."""
        return int(9 * (100 - q) / 100)

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
        print(f"[PNG_v7] Estimating for {target_size_bytes} bytes, downscale={allow_downscale}")
        ffmpeg_bin = get_ffmpeg_path()

        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))

        meta = get_media_metadata(input_path)

        if override_w and override_h:
            meta['width'] = override_w
            meta['height'] = override_h

        scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
        best_res = None

        # Progress: max 4 scales × 6 iterations = 24 probes total
        total_probes = len(scales) * 6
        completed_probes = 0

        for scale in scales:
            if stop_check and stop_check():
                break

            target_w = max(1, int(meta['width'] * scale))
            target_h = max(1, int(meta['height'] * scale))
            low, high, valid_q = 0, 100, -1

            for _ in range(6):
                if stop_check and stop_check():
                    break
                mid = (low + high) // 2
                tmp = get_temp_filename()
                comp_level = self._quality_to_compression(mid)

                try:
                    stream = (ffmpeg.input(input_path).filter('scale', target_w, target_h)
                              .output(tmp, compression_level=comp_level))
                    run_ffmpeg_skill_standard(
                        ffmpeg.compile(ffmpeg.overwrite_output(stream), cmd=ffmpeg_bin),
                        stop_check=stop_check,
                        log_target='estimator'
                    )

                    if os.path.exists(tmp):
                        size = os.path.getsize(tmp)
                        if size < target_size_bytes:
                            valid_q = mid
                            best_res = {
                                'quality': mid, 'scale_factor': scale,
                                'resolution_w': target_w, 'resolution_h': target_h,
                                'estimated_size': size,
                                'ffmpeg_out_args': {'compression_level': comp_level}
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

        emit_progress(0.70)  # Estimation complete

        if best_res is None:
            best_res = self._fallback_estimate(input_path, target_size_bytes, meta, allow_downscale, scales, stop_check)

        print(f"[PNG_v7] Estimated: Q{best_res['quality']}, scale {int(best_res['scale_factor']*100)}%")
        return best_res

    def _fallback_estimate(self, input_path, target_size_bytes, meta, allow_downscale, scales, stop_check=None):
        ffmpeg_bin = get_ffmpeg_path()
        if not allow_downscale:
            print("[PNG_v7] ⚠ Target unreachable, using max compression")
            comp_level = self._quality_to_compression(0)
            tmp = get_temp_filename()
            floor_size = 0
            try:
                stream = ffmpeg.input(input_path).output(tmp, compression_level=comp_level)
                run_ffmpeg_skill_standard(ffmpeg.compile(ffmpeg.overwrite_output(stream), cmd=ffmpeg_bin), stop_check=stop_check, log_target='estimator')
                if os.path.exists(tmp): floor_size = os.path.getsize(tmp)
            except: pass
            finally:
                if os.path.exists(tmp): os.remove(tmp)
            return {
                'quality': 0, 'scale_factor': 1.0,
                'resolution_w': meta['width'], 'resolution_h': meta['height'],
                'estimated_size': floor_size,
                'ffmpeg_out_args': {'compression_level': comp_level}
            }
        else:
            print("[PNG_v7] ⚠ Emergency downscaling")
            current_scale = scales[-1]
            for _ in range(20):
                if stop_check and stop_check():
                    break
                current_scale *= 0.90
                current_w = max(1, int(meta['width'] * current_scale))
                current_h = max(1, int(meta['height'] * current_scale))
                tmp = get_temp_filename()
                comp_level = self._quality_to_compression(5)
                try:
                    stream = (ffmpeg.input(input_path).filter('scale', current_w, current_h)
                              .output(tmp, compression_level=comp_level))
                    run_ffmpeg_skill_standard(ffmpeg.compile(ffmpeg.overwrite_output(stream), cmd=ffmpeg_bin), stop_check=stop_check, log_target='estimator')
                    size = os.path.getsize(tmp)
                    if size < target_size_bytes or current_w < 16:
                        if os.path.exists(tmp): os.remove(tmp)
                        return {
                            'quality': 5, 'scale_factor': current_scale,
                            'resolution_w': current_w, 'resolution_h': current_h,
                            'estimated_size': size,
                            'ffmpeg_out_args': {'compression_level': comp_level}
                        }
                except: pass
                finally:
                    if os.path.exists(tmp): os.remove(tmp)
            return {'quality': 0, 'scale_factor': 0.1, 'resolution_w': 16, 'resolution_h': 16,
                    'estimated_size': 0, 'ffmpeg_out_args': {'compression_level': 9}}

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
            if status_callback: status_callback(msg)

        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))

        try:
            emit_progress(0.0)
            ffmpeg_bin = get_ffmpeg_path()

            params = self.estimate(
                input_path, target_size_bytes,
                stop_check=stop_check,
                progress_callback=progress_callback,
                **options
            )
            emit(f"PNG Q{params['quality']}, scale {int(params['scale_factor']*100)}%")
            emit_progress(0.70)

            if stop_check and stop_check():
                emit("Stopped by user")
                return False

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

            stream = ffmpeg.output(stream, output_path, **params.get('ffmpeg_out_args', {}))
            stream = ffmpeg.overwrite_output(stream)

            emit("Encoding PNG...")
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
            emit("[X] Output file not created")
            return False
        except Exception as e:
            emit(f"Error: {str(e)}")
            from client.utils.error_reporter import log_error
            log_error(e, context="png_estimator_v7 / execute")
            return False


_estimator = Estimator()

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
