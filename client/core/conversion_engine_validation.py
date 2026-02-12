"""
FFmpeg Conversion Engine Validation
Provides validation logic for FFmpeg executables
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def get_bundled_ffmpeg_path():
    """Get the bundled FFmpeg path for production and development"""
    # Import here to avoid circular dependencies
    try:
        from client.core.tool_manager import bundled_tools_dir, _USER_BIN_CACHE
    except ImportError:
        # Fallback if conversion_engine is not available
        bundled_tools_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'tools')
        _USER_BIN_CACHE = None
    
    # For frozen builds (production)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # First try _MEIPASS/tools
        ffmpeg_path = os.path.join(sys._MEIPASS, 'tools', 'ffmpeg.exe')
        
        # If not found and user cache exists, try there
        if not os.path.exists(ffmpeg_path) and _USER_BIN_CACHE:
            ffmpeg_path = os.path.join(_USER_BIN_CACHE, 'ffmpeg.exe')
    else:
        # Development mode - use bundled tools directory
        ffmpeg_path = os.path.join(bundled_tools_dir, 'ffmpeg.exe')
    
    return ffmpeg_path if os.path.exists(ffmpeg_path) else ''


def get_ffprobe_path_from_ffmpeg(ffmpeg_path):
    """Get ffprobe path from ffmpeg directory - cross-platform"""
    if not ffmpeg_path:
        return ''
    
    # Use proper path construction instead of hardcoded .exe
    probe_name = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'
    ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), probe_name)
    return ffprobe_path if os.path.exists(ffprobe_path) else ''


def validate_ffmpeg_executable(ffmpeg_path, timeout=5):
    """
    Validate if the file is a valid ffmpeg executable
    
    Args:
        ffmpeg_path: Path to the ffmpeg executable
        timeout: Timeout in seconds for the validation command
        
    Returns:
        tuple: (is_valid: bool, error_message: str, version_info: str)
    """
    if not ffmpeg_path:
        return False, "No FFmpeg path provided", ""
    
    if not os.path.exists(ffmpeg_path):
        return False, f"File does not exist: {ffmpeg_path}", ""
    
    if not os.path.isfile(ffmpeg_path):
        return False, f"Path is not a file: {ffmpeg_path}", ""
    
    # Check if filename contains 'ffmpeg'
    filename = os.path.basename(ffmpeg_path).lower()
    if 'ffmpeg' not in filename:
        return False, f"Filename does not contain 'ffmpeg': {filename}", ""
    
    # Try to run ffmpeg -version
    try:
        result = subprocess.run(
            [ffmpeg_path, '-version'],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Check if output contains 'ffmpeg version'
        if result.returncode == 0 and 'ffmpeg version' in result.stdout.lower():
            # Extract version info (first line usually contains version)
            version_line = result.stdout.split('\n')[0] if result.stdout else ""
            return True, "", version_line
        else:
            return False, "FFmpeg validation command failed", ""
            
    except subprocess.TimeoutExpired:
        return False, f"FFmpeg validation timed out after {timeout} seconds", ""
    except FileNotFoundError:
        return False, "FFmpeg executable not found or not executable", ""
    except Exception as e:
        return False, f"FFmpeg validation error: {str(e)}", ""


def validate_ffmpeg_codecs(ffmpeg_path, timeout=5):
    """
    Validate if ffmpeg has all required codecs for the application
    
    Required encoders:
    - Video: libx264, libx265, libvpx-vp9, libsvtav1
    - Audio: aac, libopus
    
    Args:
        ffmpeg_path: Path to the ffmpeg executable
        timeout: Timeout in seconds for the validation command
        
    Returns:
        tuple: (has_all_codecs: bool, missing_codecs: list)
    """
    required_encoders = {
        'libx264': 'video',
        'libx265': 'video',
        'libvpx-vp9': 'video',
        'libsvtav1': 'video',
        'aac': 'audio',
        'libopus': 'audio'
    }
    
    try:
        # Use -encoders instead of -codecs to check for encoder implementations
        result = subprocess.run(
            [ffmpeg_path, '-encoders'],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if result.returncode != 0:
            return False, list(required_encoders.keys())
        
        encoder_output = result.stdout.lower()
        missing_codecs = []
        
        for encoder_name in required_encoders.keys():
            # Check if encoder name appears in the output
            if encoder_name.lower() not in encoder_output:
                missing_codecs.append(encoder_name)
        
        return len(missing_codecs) == 0, missing_codecs
        
    except Exception as e:
        print(f"DEBUG: Codec validation error: {e}")
        return False, list(required_encoders.keys())


def validate_system_ffmpeg(timeout=5):
    """
    Validate if system has a valid ffmpeg in PATH with all required codecs
    
    Args:
        timeout: Timeout in seconds for the validation command
        
    Returns:
        tuple: (is_valid: bool, error_message: str, ffmpeg_path: str, version_info: str)
    """
    # Debug: Test ffmpeg command directly
    print("DEBUG: Testing 'ffmpeg -version' command...")
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        print(f"DEBUG: 'ffmpeg -version' return code: {result.returncode}")
        if result.stdout:
            first_line = result.stdout.split('\n')[0] if '\n' in result.stdout else result.stdout.split('\r\n')[0]
            print(f"DEBUG: 'ffmpeg -version' first line: {first_line}")
    except Exception as e:
        print(f"DEBUG: 'ffmpeg -version' command failed: {e}")
    
    # Find all ffmpeg installations using 'where' on Windows or 'which -a' on Unix
    ffmpeg_paths = []
    
    if os.name == 'nt':
        print("DEBUG: Running 'where ffmpeg'...")
        try:
            where_result = subprocess.run(
                ['where', 'ffmpeg'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if where_result.returncode == 0 and where_result.stdout:
                # Split by newlines and filter out empty strings
                paths = [p.strip() for p in where_result.stdout.strip().split('\n') if p.strip()]
                ffmpeg_paths = paths
                print(f"DEBUG: 'where ffmpeg' found {len(paths)} path(s):")
                for i, path in enumerate(paths, 1):
                    print(f"DEBUG:   [{i}] {path}")
            else:
                print(f"DEBUG: 'where ffmpeg' returned no results (code: {where_result.returncode})")
        except Exception as e:
            print(f"DEBUG: 'where ffmpeg' failed: {e}")
    else:
        # Unix-like systems
        try:
            which_result = subprocess.run(
                ['which', '-a', 'ffmpeg'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if which_result.returncode == 0 and which_result.stdout:
                paths = [p.strip() for p in which_result.stdout.strip().split('\n') if p.strip()]
                ffmpeg_paths = paths
                print(f"DEBUG: 'which -a ffmpeg' found {len(paths)} path(s)")
        except Exception:
            pass
    
    # Fallback to shutil.which if no paths found
    if not ffmpeg_paths:
        print("DEBUG: Using shutil.which('ffmpeg') as fallback...")
        system_ffmpeg = shutil.which('ffmpeg')
        if system_ffmpeg:
            ffmpeg_paths = [system_ffmpeg]
            print(f"DEBUG: shutil.which found: {system_ffmpeg}")
        else:
            print("DEBUG: shutil.which('ffmpeg') returned None")
    
    if not ffmpeg_paths:
        print("DEBUG: No ffmpeg found in PATH")
        return False, "FFmpeg not found in system PATH", "", ""
    
    # Test each ffmpeg path
    for idx, ffmpeg_path in enumerate(ffmpeg_paths, 1):
        print(f"\nDEBUG: Testing FFmpeg path [{idx}/{len(ffmpeg_paths)}]: {ffmpeg_path}")
        
        # Validate the executable
        is_valid, error_msg, version_info = validate_ffmpeg_executable(ffmpeg_path, timeout)
        
        if not is_valid:
            print(f"DEBUG: [X] Basic validation failed: {error_msg}")
            continue
        
        print(f"DEBUG: [OK] Basic validation passed: {version_info}")
        
        # Validate codecs
        has_codecs, missing_codecs = validate_ffmpeg_codecs(ffmpeg_path, timeout)
        
        if not has_codecs:
            print(f"DEBUG: [X] Codec validation failed. Missing codecs: {', '.join(missing_codecs)}")
            continue
        
        print(f"DEBUG: [OK] All required codecs present")
        print(f"DEBUG: Selected FFmpeg: {ffmpeg_path}")
        return True, "", ffmpeg_path, version_info
    
    # No valid ffmpeg found
    print("DEBUG: No FFmpeg installation met all requirements")
    return False, "No FFmpeg in PATH has all required codecs (libx264, libx265, libvpx-vp9, libsvtav1, aac, libopus)", "", ""

def get_all_valid_ffmpeg_paths(timeout=5):
    """
    Get all FFmpeg installations found in PATH with their validation status
    
    Args:
        timeout: Timeout in seconds for validation commands
        
    Returns:
        list of tuples: [(path, version_info, has_all_codecs, missing_codecs), ...]
    """
    ffmpeg_paths = []
    
    # Find all ffmpeg installations
    if os.name == 'nt':
        try:
            where_result = subprocess.run(
                ['where', 'ffmpeg'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if where_result.returncode == 0 and where_result.stdout:
                paths = [p.strip() for p in where_result.stdout.strip().split('\n') if p.strip()]
                ffmpeg_paths = paths
        except Exception:
            pass
    else:
        try:
            which_result = subprocess.run(
                ['which', '-a', 'ffmpeg'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if which_result.returncode == 0 and which_result.stdout:
                paths = [p.strip() for p in which_result.stdout.strip().split('\n') if p.strip()]
                ffmpeg_paths = paths
        except Exception:
            pass
    
    # Fallback to shutil.which
    if not ffmpeg_paths:
        system_ffmpeg = shutil.which('ffmpeg')
        if system_ffmpeg:
            ffmpeg_paths = [system_ffmpeg]

    # Also check bundled tools directory for any ffmpeg executables
    try:
        from client.core.tool_manager import bundled_tools_dir
        if os.path.exists(bundled_tools_dir):
            for filename in os.listdir(bundled_tools_dir):
                # Check for files starting with ffmpeg
                if filename.lower().startswith('ffmpeg'):
                    # specific check for windows .exe extension
                    if os.name == 'nt' and not filename.lower().endswith('.exe'):
                        continue
                    
                    full_path = os.path.join(bundled_tools_dir, filename)
                    if os.path.isfile(full_path):
                        # Avoid duplicates
                        if full_path not in ffmpeg_paths:
                            ffmpeg_paths.append(full_path)
    except Exception:
        pass
    
    # Validate each path
    results = []
    for ffmpeg_path in ffmpeg_paths:
        # Basic validation
        is_valid, error_msg, version_info = validate_ffmpeg_executable(ffmpeg_path, timeout)
        
        if not is_valid:
            continue
        
        # Codec validation
        has_codecs, missing_codecs = validate_ffmpeg_codecs(ffmpeg_path, timeout)
        
        results.append((ffmpeg_path, version_info, has_codecs, missing_codecs))
    
    return results


def get_ffmpeg_version_info(ffmpeg_path):
    """
    Get version information from an ffmpeg executable
    
    Args:
        ffmpeg_path: Path to the ffmpeg executable
        
    Returns:
        str: Version information or empty string if failed
    """
    try:
        result = subprocess.run(
            [ffmpeg_path, '-version'],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if result.returncode == 0:
            # Return first line which contains version
            return result.stdout.split('\n')[0] if result.stdout else ""
    except Exception:
        pass
    
    return ""


def apply_ffmpeg_to_environment(ffmpeg_path, mode='custom'):
    """
    Apply FFmpeg path to environment variables
    
    Args:
        ffmpeg_path: Path to the ffmpeg executable
        mode: 'bundled', 'custom', or 'system'
    """
    if mode == 'system':
        # For system mode, if we have a specific path (validated from PATH), use it
        # This is more reliable than relying on PATH at runtime
        if ffmpeg_path and os.path.exists(ffmpeg_path):
            os.environ['FFMPEG_BINARY'] = ffmpeg_path
            
            # Also set ffprobe if in same directory
            ffprobe_path = get_ffprobe_path_from_ffmpeg(ffmpeg_path)
            if ffprobe_path:
                os.environ['FFPROBE_BINARY'] = ffprobe_path
        else:
            # Fallback behavior: remove variables to let subprocess use PATH
            if 'FFMPEG_BINARY' in os.environ:
                del os.environ['FFMPEG_BINARY']
            if 'FFPROBE_BINARY' in os.environ:
                del os.environ['FFPROBE_BINARY']
    else:
        # For bundled or custom mode, set the paths
        if ffmpeg_path and os.path.exists(ffmpeg_path):
            os.environ['FFMPEG_BINARY'] = ffmpeg_path
            
            # Also set ffprobe if in same directory
            ffprobe_path = get_ffprobe_path_from_ffmpeg(ffmpeg_path)
            if ffprobe_path:
                os.environ['FFPROBE_BINARY'] = ffprobe_path


def validate_and_apply_ffmpeg(mode, custom_path=''):
    """
    Validate and apply FFmpeg configuration
    
    Args:
        mode: 'bundled', 'custom', or 'system'
        custom_path: Custom FFmpeg path (only used if mode='custom')
        
    Returns:
        tuple: (success: bool, error_message: str, applied_path: str)
    """
    if mode == 'bundled':
        bundled_path = get_bundled_ffmpeg_path()
        is_valid, error_msg, version_info = validate_ffmpeg_executable(bundled_path)
        
        if is_valid:
            apply_ffmpeg_to_environment(bundled_path, mode='bundled')
            return True, "", bundled_path
        else:
            return False, f"Bundled FFmpeg validation failed: {error_msg}", ""
    
    elif mode == 'custom':
        if not custom_path:
            return False, "No custom path provided", ""
        
        is_valid, error_msg, version_info = validate_ffmpeg_executable(custom_path)
        
        if is_valid:
            apply_ffmpeg_to_environment(custom_path, mode='custom')
            return True, "", custom_path
        else:
            return False, f"Custom FFmpeg validation failed: {error_msg}", ""
    
    elif mode == 'system':
        is_valid, error_msg, system_path, version_info = validate_system_ffmpeg()
        
        if is_valid:
            # Pass the discovered system path to apply_ffmpeg_to_environment
            apply_ffmpeg_to_environment(system_path, mode='system')
            return True, "", system_path
        else:
            return False, f"System FFmpeg validation failed: {error_msg}", ""
    
    else:
        return False, f"Invalid mode: {mode}", ""
