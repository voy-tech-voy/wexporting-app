"""
Video Size Estimator - Bitrate calculation for target file sizes.
Uses 2-pass encoding approach with BPP-based resolution scaling.
"""
from typing import Dict
from ._common import get_media_metadata


def optimize_video_params(
    file_path: str,
    target_size_bytes: int,
    codec_pref: str = 'H.264 (MP4)',
    allow_downscale: bool = False
) -> Dict:
    """
    Calculate optimal video encoding parameters for target file size.
    
    Args:
        file_path: Path to input video
        target_size_bytes: Target output size in bytes
        codec_pref: Preferred codec (e.g., 'H.264 (MP4)', 'H.265 (MP4)', 'WebM (VP9)')
        allow_downscale: Whether to allow resolution downscaling
        
    Returns:
        Dict with video_bitrate_kbps, audio_bitrate_kbps, resolution_scale, etc.
    """
    meta = get_media_metadata(file_path)
    if meta['duration'] == 0:
        return {
            'video_bitrate_kbps': 1000,
            'audio_bitrate_kbps': 128,
            'encoding_mode': '2-pass',
            'resolution_scale': 1.0,
            'resolution_w': meta['width'],
            'resolution_h': meta['height']
        }
    
    # Calculate bitrate budget
    total_bits = target_size_bytes * 8 * 0.92  # 92% efficiency
    audio_kbps = 64 if target_size_bytes < 5*1024*1024 else 128
    vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'] if meta['has_audio'] else 0)
    
    # Audio safeguard
    if vid_bits < total_bits * 0.5:
        audio_kbps = 32
        vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'])
        
    vid_bps = max(vid_bits / meta['duration'], 50000)
    
    # 2. Select Codec (Strict Mapping)
    # Normalized input to lowercase for safe comparison
    c_pref = codec_pref.lower()
    
    # Defaults
    codec = "libx264"
    efficiency = 1.0

    # A. Explicit Selection (Highest Priority)
    if "av1" in c_pref:
        codec = "libaom-av1"
        efficiency = 1.8
    elif "vp9" in c_pref:
        codec = "libvpx-vp9"
        efficiency = 1.4
    elif "265" in c_pref or "hevc" in c_pref:
        codec = "libx265"
        efficiency = 1.5
    elif "264" in c_pref:
        codec = "libx264"
        efficiency = 1.0
        
    # B. Auto Mode (Only if user selected 'Auto')
    elif "auto" in c_pref:
        # Smart logic: Use AV1 for low bitrates, H.264 for high compatibility
        if vid_bps < 350000: # Below 350kbps
             codec = "libaom-av1"
             efficiency = 1.8
        else:
             codec = "libx264"
             efficiency = 1.0

    # Debug Log to verify selection
    print(f"[Estimator] Input: '{codec_pref}' -> Selected Codec: '{codec}' (Eff: {efficiency})")
    
    # BPP-based resolution scaling
    curr_w = meta['width']
    if allow_downscale:
        target_bpp = 0.08 / efficiency
        while (vid_bps / (curr_w * (curr_w * meta['height'] / meta['width']) * meta['fps'])) < target_bpp and curr_w > 240:
            curr_w = int(curr_w * 0.85)
            curr_w -= (curr_w % 2)  # Ensure even

    # Calculate output resolution
    scale = curr_w / meta['width']
    output_h = int(meta['height'] * scale)
    output_h -= (output_h % 2)  # Ensure even

    # Calculate actual estimated output size
    video_size_bytes = (vid_bps * meta['duration']) / 8
    audio_size_bytes = ((audio_kbps * 1000) * meta['duration']) / 8 if meta['has_audio'] else 0
    total_estimated_bytes = int(video_size_bytes + audio_size_bytes)
    
    return {
        'video_bitrate_kbps': int(vid_bps / 1000),
        'audio_bitrate_kbps': audio_kbps,
        'resolution_scale': scale,
        'resolution_w': curr_w,
        'resolution_h': output_h,
        'estimated_size': total_estimated_bytes,
        'codec': codec,
        'encoding_mode': '2-pass',
        'crf': None
    }
