"""
Tool-specific validation functions

These functions are assigned to ToolDescriptor.validate_capabilities
for tools that need advanced validation beyond version checking.
"""
import os
import subprocess
from typing import Tuple, List


def validate_ffmpeg_codecs(ffmpeg_path: str, timeout: int = 5) -> Tuple[bool, str, List[str]]:
    """
    Validate if FFmpeg has all required codecs for the application.
    
    Required codecs:
    - Video: libx264, libx265, libvpx-vp9, libsvtav1
    - Audio: aac, libopus
    
    Args:
        ffmpeg_path: Path to the ffmpeg executable
        timeout: Timeout in seconds for the validation command
        
    Returns:
        Tuple of (has_all_codecs, error_message, missing_codecs)
    """
    required_codecs = {
        'libx264': 'video',
        'libx265': 'video',
        'libvpx-vp9': 'video',
        'libsvtav1': 'video',
        'aac': 'audio',
        'libopus': 'audio'
    }
    
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        result = subprocess.run(
            [ffmpeg_path, '-codecs'],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags
        )
        
        if result.returncode != 0:
            return False, "Failed to query codecs", list(required_codecs.keys())
        
        codec_output = result.stdout.lower()
        missing_codecs = []
        
        for codec_name in required_codecs.keys():
            if codec_name.lower() not in codec_output:
                missing_codecs.append(codec_name)
        
        if missing_codecs:
            return False, f"Missing codecs: {', '.join(missing_codecs)}", missing_codecs
        
        return True, "", []
        
    except subprocess.TimeoutExpired:
        return False, f"Codec check timed out after {timeout}s", list(required_codecs.keys())
    except Exception as e:
        return False, f"Codec validation error: {e}", list(required_codecs.keys())


def validate_imagemagick(magick_path: str, timeout: int = 5) -> Tuple[bool, str, List[str]]:
    """
    Validate ImageMagick installation.
    
    Args:
        magick_path: Path to the ImageMagick executable (magick or convert)
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (is_valid, error_message, missing_features)
    """
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        result = subprocess.run(
            [magick_path, '-version'],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags
        )
        
        if result.returncode != 0:
            return False, "ImageMagick version check failed", []
        
        if 'imagemagick' not in result.stdout.lower():
            return False, "Not a valid ImageMagick executable", []
        
        return True, "", []
        
    except subprocess.TimeoutExpired:
        return False, f"Validation timed out after {timeout}s", []
    except Exception as e:
        return False, f"Validation error: {e}", []
