"""
Size Estimator Registry - Unified API for Size Estimation Algorithms

This registry provides version switching capability for size estimation algorithms.
Currently only v2 is active. The version switching is kept for future development.

Note: Max Size mode is now handled by the TargetSizeConversionEngine from target_size module.
This registry is primarily for version management and backward compatibility.

Usage:
    from client.core.size_estimator_registry import (
        set_estimator_version,
        get_estimator_version
    )
"""

from typing import Callable

# =============================================================================
# VERSION STATE
# =============================================================================

_active_estimator_version = 'v2'  # Default to v2 (deterministic)
_version_change_callbacks = []  # Callbacks to notify on version change

def get_estimator_version() -> str:
    """Get the currently active estimator version."""
    return _active_estimator_version

def set_estimator_version(version: str) -> bool:
    """
    Set the active estimator version and reload estimators.
    
    Args:
        version: Version identifier (e.g., 'v2', 'v3')
    
    Returns:
        True if version was changed successfully
    """
    global _active_estimator_version, _active_functions
    
    # Validate version format
    if not version.startswith('v'):
        print(f"[SizeEstimatorRegistry] Invalid version format: {version}")
        return False
    
    old_version = _active_estimator_version
    _active_estimator_version = version
    
    # Force reload of estimators for new version
    _active_functions = {}
    
    if old_version != version:
        print(f"[SizeEstimatorRegistry] Switched from {old_version} to {version}")
        
        # Try to load the new version immediately to validate it exists
        try:
            _load_active_estimators(version)
        except Exception as e:
            print(f"[SizeEstimatorRegistry] Failed to load {version}: {e}")
            # Revert to old version
            _active_estimator_version = old_version
            _active_functions = {}
            return False
        
        # Notify callbacks
        for callback in _version_change_callbacks:
            try:
                callback(version)
            except Exception as e:
                print(f"[SizeEstimatorRegistry] Callback error: {e}")
    
    return True

def register_version_change_callback(callback: Callable[[str], None]):
    """Register a callback to be notified when version changes."""
    if callback not in _version_change_callbacks:
        _version_change_callbacks.append(callback)

def unregister_version_change_callback(callback: Callable[[str], None]):
    """Unregister a version change callback."""
    if callback in _version_change_callbacks:
        _version_change_callbacks.remove(callback)

# =============================================================================
# AVAILABLE VERSIONS
# =============================================================================

AVAILABLE_VERSIONS = {
    'v2': 'Deterministic 2-Pass (Active)'
}

def get_available_versions(type_prefix: str) -> list:
    """
    Discover available estimator versions for a given type by scanning the filesystem.
    
    Args:
        type_prefix: Type prefix ('video', 'image', 'loop')
        
    Returns:
        List of tuples: [(display_name, version_key), ...]
        Example: [('video_estimator_v2.py', 'v2')]
    """
    import os
    import re
    from pathlib import Path
    
    versions = []
    
    try:
        # Get the target_size directory path (current directory since we are in it now)
        target_size_dir = Path(__file__).parent
        
        if not target_size_dir.exists():
            print(f"[SizeEstimatorRegistry] target_size directory not found: {target_size_dir}")
            return versions
        
        # Pattern to match: {type_prefix}_estimator_v{version}.py
        pattern = re.compile(rf'^{type_prefix}_estimator_v(\d+)\.py$')
        
        # Scan directory for matching files
        for file in os.listdir(target_size_dir):
            match = pattern.match(file)
            if match:
                version_num = match.group(1)
                version_key = f'v{version_num}'
                display_name = file  # Show the actual filename
                versions.append((display_name, version_key))
        
        # Sort by version number
        versions.sort(key=lambda x: int(x[1][1:]))  # Sort by numeric part of version
        
    except Exception as e:
        print(f"[SizeEstimatorRegistry] Error discovering versions for {type_prefix}: {e}")
    
    return versions


# =============================================================================
# DYNAMIC VERSION LOADING
# =============================================================================

_active_functions = {}

def _load_active_estimators(version: str = None):
    """
    Dynamically load estimator functions for the specified version.
    
    Args:
        version: Version to load (e.g., 'v2'). If None, uses current active version.
    """
    global _active_functions
    
    if version is None:
        version = _active_estimator_version
    
    # Check if already loaded
    if _active_functions.get('_loaded_version') == version:
        return _active_functions
    
    try:
        import importlib
        
        # Dynamically import estimator modules
        video_module = importlib.import_module(f"client.core.target_size.video_estimator_{version}")
        image_module = importlib.import_module(f"client.core.target_size.image_estimator_{version}")
        loop_module = importlib.import_module(f"client.core.target_size.loop_estimator_{version}")
        
        _active_functions = {
            'video': video_module.optimize_video_params,
            'image': image_module.optimize_image_params,
            'gif': loop_module.optimize_gif_params,
            '_loaded_version': version
        }
        
        print(f"[SizeEstimatorRegistry] Loaded estimators for {version}")
        
    except ImportError as e:
        print(f"[SizeEstimatorRegistry] Failed to load {version}: {e}")
        # Try fallback to v2
        if version != 'v2':
            print(f"[SizeEstimatorRegistry] Falling back to v2")
            return _load_active_estimators('v2')
        _active_functions = {}
    
    return _active_functions

# =============================================================================
# PUBLIC API FUNCTIONS
# =============================================================================

def optimize_video_params(file_path: str, target_size_bytes: int, 
                          codec_pref: str = 'H.264 (MP4)', 
                          allow_downscale: bool = False):
    """
    Calculate optimal video encoding parameters for target file size.
    Uses the currently active estimator version.
    
    Args:
        file_path: Path to input video
        target_size_bytes: Target output size in bytes
        codec_pref: Preferred codec
        allow_downscale: Whether to allow resolution downscaling
        
    Returns:
        Dict with video_bitrate_kbps, audio_bitrate_kbps, resolution_scale, etc.
    """
    funcs = _load_active_estimators()
    if 'video' in funcs:
        return funcs['video'](file_path, target_size_bytes, codec_pref, allow_downscale)
    return {}

def optimize_image_params(file_path: str, output_format: str, target_size_bytes: int,
                          allow_downscale: bool = False):
    """
    Calculate optimal image parameters for target file size.
    Uses the currently active estimator version.
    
    Args:
        file_path: Path to input image
        output_format: Output format (e.g., 'jpg', 'webp')
        target_size_bytes: Target output size in bytes
        allow_downscale: Whether to allow resolution downscaling
        
    Returns:
        Dict with quality, scale_factor, etc.
    """
    funcs = _load_active_estimators()
    if 'image' in funcs:
        return funcs['image'](file_path, output_format, target_size_bytes, allow_downscale)
    return {}

def optimize_gif_params(file_path: str, target_size_bytes: int,
                       allow_downscale: bool = False):
    """
    Calculate optimal GIF parameters for target file size.
    Uses the currently active estimator version.
    
    Args:
        file_path: Path to input video
        target_size_bytes: Target output size in bytes
        allow_downscale: Whether to allow resolution downscaling
        
    Returns:
        Dict with fps, colors, dither, resolution_scale, etc.
    """
    funcs = _load_active_estimators()
    if 'gif' in funcs:
        return funcs['gif'](file_path, target_size_bytes, allow_downscale)
    return {}

# =============================================================================
# LEGACY COMPATIBILITY (for old ConversionEngine)
# =============================================================================

def find_optimal_image_params_for_size(file_path: str, output_format: str, target_size_bytes: int,
                                       status_callback=None, auto_resize: bool = False):
    """
    Legacy wrapper for optimize_image_params.
    Kept for backward compatibility with ConversionEngine.
    """
    return optimize_image_params(file_path, output_format, target_size_bytes, auto_resize)

# =============================================================================
# MODULE __getattr__ FOR DYNAMIC EXPORTS
# =============================================================================

def __getattr__(name: str):
    """
    Dynamic attribute access for backward compatibility.
    Raises AttributeError for unknown attributes.
    """
    # Check if it's a function we support
    if name in ('find_optimal_gif_params', 'find_optimal_image_params', 'find_optimal_video_params',
                'find_optimal_gif_params_for_size', 'find_optimal_image_params_for_size', 
                'find_optimal_video_params_for_size'):
        return globals()[name]
    
    raise AttributeError(f"module 'size_estimator_registry' has no attribute '{name}'")
