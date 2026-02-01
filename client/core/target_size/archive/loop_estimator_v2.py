import os
import tempfile
import ffmpeg
from typing import Dict

def get_temp_filename(ext): f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False); f.close(); return f.name

def get_media_metadata(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        fmt = probe['format']
        video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        duration = float(fmt.get('duration', 0))
        if duration == 0 and video: duration = float(video.get('duration', 0))
        return {'duration': duration, 'width': int(video['width']), 'height': int(video['height'])}
    except: return {'duration': 0, 'width': 0, 'height': 0}

GIF_PRESETS = [
    (25, 256, "floyd_steinberg", 1.0), (20, 256, "bayer:bayer_scale=3", 1.0),
    (15, 128, "bayer:bayer_scale=2", 1.0), (15, 128, "bayer:bayer_scale=2", 0.85),
    (12, 64, "bayer:bayer_scale=1", 0.85), (10, 64, "none", 0.70), (8, 32, "none", 0.50),
]

def optimize_gif_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    meta = get_media_metadata(file_path)
    if meta['duration'] == 0: return {'fps': 15, 'colors': 128}

    sample_len = min(2.0, meta['duration'])
    start = min(meta['duration'] * 0.2, meta['duration'] - sample_len)
    mult = (meta['duration'] / sample_len) * 1.1
    valid = [p for p in GIF_PRESETS if allow_downscale or p[3] == 1.0]
    
    left, right, best = 0, len(valid) - 1, len(valid) - 1
    
    while left <= right:
        mid = (left + right) // 2
        fps, colors, dither, scale = valid[mid]
        w, h = int(meta['width'] * scale), int(meta['height'] * scale)
        tmp = get_temp_filename('gif')
        try:
            (ffmpeg.input(file_path, ss=start, t=sample_len).filter('fps', fps).filter('scale', w, h).filter('split')
             .output(tmp, vframes=int(fps*sample_len), filter_complex=f"[0:v]palettegen=max_colors={colors}[p];[0:v][p]paletteuse=dither={dither.split(':')[0] if ':' in dither else dither}")
             .run(quiet=True, overwrite_output=True))
            if os.path.exists(tmp) and (os.path.getsize(tmp) * mult) <= target_size_bytes:
                best = mid; right = mid - 1
            else: left = mid + 1
        except: left = mid + 1
        finally: 
            if os.path.exists(tmp): os.remove(tmp)
            
    p = valid[best]
    return {'fps': p[0], 'colors': p[1], 'dither': p[2], 'resolution_scale': p[3]}
