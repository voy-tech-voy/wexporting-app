"""
Tool Registry Package

Centralized management for external CLI tools (FFmpeg, ImageMagick, etc.)

Usage:
    from client.core.tool_registry import get_registry, ToolDescriptor
    
    # Get singleton registry
    registry = get_registry()
    
    # Register a tool
    registry.register(ToolDescriptor(
        id="ffmpeg",
        display_name="FFmpeg",
        env_var_name="FFMPEG_BINARY",
        binary_name="ffmpeg.exe",
    ))
    
    # Resolve all tools (call once at startup)
    registry.resolve_all()
    
    # Use in code
    ffmpeg_path = registry.get_tool_path("ffmpeg")
"""
import os
from .descriptor import ToolDescriptor
from .protocol import ToolRegistryProtocol
from .registry import ToolRegistry
from .validators import validate_ffmpeg_codecs


# Singleton instance
_registry: ToolRegistry = None


def get_registry() -> ToolRegistry:
    """Get the global ToolRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_default_tools(_registry)
    return _registry


def get_ffmpeg_path() -> str:
    """
    Get FFmpeg binary path - SINGLE SOURCE OF TRUTH
    
    Resolution order (handled by ToolRegistry):
    1. User-selected path from Advanced Settings
    2. Bundled FFmpeg (if exists)
    3. System FFmpeg (from PATH)
    
    Returns:
        Absolute path to FFmpeg binary
    """
    registry = get_registry()
    
    # Ensure registry is initialized
    if not registry._initialized:
        registry.resolve_all()
    
    path = registry.get_tool_path('ffmpeg')
    if not path:
        raise RuntimeError("FFmpeg not found. Please configure in Advanced Settings.")
    
    return path


def get_ffprobe_path() -> str:
    """
    Get FFprobe binary path - derived from FFmpeg location
    
    Uses companion tool resolution to find FFprobe in same directory as FFmpeg.
    Cross-platform: checks both 'ffprobe.exe' (Windows) and 'ffprobe' (Unix/macOS)
    
    Returns:
        Absolute path to FFprobe binary
    """
    from pathlib import Path
    
    ffmpeg_path = get_ffmpeg_path()
    ffmpeg_dir = Path(ffmpeg_path).parent
    
    # Try platform-specific probe names
    probe_names = ['ffprobe.exe', 'ffprobe'] if os.name == 'nt' else ['ffprobe']
    
    for name in probe_names:
        probe_path = ffmpeg_dir / name
        if probe_path.exists():
            return str(probe_path)
    
    # Fallback: construct expected path
    probe_name = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'
    return str(ffmpeg_dir / probe_name)


def get_imagemagick_path() -> str:
    """
    Get ImageMagick binary path - SINGLE SOURCE OF TRUTH
    
    Resolution order (handled by ToolRegistry):
    1. User-selected path from Advanced Settings
    2. Bundled ImageMagick (if exists)
    3. System ImageMagick (from PATH)
    
    Returns:
        Absolute path to ImageMagick binary
    """
    registry = get_registry()
    
    # Ensure registry is initialized
    if not registry._initialized:
        registry.resolve_all()
    
    path = registry.get_tool_path('magick')
    if not path:
        raise RuntimeError("ImageMagick not found. Please configure in Advanced Settings.")
    
    return path


def _register_default_tools(registry: ToolRegistry) -> None:
    """Register default tools (FFmpeg and ImageMagick)."""
    
    # FFmpeg
    registry.register(ToolDescriptor(
        id="ffmpeg",
        display_name="FFmpeg",
        env_var_name="FFMPEG_BINARY",
        binary_name="ffmpeg.exe" if os.name == 'nt' else "ffmpeg",
        version_args=["-version"],
        version_pattern=r"ffmpeg version (\d+[\.\d]*)",
        validate_capabilities=validate_ffmpeg_codecs,
        required_capabilities=["libx264", "libx265", "libvpx-vp9", "libsvtav1", "aac", "libopus"],
        companions=["ffprobe"],
        is_bundled=True,
        bundle_subpath="tools",
        file_filter="FFmpeg Executable (ffmpeg.exe);;All Files (*.*)" if os.name == 'nt' else "All Files (*)"
    ))
    
    # ImageMagick
    from .validators import validate_imagemagick
    registry.register(ToolDescriptor(
        id="magick",
        display_name="ImageMagick",
        env_var_name="IMAGEMAGICK_BINARY",
        binary_name="magick.exe" if os.name == 'nt' else "magick",
        version_args=["-version"],
        version_pattern=r"Version: ImageMagick ([\d\.\-]+)",
        validate_capabilities=validate_imagemagick,
        required_capabilities=[],  # Basic validation only checks if it's ImageMagick
        companions=[],
        is_bundled=True,
        bundle_subpath="tools",
        file_filter="ImageMagick Executable (magick.exe);;All Files (*.*)" if os.name == 'nt' else "All Files (*)"
    ))


# Exports
__all__ = [
    'ToolDescriptor',
    'ToolRegistryProtocol', 
    'ToolRegistry',
    'get_registry',
    'get_ffmpeg_path',
    'get_ffprobe_path',
    'get_imagemagick_path',
    'validate_ffmpeg_codecs',
]
