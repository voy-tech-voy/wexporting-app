"""
PNG Image Estimator v5
Optimizes PNG images for target file size using compression_level (0-9).
Quality 0-100 maps to compression_level 9-0 (higher compression = smaller file).

This is a self-contained estimator that owns its complete encoding strategy.
"""
import os
import tempfile
import ffmpeg
from typing import Dict, Optional, Callable, Any

from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata


def get_temp_filename(ext='png'): 
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name


class Estimator(EstimatorProtocol):
    """PNG compression level binary search estimator."""
    
    @property
    def version(self) -> str:
        return "v5"
    
    @property
    def description(self) -> str:
        return "PNG binary search compression optimization"
    
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
        print(f"[PNG_v5] Estimating for {target_size_bytes} bytes, downscale={allow_downscale}")
        
        meta = get_media_metadata(input_path)
        scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
        best_res = None
        
        for scale in scales:
            target_w = max(1, int(meta['width'] * scale))
            target_h = max(1, int(meta['height'] * scale))
            low, high, valid_q = 0, 100, -1
            
            for _ in range(6):
                mid = (low + high) // 2
                tmp = get_temp_filename()
                comp_level = self._quality_to_compression(mid)
                
                try:
                    (ffmpeg.input(input_path).filter('scale', target_w, target_h)
                     .output(tmp, compression_level=comp_level).run(quiet=True, overwrite_output=True))
                    
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
            
            if valid_q >= 50: break
        
        if best_res is None:
            best_res = self._fallback_estimate(input_path, target_size_bytes, meta, allow_downscale, scales)
        
        print(f"[PNG_v5] Estimated: Q{best_res['quality']}, scale {int(best_res['scale_factor']*100)}%")
        return best_res
    
    def _fallback_estimate(self, input_path, target_size_bytes, meta, allow_downscale, scales):
        if not allow_downscale:
            print("[PNG_v5] ⚠ Target unreachable, using max compression")
            comp_level = self._quality_to_compression(0)
            tmp = get_temp_filename()
            floor_size = 0
            try:
                (ffmpeg.input(input_path).output(tmp, compression_level=comp_level)
                 .run(quiet=True, overwrite_output=True))
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
            print("[PNG_v5] ⚠ Emergency downscaling")
            current_scale = scales[-1]
            for _ in range(20):
                current_scale *= 0.90
                current_w = max(1, int(meta['width'] * current_scale))
                current_h = max(1, int(meta['height'] * current_scale))
                tmp = get_temp_filename()
                comp_level = self._quality_to_compression(5)
                try:
                    (ffmpeg.input(input_path).filter('scale', current_w, current_h)
                     .output(tmp, compression_level=comp_level).run(quiet=True, overwrite_output=True))
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
        **options
    ) -> bool:
        def emit(msg: str):
            if status_callback: status_callback(msg)
        
        try:
            params = self.estimate(input_path, target_size_bytes, **options)
            emit(f"PNG Q{params['quality']}, scale {int(params['scale_factor']*100)}%")
            
            stream = ffmpeg.input(input_path)
            if params['scale_factor'] < 1.0:
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
            ffmpeg.run(stream, quiet=True)
            
            if os.path.exists(output_path):
                actual_kb = os.path.getsize(output_path) / 1024
                emit(f"✓ Complete: {actual_kb:.1f} KB")
                return True
            emit("✗ Output file not created")
            return False
        except Exception as e:
            emit(f"Error: {str(e)}")
            return False


_estimator = Estimator()

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
