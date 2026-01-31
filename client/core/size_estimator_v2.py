"""
Size Estimator V2 (Production Ready)
Implements Deterministic Size Estimation:
1. Video: Bitrate Calculation + BPP-based Resolution Scaling (2-Pass approach).
2. Image: Iterative Binary Search for exact quality fitting.
3. GIF:   Representative Sampling + Preset Search.
"""
import os
import math
import tempfile
import ffmpeg
from typing import Dict, Optional

# --- INTERNAL HELPERS ---
def get_media_metadata(file_path: str) -> dict:
    try:
        probe = ffmpeg.probe(file_path)
        video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        audio = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
        fmt = probe['format']
        duration = float(fmt.get('duration', 0))
        if duration == 0 and video: duration = float(video.get('duration', 0))
        width = int(video.get('width', 0))
        height = int(video.get('height', 0))
        fps = 30.0
        if video and 'r_frame_rate' in video:
            fps_str = video['r_frame_rate']
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                if den > 0: fps = num / den
            else: fps = float(fps_str)
        return {'duration': duration, 'width': width, 'height': height, 'fps': fps, 'has_audio': audio is not None}
    except: return {'duration': 0, 'width': 0, 'height': 0, 'fps': 30, 'has_audio': False}

def get_temp_filename(extension: str) -> str:
    f = tempfile.NamedTemporaryFile(suffix=f'.{extension}', delete=False)
    f.close(); return f.name

# --- GIF LOGIC ---
GIF_PRESETS = [
    (25, 256, "floyd_steinberg", 1.0), (20, 256, "bayer:bayer_scale=3", 1.0),
    (15, 128, "bayer:bayer_scale=2", 1.0), (15, 128, "bayer:bayer_scale=2", 0.85),
    (12, 64, "bayer:bayer_scale=1", 0.85), (10, 64, "none", 0.70), (8, 32, "none", 0.50),
]
def optimize_gif_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False) -> dict:
    meta = get_media_metadata(file_path)
    if meta['duration'] == 0: return {'fps': 15, 'colors': 128, 'resolution_scale': 1.0}
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

# --- IMAGE LOGIC ---
def optimize_image_params(file_path: str, output_format: str, target_size_bytes: int, allow_downscale: bool = False) -> dict:
    meta = get_media_metadata(file_path)
    scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
    best_res = {'quality': 30, 'scale_factor': scales[-1]}
    
    def get_args(q, fmt):
        if 'webp' in fmt: return {'quality': q}
        if 'jpg' in fmt: return {'qscale:v': int(31 - (q/100)*30)}
        return {'compression_level': 6}

    for scale in scales:
        target_w, target_h = int(meta['width'] * scale), int(meta['height'] * scale)
        low, high, valid_q = 1, 100, 0
        for _ in range(6): # Binary search
            mid = (low + high) // 2
            tmp = get_temp_filename(output_format)
            try:
                (ffmpeg.input(file_path).filter('scale', target_w, target_h)
                 .output(tmp, **get_args(mid, output_format)).run(quiet=True, overwrite_output=True))
                if os.path.getsize(tmp) < target_size_bytes:
                    valid_q = mid; best_res = {'quality': mid, 'scale_factor': scale}; low = mid + 1
                else: high = mid - 1
            except: high = mid - 1
            finally: 
                if os.path.exists(tmp): os.remove(tmp)
        if valid_q >= 50: break
    return best_res

# --- VIDEO LOGIC (2-PASS) ---
def optimize_video_params(file_path: str, target_size_bytes: int, codec_pref: str = 'H.264 (MP4)', allow_downscale: bool = False) -> dict:
    meta = get_media_metadata(file_path)
    if meta['duration'] == 0: return {'video_bitrate_kbps': 1000, 'encoding_mode': '2-pass'}
    
    total_bits = target_size_bytes * 8 * 0.92
    audio_kbps = 64 if target_size_bytes < 5*1024*1024 else 128
    vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'] if meta['has_audio'] else 0)
    
    if vid_bits < total_bits * 0.5: # Audio safeguard
        audio_kbps = 32; vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'])
        
    vid_bps = max(vid_bits / meta['duration'], 50000)
    
    # Codec Selection
    codec = "libx264"
    efficiency = 1.0
    c_pref = codec_pref.lower()
    if "av1" in c_pref: codec, efficiency = "libaom-av1", 1.8
    elif "vp9" in c_pref: codec, efficiency = "libvpx-vp9", 1.4
    elif "265" in c_pref: codec, efficiency = "libx265", 1.5
    
    if vid_bps < 300000 and "auto" in c_pref: codec, efficiency = "libaom-av1", 1.8
    
    # BPP Resolution Scaling
    curr_w = meta['width']
    if allow_downscale:
        target_bpp = 0.08 / efficiency
        while (vid_bps / (curr_w * (curr_w * meta['height'] / meta['width']) * meta['fps'])) < target_bpp and curr_w > 240:
            curr_w = int(curr_w * 0.85); curr_w -= (curr_w % 2)

    # Calculate actual estimated output size based on bitrates and duration
    video_size_bytes = (vid_bps * meta['duration']) / 8
    audio_size_bytes = ((audio_kbps * 1000) * meta['duration']) / 8 if meta['has_audio'] else 0
    total_estimated_bytes = int(video_size_bytes + audio_size_bytes)
    
    return {
        'video_bitrate_kbps': int(vid_bps / 1000),
        'audio_bitrate_kbps': audio_kbps,
        'resolution_scale': curr_w / meta['width'],
        'estimated_size': total_estimated_bytes,
        'codec': codec,
        'encoding_mode': '2-pass', 
        'crf': None
    }