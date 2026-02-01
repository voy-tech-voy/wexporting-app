"""
WebP Image Estimator v5
Optimizes WebP images for target file size using quality parameter (0-100).
Direct quality mapping - no conversion needed.
"""
import os
import tempfile
import ffmpeg
from typing import Dict

def get_temp_filename(ext='webp'): 
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name

def get_media_metadata(file_path: str):
    try:
        probe = ffmpeg.probe(file_path)
        video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        return {'width': int(video['width']), 'height': int(video['height'])}
    except: return {'width': 0, 'height': 0}

def optimize_image_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    """
    Optimize WebP image for target size using binary search on quality (0-100).
    
    Args:
        file_path: Input image path
        target_size_bytes: Target file size in bytes
        allow_downscale: Allow resolution downscaling if True
    
    Returns:
        Dict with quality, scale_factor, resolution, estimated_size, and ffmpeg_out_args
    """
    print(f"[WebP_v5] Optimizing for {target_size_bytes} bytes, downscale={allow_downscale}")
    
    meta = get_media_metadata(file_path)
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
            
            try:
                (ffmpeg.input(file_path).filter('scale', target_w, target_h)
                 .output(tmp, quality=mid).run(quiet=True, overwrite_output=True))
                
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
                            'ffmpeg_out_args': {'quality': mid}
                        }
                        low = mid + 1  # Try higher quality
                    else:
                        high = mid - 1  # File too big, reduce quality
                else:
                    high = mid - 1
            except:
                high = mid - 1
            finally:
                if os.path.exists(tmp): os.remove(tmp)
        
        # Stop if we found good quality (>=50)
        if valid_q >= 50: break
    
    # Fallback strategies
    if best_res is None:
        if not allow_downscale:
            # Max compression at native resolution
            print("[WebP_v5] ⚠ Target unreachable, using max compression")
            
            tmp = get_temp_filename()
            floor_size = 0
            try:
                (ffmpeg.input(file_path).output(tmp, quality=0)
                 .run(quiet=True, overwrite_output=True))
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
                'ffmpeg_out_args': {'quality': 0}
            }
        else:
            # Emergency downscaling
            print("[WebP_v5] ⚠ Emergency downscaling")
            current_scale = scales[-1]
            
            for _ in range(20):
                current_scale *= 0.90
                current_w = max(1, int(meta['width'] * current_scale))
                current_h = max(1, int(meta['height'] * current_scale))
                
                tmp = get_temp_filename()
                test_q = 5
                
                try:
                    (ffmpeg.input(file_path).filter('scale', current_w, current_h)
                     .output(tmp, quality=test_q).run(quiet=True, overwrite_output=True))
                    
                    size = os.path.getsize(tmp)
                    if size < target_size_bytes or current_w < 16:
                        best_res = {
                            'quality': test_q,
                            'scale_factor': current_scale,
                            'resolution_w': current_w,
                            'resolution_h': current_h,
                            'estimated_size': size,
                            'ffmpeg_out_args': {'quality': test_q}
                        }
                        if os.path.exists(tmp): os.remove(tmp)
                        break
                except: pass
                finally:
                    if os.path.exists(tmp): os.remove(tmp)
    
    print(f"[WebP_v5] Result: Q{best_res['quality']}, scale {int(best_res['scale_factor']*100)}%")
    return best_res
