"""
Target Size Module - Common utilities shared across estimators.
"""
import os
import tempfile
import ffmpeg
from typing import Dict


def get_ffmpeg_binary() -> str:
    """
    Get the configured FFmpeg binary path.
    
    Returns the path from FFMPEG_BINARY environment variable if set,
    otherwise falls back to 'ffmpeg' (system PATH).
    """
    return os.environ.get('FFMPEG_BINARY', 'ffmpeg')


def get_ffprobe_binary() -> str:
    """
    Get the configured FFprobe binary path.
    
    Derives ffprobe path from FFMPEG_BINARY by replacing 'ffmpeg' with 'ffprobe'.
    Falls back to 'ffprobe' (system PATH) if not found.
    """
    ffmpeg_path = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
    
    # If using custom ffmpeg, try to derive ffprobe path
    if ffmpeg_path != 'ffmpeg':
        # Replace 'ffmpeg' with 'ffprobe' in the path
        ffprobe_path = ffmpeg_path.replace('ffmpeg', 'ffprobe')
        if os.path.exists(ffprobe_path):
            return ffprobe_path
    
    # Fallback to system ffprobe
    return 'ffprobe'


def get_media_metadata(file_path: str) -> Dict:
    """Extract media metadata using ffprobe."""
    try:
        ffprobe_bin = get_ffprobe_binary()
        probe = ffmpeg.probe(file_path, cmd=ffprobe_bin)
        video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        audio = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
        fmt = probe['format']
        duration = float(fmt.get('duration', 0))
        if duration == 0 and video:
            duration = float(video.get('duration', 0))
        width = int(video.get('width', 0)) if video else 0
        height = int(video.get('height', 0)) if video else 0
        fps = 30.0
        if video and 'r_frame_rate' in video:
            fps_str = video['r_frame_rate']
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                if den > 0:
                    fps = num / den
            else:
                fps = float(fps_str)
        return {
            'duration': duration,
            'width': width,
            'height': height,
            'fps': fps,
            'has_audio': audio is not None
        }
    except:
        return {
            'duration': 0,
            'width': 0,
            'height': 0,
            'fps': 30,
            'has_audio': False
        }


def get_temp_filename(extension: str) -> str:
    """Generate a temporary filename with the given extension."""
    f = tempfile.NamedTemporaryFile(suffix=f'.{extension}', delete=False)
    f.close()
    return f.name
