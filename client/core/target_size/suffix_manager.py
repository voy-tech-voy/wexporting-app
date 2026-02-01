"""
Suffix Manager for Target Size Conversions.
Generates descriptive filenames with target size, resolution, codec, etc.
"""
import os
from pathlib import Path
from typing import Dict, Optional


def generate_target_size_suffix(
    params: Dict,
    optimal: Dict,
    extension: str,
    target_mb: Optional[float] = None
) -> str:
    """
    Generate comprehensive suffix for target size conversions.
    
    Args:
        params: Conversion parameters from UI
        optimal: Optimal parameters from estimator
        extension: Output file extension
        target_mb: Optional explicit target size (for multiple variants)
        
    Returns:
        Suffix string (e.g., "_v2TargetSize5MB_1920x1080_codecH264")
    """
    parts = []
    
    # Get target size (use explicit if provided, otherwise from params)
    if target_mb is None:
        target_mb = params.get('video_max_size_mb') or \
                    params.get('image_max_size_mb') or \
                    params.get('gif_max_size_mb') or 0
    
    # Format size string
    if target_mb >= 1:
        size_str = f"{target_mb:.0f}MB" if target_mb == int(target_mb) else f"{target_mb:.1f}MB"
    elif target_mb < 0.1:
        size_str = f"{int(target_mb * 1024)}KB"
    else:
        size_str = f"{target_mb:.2f}MB".rstrip('0').rstrip('.')
    
    # Resolution from optimal params
    resolution_str = ""
    if optimal and 'resolution_w' in optimal and 'resolution_h' in optimal:
        w = optimal['resolution_w']
        h = optimal['resolution_h']
        if w > 0 and h > 0:
            resolution_str = f"_{w}x{h}"
    
    # Estimator version - prioritize UI selection from params, fallback to estimator's version
    version_str = ""
    if params and 'estimator_version' in params and params['estimator_version']:
        version_str = params['estimator_version']
    elif optimal and 'estimator_version' in optimal:
        version_str = optimal['estimator_version']
    
    # Build suffix: v{version}TargetSize{size}MB_{resolution}
    if version_str:
        parts.append(f"_{version_str}TargetSize{size_str}{resolution_str}")
    else:
        parts.append(f"_TargetSize{size_str}{resolution_str}")
    
    # Rotation suffix
    rot = params.get('rotation_angle')
    if rot and rot != 'No rotation':
        if '90' in rot and '270' not in rot:
            parts.append('_rot90')
        elif '180' in rot:
            parts.append('_rot180')
        elif '270' in rot:
            parts.append('_rot270')
    
    # Codec suffix (for video only)
    if extension in ['mp4', 'webm']:
        codec = params.get('codec', '')
        if codec and '(' in codec:
            # Extract codec name from "MP4 (H.264)" -> "H264"
            cleaned = codec.split('(')[1].split(')')[0].replace('.', '').replace(' ', '')
            if cleaned:
                parts.append(f"_codec{cleaned}")
    
    # GIF specifics
    if extension == 'gif' and optimal:
        if 'fps' in optimal:
            parts.append(f"_{optimal['fps']}fps")
        if 'colors' in optimal:
            parts.append(f"_{optimal['colors']}colors")
    
    return ''.join(parts)


def get_output_path(
    file_path: str,
    params: Dict,
    extension: str,
    optimal: Optional[Dict] = None,
    target_mb: Optional[float] = None
) -> str:
    """
    Generate full output path with comprehensive suffix.
    
    Args:
        file_path: Input file path
        params: Conversion parameters
        extension: Output extension
        optimal: Optional optimal parameters from estimator
        target_mb: Optional explicit target size (for multiple variants)
        
    Returns:
        Full output path
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    suffix = generate_target_size_suffix(params, optimal, extension, target_mb)
    
    # Determine output directory
    if params.get('use_nested_output', True):
        output_dir = os.path.join(
            os.path.dirname(file_path),
            params.get('nested_output_name', 'output')
        )
    else:
        output_dir = os.path.dirname(file_path)
        
    os.makedirs(output_dir, exist_ok=True)
    
    return os.path.join(output_dir, f"{base_name}{suffix}.{extension}")
