"""
GIF Estimator v2
Optimizes GIF animations for target file size using palette-based compression.
Uses preset combinations of FPS, colors, dither, and scale.
"""
import os
import tempfile
import ffmpeg
from typing import Dict

def get_temp_filename(ext='gif'): 
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name

def get_media_metadata(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        fmt = probe['format']
        video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        duration = float(fmt.get('duration', 0))
        if duration == 0 and video: duration = float(video.get('duration', 0))
        return {'duration': duration, 'width': int(video['width']), 'height': int(video['height'])}
    except: return {'duration': 0, 'width': 0, 'height': 0}

# GIF Presets: (fps, colors, dither, scale)
# Ordered from highest quality to lowest
GIF_PRESETS = [
    (25, 256, "floyd_steinberg", 1.0),
    (20, 256, "bayer:bayer_scale=3", 1.0),
    (15, 128, "bayer:bayer_scale=2", 1.0),
    (15, 128, "bayer:bayer_scale=2", 0.85),
    (12, 64, "bayer:bayer_scale=1", 0.85),
    (10, 64, "none", 0.70),
    (8, 32, "none", 0.50),
]

def optimize_gif_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    """
    Optimize GIF for target size using binary search on preset combinations.
    
    Args:
        file_path: Input video/image path
        target_size_bytes: Target file size in bytes
        allow_downscale: Allow resolution downscaling if True
    
    Returns:
        Dict with fps, colors, dither, and resolution_scale
    """
    print(f"[GIF_v2] Optimizing for {target_size_bytes} bytes, downscale={allow_downscale}")
    
    meta = get_media_metadata(file_path)
    if meta['duration'] == 0: 
        return {'fps': 15, 'colors': 128, 'dither': 'bayer:bayer_scale=2', 'resolution_scale': 1.0}
    
    # Sample a portion of the video for testing
    sample_len = min(2.0, meta['duration'])
    start = min(meta['duration'] * 0.2, meta['duration'] - sample_len)
    mult = (meta['duration'] / sample_len) * 1.1  # Multiplier to estimate full size
    
    # Filter presets based on downscale permission
    valid = [p for p in GIF_PRESETS if allow_downscale or p[3] == 1.0]
    
    # Binary search for optimal preset
    left, right, best = 0, len(valid) - 1, len(valid) - 1
    
    while left <= right:
        mid = (left + right) // 2
        fps, colors, dither, scale = valid[mid]
        w, h = int(meta['width'] * scale), int(meta['height'] * scale)
        tmp = get_temp_filename()
        
        try:
            # Re-assemble dither string map
            dither_args = {}
            if ':' in dither:
                base, params = dither.split(':', 1)
                dither_args['dither'] = base
                for p in params.split(':'):
                    k, v = p.split('=')
                    dither_args[k] = v
            else:
                dither_args['dither'] = dither

            # Build graph correctly
            in_stream = ffmpeg.input(file_path, ss=start, t=sample_len)
            scaled = (
                in_stream
                .filter('fps', fps)
                .filter('scale', w, h)
            )
            split = scaled.filter('split')
            palette = split[0].filter('palettegen', max_colors=colors)
            
            out = ffmpeg.filter([split[1], palette], 'paletteuse', **dither_args)
            
            out.output(tmp, vframes=int(fps*sample_len)).run(quiet=True, overwrite_output=True)
            
            if os.path.exists(tmp) and (os.path.getsize(tmp) * mult) <= target_size_bytes:
                best = mid
                right = mid - 1  # Try higher quality
            else:
                left = mid + 1  # File too big, reduce quality
        except:
            left = mid + 1
        finally:
            if os.path.exists(tmp): os.remove(tmp)
    
    p = valid[best]
    print(f"[GIF_v2] Result: {p[0]}fps, {p[1]} colors, scale {int(p[3]*100)}%")
    
    return {
        'fps': p[0],
        'colors': p[1],
        'dither': p[2],
        'resolution_scale': p[3]
    }
