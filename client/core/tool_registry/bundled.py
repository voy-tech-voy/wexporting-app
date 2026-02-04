"""
Bundled Tool Manager - Handles PyInstaller extraction and path resolution
"""
import os
import sys
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List
from client.version import APP_NAME


def get_bundled_tools_cache_dir() -> str:
    """Get the persistent cache directory for bundled tools."""
    if os.name == 'nt':
        cache_root = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA') or os.path.expanduser('~')
    else:
        cache_root = os.getenv('XDG_CACHE_HOME') or os.path.expanduser('~/.cache')
    
    cache_dir = os.path.join(cache_root, APP_NAME, 'bin')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def is_frozen() -> bool:
    """Check if running as PyInstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_meipass_tools_dir() -> Optional[str]:
    """Get the tools directory from PyInstaller bundle."""
    if is_frozen():
        tools_dir = os.path.join(sys._MEIPASS, 'tools')
        if os.path.isdir(tools_dir):
            return tools_dir
    return None


def get_dev_tools_dir() -> str:
    """Get the tools directory for development mode."""
    # Go up from client/core/tool_registry to project root, then into tools/
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(project_root, 'tools')


def resolve_bundled_tool_path(binary_name: str, bundle_subpath: str = "tools") -> Optional[str]:
    """
    Resolve path to a bundled tool executable.
    
    For frozen builds:
    1. Check persistent cache (extracted from _MEIPASS)
    2. Check _MEIPASS/tools directly
    
    For development:
    1. Check project tools/ directory
    
    Args:
        binary_name: Name of the executable (e.g., "ffmpeg.exe")
        bundle_subpath: Subpath within bundle (default "tools")
        
    Returns:
        Absolute path to executable, or None if not found
    """
    if is_frozen():
        # Try persistent cache first
        cache_dir = get_bundled_tools_cache_dir()
        cached_path = os.path.join(cache_dir, binary_name)
        if os.path.exists(cached_path):
            return cached_path
        
        # Try _MEIPASS directly
        meipass_path = os.path.join(sys._MEIPASS, bundle_subpath, binary_name)
        if os.path.exists(meipass_path):
            return meipass_path
    else:
        # Development mode
        dev_path = os.path.join(get_dev_tools_dir(), binary_name)
        if os.path.exists(dev_path):
            return dev_path
    
    return None


def resolve_system_tool_path(binary_name: str) -> Optional[str]:
    """
    Find tool in system PATH.
    
    Args:
        binary_name: Name of the executable
        
    Returns:
        Absolute path to executable, or None if not found
    """
    return shutil.which(binary_name)


def resolve_all_system_tool_paths(binary_name: str) -> List[str]:
    """
    Find all instances of a tool in system PATH.
    
    Args:
        binary_name: Name of the executable (e.g., "ffmpeg.exe")
        
    Returns:
        List of absolute paths to all found executables
    """
    paths = []
    
    # Extract base name without extension for search
    base_name = binary_name.replace('.exe', '') if binary_name.endswith('.exe') else binary_name
    
    if os.name == 'nt':
        # Windows: use 'where' command
        try:
            result = subprocess.run(
                ['where', base_name],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and result.stdout:
                paths = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
        except Exception:
            pass
    else:
        # Unix: use 'which -a'
        try:
            result = subprocess.run(
                ['which', '-a', base_name],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and result.stdout:
                paths = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
        except Exception:
            pass
    
    # Fallback to shutil.which if nothing found
    if not paths:
        single = shutil.which(binary_name)
        if single:
            paths = [single]
    
    return paths


def resolve_companion_tool_path(primary_path: str, companion_name: str) -> Optional[str]:
    """
    Resolve companion tool path from primary tool's directory.
    
    E.g., find ffprobe.exe in the same directory as ffmpeg.exe
    
    Args:
        primary_path: Path to primary tool
        companion_name: Name of companion executable
        
    Returns:
        Absolute path to companion, or None if not found
    """
    if not primary_path:
        return None
    
    tool_dir = os.path.dirname(primary_path)
    companion_path = os.path.join(tool_dir, companion_name)
    
    if os.path.exists(companion_path):
        return companion_path
    
    return None


def extract_bundled_tools_to_cache() -> str:
    """
    Extract bundled tools from _MEIPASS to persistent cache.
    
    Called once at startup for frozen builds to ensure tools
    are available at stable paths.
    
    Returns:
        Path to cache directory
    """
    if not is_frozen():
        return get_dev_tools_dir()
    
    cache_dir = get_bundled_tools_cache_dir()
    meipass_tools = get_meipass_tools_dir()
    
    if not meipass_tools:
        return cache_dir
    
    # Copy tools to cache if not present or size differs
    for name in os.listdir(meipass_tools):
        src = os.path.join(meipass_tools, name)
        dst = os.path.join(cache_dir, name)
        
        try:
            if not os.path.exists(dst) or os.path.getsize(src) != os.path.getsize(dst):
                # Atomic copy
                tmp = dst + '.tmp'
                with open(src, 'rb') as sf, open(tmp, 'wb') as df:
                    df.write(sf.read())
                try:
                    os.replace(tmp, dst)
                except Exception:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                    shutil.copy2(src, dst)
                
                # Ensure executable on Unix
                if os.name != 'nt':
                    os.chmod(dst, 0o755)
        except Exception as e:
            print(f"Warning: Failed to extract {name}: {e}")
    
    return cache_dir
