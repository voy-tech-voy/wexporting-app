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
    Validate if FFmpeg has required capabilities (encoders/decoders).
    
    Checks for presence of ANY encoder for required codecs:
    - H.264 (libx264, h264_nvenc, h264_qsv, etc.)
    - H.265 (libx265, hevc_nvenc, etc.)
    - VP9 (libvpx-vp9, vp9_qsv, etc.)
    - AV1 (libsvtav1, av1_nvenc, etc.)
    - Audio (aac, libopus)
    
    Args:
        ffmpeg_path: Path to the ffmpeg executable
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (has_all_codecs, error_message, missing_codecs)
    """
    # Map required codec standard -> list of acceptable encoder substrings
    # If ANY encoder in the list is found, the requirement is met.
    required_capabilities = {
        'H.264': ['libx264', 'libopenh264', 'h264_nvenc', 'h264_qsv', 'h264_amf', 'h264_vaapi'],
        'H.265': ['libx265', 'libkvazaar', 'hevc_nvenc', 'hevc_qsv', 'hevc_amf', 'hevc_vaapi'],
        'VP9':   ['libvpx-vp9', 'vp9_qsv', 'vp9_vaapi'],
        'AV1':   ['libsvtav1', 'libaom-av1', 'av1_nvenc', 'av1_qsv', 'av1_amf'],
        'AAC':   ['aac'],
        'Opus':  ['libopus', 'opus']
    }
    
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        
        # We need to set CWD/PATH for DLL-based builds (handled by caller usually, but safe to do here)
        tool_dir = os.path.dirname(os.path.abspath(ffmpeg_path))
        env = os.environ.copy()
        if tool_dir not in env.get('PATH', ''):
            env['PATH'] = tool_dir + os.pathsep + env.get('PATH', '')

        # Check encoders
        result = subprocess.run(
            [ffmpeg_path, '-encoders', '-hide_banner'],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
            cwd=tool_dir,
            env=env
        )
        
        if result.returncode != 0:
            return False, "Failed to query encoders", list(required_capabilities.keys())
        
        output = result.stdout.lower()
        missing_capabilities = []
        
        for cap_name, acceptable_encoders in required_capabilities.items():
            found = False
            for enc in acceptable_encoders:
                # Check for " V..... encoder_name " pattern or just presence
                # Real output: " V..... h264_nvenc NVIDIA NVENC H.264 (codec h264)"
                if f" {enc.lower()} " in output or f" {enc.lower()}\n" in output:
                    found = True
                    break
            
            if not found:
                # Double check with loose matching for some cases
                for enc in acceptable_encoders:
                    if enc in output:
                        found = True
                        break
            
            if not found:
                missing_capabilities.append(cap_name)
        
        if missing_capabilities:
            # If critical codecs are missing, fail
            return False, f"Missing support for: {', '.join(missing_capabilities)}", missing_capabilities
        
        return True, "", []
        
    except subprocess.TimeoutExpired:
        return False, f"Capability check timed out after {timeout}s", list(required_capabilities.keys())
    except Exception as e:
        return False, f"Capability validation error: {e}", list(required_capabilities.keys())


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
