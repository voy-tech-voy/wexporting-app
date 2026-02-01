"""
Image Size Estimator - Binary search for optimal quality settings.
"""
import os
import ffmpeg
from typing import Dict
from ._common import get_media_metadata, get_temp_filename


def optimize_image_params(
    file_path: str,
    output_format: str,
    target_size_bytes: int,
    allow_downscale: bool = False
) -> Dict:
    """
    Find optimal image quality and scale for target file size.
    
    Args:
        file_path: Path to input image
        output_format: Output format (jpg, png, webp)
        target_size_bytes: Target output size in bytes
        allow_downscale: Whether to allow resolution downscaling
        
    Returns:
        Dict with quality and scale_factor
    """
    meta = get_media_metadata(file_path)
    scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
    best_res = {'quality': 30, 'scale_factor': scales[-1]}
    
    def get_args(q, fmt):
        if 'webp' in fmt:
            return {'quality': q}
        if 'jpg' in fmt:
            return {'qscale:v': int(31 - (q/100)*30)}
        return {'compression_level': 6}

    for scale in scales:
        target_w = int(meta['width'] * scale)
        target_h = int(meta['height'] * scale)
        low, high, valid_q = 1, 100, 0
        
        # Binary search for quality
        for _ in range(6):
            mid = (low + high) // 2
            tmp = get_temp_filename(output_format)
            try:
                (ffmpeg.input(file_path)
                 .filter('scale', target_w, target_h)
                 .output(tmp, **get_args(mid, output_format))
                 .run(quiet=True, overwrite_output=True))
                
                if os.path.getsize(tmp) < target_size_bytes:
                    valid_q = mid
                    best_res = {
                        'quality': mid,
                        'scale_factor': scale,
                        'resolution_w': target_w,
                        'resolution_h': target_h
                    }
                    low = mid + 1
                else:
                    high = mid - 1
            except:
                high = mid - 1
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        
        if valid_q >= 50:
            break
    
    return best_res
