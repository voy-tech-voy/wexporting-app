"""
WebP Image Estimator v5
Optimizes WebP images for target file size using quality parameter (0-100).
Direct quality mapping - no conversion needed.

This is a self-contained estimator that owns its complete encoding strategy.
"""
import os
import subprocess
import tempfile
import ffmpeg
from typing import Dict, Optional, Callable, Any

from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata


def get_temp_filename(ext='webp'): 
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name


class Estimator(EstimatorProtocol):
    """WebP quality binary search estimator."""
    
    @property
    def version(self) -> str:
        return "v5"
    
    @property
    def description(self) -> str:
        return "WebP binary search quality optimization"
    
    def get_output_extension(self) -> str:
        return "webp"
    
    def estimate(
        self, 
        input_path: str, 
        target_size_bytes: int, 
        **options
    ) -> Dict[str, Any]:
        allow_downscale = options.get('allow_downscale', False)
        override_w = options.get('override_width')
        override_h = options.get('override_height')
        print(f"[WebP_v5] Estimating for {target_size_bytes} bytes, downscale={allow_downscale}")
        
        meta = get_media_metadata(input_path)
        
        # Use user override dimensions if provided
        if override_w and override_h:
            meta['width'] = override_w
            meta['height'] = override_h
        
        scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
        best_res = None
        
        for scale in scales:
            target_w = max(1, int(meta['width'] * scale))
            target_h = max(1, int(meta['height'] * scale))
            low, high, valid_q = 0, 100, -1
            
            for _ in range(6):
                mid = (low + high) // 2
                tmp = get_temp_filename()
                
                try:
                    (ffmpeg.input(input_path).filter('scale', target_w, target_h)
                     .output(tmp, **{'c:v': 'libwebp', 'quality': mid}).run(quiet=True, overwrite_output=True))
                    
                    if os.path.exists(tmp):
                        size = os.path.getsize(tmp)
                        if size < target_size_bytes:
                            valid_q = mid
                            best_res = {
                                'quality': mid, 'scale_factor': scale,
                                'resolution_w': target_w, 'resolution_h': target_h,
                                'estimated_size': size,
                                'ffmpeg_out_args': {'c:v': 'libwebp', 'quality': mid}
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
        
        print(f"[WebP_v5] Estimated: Q{best_res['quality']}, scale {int(best_res['scale_factor']*100)}%")
        return best_res
    
    def _fallback_estimate(self, input_path, target_size_bytes, meta, allow_downscale, scales):
        if not allow_downscale:
            print("[WebP_v5] ⚠ Target unreachable, using max compression")
            tmp = get_temp_filename()
            floor_size = 0
            try:
                (ffmpeg.input(input_path).output(tmp, quality=0).run(quiet=True, overwrite_output=True))
                if os.path.exists(tmp): floor_size = os.path.getsize(tmp)
            except: pass
            finally:
                if os.path.exists(tmp): os.remove(tmp)
            return {
                'quality': 0, 'scale_factor': 1.0,
                'resolution_w': meta['width'], 'resolution_h': meta['height'],
                'estimated_size': floor_size,
                'ffmpeg_out_args': {'c:v': 'libwebp', 'quality': 0}
            }
        else:
            print("[WebP_v5] ⚠ Emergency downscaling")
            current_scale = scales[-1]
            for _ in range(20):
                current_scale *= 0.90
                current_w = max(1, int(meta['width'] * current_scale))
                current_h = max(1, int(meta['height'] * current_scale))
                tmp = get_temp_filename()
                try:
                    (ffmpeg.input(input_path).filter('scale', current_w, current_h)
                     .output(tmp, quality=5).run(quiet=True, overwrite_output=True))
                    size = os.path.getsize(tmp)
                    if size < target_size_bytes or current_w < 16:
                        if os.path.exists(tmp): os.remove(tmp)
                        return {
                            'quality': 5, 'scale_factor': current_scale,
                            'resolution_w': current_w, 'resolution_h': current_h,
                            'estimated_size': size,
                            'ffmpeg_out_args': {'c:v': 'libwebp', 'quality': 5}
                        }
                except: pass
                finally:
                    if os.path.exists(tmp): os.remove(tmp)
            return {'quality': 0, 'scale_factor': 0.1, 'resolution_w': 16, 'resolution_h': 16,
                    'estimated_size': 0, 'ffmpeg_out_args': {'c:v': 'libwebp', 'quality': 0}}
    
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
            emit(f"WebP Q{params['quality']}, scale {int(params['scale_factor']*100)}%")
            
            stream = ffmpeg.input(input_path)
            
            # Get user override dimensions
            override_w = options.get('override_width')
            override_h = options.get('override_height')
            
            # Apply scale if: user provided override OR auto-resize reduced size
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
            
            # Use compile + subprocess like video estimators for proper FFmpeg binary selection
            cmd = ffmpeg.compile(stream)
            
            # Replace cmd[0] with actual FFMPEG_BINARY path (ffmpeg.compile returns just 'ffmpeg')
            ffmpeg_bin = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
            if ffmpeg_bin and os.path.exists(ffmpeg_bin):
                cmd = [ffmpeg_bin] + list(cmd[1:])
            
            print(f"[WebP_v5 DEBUG] Using FFmpeg: {cmd[0]}")
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode != 0:
                stderr_output = result.stderr.decode('utf-8') if result.stderr else 'No stderr'
                print(f"[WebP_v5 FFMPEG ERROR] {stderr_output}")
                emit(f"FFmpeg error (code {result.returncode})")
                return False
            
            if os.path.exists(output_path):
                actual_kb = os.path.getsize(output_path) / 1024
                emit(f"✓ Complete: {actual_kb:.1f} KB")
                return True
            emit("✗ Output file not created")
            return False
        except Exception as e:
            import traceback
            emit(f"Error: {str(e)}")
            print(f"[WebP_v5 ERROR] {traceback.format_exc()}")
            return False


_estimator = Estimator()

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
