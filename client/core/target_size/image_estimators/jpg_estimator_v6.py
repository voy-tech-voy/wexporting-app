"""
JPG Image Estimator v5
Optimizes JPEG images for target file size using binary search on qscale:v.
Quality 0-100 maps to qscale:v 31-2 (lower qscale = higher quality).

This is a self-contained estimator that owns its complete encoding strategy.
"""
import os
import tempfile
import ffmpeg
from typing import Dict, Optional, Callable, Any

from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata, run_ffmpeg_skill_standard
from client.core.ffmpeg_utils import run_ffmpeg_hidden
from client.core.tool_registry import get_ffmpeg_path


def get_temp_filename(ext='jpg'): 
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name


class Estimator(EstimatorProtocol):
    """
    JPG quality binary search estimator.
    
    Strategy: Binary search across quality levels (and optionally resolution)
    to find the highest quality that fits within target size.
    """
    
    @property
    def version(self) -> str:
        return "v5"
    
    @property
    def description(self) -> str:
        return "JPG binary search quality optimization"
    
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
        print(f"[JPG_v5] Estimating for {target_size_bytes} bytes, downscale={allow_downscale}")
        
        meta = get_media_metadata(input_path)
        
        # Use user override dimensions if provided
        if override_w and override_h:
            meta['width'] = override_w
            meta['height'] = override_h
        
        scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
        best_res = None
        
        # Binary search across resolutions
        for scale in scales:
            target_w = max(1, int(meta['width'] * scale))
            target_h = max(1, int(meta['height'] * scale))
            
            low, high, valid_q = 0, 100, -1
            
            for _ in range(6):  # 6 iterations for binary search
                mid = (low + high) // 2
                tmp = get_temp_filename()
                qscale = self._quality_to_qscale(mid)
                
                try:
                    stream_tmp = ffmpeg.overwrite_output(
                        ffmpeg.input(input_path).filter('scale', target_w, target_h)
                        .output(tmp, **{'qscale:v': qscale}))
                    run_ffmpeg_skill_standard(ffmpeg.compile(stream_tmp, cmd=ffmpeg_bin), stop_check=getattr(self, '_current_stop_check', None), log_target='estimator')
                    
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
            
            if valid_q >= 50: break
        
        # Fallback strategies
        if best_res is None:
            best_res = self._fallback_estimate(input_path, target_size_bytes, meta, allow_downscale, scales)
        
        print(f"[JPG_v5] Estimated: Q{best_res['quality']}, scale {int(best_res['scale_factor']*100)}%")
        return best_res
    
    def _fallback_estimate(self, input_path, target_size_bytes, meta, allow_downscale, scales):
        """Fallback estimation when binary search fails to find valid quality."""
        ffmpeg_bin = get_ffmpeg_path()
        if not allow_downscale:
            # Max compression at native resolution
            print("[JPG_v5] ⚠ Target unreachable, using max compression")
            qscale = self._quality_to_qscale(0)
            
            tmp = get_temp_filename()
            floor_size = 0
            try:
                stream_tmp = ffmpeg.overwrite_output(
                    ffmpeg.input(input_path).output(tmp, **{'qscale:v': qscale}))
                run_ffmpeg_skill_standard(ffmpeg.compile(stream_tmp, cmd=ffmpeg_bin), stop_check=getattr(self, '_current_stop_check', None), log_target='estimator')
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
            # Emergency downscaling
            print("[JPG_v5] ⚠ Emergency downscaling")
            current_scale = scales[-1]
            
            for _ in range(20):
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
                    run_ffmpeg_skill_standard(ffmpeg.compile(stream_tmp, cmd=ffmpeg_bin), stop_check=getattr(self, '_current_stop_check', None), log_target='estimator')
                    
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
            
            # Ultimate fallback
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
        **options
    ) -> bool:
        """Execute JPG encoding using estimated parameters."""
        self._current_stop_check = stop_check

        def emit(msg: str):
            if status_callback:
                status_callback(msg)
        
        try:
            ffmpeg_bin = get_ffmpeg_path()
            # Get optimal parameters
            params = self.estimate(input_path, target_size_bytes, **options)
            
            emit(f"JPG Q{params['quality']}, scale {int(params['scale_factor']*100)}%")
            
            # Build FFmpeg command
            stream = ffmpeg.input(input_path)
            
            # Get user override dimensions
            override_w = options.get('override_width')
            override_h = options.get('override_height')
            
            # Apply scale if: user provided override OR auto-resize reduced size
            needs_scale = (override_w and override_h) or params['scale_factor'] < 1.0
            if needs_scale:
                stream = ffmpeg.filter(stream, 'scale', params['resolution_w'], params['resolution_h'])
            
            # Apply rotation if specified
            rotation = options.get('rotation')
            if rotation and rotation != "No rotation":
                if rotation == "90° clockwise":
                    stream = ffmpeg.filter(stream, 'transpose', 1)
                elif rotation == "180°":
                    stream = ffmpeg.filter(stream, 'transpose', 2)
                    stream = ffmpeg.filter(stream, 'transpose', 2)
                elif rotation == "270° clockwise":
                    stream = ffmpeg.filter(stream, 'transpose', 2)
            
            # Output with quality settings
            ffmpeg_args = params.get('ffmpeg_out_args', {})
            stream = ffmpeg.output(stream, output_path, **ffmpeg_args)
            stream = ffmpeg.overwrite_output(stream)
            
            # Run encoding
            run_ffmpeg_skill_standard(ffmpeg.compile(stream, cmd=ffmpeg_bin), stop_check=getattr(self, '_current_stop_check', None), log_target='estimator')
            
            # Verify output
            if os.path.exists(output_path):
                actual_kb = os.path.getsize(output_path) / 1024
                emit(f"[OK] Complete: {actual_kb:.1f} KB")
                return True
            else:
                emit("[X] Output file not created")
                return False
                
        except Exception as e:
            emit(f"Error: {str(e)}")
            return False


# Backward compatibility
_estimator = Estimator()

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
