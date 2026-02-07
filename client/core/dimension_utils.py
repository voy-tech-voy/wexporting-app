"""
Dimension Utilities - Single Source of Truth for Dimension Calculations

Consolidates all dimension calculation logic to ensure consistency between:
- FFmpeg scale filters (ConversionEngine)
- Filename suffix generation (SuffixManager)
"""

from typing import Tuple, Optional


def clamp_resize_width(original_width: int, target_width: int) -> int:
    """
    Prevent upscaling by clamping target width to original width.
    
    Args:
        original_width: Original image/video width
        target_width: Desired target width
        
    Returns:
        Clamped width (never larger than original)
    """
    if original_width and target_width > original_width:
        return original_width
    return target_width


def calculate_longer_edge_resize(original_width: int, original_height: int, target_longer_edge: int) -> Tuple[int, int]:
    """
    Calculate new dimensions based on longer edge resize (no upscaling).
    
    Rules:
    - Identify the longer edge
    - Scale so longer edge becomes target_longer_edge
    - If longer edge is already smaller than target, don't resize
    - Maintain aspect ratio
    - Ensure even dimensions (codec requirement)
    
    Args:
        original_width: Original width
        original_height: Original height
        target_longer_edge: Target size for the longer edge
        
    Returns:
        (new_width, new_height) or original dimensions if no resize needed
    """
    if not original_width or not original_height:
        return (original_width, original_height)
    
    longer_edge = max(original_width, original_height)
    
    # Don't upscale if longer edge is already smaller than target
    if longer_edge < target_longer_edge:
        return (original_width, original_height)
    
    # Calculate scale factor based on longer edge
    scale_factor = target_longer_edge / longer_edge
    
    # Calculate new dimensions maintaining aspect ratio
    new_width = int(original_width * scale_factor)
    new_height = int(original_height * scale_factor)
    
    # Ensure even dimensions (required for some codecs)
    new_width = new_width if new_width % 2 == 0 else new_width - 1
    new_height = new_height if new_height % 2 == 0 else new_height - 1
    
    return (new_width, new_height)


def calculate_percent_resize(original_width: int, original_height: int, percent: float) -> Tuple[int, int]:
    """
    Calculate new dimensions based on percentage.
    
    Args:
        original_width: Original width
        original_height: Original height
        percent: Scale percentage (e.g., 0.5 for 50%)
        
    Returns:
        (new_width, new_height) with even dimensions
    """
    if not original_width or not original_height:
        return (original_width, original_height)
    
    new_width = int(original_width * percent)
    new_height = int(original_height * percent)
    
    # Ensure even dimensions
    new_width = new_width if new_width % 2 == 0 else new_width - 1
    new_height = new_height if new_height % 2 == 0 else new_height - 1
    
    return (new_width, new_height)


def calculate_width_resize(original_width: int, original_height: int, target_width: int, allow_upscale: bool = False) -> Tuple[int, int]:
    """
    Calculate new dimensions based on target width while maintaining aspect ratio.
    
    Args:
        original_width: Original width
        original_height: Original height
        target_width: Desired width
        allow_upscale: Whether to allow upscaling (default: False)
        
    Returns:
        (new_width, new_height) with even dimensions
    """
    if not original_width or not original_height:
        return (target_width, -1)  # Let FFmpeg calculate height
    
    # Clamp if upscaling not allowed
    if not allow_upscale:
        target_width = clamp_resize_width(original_width, target_width)
    
    # Calculate height maintaining aspect ratio
    new_height = int((target_width * original_height) / original_width)
    
    # Ensure even dimensions
    new_width = target_width if target_width % 2 == 0 else target_width - 1
    new_height = new_height if new_height % 2 == 0 else new_height - 1
    
    return (new_width, new_height)


def calculate_target_dimensions(
    file_path: str,
    resize_spec: str,
    original_width: int,
    original_height: int,
    allow_upscale: bool = False
) -> Optional[Tuple[int, int]]:
    """
    Calculate target dimensions from a resize specification string.
    
    This is the SINGLE SOURCE OF TRUTH for dimension calculation.
    All components (Engine, SuffixManager, Converters) should use this.
    
    Args:
        file_path: Path to media file (for context/logging)
        resize_spec: Resize specification:
            - "L720" = Longer edge 720px
            - "50%" = 50 percent scale
            - "1280" = Width 1280px
            - None = No resize
        original_width: Original media width
        original_height: Original media height
        allow_upscale: Whether to allow upscaling
        
    Returns:
        (width, height) tuple or None if no resize
    """
    if not resize_spec or resize_spec == "No resize":
        return None
    
    spec = str(resize_spec).strip()
    
    # Longer edge format: "L720"
    if spec.startswith('L'):
        try:
            target = int(spec[1:])
            return calculate_longer_edge_resize(original_width, original_height, target)
        except ValueError:
            return None
    
    # Percentage format: "50%"
    elif spec.endswith('%'):
        try:
            percent = float(spec[:-1]) / 100.0
            return calculate_percent_resize(original_width, original_height, percent)
        except ValueError:
            return None
    
    # Width format: "1280"
    elif spec.isdigit():
        try:
            target_width = int(spec)
            return calculate_width_resize(original_width, original_height, target_width, allow_upscale)
        except ValueError:
            return None
    
    return None


def format_dimension_suffix(width: int, height: int) -> str:
    """
    Format dimensions as a filename suffix.
    
    Args:
        width: Width in pixels
        height: Height in pixels
        
    Returns:
        Formatted suffix string (e.g., "_1280x720")
    """
    return f"_{width}x{height}"
