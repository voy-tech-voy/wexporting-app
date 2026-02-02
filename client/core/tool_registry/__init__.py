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


def _register_default_tools(registry: ToolRegistry) -> None:
    """Register default tools (FFmpeg only for now)."""
    
    # FFmpeg
    registry.register(ToolDescriptor(
        id="ffmpeg",
        display_name="FFmpeg",
        env_var_name="FFMPEG_BINARY",
        binary_name="ffmpeg.exe" if os.name == 'nt' else "ffmpeg",
        version_args=["-version"],
        version_pattern=r"ffmpeg version (\d+[\.\d]*)",
        validate_capabilities=validate_ffmpeg_codecs,
        required_capabilities=["libx264", "libx265", "libvpx-vp9", "libaom-av1", "libsvtav1", "aac", "libopus"],
        companions=["ffprobe"],
        is_bundled=True,
        bundle_subpath="tools",
        file_filter="FFmpeg Executable (ffmpeg.exe);;All Files (*.*)" if os.name == 'nt' else "All Files (*)"
    ))
    
    # NOTE: ImageMagick not registered - not needed at this stage


# Exports
__all__ = [
    'ToolDescriptor',
    'ToolRegistryProtocol', 
    'ToolRegistry',
    'get_registry',
    'validate_ffmpeg_codecs',
]
