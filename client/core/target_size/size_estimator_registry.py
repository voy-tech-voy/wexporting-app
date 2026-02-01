"""
Size Estimator Registry - Format-Aware Dynamic Loading
Supports independent versioning per format/codec.
"""
from typing import Callable, List, Tuple
import importlib
from pathlib import Path

# =============================================================================
# VERSION STATE
# =============================================================================
_active_estimator_version = 'v2'

def get_estimator_version(): 
    return _active_estimator_version

def set_estimator_version(version: str):
    global _active_estimator_version
    _active_estimator_version = version
    return True

# =============================================================================
# FORMAT NORMALIZATION
# =============================================================================
def _normalize_image_format(fmt: str) -> str:
    """Normalize image format to estimator key."""
    fmt_lower = fmt.lower()
    if 'jpg' in fmt_lower or 'jpeg' in fmt_lower: return 'jpg'
    if 'webp' in fmt_lower: return 'webp'
    if 'png' in fmt_lower: return 'png'
    return 'jpg'  # default

def _normalize_video_codec(codec: str) -> str:
    """Normalize codec preference to estimator key."""
    codec_lower = codec.lower()
    
    # Handle already-normalized keys (mp4_h264, mp4_h265, webm_vp9, webm_av1)
    if codec_lower in ('mp4_h264', 'mp4_h265', 'webm_vp9', 'webm_av1'):
        return codec_lower
    
    # Check more specific codecs FIRST (order matters!)
    if 'h.265' in codec_lower or 'h265' in codec_lower or 'hevc' in codec_lower: return 'mp4_h265'
    if 'vp9' in codec_lower: return 'webm_vp9'
    if 'av1' in codec_lower: return 'webm_av1'
    # H.264/MP4 is the fallback (check last since mp4 is too generic)
    if 'h.264' in codec_lower or 'h264' in codec_lower or 'mp4' in codec_lower: return 'mp4_h264'
    return 'mp4_h264'  # default

def _normalize_loop_format(fmt: str) -> str:
    """Normalize loop format to estimator key."""
    fmt_lower = fmt.lower()
    if 'gif' in fmt_lower: return 'gif'
    if 'webm' in fmt_lower: return 'webm_loop'
    return 'gif'  # default

# =============================================================================
# DYNAMIC LOADING
# =============================================================================
def _load_format_estimator(media_type: str, format_key: str, version: str):
    """
    Load a format-specific estimator FUNCTION (legacy interface).
    
    Args:
        media_type: 'image', 'video', or 'loop'
        format_key: Normalized format/codec key (e.g., 'jpg', 'mp4_h264', 'gif')
        version: Version string (e.g., 'v2', 'v5')
    
    Returns:
        Estimator function or None if not found
    """
    try:
        module_name = f"client.core.target_size.{media_type}_estimators.{format_key}_estimator_{version}"
        module = importlib.import_module(module_name)
        
        if media_type == 'image':
            func = getattr(module, 'optimize_image_params')
        elif media_type == 'video':
            func = getattr(module, 'optimize_video_params')
        else:  # loop
            func = getattr(module, 'optimize_gif_params')
        
        print(f"[Registry] Loaded {format_key} estimator {version}")
        return func
    except Exception as e:
        print(f"[Registry] Could not load {format_key} estimator {version}: {e}")
        return None


def _load_estimator_class(media_type: str, format_key: str, version: str):
    """
    Load a format-specific estimator CLASS (new interface).
    
    The new interface expects estimators to be classes with:
    - estimate(input_path, target_size_bytes, **options) -> dict
    - execute(input_path, output_path, target_size_bytes, callbacks, **options) -> bool
    
    Args:
        media_type: 'image', 'video', or 'loop'
        format_key: Normalized format/codec key (e.g., 'jpg', 'mp4_h264', 'gif')
        version: Version string (e.g., 'v2', 'v5')
    
    Returns:
        Estimator class instance or None if not found
    """
    try:
        module_name = f"client.core.target_size.{media_type}_estimators.{format_key}_estimator_{version}"
        module = importlib.import_module(module_name)
        
        # Try to get the Estimator class
        estimator_class = getattr(module, 'Estimator', None)
        if estimator_class:
            instance = estimator_class()
            print(f"[Registry] Loaded {format_key} Estimator class {version}")
            return instance
        
        return None
    except Exception as e:
        print(f"[Registry] Could not load {format_key} Estimator class {version}: {e}")
        return None


def get_video_estimator(codec_pref: str, version: str = None):
    """
    Get a video estimator class instance.
    
    Args:
        codec_pref: Codec preference (e.g., 'H.264 (MP4)', 'H.265/HEVC')
        version: Optional version override, defaults to active version
    
    Returns:
        Estimator class instance or None
    """
    version = version or _active_estimator_version
    codec_key = _normalize_video_codec(codec_pref)
    
    estimator = _load_estimator_class('video', codec_key, version)
    
    if not estimator:
        # Fallback to available versions
        versions = get_available_versions_for_format('video', codec_key)
        if versions:
            fallback_version = versions[-1][1]
            estimator = _load_estimator_class('video', codec_key, fallback_version)
    
    return estimator


def run_video_conversion(
    input_path: str,
    output_path: str,
    target_size_bytes: int,
    codec_pref: str,
    status_callback=None,
    stop_check=None,
    **options
) -> bool:
    """
    Run video conversion using new self-contained estimator.
    
    This is the preferred entry point for video conversions.
    The estimator handles the complete encoding pipeline.
    
    Args:
        input_path: Source video file
        output_path: Destination file
        target_size_bytes: Target size in bytes
        codec_pref: Codec preference string
        status_callback: Optional status update callback
        stop_check: Optional stop check callback
        **options: Additional options (rotation, allow_downscale, etc.)
    
    Returns:
        True if conversion succeeded
    """
    estimator = get_video_estimator(codec_pref)
    
    if not estimator:
        if status_callback:
            status_callback(f"No estimator found for {codec_pref}")
        return False
    
    return estimator.execute(
        input_path=input_path,
        output_path=output_path,
        target_size_bytes=target_size_bytes,
        status_callback=status_callback,
        stop_check=stop_check,
        **options
    )


def get_image_estimator(output_format: str, version: str = None):
    """
    Get an image estimator class instance.
    
    Args:
        output_format: Output format (JPG, WebP, PNG, etc.)
        version: Optional version override, defaults to active version
    
    Returns:
        Estimator class instance or None
    """
    version = version or _active_estimator_version
    format_key = _normalize_image_format(output_format)
    
    estimator = _load_estimator_class('image', format_key, version)
    
    if not estimator:
        # Fallback to available versions
        versions = get_available_versions_for_format('image', format_key)
        if versions:
            fallback_version = versions[-1][1]
            estimator = _load_estimator_class('image', format_key, fallback_version)
    
    return estimator


def run_image_conversion(
    input_path: str,
    output_path: str,
    target_size_bytes: int,
    output_format: str,
    status_callback=None,
    stop_check=None,
    **options
) -> bool:
    """
    Run image conversion using new self-contained estimator.
    
    Args:
        input_path: Source image file
        output_path: Destination file
        target_size_bytes: Target size in bytes
        output_format: Output format (JPG, WebP, PNG)
        status_callback: Optional status update callback
        stop_check: Optional stop check callback
        **options: Additional options (rotation, allow_downscale, etc.)
    
    Returns:
        True if conversion succeeded
    """
    estimator = get_image_estimator(output_format)
    
    if not estimator:
        if status_callback:
            status_callback(f"No estimator found for {output_format}")
        return False
    
    return estimator.execute(
        input_path=input_path,
        output_path=output_path,
        target_size_bytes=target_size_bytes,
        status_callback=status_callback,
        stop_check=stop_check,
        **options
    )

# =============================================================================
# PUBLIC API
# =============================================================================
def optimize_image_params(file_path: str, output_format: str, target_size_bytes: int, **kwargs):
    """
    Optimize image for target size using format-specific estimator.
    
    Args:
        file_path: Input image path
        output_format: Output format (JPG, WebP, PNG, etc.)
        target_size_bytes: Target file size in bytes
        **kwargs: Additional parameters (allow_downscale, auto_resize, etc.)
    
    Returns:
        Dict with optimization parameters
    """
    version = _active_estimator_version
    format_key = _normalize_image_format(output_format)
    
    # Try to load format-specific estimator
    estimator = _load_format_estimator('image', format_key, version)
    
    if not estimator:
        # Fallback: try to find any available version
        print(f"[Registry] {version} estimator not found for {format_key}, attempting fallback...")
        versions = get_available_versions_for_format('image', format_key)
        if versions:
            # Use the highest version available (last in the sorted list)
            fallback_version = versions[-1][1]
            print(f"[Registry] Falling back to {fallback_version} for {format_key}")
            estimator = _load_format_estimator('image', format_key, fallback_version)
    
    if estimator:
        downscale = kwargs.pop('allow_downscale', kwargs.pop('auto_resize', False))
        return estimator(file_path, target_size_bytes, allow_downscale=downscale, **kwargs)
    
    # Fallback: return empty dict
    print(f"[Registry] No {format_key} estimator available (tried {version} and fallbacks)")
    return {}

def optimize_video_params(file_path: str, target_size_bytes: int, **kwargs):
    """
    Optimize video for target size using codec-specific estimator.
    
    Args:
        file_path: Input video path
        target_size_bytes: Target file size in bytes
        **kwargs: Additional parameters (codec_pref, allow_downscale, etc.)
    
    Returns:
        Dict with optimization parameters
    """
    version = _active_estimator_version
    codec_pref = kwargs.pop('codec_pref', kwargs.pop('codec', 'H.264 (MP4)'))
    codec_key = _normalize_video_codec(codec_pref)
    
    # Try to load codec-specific estimator
    estimator = _load_format_estimator('video', codec_key, version)
    
    if not estimator:
        # Fallback: try to find any available version
        print(f"[Registry] {version} estimator not found for {codec_key}, attempting fallback...")
        versions = get_available_versions_for_format('video', codec_key)
        if versions:
            fallback_version = versions[-1][1]
            print(f"[Registry] Falling back to {fallback_version} for {codec_key}")
            estimator = _load_format_estimator('video', codec_key, fallback_version)

    if estimator:
        downscale = kwargs.pop('allow_downscale', kwargs.pop('auto_resize', False))
        return estimator(file_path, target_size_bytes, allow_downscale=downscale, **kwargs)
    
    # Fallback: return empty dict
    print(f"[Registry] No {codec_key} estimator available (tried {version} and fallbacks)")
    return {}

def optimize_gif_params(file_path: str, target_size_bytes: int, **kwargs):
    """
    Optimize loop/GIF for target size using format-specific estimator.
    
    Args:
        file_path: Input video/image path
        target_size_bytes: Target file size in bytes
        **kwargs: Additional parameters (format, allow_downscale, etc.)
    
    Returns:
        Dict with optimization parameters
    """
    version = _active_estimator_version
    loop_format = kwargs.pop('format', 'GIF')
    format_key = _normalize_loop_format(loop_format)
    
    # Try to load format-specific estimator
    estimator = _load_format_estimator('loop', format_key, version)
    
    if not estimator:
        # Fallback: try to find any available version
        print(f"[Registry] {version} estimator not found for {format_key}, attempting fallback...")
        versions = get_available_versions_for_format('loop', format_key)
        if versions:
            fallback_version = versions[-1][1]
            print(f"[Registry] Falling back to {fallback_version} for {format_key}")
            estimator = _load_format_estimator('loop', format_key, fallback_version)

    if estimator:
        downscale = kwargs.pop('allow_downscale', kwargs.pop('auto_resize', False))
        return estimator(file_path, target_size_bytes, allow_downscale=downscale, **kwargs)
    
    # Fallback: return empty dict
    print(f"[Registry] No {format_key} estimator available (tried {version} and fallbacks)")
    return {}

# =============================================================================
# VERSION DETECTION
# =============================================================================
def get_available_versions_for_format(media_type: str, format_or_codec: str) -> List[Tuple[str, str]]:
    """
    Get available versions for a specific format/codec.
    
    Args:
        media_type: 'image', 'video', or 'loop'
        format_or_codec: Format (JPG, WebP) or codec (H.264, VP9)
    
    Returns:
        List of (display_name, version_key) tuples
    """
    # Normalize format/codec
    if media_type == 'image':
        format_key = _normalize_image_format(format_or_codec)
        search_dir = Path(__file__).parent / "image_estimators"
    elif media_type == 'video':
        format_key = _normalize_video_codec(format_or_codec)
        search_dir = Path(__file__).parent / "video_estimators"
    else:  # loop
        format_key = _normalize_loop_format(format_or_codec)
        search_dir = Path(__file__).parent / "loop_estimators"
    
    # Scan for estimator files
    pattern = f"{format_key}_estimator_v*.py"
    versions = []
    
    if search_dir.exists():
        for file_path in search_dir.glob(pattern):
            version_part = file_path.stem.split('_')[-1]  # e.g., "v5"
            if version_part.startswith('v'):
                version_num = version_part[1:]
                display_name = f"{version_part} ({format_key.upper()})"
                versions.append((display_name, version_part))
    
    # Sort by version number
    versions.sort(key=lambda x: int(x[1][1:]))
    return versions

def get_available_versions(type_prefix: str = 'image') -> List[Tuple[str, str]]:
    """
    Legacy function for backward compatibility.
    Scans for old-style unified estimators.
    """
    pattern = f"{type_prefix}_estimator_v*.py"
    target_size_dir = Path(__file__).parent
    versions = []
    
    for file_path in target_size_dir.glob(pattern):
        filename = file_path.stem
        version_part = filename.split('_')[-1]
        
        if version_part.startswith('v'):
            display_name = f"{version_part} ({filename})"
            versions.append((display_name, version_part))
    
    versions.sort(key=lambda x: x[1])
    return versions

def get_available_video_estimator_versions(codec_key: str) -> List[str]:
    """
    Get available estimator versions for a specific video codec.
    
    Args:
        codec_key: Normalized codec key (e.g., 'mp4_h264', 'mp4_h265', 'webm_vp9')
    
    Returns:
        List of version strings (e.g., ['v2', 'v5'])
    """
    versions_with_display = get_available_versions_for_format('video', codec_key)
    # Extract just the version keys (e.g., 'v2', 'v5')
    return [version_key for _, version_key in versions_with_display]

# =============================================================================
# LEGACY ADAPTERS (Used by Conversion Engine)
# =============================================================================
def find_optimal_video_params_for_size(file_path, codec, params, target_size_bytes, callback=None, auto_resize=False):
    return optimize_video_params(file_path, target_size_bytes, codec=codec, auto_resize=auto_resize, legacy_params=params)

def find_optimal_image_params_for_size(file_path, output_format, target_size_bytes, callback=None, auto_resize=False):
    return optimize_image_params(file_path, output_format, target_size_bytes, auto_resize=auto_resize)

def find_optimal_gif_params_for_size(file_path, params, target_size_bytes, callback=None, auto_resize=False):
    loop_format = params.get('format', 'GIF') if isinstance(params, dict) else 'GIF'
    return optimize_gif_params(file_path, target_size_bytes, format=loop_format, auto_resize=auto_resize, legacy_params=params)
