"""
Size Estimator Registry - Unified API for Size Estimation Algorithms

This registry provides a single import point for size estimation functions,
allowing runtime switching between algorithm versions (v1, v2, etc.).

Usage:
    from client.core.size_estimator_registry import (
        find_optimal_video_params,
        find_optimal_image_params,
        find_optimal_gif_params,
        set_estimator_version,
        get_estimator_version
    )
"""

from typing import Dict, Optional, Callable

# =============================================================================
# VERSION STATE
# =============================================================================

_current_version = 'v1'  # Default to v1 (preset-based)
_version_change_callbacks = []  # Callbacks to notify on version change

def get_estimator_version() -> str:
    """Get the currently active estimator version."""
    return _current_version

def set_estimator_version(version: str) -> bool:
    """
    Set the active estimator version.
    
    Args:
        version: 'v1' (preset-based) or 'v2' (deterministic/binary-search)
    
    Returns:
        True if version was changed successfully
    """
    global _current_version
    if version not in ('v1', 'v2'):
        print(f"[SizeEstimatorRegistry] Unknown version: {version}. Using 'v1'.")
        return False
    
    old_version = _current_version
    _current_version = version
    
    if old_version != version:
        print(f"[SizeEstimatorRegistry] Switched from {old_version} to {version}")
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
    'v1': 'Preset-Based (Default)',
    'v2': 'Deterministic 2-Pass'
}

# =============================================================================
# V1 IMPORTS (Lazy to avoid circular imports)
# =============================================================================

_v1_cache = {}

def _get_v1_functions():
    """Lazy import v1 functions."""
    global _v1_cache
    if not _v1_cache:
        from client.core.size_estimator_v1 import (
            find_optimal_gif_params_for_size,
            find_optimal_image_params_for_size,
            find_optimal_video_params_for_size,
            # Also export presets and utilities for backward compatibility
            QUALITY_PRESETS_STANDARD,
            QUALITY_PRESETS_AUTORESIZE,
            REFERENCE_PRESET_IDX,
            DITHER_MAP,
            estimate_all_preset_sizes,
            IMAGE_QUALITY_PRESETS_STANDARD,
            IMAGE_QUALITY_PRESETS_AUTORESIZE,
            IMAGE_REFERENCE_PRESET_IDX,
            estimate_all_image_preset_sizes,
            VIDEO_QUALITY_PRESETS_STANDARD,
            VIDEO_QUALITY_PRESETS_AUTORESIZE,
            VIDEO_REFERENCE_PRESET_IDX,
            estimate_all_video_preset_sizes,
            get_video_frame_rate,
            estimate_gif_size_fast_preview,
            estimate_gif_size_heuristic,
        )
        _v1_cache = {
            'gif': find_optimal_gif_params_for_size,
            'image': find_optimal_image_params_for_size,
            'video': find_optimal_video_params_for_size,
            # Presets and utilities
            'QUALITY_PRESETS_STANDARD': QUALITY_PRESETS_STANDARD,
            'QUALITY_PRESETS_AUTORESIZE': QUALITY_PRESETS_AUTORESIZE,
            'REFERENCE_PRESET_IDX': REFERENCE_PRESET_IDX,
            'DITHER_MAP': DITHER_MAP,
            'estimate_all_preset_sizes': estimate_all_preset_sizes,
            'IMAGE_QUALITY_PRESETS_STANDARD': IMAGE_QUALITY_PRESETS_STANDARD,
            'IMAGE_QUALITY_PRESETS_AUTORESIZE': IMAGE_QUALITY_PRESETS_AUTORESIZE,
            'IMAGE_REFERENCE_PRESET_IDX': IMAGE_REFERENCE_PRESET_IDX,
            'estimate_all_image_preset_sizes': estimate_all_image_preset_sizes,
            'VIDEO_QUALITY_PRESETS_STANDARD': VIDEO_QUALITY_PRESETS_STANDARD,
            'VIDEO_QUALITY_PRESETS_AUTORESIZE': VIDEO_QUALITY_PRESETS_AUTORESIZE,
            'VIDEO_REFERENCE_PRESET_IDX': VIDEO_REFERENCE_PRESET_IDX,
            'estimate_all_video_preset_sizes': estimate_all_video_preset_sizes,
            'get_video_frame_rate': get_video_frame_rate,
            'estimate_gif_size_fast_preview': estimate_gif_size_fast_preview,
            'estimate_gif_size_heuristic': estimate_gif_size_heuristic,
        }
    return _v1_cache

# =============================================================================
# V2 IMPORTS AND ADAPTERS
# =============================================================================

_v2_cache = {}

def _get_v2_functions():
    """Lazy import v2 functions with adapters to match v1 signatures."""
    global _v2_cache
    if not _v2_cache:
        try:
            from client.core.size_estimator_v2 import (
                optimize_gif_params,
                optimize_image_params,
                optimize_video_params,
            )
            _v2_cache = {
                'gif_raw': optimize_gif_params,
                'image_raw': optimize_image_params,
                'video_raw': optimize_video_params,
            }
        except ImportError as e:
            print(f"[SizeEstimatorRegistry] v2 not available: {e}")
            _v2_cache = {}
    return _v2_cache

def _adapt_v2_gif(file_path: str, base_params: dict, target_size_bytes: int,
                   status_callback=None, auto_resize: bool = False) -> dict:
    """Adapter to make v2 GIF function match v1 signature."""
    v2 = _get_v2_functions()
    if 'gif_raw' not in v2:
        # Fallback to v1
        return _get_v1_functions()['gif'](file_path, base_params, target_size_bytes, 
                                           status_callback, auto_resize)
    
    if status_callback:
        status_callback("[v2] Starting deterministic GIF optimization...")
    
    result = v2['gif_raw'](file_path, target_size_bytes, allow_downscale=auto_resize)
    
    # Adapt v2 result to v1 format
    adapted = base_params.copy()
    if result:
        adapted['ffmpeg_fps'] = result.get('fps', 15)
        adapted['ffmpeg_colors'] = result.get('colors', 256)
        adapted['ffmpeg_dither'] = result.get('dither', 'bayer:bayer_scale=3')
        if result.get('resolution_scale', 1.0) != 1.0:
            adapted['_resolution_scale'] = result['resolution_scale']
        adapted['_estimated_size'] = result.get('estimated_size', 0)
        adapted['_preset_info'] = f"v2: {result.get('fps')}fps {result.get('colors')}col"
    
    if status_callback:
        status_callback(f"[v2] GIF optimization complete")
    
    return adapted

def _adapt_v2_image(file_path: str, output_format: str, target_size_bytes: int,
                     status_callback=None, auto_resize: bool = False) -> dict:
    """Adapter to make v2 image function match v1 signature."""
    v2 = _get_v2_functions()
    if 'image_raw' not in v2:
        # Fallback to v1
        return _get_v1_functions()['image'](file_path, output_format, target_size_bytes,
                                             status_callback, auto_resize)
    
    if status_callback:
        status_callback("[v2] Starting binary-search image optimization...")
    
    result = v2['image_raw'](file_path, output_format, target_size_bytes, 
                              allow_downscale=auto_resize)
    
    # Adapt v2 result to v1 format
    adapted = {
        'quality': result.get('quality', 80),
        '_estimated_size': result.get('estimated_size', 0),
        '_preset_info': f"v2: Q{result.get('quality')}",
    }
    if result.get('scale_factor', 1.0) != 1.0:
        adapted['_resolution_scale'] = result['scale_factor']
        adapted['_preset_info'] += f" @{int(result['scale_factor']*100)}%"
    
    if status_callback:
        status_callback(f"[v2] Image optimization complete: Q{adapted['quality']}")
    
    return adapted

def _adapt_v2_video(file_path: str, codec: str, base_params: dict, target_size_bytes: int,
                     status_callback=None, auto_resize: bool = False) -> dict:
    """Adapter to make v2 video function match v1 signature."""
    v2 = _get_v2_functions()
    if 'video_raw' not in v2:
        # Fallback to v1
        return _get_v1_functions()['video'](file_path, codec, base_params, target_size_bytes,
                                             status_callback, auto_resize)
    
    if status_callback:
        status_callback("[v2] Starting 2-pass bitrate video optimization...")
    
    result = v2['video_raw'](file_path, target_size_bytes, codec_pref=codec,
                              allow_downscale=auto_resize)
    
    # Adapt v2 result to v1 format
    # v2 returns bitrate-based params, v1 expects CRF-based
    # We'll use the v2 codec suggestion and bitrate mode
    adapted = {
        'crf': result.get('crf', 23),  # Use returned CRF if available (compatibility mode)
        'audio_bitrate': result.get('audio_bitrate_kbps', 128),
        '_video_bitrate_kbps': result.get('video_bitrate_kbps', 1000),
        '_encoding_mode': result.get('encoding_mode', '2-pass'),
        '_codec_suggestion': result.get('codec', codec),
        '_estimated_size': result.get('estimated_size', target_size_bytes),
        '_preset_info': f"v2: {result.get('video_bitrate_kbps')}kbps",
    }
    
    # Resolution scaling
    from client.core.size_estimator_v2 import get_media_metadata
    meta = get_media_metadata(file_path)
    if meta['width'] > 0:
        scale = result.get('resolution_w', meta['width']) / meta['width']
        if scale < 1.0:
            adapted['_resolution_scale'] = scale
            adapted['_preset_info'] += f" @{int(scale*100)}%"
    
    if status_callback:
        status_callback(f"[v2] Video optimization complete: {adapted['_video_bitrate_kbps']}kbps")
    
    return adapted

# =============================================================================
# UNIFIED API FUNCTIONS
# =============================================================================

def find_optimal_gif_params(file_path: str, base_params: dict, target_size_bytes: int,
                             status_callback=None, auto_resize: bool = False) -> dict:
    """
    Find optimal GIF parameters for target file size.
    Uses the currently active estimator version.
    
    Args:
        file_path: Path to source video file
        base_params: Base parameters dict to update
        target_size_bytes: Target file size in bytes
        status_callback: Optional callback for status messages
        auto_resize: Whether to allow resolution scaling
    
    Returns:
        Updated params dict with optimized values
    """
    if _current_version == 'v2':
        return _adapt_v2_gif(file_path, base_params, target_size_bytes, 
                              status_callback, auto_resize)
    else:
        return _get_v1_functions()['gif'](file_path, base_params, target_size_bytes,
                                           status_callback, auto_resize)

def find_optimal_image_params(file_path: str, output_format: str, target_size_bytes: int,
                               status_callback=None, auto_resize: bool = False) -> dict:
    """
    Find optimal image parameters for target file size.
    Uses the currently active estimator version.
    
    Args:
        file_path: Path to source image file
        output_format: Output format (jpg, png, webp)
        target_size_bytes: Target file size in bytes
        status_callback: Optional callback for status messages
        auto_resize: Whether to allow resolution scaling
    
    Returns:
        Dict with optimized quality and resolution params
    """
    if _current_version == 'v2':
        return _adapt_v2_image(file_path, output_format, target_size_bytes,
                                status_callback, auto_resize)
    else:
        return _get_v1_functions()['image'](file_path, output_format, target_size_bytes,
                                             status_callback, auto_resize)

def find_optimal_video_params(file_path: str, codec: str, base_params: dict,
                               target_size_bytes: int, status_callback=None,
                               auto_resize: bool = False) -> dict:
    """
    Find optimal video parameters for target file size.
    Uses the currently active estimator version.
    
    Args:
        file_path: Path to source video file
        codec: Target codec (h264, h265, vp9, av1)
        base_params: Base parameters dict
        target_size_bytes: Target file size in bytes
        status_callback: Optional callback for status messages
        auto_resize: Whether to allow resolution scaling
    
    Returns:
        Dict with optimized encoding params (crf, bitrate, resolution)
    """
    if _current_version == 'v2':
        return _adapt_v2_video(file_path, codec, base_params, target_size_bytes,
                                status_callback, auto_resize)
    else:
        return _get_v1_functions()['video'](file_path, codec, base_params, target_size_bytes,
                                             status_callback, auto_resize)

# =============================================================================
# LEGACY COMPATIBILITY EXPORTS
# =============================================================================
# These allow existing code to import from registry without changes

def find_optimal_gif_params_for_size(*args, **kwargs):
    """Legacy compatibility wrapper."""
    return find_optimal_gif_params(*args, **kwargs)

def find_optimal_image_params_for_size(*args, **kwargs):
    """Legacy compatibility wrapper."""
    return find_optimal_image_params(*args, **kwargs)

def find_optimal_video_params_for_size(*args, **kwargs):
    """Legacy compatibility wrapper."""
    return find_optimal_video_params(*args, **kwargs)

# =============================================================================
# V1 PASSTHROUGH EXPORTS (for backward compatibility)
# =============================================================================
# These are re-exported from v1 for code that imports them from registry

def get_v1_presets():
    """Get v1 presets for backward compatibility."""
    return _get_v1_functions()

# Lazy properties for direct access
class _LazyV1Exports:
    """Lazy loader for v1 exports to avoid circular imports."""
    
    def __getattr__(self, name):
        v1 = _get_v1_functions()
        if name in v1:
            return v1[name]
        raise AttributeError(f"No attribute '{name}' in size_estimator_registry")

_lazy_v1 = _LazyV1Exports()

# Re-export common v1 utilities
def get_video_frame_rate(file_path: str) -> float:
    return _get_v1_functions()['get_video_frame_rate'](file_path)

def estimate_gif_size_fast_preview(file_path: str, params: dict, sample_seconds: float = 2.0) -> dict:
    return _get_v1_functions()['estimate_gif_size_fast_preview'](file_path, params, sample_seconds)

def estimate_gif_size_heuristic(file_path: str, params: dict) -> dict:
    return _get_v1_functions()['estimate_gif_size_heuristic'](file_path, params)

def estimate_all_preset_sizes(file_path: str, base_params: dict, sample_seconds: float = 1.5,
                               auto_resize: bool = False) -> dict:
    return _get_v1_functions()['estimate_all_preset_sizes'](file_path, base_params, sample_seconds, auto_resize)

def estimate_all_image_preset_sizes(file_path: str, output_format: str, auto_resize: bool = False) -> dict:
    return _get_v1_functions()['estimate_all_image_preset_sizes'](file_path, output_format, auto_resize)

def estimate_all_video_preset_sizes(file_path: str, codec: str, base_params: dict, auto_resize: bool = False) -> dict:
    return _get_v1_functions()['estimate_all_video_preset_sizes'](file_path, codec, base_params, auto_resize)

# Preset constants (lazy loaded)
def _get_preset(name):
    return _get_v1_functions()[name]

# These will be accessed as module-level constants by importing code
# We use __getattr__ at module level for lazy loading
def __getattr__(name):
    """Module-level lazy attribute access for v1 constants."""
    v1_exports = [
        'QUALITY_PRESETS_STANDARD', 'QUALITY_PRESETS_AUTORESIZE', 'REFERENCE_PRESET_IDX', 'DITHER_MAP',
        'IMAGE_QUALITY_PRESETS_STANDARD', 'IMAGE_QUALITY_PRESETS_AUTORESIZE', 'IMAGE_REFERENCE_PRESET_IDX',
        'VIDEO_QUALITY_PRESETS_STANDARD', 'VIDEO_QUALITY_PRESETS_AUTORESIZE', 'VIDEO_REFERENCE_PRESET_IDX',
    ]
    if name in v1_exports:
        return _get_v1_functions()[name]
    raise AttributeError(f"module 'size_estimator_registry' has no attribute '{name}'")
