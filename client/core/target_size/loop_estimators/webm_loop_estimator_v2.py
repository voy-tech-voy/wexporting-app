"""
WebM Loop Estimator v2
Optimizes WebM loop videos for target file size using VP9 codec.
Similar to regular video but optimized for short loops.
"""
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

def optimize_gif_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    """
    Optimize WebM loop for target size using VP9 codec.
    
    Args:
        file_path: Input video path
        target_size_bytes: Target file size in bytes
        allow_downscale: Allow resolution downscaling if True
    
    Returns:
        Dict with bitrate, resolution, codec, and encoding settings
    """
    print(f"[WebM_Loop_v2] Optimizing for {target_size_bytes} bytes, downscale={allow_downscale}")
    
    meta = get_media_metadata(file_path)
    if meta['duration'] == 0: 
        return {'video_bitrate_kbps': 500, 'audio_bitrate_kbps': 0, 'encoding_mode': '2-pass', 'codec': 'libvpx-vp9'}
    
    # 1. Bitrate Budget (no audio for loops typically)
    total_bits = target_size_bytes * 8 * 0.92
    audio_kbps = 0  # Loops typically don't need audio
    vid_bits = total_bits
    vid_bps = max(vid_bits / meta['duration'], 50000)
    
    # 2. VP9 for WebM loops
    codec = "libvpx-vp9"
    efficiency = 1.4
    
    # 3. Resolution Scaling
    curr_w = meta['width']
    if allow_downscale:
        target_bpp = 0.08 / efficiency
        while (vid_bps / (curr_w * (curr_w * meta['height'] / meta['width']) * meta['fps'])) < target_bpp and curr_w > 480:
            curr_w = int(curr_w * 0.85)
            curr_w -= (curr_w % 2)
    
    print(f"[WebM_Loop_v2] Result: {int(vid_bps/1000)}kbps, {curr_w}x{int(meta['height'] * (curr_w / meta['width'])) & ~1}")
    
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
