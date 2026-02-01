import ffmpeg
from typing import Dict

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
            parts = video['r_frame_rate'].split('/')
            if len(parts) == 2 and int(parts[1]) > 0: fps = int(parts[0]) / int(parts[1])
            else: fps = float(video['r_frame_rate'])
        return {'duration': duration, 'width': width, 'height': height, 'fps': fps, 'has_audio': audio is not None}
    except: return {'duration': 0, 'width': 0, 'height': 0, 'fps': 30, 'has_audio': False}

def optimize_video_params(file_path: str, target_size_bytes: int, codec_pref: str = 'H.264 (MP4)', allow_downscale: bool = False, **kwargs) -> Dict:
    meta = get_media_metadata(file_path)
    if meta['duration'] == 0: return {'video_bitrate_kbps': 1000, 'encoding_mode': '2-pass'}
    
    # 1. Budget
    total_bits = target_size_bytes * 8 * 0.92
    audio_kbps = 64 if target_size_bytes < 5*1024*1024 else 128
    vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'] if meta['has_audio'] else 0)
    
    if vid_bits < total_bits * 0.5:
        audio_kbps = 32; vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'])
        
    vid_bps = max(vid_bits / meta['duration'], 50000)
    
    # 2. Strict Codec Selection
    c_pref = codec_pref.lower()
    codec = "libx264"
    efficiency = 1.0

    if "av1" in c_pref: codec, efficiency = "libaom-av1", 1.8
    elif "vp9" in c_pref: codec, efficiency = "libvpx-vp9", 1.4
    elif "265" in c_pref or "hevc" in c_pref: codec, efficiency = "libx265", 1.5
    elif "auto" in c_pref:
        if vid_bps < 350000: codec, efficiency = "libaom-av1", 1.8
        else: codec, efficiency = "libx264", 1.0
    
    # 3. Resolution Scaling (BPP)
    curr_w = meta['width']
    if allow_downscale:
        target_bpp = 0.08 / efficiency
        while (vid_bps / (curr_w * (curr_w * meta['height'] / meta['width']) * meta['fps'])) < target_bpp and curr_w > 480:
            curr_w = int(curr_w * 0.85); curr_w -= (curr_w % 2)

    return {
        'video_bitrate_kbps': int(vid_bps / 1000),
        'audio_bitrate_kbps': audio_kbps,
        'resolution_scale': curr_w / meta['width'],
        'resolution_w': curr_w,
        'resolution_h': int(meta['height'] * (curr_w / meta['width'])) & ~1,
        'estimated_size': target_size_bytes,
        'codec': codec,
        'encoding_mode': '2-pass',
        'crf': None
    }
