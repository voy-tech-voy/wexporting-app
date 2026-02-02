"""
WebP Image Estimator v6
Optimizes WebP images for target file size using quality parameter (0-100).

Changes from v5:
- Fixed binary search to find HIGHEST quality under target (was stopping early)
- Fixed FFMPEG_BINARY path handling in estimate() method
- Added proper subprocess execution matching video estimator patterns
- Improved logging for debugging
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
    """WebP quality binary search estimator v6 - improved quality targeting."""
    
    @property
    def version(self) -> str:
        return "v6"
    
    @property
    def description(self) -> str:
        return "WebP binary search quality optimization (improved)"
    
    def get_output_extension(self) -> str:
        return "webp"
    
    def _encode_test(self, input_path: str, output_path: str, width: int, height: int, quality: int) -> Optional[int]:
        """Encode a test image and return file size, or None on failure."""
        cmd_args = [
            '-y',  # Overwrite
            '-i', input_path,
            '-vf', f'scale={width}:{height}',
            '-c:v', 'libwebp',
            '-quality', str(quality),
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
        override_w = options.get('override_width')
        override_h = options.get('override_height')
        print(f"[WebP_v6] Estimating for {target_size_bytes} bytes ({target_size_bytes/1024:.1f} KB), downscale={allow_downscale}")
        
        meta = get_media_metadata(input_path)
        
        # Use user override dimensions if provided
        original_w, original_h = meta['width'], meta['height']
        if override_w and override_h:
            meta['width'] = override_w
            meta['height'] = override_h
        
        scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
        best_res = None
        best_quality = -1
        
        for scale in scales:
            target_w = max(1, int(meta['width'] * scale))
            target_h = max(1, int(meta['height'] * scale))
            # Ensure even dimensions
            target_w = target_w - (target_w % 2) if target_w > 1 else target_w
            target_h = target_h - (target_h % 2) if target_h > 1 else target_h
            
            # Binary search for HIGHEST quality that fits under target
            low, high = 0, 100
            scale_best_quality = -1
            scale_best_size = 0
            
            # More iterations for better precision
            for iteration in range(10):
                mid = (low + high) // 2
                tmp = get_temp_filename()
                
                try:
                    size = self._encode_test(input_path, tmp, target_w, target_h, mid)
                    
                    if size is not None:
                        print(f"[WebP_v6] Scale {int(scale*100)}%, Q{mid}: {size/1024:.1f} KB (target: {target_size_bytes/1024:.1f} KB)")
                        
                        if size <= target_size_bytes:
                            # This quality fits - try higher
                            if mid > scale_best_quality:
                                scale_best_quality = mid
                                scale_best_size = size
                            low = mid + 1
                        else:
                            # Too big - try lower quality
                            high = mid - 1
                    else:
                        # Encoding failed - try lower quality
                        high = mid - 1
                except Exception as e:
                    print(f"[WebP_v6] Encode test failed: {e}")
                    high = mid - 1
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                
                # Early exit if converged
                if low > high:
                    break
            
            # Update best result if this scale found a valid quality
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
            
            # If we found a high quality solution, stop searching lower scales
            if scale_best_quality >= 75:
                print(f"[WebP_v6] Found high quality Q{scale_best_quality} at scale {int(scale*100)}%, stopping search")
                break
        
        if best_res is None:
            best_res = self._fallback_estimate(input_path, target_size_bytes, meta, allow_downscale)
        
        print(f"[WebP_v6] Final: Q{best_res['quality']}, scale {int(best_res['scale_factor']*100)}%, estimated {best_res['estimated_size']/1024:.1f} KB")
        return best_res
    
    def _fallback_estimate(self, input_path, target_size_bytes, meta, allow_downscale):
        """Fallback when target is unreachable with normal quality range."""
        print("[WebP_v6] ⚠ Target unreachable with standard settings")
        
        if allow_downscale:
            # Try progressively smaller sizes with minimum quality
            print("[WebP_v6] Attempting emergency downscaling...")
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
                        print(f"[WebP_v6] Emergency scale found: {int(current_scale*100)}% = {size/1024:.1f} KB")
                        return {
                            'quality': 10,
                            'scale_factor': current_scale,
                            'resolution_w': current_w,
                            'resolution_h': current_h,
                            'estimated_size': size,
                            'original_width': meta['width'],
                            'original_height': meta['height'],
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
        
        # Last resort: use minimum quality at original size
        print("[WebP_v6] Using minimum quality fallback")
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
            'original_width': meta['width'],
            'original_height': meta['height'],
            'ffmpeg_out_args': {'c:v': 'libwebp', 'quality': 0}
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
        def emit(msg: str):
            if status_callback:
                status_callback(msg)
        
        def should_stop() -> bool:
            return stop_check() if stop_check else False
        
        try:
            if should_stop():
                emit("Stopped by user")
                return False
            
            params = self.estimate(input_path, target_size_bytes, **options)
            emit(f"WebP Q{params['quality']}, {params['resolution_w']}x{params['resolution_h']}")
            
            if should_stop():
                emit("Stopped by user")
                return False
            
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
                '-c:v', 'libwebp',
                '-quality', str(params['quality']),
                output_path
            ])
            
            emit("Encoding WebP...")
            
            ffmpeg_bin = get_ffmpeg_binary()
            cmd = [ffmpeg_bin] + cmd_args
            
            print(f"[WebP_v6 DEBUG] Command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode != 0:
                stderr_output = result.stderr.decode('utf-8', errors='ignore') if result.stderr else 'No stderr'
                print(f"[WebP_v6 FFMPEG ERROR] {stderr_output}")
                emit(f"FFmpeg error (code {result.returncode})")
                return False
            
            if os.path.exists(output_path):
                actual_kb = os.path.getsize(output_path) / 1024
                target_kb = target_size_bytes / 1024
                emit(f"✓ Complete: {actual_kb:.1f} KB (target: {target_kb:.1f} KB)")
                return True
            
            emit("✗ Output file not created")
            return False
            
        except Exception as e:
            import traceback
            emit(f"Error: {str(e)}")
            print(f"[WebP_v6 ERROR] {traceback.format_exc()}")
            return False


_estimator = Estimator()

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
