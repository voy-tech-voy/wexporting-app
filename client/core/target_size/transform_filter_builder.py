"""
Transform Filter Builder - Converts UI parameters to FFmpeg filter chains.

Extracts transform parameters (resize, rotate, retime, time trim) from UI params
and builds FFmpeg-ready filter chains for single-pass encoding.
"""

from typing import Dict, List, Optional, Tuple
from client.core.dimension_utils import calculate_target_dimensions
from client.core.ffmpeg_utils import get_video_dimensions, get_video_duration


def build_transform_filters(params: dict, input_path: str) -> dict:
    """
    Build transform configuration from UI parameters.
    
    Args:
        params: UI parameters from tab (VideoTab, LoopTab, ImageTab)
        input_path: Path to input media file
        
    Returns:
        {
            'vf_filters': ['scale=1280:-2', 'transpose=1'],  # Video filters
            'af_filters': ['atempo=1.5'],                    # Audio filters  
            'input_args': {'ss': 0.0, 'to': 10.0},          # Time trim args
            'target_dimensions': (1280, 720),               # For estimation
        }
    """
    result = {
        'vf_filters': [],
        'af_filters': [],
        'input_args': {},
        'target_dimensions': None
    }
    
    # Get original dimensions
    try:
        orig_w, orig_h = get_video_dimensions(input_path)
    except:
        orig_w, orig_h = 0, 0
    
    # 1. Time trim (applied as input args, not filters)
    time_args = _build_time_trim_args(params, input_path)
    if time_args:
        result['input_args'].update(time_args)
    
    # 2. Retime (speed change)
    retime_filters = _build_retime_filters(params)
    if retime_filters:
        result['vf_filters'].extend(retime_filters.get('video', []))
        result['af_filters'].extend(retime_filters.get('audio', []))
    
    # 3. Resize
    resize_filter, target_dims = _build_resize_filter(params, orig_w, orig_h)
    if resize_filter:
        result['vf_filters'].append(resize_filter)
        result['target_dimensions'] = target_dims
    
    # 4. Rotation
    rotation_filters = _build_rotation_filter(params)
    if rotation_filters:
        result['vf_filters'].extend(rotation_filters)
    
    return result


def _build_time_trim_args(params: dict, input_path: str) -> Optional[dict]:
    """
    Build time trim input arguments.
    
    Returns:
        {'ss': start_time, 'to': end_time} or None
    """
    enable_time_cutting = params.get('enable_time_cutting', False)
    if not enable_time_cutting:
        return None
    
    time_start = params.get('time_start')
    time_end = params.get('time_end')
    
    if time_start is None or time_end is None or time_start >= time_end:
        return None
    
    # Get video duration to convert normalized time to actual time
    try:
        video_duration = get_video_duration(input_path)
        if video_duration > 0:
            start_time = time_start * video_duration
            end_time = time_end * video_duration
            return {'ss': start_time, 'to': end_time}
    except:
        pass
    
    return None


def _build_retime_filters(params: dict) -> Optional[dict]:
    """
    Build retime (speed change) filters for video and audio.
    
    Returns:
        {'video': ['setpts=PTS/1.5'], 'audio': ['atempo=1.5']} or None
    """
    retime_enabled = params.get('retime_enabled') or params.get('enable_retime')
    retime_speed = params.get('retime_speed', 1.0)
    
    if not retime_enabled or not retime_speed or retime_speed == 1.0:
        return None
    
    try:
        speed = float(retime_speed)
        speed = max(0.1, min(3.0, speed))  # Clamp to valid range
        
        result = {
            'video': [f'setpts=PTS/{speed}'],
            'audio': []
        }
        
        # Audio tempo filter (atempo has range limits)
        if speed <= 2.0:
            result['audio'].append(f'atempo={speed}')
        else:
            # Chain atempo filters for speeds > 2.0
            result['audio'].append(f'atempo=2.0')
            result['audio'].append(f'atempo={speed / 2.0}')
        
        return result
    except:
        return None


def _build_resize_filter(params: dict, orig_w: int, orig_h: int) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    """
    Build resize filter from UI parameters.
    
    Returns:
        (filter_string, target_dimensions) or (None, None)
    """
    current_resize = params.get('current_resize')
    if not current_resize or current_resize == "No resize":
        return None, None
    
    allow_upscale = params.get('allow_upscaling', False)
    
    # Calculate target dimensions
    target_dims = calculate_target_dimensions(
        file_path="",  # Not used in calculation
        resize_spec=current_resize,
        original_width=orig_w,
        original_height=orig_h,
        allow_upscale=allow_upscale
    )
    
    if not target_dims:
        return None, None
    
    target_w, target_h = target_dims
    
    # Build filter string
    # Use -2 for auto-calculated dimension to ensure even values
    if target_h == -1:
        filter_str = f'scale={target_w}:-2:flags=lanczos'
    else:
        filter_str = f'scale={target_w}:{target_h}:flags=lanczos'
    
    return filter_str, target_dims


def _build_rotation_filter(params: dict) -> Optional[List[str]]:
    """
    Build rotation filter using transpose.
    
    Returns:
        List of filter strings or None
    """
    rotation_angle = params.get('rotation_angle')
    
    if not rotation_angle or rotation_angle == "No rotation":
        return None
    
    # Skip rotation for longer edge mode unless explicitly set
    current_resize = params.get('current_resize')
    if current_resize and current_resize.startswith('L'):
        return None
    
    filters = []
    
    if rotation_angle == "90° clockwise":
        filters.append('transpose=1')
    elif rotation_angle == "180°":
        # Apply transpose twice for 180 degrees
        filters.append('transpose=2')
        filters.append('transpose=2')
    elif rotation_angle == "270° clockwise":
        filters.append('transpose=2')
    
    return filters if filters else None
