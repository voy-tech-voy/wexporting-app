"""
Loop/GIF Size Estimator - Preset-based optimization.
"""
import os
import ffmpeg
from typing import Dict
from ._common import get_media_metadata, get_temp_filename


# GIF quality presets (fps, colors, dither, scale)
GIF_PRESETS = [
    (25, 256, "floyd_steinberg", 1.0),
    (20, 256, "bayer:bayer_scale=3", 1.0),
    (15, 128, "bayer:bayer_scale=2", 1.0),
    (15, 128, "bayer:bayer_scale=2", 0.85),
    (12, 64, "bayer:bayer_scale=1", 0.85),
    (10, 64, "none", 0.70),
    (8, 32, "none", 0.50),
]


def optimize_gif_params(
    file_path: str,
    target_size_bytes: int,
    allow_downscale: bool = False
) -> Dict:
    """
    Find optimal GIF parameters using preset search.
    
    Args:
        file_path: Path to input video
        target_size_bytes: Target output size in bytes
        allow_downscale: Whether to allow resolution downscaling
        
    Returns:
        Dict with fps, colors, dither, resolution_scale
    """
    meta = get_media_metadata(file_path)
    if meta['duration'] == 0:
        return {
            'fps': 15,
            'colors': 128,
            'resolution_scale': 1.0,
            'resolution_w': meta['width'],
            'resolution_h': meta['height']
        }
    
    # Sample a representative portion
    sample_len = min(2.0, meta['duration'])
    start = min(meta['duration'] * 0.2, meta['duration'] - sample_len)
    mult = (meta['duration'] / sample_len) * 1.1
    
    # Filter presets based on downscale permission
    valid = [p for p in GIF_PRESETS if allow_downscale or p[3] == 1.0]
    left, right, best = 0, len(valid) - 1, len(valid) - 1
    
    # Binary search through presets
    while left <= right:
        mid = (left + right) // 2
        fps, colors, dither, scale = valid[mid]
        w = int(meta['width'] * scale)
        h = int(meta['height'] * scale)
        tmp = get_temp_filename('gif')
        
        try:
            # Generate palette and apply
            (ffmpeg.input(file_path, ss=start, t=sample_len)
             .filter('fps', fps)
             .filter('scale', w, h)
             .filter('split')
             .output(tmp, vframes=int(fps*sample_len),
                     filter_complex=f"[0:v]palettegen=max_colors={colors}[p];[0:v][p]paletteuse=dither={dither.split(':')[0] if ':' in dither else dither}")
             .run(quiet=True, overwrite_output=True))
            
            if os.path.exists(tmp) and (os.path.getsize(tmp) * mult) <= target_size_bytes:
                best = mid
                right = mid - 1
            else:
                left = mid + 1
        except:
            left = mid + 1
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    
    p = valid[best]
    output_w = int(meta['width'] * p[3])
    output_h = int(meta['height'] * p[3])
    
    return {
        'fps': p[0],
        'colors': p[1],
        'dither': p[2],
        'resolution_scale': p[3],
        'resolution_w': output_w,
        'resolution_h': output_h
    }
