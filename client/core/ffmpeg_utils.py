"""
FFmpeg Utility Functions
Shared helper functions for media analysis and manipulation.
"""
import ffmpeg
import os


def get_selected_ffmpeg_path() -> str:
    """
    Get FFmpeg path - backward compatibility wrapper
    
    Delegates to tool_registry as single source of truth.
    Respects user selection from Advanced Settings.
    
    Returns:
        Absolute path to FFmpeg binary
    """
    from client.core.tool_registry import get_ffmpeg_path
    return get_ffmpeg_path()


def get_selected_ffprobe_path() -> str:
    """
    Get FFprobe path - backward compatibility wrapper
    
    Delegates to tool_registry as single source of truth.
    
    Returns:
        Absolute path to FFprobe binary
    """
    from client.core.tool_registry import get_ffprobe_path
    return get_ffprobe_path()


def probe_hidden(file_path: str, cmd: str = None) -> dict:
    """Run ffprobe with CREATE_NO_WINDOW. Returns parsed JSON like ffmpeg.probe()."""
    import subprocess
    import sys
    import json
    from client.core.tool_registry import get_ffprobe_path
    ffprobe_bin = cmd or get_ffprobe_path()
    args = [ffprobe_bin, '-v', 'quiet', '-print_format', 'json',
            '-show_streams', '-show_format', file_path]
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    startupinfo = None
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=creationflags, startupinfo=startupinfo)
    return json.loads(result.stdout)


def run_ffmpeg_hidden(stream, cmd='ffmpeg', quiet=False):
    """
    Run an ffmpeg-python stream with CREATE_NO_WINDOW on Windows.
    Drop-in replacement for ffmpeg.run() that prevents console popups.
    Returns (stdout, stderr) bytes.
    """
    import subprocess
    import sys
    args = ffmpeg.compile(stream, cmd=cmd)

    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    startupinfo = None
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
        startupinfo=startupinfo
    )
    if result.returncode != 0 and not quiet:
        raise ffmpeg.Error('ffmpeg', result.stdout, result.stderr)
    return result.stdout, result.stderr


def map_ui_quality_to_crf(ui_quality: int, codec: str = 'generic') -> int:
    """
    Map UI quality value (0-100) to CRF value.
    Higher UI quality = Lower CRF (Better).
    
    Ranges:
    - x264/x265: 0-51 (0 is lossless, 51 is worst)
    - VP9/AV1: 0-63 (0 is lossless, 63 is worst)
    """
    # Determine max CRF based on codec
    if 'libx264' in codec or 'libx265' in codec:
        max_crf = 51
    elif 'vp9' in codec or 'av1' in codec or 'libvpx' in codec or 'libaom' in codec:
        max_crf = 63
    else:
        max_crf = 51 # Default safe limit

    # Invert: UI 100 -> CRF 0, UI 0 -> max_crf
    # Ensure ui_quality is clamped 0-100
    ui_quality = max(0, min(100, int(ui_quality)))
    return int((100 - ui_quality) * (max_crf / 100.0))

def get_image_dimensions(file_path: str) -> tuple:
    """
    Get image dimensions using FFmpeg probe, accounting for EXIF rotation
    Returns (width, height) after applying rotation, or (0, 0) if unable to determine
    """
    try:
        probe = probe_hidden(file_path)
        # Try video stream first (for images, they're treated as single-frame videos)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream:
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            
            # Check for EXIF rotation (side_data_list or tags.rotate)
            rotation = 0
            
            # Method 1: Check side_data_list for displaymatrix rotation
            if 'side_data_list' in video_stream:
                for side_data in video_stream['side_data_list']:
                    if side_data.get('side_data_type') == 'Display Matrix':
                        rotation = side_data.get('rotation', 0)
                        break
            
            # Method 2: Check tags.rotate
            if rotation == 0 and 'tags' in video_stream:
                rotation = int(video_stream['tags'].get('rotate', 0))
            
            # Swap dimensions if rotation is 90 or 270 degrees
            if abs(rotation) == 90 or abs(rotation) == 270:
                return (height, width)  # Swap for portrait orientation
            
            return (width, height)
    except Exception:
        pass
    return (0, 0)

def get_video_dimensions(file_path: str) -> tuple:
    """
    Get video dimensions using FFmpeg
    Returns (width, height) or (0, 0) if unable to determine
    """
    try:
        probe = probe_hidden(file_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream:
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            return (width, height)
    except Exception:
        pass
    return (0, 0)

def get_video_duration(file_path: str) -> float:
    """
    Get video duration in seconds using FFmpeg probe
    Returns duration in seconds or 0.0 if unable to determine
    """
    try:
        probe = probe_hidden(file_path)
        duration = float(probe['format']['duration'])
        return duration
    except Exception:
        return 0.0

def has_audio_stream(file_path: str) -> bool:
    """
    Check if video file has an audio stream using FFmpeg probe
    Returns True if audio stream exists, False otherwise
    """
    try:
        probe = probe_hidden(file_path)
        audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
        return audio_stream is not None
    except Exception:
        return False


# Import dimension calculation functions from centralized module
from client.core.dimension_utils import (
    clamp_resize_width,
    calculate_longer_edge_resize,
    calculate_percent_resize,
    calculate_width_resize
)



def mkdir(path: str) -> None:
    """
    Recursively create directories using os.mkdir() for each missing level
    """
    if not path or os.path.exists(path):
        return

    # Create parent directories first
    parent = os.path.dirname(path)
    if parent and parent != path:  # Avoid infinite recursion
        mkdir(parent)

    # Create this directory level
    try:
        os.mkdir(path)
    except FileExistsError:
        # Directory already exists, which is fine
        pass

def ensure_output_directory_exists(output_path: str) -> bool:
    """
    Ensure the output directory exists, creating it if necessary
    Returns True if directory exists/was created, False on error
    """
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            mkdir(output_dir)
        return True
    except Exception as e:
        print(f"Failed to create output directory for {output_path}: {e}")
        return False
