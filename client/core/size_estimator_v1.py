"""
Size Estimation Module for Media Conversion

This module contains all size estimation algorithms and quality presets for
determining optimal encoding parameters to meet target file size constraints.

Extracted from conversion_engine.py to improve modularity and maintainability.

Supports:
- GIF size estimation and optimization
- Image (JPEG/PNG/WebP) size estimation
- Video (H.264/H.265/VP9/AV1) size estimation
"""

import os
import tempfile
import subprocess
import time
import ffmpeg
from typing import Dict, Callable, Optional


# =============================================================================
# UTILITY FUNCTION IMPORTS (Runtime to avoid circular dependency)
# =============================================================================

def _get_utils():
    """
    Runtime import of utility functions from conversion_engine to avoid circular imports.
    Returns a dict of utility functions.
    """
    from client.core.ffmpeg_utils import (
        get_video_dimensions,
        get_video_duration,
        has_audio_stream,
        calculate_longer_edge_resize,
        clamp_resize_width
    )
    return {
        'get_video_dimensions': get_video_dimensions,
        'get_video_duration': get_video_duration,
        'has_audio_stream': has_audio_stream,
        'calculate_longer_edge_resize': calculate_longer_edge_resize,
        'clamp_resize_width': clamp_resize_width
    }

# Cache the utils after first import
_utils_cache = None

def get_video_dimensions(file_path: str):
    """Wrapper for runtime import"""
    global _utils_cache
    if _utils_cache is None:
        _utils_cache = _get_utils()
    return _utils_cache['get_video_dimensions'](file_path)

def get_video_duration(file_path: str):
    """Wrapper for runtime import"""
    global _utils_cache
    if _utils_cache is None:
        _utils_cache = _get_utils()
    return _utils_cache['get_video_duration'](file_path)

def has_audio_stream(file_path: str):
    """Wrapper for runtime import"""
    global _utils_cache
    if _utils_cache is None:
        _utils_cache = _get_utils()
    return _utils_cache['has_audio_stream'](file_path)

def calculate_longer_edge_resize(width: int, height: int, target: int):
    """Wrapper for runtime import"""
    global _utils_cache
    if _utils_cache is None:
        _utils_cache = _get_utils()
    return _utils_cache['calculate_longer_edge_resize'](width, height, target)

def clamp_resize_width(original_width: int, new_width: int):
    """Wrapper for runtime import"""
    global _utils_cache
    if _utils_cache is None:
        _utils_cache = _get_utils()
    return _utils_cache['clamp_resize_width'](original_width, new_width)



# =============================================================================
# GIF QUALITY PRESETS FOR SIZE OPTIMIZATION
# =============================================================================
# Each preset: (dither_level, fps, colors, resolution_percent, size_factor)
# Ordered from highest quality (index 0) to lowest (index N)
# 
# Degradation strategy (preserves perceived quality):
# 1. Dither first (minimal visual/size impact)
# 2. Colors second (moderate size impact, less perceptible down to 64)
# 3. FPS third (high size impact, but affects smoothness)
# 4. Resolution (when auto-resize enabled) - try scaling before very low quality
#
# Size factors are CALIBRATED from real encoding tests.
# Resolution scaling happens BEFORE going to low quality (colors<=32, fps<=12)

# Standard presets (no resolution scaling)
QUALITY_PRESETS_STANDARD = [
    # (dither, fps, colors, resolution, size_factor)
    # --- TIER 1: Maximum Quality ---
    (5, 24, 256, 100, 1.00),   # 0: Maximum - floyd_steinberg, full fps/colors
    (4, 24, 256, 100, 1.00),   # 1: Very high - bayer:1
    (3, 24, 256, 100, 0.85),   # 2: High - bayer:3
    
    # --- TIER 2: Good Quality (reduce colors, keep fps) ---
    (3, 24, 192, 100, 0.77),   # 3: Good+
    (3, 24, 128, 100, 0.66),   # 4: Good - half colors
    (3, 20, 128, 100, 0.55),   # 5: Good (lower fps)
    (2, 20, 128, 100, 0.45),   # 6: Good- - reduce dither
    
    # --- TIER 3: Medium Quality ---
    (2, 18, 128, 100, 0.43),   # 7: Medium+
    (2, 15, 128, 100, 0.41),   # 8: Medium - REFERENCE PRESET
    (2, 15, 96, 100, 0.36),    # 9: Medium (fewer colors)
    (2, 15, 64, 100, 0.32),    # 10: Medium-
    (2, 12, 64, 100, 0.26),    # 11: Medium-- (lower fps)
    (1, 12, 64, 100, 0.23),    # 12: Lower medium
    
    # --- TIER 4: Low Quality ---
    (1, 12, 48, 100, 0.20),    # 13: Low+
    (1, 10, 32, 100, 0.14),    # 14: Low
    (1, 8, 32, 100, 0.11),     # 15: Low-
    (0, 8, 16, 100, 0.08),     # 16: Very low
    (0, 6, 16, 100, 0.06),     # 17: Minimum
]

# Presets with auto-resize: try resolution scaling before low quality
QUALITY_PRESETS_AUTORESIZE = [
    # (dither, fps, colors, resolution, size_factor)
    # --- TIER 1: Maximum Quality ---
    (5, 24, 256, 100, 1.00),   # 0: Maximum
    (4, 24, 256, 100, 1.00),   # 1: Very high
    (3, 24, 256, 100, 0.85),   # 2: High
    
    # --- TIER 2: Good Quality ---
    (3, 24, 192, 100, 0.77),   # 3: Good+
    (3, 24, 128, 100, 0.66),   # 4: Good
    (3, 20, 128, 100, 0.55),   # 5: Good (lower fps)
    (2, 20, 128, 100, 0.45),   # 6: Good-
    
    # --- TIER 3: Medium Quality ---
    (2, 18, 128, 100, 0.43),   # 7: Medium+
    (2, 15, 128, 100, 0.41),   # 8: Medium - REFERENCE PRESET
    (2, 15, 96, 100, 0.36),    # 9: Medium (fewer colors)
    (2, 15, 64, 100, 0.32),    # 10: Medium-
    (2, 12, 64, 100, 0.26),    # 11: Medium--
    (1, 12, 64, 100, 0.23),    # 12: Lower medium
    
    # --- TIER 3.5: Resolution scaling (before low quality) ---
    # 90% resolution with medium quality settings
    (2, 15, 64, 90, 0.26),     # 13: Medium @ 90% res (~0.81x pixels)
    (2, 15, 64, 80, 0.21),     # 14: Medium @ 80% res (~0.64x pixels)
    (2, 15, 64, 70, 0.16),     # 15: Medium @ 70% res (~0.49x pixels)
    (2, 12, 64, 60, 0.10),     # 16: Medium @ 60% res (~0.36x pixels)
    
    # --- TIER 4: Low Quality (last resort) ---
    (1, 12, 48, 100, 0.20),    # 17: Low+ (back to 100% but lower quality)
    (1, 10, 32, 100, 0.14),    # 18: Low
    (1, 8, 32, 100, 0.11),     # 19: Low-
    (0, 8, 16, 100, 0.08),     # 20: Very low
    (0, 6, 16, 100, 0.06),     # 21: Minimum
]

# Reference preset index for calibration (middle quality for best accuracy)
REFERENCE_PRESET_IDX = 8

# Dither level to FFmpeg string mapping
DITHER_MAP = {
    0: 'none',
    1: 'bayer:bayer_scale=5',
    2: 'bayer:bayer_scale=4',
    3: 'bayer:bayer_scale=3',
    4: 'bayer:bayer_scale=1',
    5: 'floyd_steinberg',
}


# =============================================================================
# IMAGE MAX SIZE PRESETS
# =============================================================================
# Each preset: (quality, resolution_percent, size_factor)
# quality: 1-100 (FFmpeg/image encoder quality)
# resolution_percent: 100 = original, 90 = 90% width/height, etc.
# size_factor: relative size multiplier (calibrated from real encodes)

IMAGE_QUALITY_PRESETS_STANDARD = [
    # (quality, resolution, size_factor)
    # --- TIER 1: Maximum Quality ---
    (100, 100, 1.00),    # 0: Lossless/Maximum
    (95, 100, 0.85),     # 1: Very high
    (90, 100, 0.70),     # 2: High
    (85, 100, 0.58),     # 3: Good+
    
    # --- TIER 2: Good Quality ---
    (80, 100, 0.48),     # 4: Good
    (75, 100, 0.40),     # 5: Medium-high
    (70, 100, 0.34),     # 6: Medium+
    
    # --- TIER 3: Medium Quality ---
    (65, 100, 0.29),     # 7: Medium
    (60, 100, 0.25),     # 8: Medium - REFERENCE PRESET
    (55, 100, 0.22),     # 9: Medium-
    (50, 100, 0.19),     # 10: Lower medium
    
    # --- TIER 4: Low Quality ---
    (45, 100, 0.16),     # 11: Low+
    (40, 100, 0.14),     # 12: Low
    (35, 100, 0.12),     # 13: Low-
    (30, 100, 0.10),     # 14: Very low
    (25, 100, 0.08),     # 15: Minimum+
    (20, 100, 0.06),     # 16: Minimum
]

IMAGE_QUALITY_PRESETS_AUTORESIZE = [
    # (quality, resolution, size_factor)
    # --- TIER 1: Maximum Quality ---
    (100, 100, 1.00),    # 0: Lossless/Maximum
    (95, 100, 0.85),     # 1: Very high
    (90, 100, 0.70),     # 2: High
    (85, 100, 0.58),     # 3: Good+
    
    # --- TIER 2: Good Quality ---
    (80, 100, 0.48),     # 4: Good
    (75, 100, 0.40),     # 5: Medium-high
    (70, 100, 0.34),     # 6: Medium+
    
    # --- TIER 3: Medium Quality ---
    (65, 100, 0.29),     # 7: Medium
    (60, 100, 0.25),     # 8: Medium - REFERENCE PRESET
    (55, 100, 0.22),     # 9: Medium-
    (50, 100, 0.19),     # 10: Lower medium
    
    # --- TIER 3.5: Resolution scaling (before low quality) ---
    (55, 90, 0.18),      # 11: Medium @ 90% res (~0.81x pixels)
    (55, 80, 0.14),      # 12: Medium @ 80% res (~0.64x pixels)
    (50, 70, 0.10),      # 13: Medium @ 70% res (~0.49x pixels)
    (50, 60, 0.07),      # 14: Medium @ 60% res (~0.36x pixels)
    
    # --- TIER 4: Low Quality (last resort) ---
    (45, 100, 0.16),     # 15: Low+ (back to 100% but lower quality)
    (40, 100, 0.14),     # 16: Low
    (35, 100, 0.12),     # 17: Low-
    (30, 100, 0.10),     # 18: Very low
    (25, 100, 0.08),     # 19: Minimum+
    (20, 100, 0.06),     # 20: Minimum
]

IMAGE_REFERENCE_PRESET_IDX = 8


# =============================================================================
# VIDEO MAX SIZE PRESETS
# =============================================================================
# Each preset: (crf, resolution_percent, audio_bitrate_kbps, size_factor)
# crf: Constant Rate Factor (0=lossless, 51=worst for H.264/H.265)
# resolution_percent: 100 = original, 90 = 90% width/height, etc.
# audio_bitrate_kbps: audio bitrate in kbps (0 = no audio)
# size_factor: relative size multiplier (calibrated from real encodes)

VIDEO_QUALITY_PRESETS_STANDARD = [
    # (crf, resolution, audio_kbps, size_factor)
    # --- TIER 1: Maximum Quality ---
    (18, 100, 192, 1.00),    # 0: Near-lossless
    (20, 100, 192, 0.78),    # 1: Very high
    (22, 100, 160, 0.62),    # 2: High
    (23, 100, 160, 0.53),    # 3: Good+
    
    # --- TIER 2: Good Quality ---
    (24, 100, 128, 0.45),    # 4: Good
    (25, 100, 128, 0.39),    # 5: Medium-high
    (26, 100, 128, 0.33),    # 6: Medium+
    
    # --- TIER 3: Medium Quality ---
    (27, 100, 96, 0.28),     # 7: Medium
    (28, 100, 96, 0.24),     # 8: Medium - REFERENCE PRESET
    (29, 100, 96, 0.21),     # 9: Medium-
    (30, 100, 64, 0.18),     # 10: Lower medium
    
    # --- TIER 4: Low Quality ---
    (32, 100, 64, 0.14),     # 11: Low+
    (34, 100, 48, 0.11),     # 12: Low
    (36, 100, 48, 0.08),     # 13: Low-
    (38, 100, 32, 0.06),     # 14: Very low
    (42, 100, 32, 0.04),     # 15: Minimum
]

VIDEO_QUALITY_PRESETS_AUTORESIZE = [
    # (crf, resolution, audio_kbps, size_factor)
    # --- TIER 1: Maximum Quality ---
    (18, 100, 192, 1.00),    # 0: Near-lossless
    (20, 100, 192, 0.78),    # 1: Very high
    (22, 100, 160, 0.62),    # 2: High
    (23, 100, 160, 0.53),    # 3: Good+
    
    # --- TIER 2: Good Quality ---
    (24, 100, 128, 0.45),    # 4: Good
    (25, 100, 128, 0.39),    # 5: Medium-high
    (26, 100, 128, 0.33),    # 6: Medium+
    
    # --- TIER 3: Medium Quality ---
    (27, 100, 96, 0.28),     # 7: Medium
    (28, 100, 96, 0.24),     # 8: Medium - REFERENCE PRESET
    (29, 100, 96, 0.21),     # 9: Medium-
    (30, 100, 64, 0.18),     # 10: Lower medium
    
    # --- TIER 3.5: Resolution scaling (before low quality) ---
    (28, 90, 96, 0.19),      # 11: Medium @ 90% res
    (28, 80, 96, 0.15),      # 12: Medium @ 80% res
    (28, 70, 64, 0.11),      # 13: Medium @ 70% res
    (28, 60, 64, 0.08),      # 14: Medium @ 60% res
    
    # --- TIER 4: Low Quality (last resort) ---
    (32, 100, 64, 0.14),     # 15: Low+
    (34, 100, 48, 0.11),     # 16: Low
    (36, 100, 48, 0.08),     # 17: Low-
    (38, 100, 32, 0.06),     # 18: Very low
    (42, 100, 32, 0.04),     # 19: Minimum
]

VIDEO_REFERENCE_PRESET_IDX = 8


# =============================================================================
# GIF SIZE ESTIMATION UTILITIES
# =============================================================================

def get_video_frame_rate(file_path: str) -> float:
    """
    Get video frame rate using FFmpeg probe
    Returns fps as float or 30.0 as default
    """
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        if video_stream:
            fps_str = video_stream.get('r_frame_rate', '30/1')
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                return num / den if den > 0 else 30.0
            return float(fps_str)
    except Exception:
        pass
    return 30.0


def extract_frame_as_gif_sample(file_path: str, time_offset: float, params: dict, temp_dir: str) -> int:
    """
    Extract a single frame at the given time offset, apply GIF-like processing,
    and return the resulting file size in bytes.
    
    This mimics the GIF conversion pipeline to get accurate per-frame size estimates.
    """
    temp_output = os.path.join(temp_dir, f"frame_sample_{time_offset:.3f}.gif")
    
    try:
        # Build input with seek
        input_stream = ffmpeg.input(file_path, ss=time_offset)
        
        # Apply same filters as GIF conversion
        fps = params.get('ffmpeg_fps', 15)
        colors = params.get('ffmpeg_colors', 256)
        
        # Get dimensions for resize calculation
        original_width, original_height = get_video_dimensions(file_path)
        resize_mode = params.get('gif_resize_mode', 'No resize')
        resize_values = params.get('gif_resize_values', [])
        
        # Apply resize if specified
        if resize_mode != 'No resize' and resize_values:
            resize_value = resize_values[0]
            if isinstance(resize_value, str) and resize_value.startswith('L'):
                target_longer_edge = int(resize_value[1:])
                new_w, new_h = calculate_longer_edge_resize(original_width, original_height, target_longer_edge)
                if new_w != original_width:
                    input_stream = ffmpeg.filter(input_stream, 'scale', str(new_w), str(new_h))
            elif resize_mode == 'By ratio (percent)':
                if resize_value.endswith('%'):
                    percent = float(resize_value[:-1]) / 100.0
                    new_width = int(original_width * percent)
                    new_width = clamp_resize_width(original_width, new_width)
                    input_stream = ffmpeg.filter(input_stream, 'scale', str(new_width), '-2')
            elif resize_mode == 'By width (pixels)':
                new_width = int(resize_value)
                new_width = clamp_resize_width(original_width, new_width)
                input_stream = ffmpeg.filter(input_stream, 'scale', str(new_width), '-2')
            elif resize_mode == 'By longer edge (pixels)':
                if isinstance(resize_value, str) and resize_value.startswith('L'):
                    target_longer_edge = int(resize_value[1:])
                else:
                    target_longer_edge = int(resize_value)
                new_w, new_h = calculate_longer_edge_resize(original_width, original_height, target_longer_edge)
                if new_w != original_width:
                    input_stream = ffmpeg.filter(input_stream, 'scale', str(new_w), str(new_h))
        
        # FPS filter (single frame, but keeps pipeline consistent)
        input_stream = ffmpeg.filter(input_stream, 'fps', fps=fps)
        
        # Palette generation (single frame palette)
        split = input_stream.split()
        palette = split[0].filter('palettegen', max_colors=colors)
        
        # Palette use with dither
        dither = params.get('ffmpeg_dither', 'sierra2_4a')
        paletteuse_args = {}
        if dither.startswith('bayer:bayer_scale='):
            try:
                scale = int(dither.split('=')[1])
                paletteuse_args['dither'] = 'bayer'
                paletteuse_args['bayer_scale'] = scale
            except:
                paletteuse_args['dither'] = dither
        else:
            paletteuse_args['dither'] = dither
        
        final = ffmpeg.filter([split[1], palette], 'paletteuse', **paletteuse_args)
        
        # Output single frame as GIF
        out = ffmpeg.output(final, temp_output, vframes=1)
        out = ffmpeg.overwrite_output(out)
        
        # Run silently
        ffmpeg.run(out, quiet=True)
        
        if os.path.exists(temp_output):
            size = os.path.getsize(temp_output)
            os.remove(temp_output)
            return size
    except Exception:
        pass
    
    return 0


def estimate_gif_size_fast_preview(file_path: str, params: dict, sample_seconds: float = 2.0) -> dict:
    """
    Fast GIF size estimation by encoding a short preview.
    Much faster than checkpoint sampling (~2-3s vs ~100s) and more accurate
    since it uses actual GIF compression with real inter-frame optimization.
    
    Returns a dict with:
        - estimated_size: int (bytes)
        - sample_size: actual sample file size
        - confidence: estimation confidence level
    """
    duration = get_video_duration(file_path)
    if duration <= 0:
        return {'estimated_size': 0, 'error': 'Could not determine video duration'}
    
    # Calculate effective duration after time cutting and retime
    enable_time_cutting = params.get('enable_time_cutting', False)
    if enable_time_cutting:
        time_start = params.get('time_start', 0.0)
        time_end = params.get('time_end', 1.0)
        effective_duration = (time_end - time_start) * duration
    else:
        effective_duration = duration
    
    # Account for retime
    retime_enabled = params.get('retime_enabled', False) or params.get('enable_retime', False)
    retime_speed = params.get('retime_speed', 1.0)
    if retime_enabled and retime_speed > 0:
        effective_duration = effective_duration / retime_speed
    
    # Use smaller sample if video is very short
    actual_sample_seconds = min(sample_seconds, effective_duration * 0.8)
    if actual_sample_seconds < 0.5:
        # Video too short, use heuristic
        return estimate_gif_size_heuristic(file_path, params)
    
    # Create temp file for sample GIF
    temp_output = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as tmp_file:
            temp_output = tmp_file.name
        
        # Build FFmpeg command for sample encoding (same as full conversion)
        input_args = {}
        
        # Apply time cutting to extract sample from start of effective range
        if enable_time_cutting:
            time_start = params.get('time_start', 0.0)
            input_args['ss'] = time_start * duration
            input_args['t'] = actual_sample_seconds  # Duration of sample
        else:
            input_args['t'] = actual_sample_seconds
        
        input_stream = ffmpeg.input(file_path, **input_args)
        
        # Apply retime
        if retime_enabled and retime_speed != 1.0:
            input_stream = ffmpeg.filter(input_stream, 'setpts', f'PTS/{retime_speed}')
        
        # FPS
        fps = params.get('ffmpeg_fps', 15)
        input_stream = ffmpeg.filter(input_stream, 'fps', fps=fps)
        
        # Resize
        original_width, original_height = get_video_dimensions(file_path)
        resize_mode = params.get('gif_resize_mode', 'No resize')
        resize_values = params.get('gif_resize_values', [])
        
        if resize_mode != 'No resize' and resize_values:
            resize_value = resize_values[0]
            if resize_mode == 'By ratio (percent)':
                if isinstance(resize_value, str) and resize_value.endswith('%'):
                    percent = float(resize_value[:-1]) / 100.0
                else:
                    percent = float(resize_value) / 100.0
                new_width = int(original_width * percent)
                new_width = clamp_resize_width(original_width, new_width)
                input_stream = ffmpeg.filter(input_stream, 'scale', str(new_width), '-2')
            elif resize_mode == 'By width (pixels)':
                new_width = int(resize_value)
                new_width = clamp_resize_width(original_width, new_width)
                input_stream = ffmpeg.filter(input_stream, 'scale', str(new_width), '-2')
            elif resize_mode == 'By longer edge (pixels)':
                if isinstance(resize_value, str) and resize_value.startswith('L'):
                    target = int(resize_value[1:])
                else:
                    target = int(resize_value)
                new_w, new_h = calculate_longer_edge_resize(original_width, original_height, target)
                if new_w != original_width:
                    input_stream = ffmpeg.filter(input_stream, 'scale', str(new_w), str(new_h))
        
        # Palette generation and use (same as full conversion)
        split = input_stream.split()
        colors = params.get('ffmpeg_colors', 256)
        palette = split[0].filter('palettegen', max_colors=colors)
        
        dither = params.get('ffmpeg_dither', 'sierra2_4a')
        paletteuse_args = {}
        if dither.startswith('bayer:bayer_scale='):
            try:
                scale = int(dither.split('=')[1])
                paletteuse_args['dither'] = 'bayer'
                paletteuse_args['bayer_scale'] = scale
            except:
                paletteuse_args['dither'] = dither
        else:
            paletteuse_args['dither'] = dither
        
        final = ffmpeg.filter([split[1], palette], 'paletteuse', **paletteuse_args)
        
        # Output
        out = ffmpeg.output(final, temp_output)
        out = ffmpeg.overwrite_output(out)
        
        # Run encoding
        ffmpeg.run(out, quiet=True)
        
        # Measure sample size
        if os.path.exists(temp_output):
            sample_size = os.path.getsize(temp_output)
            os.remove(temp_output)
            
            # Extrapolate to full duration
            size_per_second = sample_size / actual_sample_seconds
            estimated_size = int(size_per_second * effective_duration)
            
            return {
                'estimated_size': estimated_size,
                'sample_size': sample_size,
                'sample_duration': actual_sample_seconds,
                'total_duration': effective_duration,
                'confidence': 'high',
                'method': 'fast_preview',
            }
        else:
            # Sample encoding failed, use heuristic
            return estimate_gif_size_heuristic(file_path, params)
            
    except Exception as e:
        # Clean up temp file if it exists
        if temp_output and os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except:
                pass
        # Fallback to heuristic
        return estimate_gif_size_heuristic(file_path, params)


def estimate_gif_size_heuristic(file_path: str, params: dict) -> dict:
    """
    Quick heuristic estimation when frame sampling fails.
    Less accurate but faster fallback.
    """
    width, height = get_video_dimensions(file_path)
    duration = get_video_duration(file_path)
    
    if width == 0 or height == 0 or duration == 0:
        return {'estimated_size': 0, 'error': 'Could not determine video properties'}
    
    # Account for time cutting
    enable_time_cutting = params.get('enable_time_cutting', False)
    if enable_time_cutting:
        time_start = params.get('time_start', 0.0)
        time_end = params.get('time_end', 1.0)
        duration = duration * (time_end - time_start)
    
    # Account for retime
    retime_enabled = params.get('retime_enabled', False)
    retime_speed = params.get('retime_speed', 1.0)
    if retime_enabled and retime_speed > 0:
        duration = duration / retime_speed
    
    fps = params.get('ffmpeg_fps', 15)
    colors = params.get('ffmpeg_colors', 256)
    total_frames = int(duration * fps)
    
    # Apply resize
    resize_mode = params.get('gif_resize_mode', 'No resize')
    resize_values = params.get('gif_resize_values', [])
    
    if resize_mode != 'No resize' and resize_values:
        resize_value = resize_values[0]
        if resize_mode == 'By ratio (percent)':
            if isinstance(resize_value, str) and resize_value.endswith('%'):
                percent = float(resize_value[:-1]) / 100.0
            else:
                percent = float(resize_value) / 100.0
            width = int(width * percent)
            height = int(height * percent)
        elif resize_mode == 'By width (pixels)':
            new_width = int(resize_value) if isinstance(resize_value, str) else resize_value
            new_width = min(new_width, width)  # No upscaling
            scale = new_width / width
            width = new_width
            height = int(height * scale)
        elif resize_mode == 'By longer edge (pixels)':
            if isinstance(resize_value, str) and resize_value.startswith('L'):
                target = int(resize_value[1:])
            else:
                target = int(resize_value)
            width, height = calculate_longer_edge_resize(width, height, target)
    
    pixels_per_frame = width * height
    
    # Heuristic: bytes per pixel based on colors and typical GIF compression
    # GIF uses 1 byte per pixel (palette index) + LZW compression (~50-70% of raw)
    # Lower colors = better compression
    color_factor = 0.3 + (colors / 256) * 0.4  # 0.3 to 0.7
    bytes_per_pixel = color_factor
    
    # Inter-frame compression benefit (assume moderate motion)
    inter_frame_factor = 0.75
    
    estimated_size = int(pixels_per_frame * bytes_per_pixel * total_frames * inter_frame_factor)
    
    # Add header overhead
    header_overhead = 800 + (colors * 3)
    estimated_size += header_overhead
    
    return {
        'estimated_size': estimated_size,
        'total_frames': total_frames,
        'dimensions': (width, height),
        'confidence': 'low',
        'method': 'heuristic',
    }



def estimate_all_preset_sizes(file_path: str, base_params: dict, sample_seconds: float = 1.5,
                               auto_resize: bool = False) -> dict:
    """
    Ultra-fast estimation: encode ONE sample at reference preset,
    then calculate ALL preset sizes using pre-computed ratios.
    
    Args:
        auto_resize: If True, uses QUALITY_PRESETS_AUTORESIZE which includes
                     resolution scaling tiers before low quality presets.
    
    Returns dict with:
        - preset_sizes: list of estimated sizes for each preset (bytes)
        - reference_size: actual encoded size at reference preset
        - calibration_time: time taken for the single encode
        - presets_used: the preset list used (for external reference)
    """
    # Select preset list based on auto_resize option
    presets = QUALITY_PRESETS_AUTORESIZE if auto_resize else QUALITY_PRESETS_STANDARD
    
    duration = get_video_duration(file_path)
    if duration <= 0:
        return {'error': 'Could not determine video duration'}
    
    # Calculate effective duration (time cutting + retime)
    enable_time_cutting = base_params.get('enable_time_cutting', False)
    if enable_time_cutting:
        time_start = base_params.get('time_start', 0.0)
        time_end = base_params.get('time_end', 1.0)
        effective_duration = (time_end - time_start) * duration
    else:
        effective_duration = duration
    
    retime_enabled = base_params.get('retime_enabled', False) or base_params.get('enable_retime', False)
    retime_speed = base_params.get('retime_speed', 1.0)
    if retime_enabled and retime_speed > 0:
        effective_duration = effective_duration / retime_speed
    
    # Sample duration
    actual_sample_seconds = min(sample_seconds, effective_duration * 0.8)
    if actual_sample_seconds < 0.3:
        # Video too short, use heuristic for all
        heuristic = estimate_gif_size_heuristic(file_path, base_params)
        base_size = heuristic.get('estimated_size', 1000000)
        preset_sizes = [int(base_size * p[4]) for p in presets]
        return {
            'preset_sizes': preset_sizes,
            'reference_size': base_size,
            'calibration_time': 0,
            'method': 'heuristic_fallback',
            'presets_used': presets,
        }
    
    # Build params for reference preset
    ref_preset = presets[REFERENCE_PRESET_IDX]
    ref_params = base_params.copy()
    ref_params['ffmpeg_dither'] = DITHER_MAP[ref_preset[0]]
    ref_params['ffmpeg_fps'] = ref_preset[1]
    ref_params['ffmpeg_colors'] = ref_preset[2]
    # Resolution: preserve user's resize choice (preset[3] is placeholder at 100%)
    
    # Create temp file for sample
    temp_output = None
    try:
        import time
        start_time = time.time()
        
        with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as tmp_file:
            temp_output = tmp_file.name
        
        # Build FFmpeg command
        input_args = {}
        if enable_time_cutting:
            time_start = base_params.get('time_start', 0.0)
            input_args['ss'] = time_start * duration
        input_args['t'] = actual_sample_seconds
        
        input_stream = ffmpeg.input(file_path, **input_args)
        
        # Retime
        if retime_enabled and retime_speed != 1.0:
            input_stream = ffmpeg.filter(input_stream, 'setpts', f'PTS/{retime_speed}')
        
        # FPS
        input_stream = ffmpeg.filter(input_stream, 'fps', fps=ref_params['ffmpeg_fps'])
        
        # Resize (preserve user's choice)
        original_width, original_height = get_video_dimensions(file_path)
        resize_mode = base_params.get('gif_resize_mode', 'No resize')
        resize_values = base_params.get('gif_resize_values', [])
        
        if resize_mode != 'No resize' and resize_values:
            resize_value = resize_values[0]
            if resize_mode == 'By ratio (percent)':
                if isinstance(resize_value, str) and resize_value.endswith('%'):
                    percent = float(resize_value[:-1]) / 100.0
                else:
                    percent = float(resize_value) / 100.0
                new_width = int(original_width * percent)
                new_width = clamp_resize_width(original_width, new_width)
                input_stream = ffmpeg.filter(input_stream, 'scale', str(new_width), '-2')
            elif resize_mode == 'By width (pixels)':
                new_width = int(resize_value)
                new_width = clamp_resize_width(original_width, new_width)
                input_stream = ffmpeg.filter(input_stream, 'scale', str(new_width), '-2')
            elif resize_mode == 'By longer edge (pixels)':
                if isinstance(resize_value, str) and resize_value.startswith('L'):
                    target = int(resize_value[1:])
                else:
                    target = int(resize_value)
                new_w, new_h = calculate_longer_edge_resize(original_width, original_height, target)
                if new_w != original_width:
                    input_stream = ffmpeg.filter(input_stream, 'scale', str(new_w), str(new_h))
        
        # Palette generation
        split = input_stream.split()
        palette = split[0].filter('palettegen', max_colors=ref_params['ffmpeg_colors'])
        
        # Palette use with dither
        dither = ref_params['ffmpeg_dither']
        paletteuse_args = {}
        if dither.startswith('bayer:bayer_scale='):
            try:
                scale = int(dither.split('=')[1])
                paletteuse_args['dither'] = 'bayer'
                paletteuse_args['bayer_scale'] = scale
            except:
                paletteuse_args['dither'] = dither
        else:
            paletteuse_args['dither'] = dither
        
        final = ffmpeg.filter([split[1], palette], 'paletteuse', **paletteuse_args)
        
        # Output
        out = ffmpeg.output(final, temp_output)
        out = ffmpeg.overwrite_output(out)
        ffmpeg.run(out, quiet=True)
        
        calibration_time = time.time() - start_time
        
        # Measure reference size
        if os.path.exists(temp_output):
            sample_size = os.path.getsize(temp_output)
            os.remove(temp_output)
            
            # Extrapolate reference size to full duration
            size_per_second = sample_size / actual_sample_seconds
            reference_full_size = size_per_second * effective_duration
            
            # Calculate all preset sizes using ratios relative to reference
            ref_factor = presets[REFERENCE_PRESET_IDX][4]
            preset_sizes = []
            for preset in presets:
                # Scale by ratio of this preset's factor to reference factor
                ratio = preset[4] / ref_factor
                preset_sizes.append(int(reference_full_size * ratio))
            
            return {
                'preset_sizes': preset_sizes,
                'reference_size': int(reference_full_size),
                'sample_size': sample_size,
                'sample_duration': actual_sample_seconds,
                'total_duration': effective_duration,
                'calibration_time': calibration_time,
                'method': 'calibrated',
                'presets_used': presets,
            }
        else:
            raise Exception("Sample encoding failed")
            
    except Exception as e:
        if temp_output and os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except:
                pass
        # Fallback to heuristic
        heuristic = estimate_gif_size_heuristic(file_path, base_params)
        base_size = heuristic.get('estimated_size', 1000000)
        preset_sizes = [int(base_size * p[4]) for p in presets]
        return {
            'preset_sizes': preset_sizes,
            'reference_size': base_size,
            'calibration_time': 0,
            'method': 'heuristic_fallback',
            'error': str(e),
            'presets_used': presets,
        }


def find_optimal_gif_params_for_size(file_path: str, base_params: dict, target_size_bytes: int, 
                                      status_callback=None, auto_resize: bool = False) -> dict:
    """
    Find optimal GIF parameters to achieve target file size.
    
    Uses a two-phase approach for maximum speed:
    1. Single calibration encode at reference preset (~1.5s)
    2. Binary search through pre-computed preset sizes (instant)
    
    Quality presets degrade in order: dither → colors → fps
    If auto_resize=True, resolution scaling is tried before low quality presets.
    
    Args:
        auto_resize: If True, allows resolution reduction (90%, 80%, 70%, 60%) 
                     before falling back to very low quality settings (colors<=32, fps<=12).
                     Resolution scaling is applied on top of user's resize choice.
    
    Returns optimized params dict with estimated_size and optional resolution_scale.
    """
    
    def log(msg):
        if status_callback:
            status_callback(msg)
    
    log(f"Target size: {target_size_bytes / (1024*1024):.2f} MB")
    log(f"Auto-resize: {'enabled' if auto_resize else 'disabled'}")
    log("Calibrating size estimation...")
    
    # Select preset list based on auto_resize
    presets = QUALITY_PRESETS_AUTORESIZE if auto_resize else QUALITY_PRESETS_STANDARD
    
    # Phase 1: Single calibration encode
    calibration = estimate_all_preset_sizes(file_path, base_params, sample_seconds=1.5, 
                                            auto_resize=auto_resize)
    
    if 'error' in calibration and calibration.get('method') == 'heuristic_fallback':
        log(f"⚠ Using heuristic estimation (encode failed)")
    else:
        log(f"✓ Calibration complete in {calibration.get('calibration_time', 0):.1f}s")
    
    preset_sizes = calibration.get('preset_sizes', [])
    if not preset_sizes:
        log("Error: Could not estimate preset sizes")
        return base_params.copy()
    
    # Log all preset sizes for debugging
    log(f"Preset size estimates ({len(presets)} presets):")
    for i, (preset, size) in enumerate(zip(presets, preset_sizes)):
        dither, fps, colors, res, factor = preset
        res_str = f" @{res}%" if res != 100 else ""
        marker = " ← REF" if i == REFERENCE_PRESET_IDX else ""
        log(f"  [{i:2d}] D{dither} {fps:2d}fps {colors:3d}col{res_str} → {size/(1024*1024):6.2f} MB{marker}")
    
    # Phase 2: Binary search through presets (with budget optimization)
    log(f"Finding optimal preset for target {target_size_bytes / (1024*1024):.2f} MB...")
    
    # Check maximum quality preset size vs target
    max_quality_size = preset_sizes[0]
    size_ratio = max_quality_size / target_size_bytes
    
    # Case 1: Max quality is far below target (<70%) - use maximum quality
    if size_ratio < 0.70:
        log(f"✓ Maximum quality ({max_quality_size/(1024*1024):.2f} MB) is well below target")
        log(f"  Using highest quality settings (no optimization needed)")
        best_idx = 0
    # Case 2: Max quality fits comfortably (70-105%)
    elif size_ratio <= 1.05:
        log(f"✓ Maximum quality fits target!")
        best_idx = 0
    # Case 3: Max quality exceeds target - need to optimize
    else:
        log(f"Maximum quality ({max_quality_size/(1024*1024):.2f} MB) exceeds target - optimizing...")
        
        # Find the best preset using binary search
        left, right = 0, len(presets) - 1
        best_idx = right  # Default to lowest quality if nothing fits
        
        # Quick check: if even minimum preset is too large, use it anyway
        if preset_sizes[-1] > target_size_bytes * 1.05:
            log(f"⚠ Even minimum preset exceeds target: {preset_sizes[-1]/(1024*1024):.2f} MB > {target_size_bytes/(1024*1024):.2f} MB")
            best_idx = len(presets) - 1
        else:
            # Binary search for highest quality preset that fits
            iterations = 0
            while left <= right:
                mid = (left + right) // 2
                est_size = preset_sizes[mid]
                iterations += 1
                
                log(f"  Binary search [{iterations}]: preset[{mid}] = {est_size/(1024*1024):.2f} MB")
                
                if est_size <= target_size_bytes * 1.05:
                    # This preset fits, try higher quality (lower index)
                    best_idx = mid
                    right = mid - 1
                else:
                    # This preset too large, try lower quality (higher index)
                    left = mid + 1
            
            log(f"✓ Binary search complete in {iterations} iterations")
    
    # Build output params from best preset
    best_preset = presets[best_idx]
    dither, fps, colors, resolution, factor = best_preset
    
    optimized_params = base_params.copy()
    optimized_params['ffmpeg_dither'] = DITHER_MAP[dither]
    optimized_params['ffmpeg_fps'] = fps
    optimized_params['ffmpeg_colors'] = colors
    
    # Handle resolution scaling from preset
    if resolution != 100:
        # Store resolution scale factor to apply on top of user's resize choice
        optimized_params['_resolution_scale'] = resolution / 100.0
        log(f"  Resolution scale: {resolution}% (applied on top of user resize)")
    
    estimated_size = preset_sizes[best_idx]
    optimized_params['_estimated_size'] = estimated_size
    optimized_params['_preset_index'] = best_idx
    res_str = f" @{resolution}%" if resolution != 100 else ""
    optimized_params['_preset_info'] = f"D{dither} {fps}fps {colors}col{res_str}"
    optimized_params['_calibration_time'] = calibration.get('calibration_time', 0)
    optimized_params['_auto_resize'] = auto_resize
    optimized_params['_budget_utilization'] = (estimated_size / target_size_bytes) * 100
    
    log(f"✓ Selected preset[{best_idx}]: {optimized_params['_preset_info']}")
    log(f"  Estimated size: {estimated_size/(1024*1024):.2f} MB ({optimized_params['_budget_utilization']:.1f}% of target)")
    
    return optimized_params

def estimate_image_size_at_preset(file_path: str, output_format: str, preset: tuple) -> int:
    """
    Estimate image size by encoding at a specific preset.
    Returns file size in bytes.
    """
    quality, resolution, _ = preset
    
    temp_output = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as tmp_file:
            temp_output = tmp_file.name
        
        # Build FFmpeg command
        input_stream = ffmpeg.input(file_path)
        stream = input_stream
        
        # Apply resolution scaling if needed
        if resolution != 100:
            stream = stream.filter('scale', f'iw*{resolution/100}', f'ih*{resolution/100}')
        
        # Output options based on format
        output_args = {}
        if output_format in ['jpg', 'jpeg']:
            output_args['qscale:v'] = max(1, int(31 - (quality / 100) * 30))  # 1-31 (lower is better)
        elif output_format == 'webp':
            output_args['quality'] = quality
        elif output_format == 'png':
            output_args['compression_level'] = max(0, 9 - int(quality / 11))  # 0-9
        
        stream = ffmpeg.output(stream, temp_output, **output_args)
        stream = ffmpeg.overwrite_output(stream)
        
        # Run FFmpeg silently
        ffmpeg_path = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
        cmd = stream.compile(cmd=ffmpeg_path)
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        
        if result.returncode == 0 and os.path.exists(temp_output):
            return os.path.getsize(temp_output)
        return 0
        
    except Exception as e:
        return 0
    finally:
        if temp_output and os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except:
                pass


def estimate_all_image_preset_sizes(file_path: str, output_format: str, 
                                     auto_resize: bool = False) -> dict:
    """
    Estimate image sizes for all presets using single reference encode + extrapolation.
    """
    presets = IMAGE_QUALITY_PRESETS_AUTORESIZE if auto_resize else IMAGE_QUALITY_PRESETS_STANDARD
    
    import time
    start_time = time.time()
    
    # Encode at reference preset
    ref_preset = presets[IMAGE_REFERENCE_PRESET_IDX]
    reference_size = estimate_image_size_at_preset(file_path, output_format, ref_preset)
    
    if reference_size <= 0:
        # Fallback: estimate based on original file size
        try:
            original_size = os.path.getsize(file_path)
            reference_size = int(original_size * 0.5)  # Assume 50% for reference
        except:
            reference_size = 500000  # 500KB default
    
    # Extrapolate all preset sizes using size_factor ratios
    ref_factor = ref_preset[2]  # size_factor of reference preset
    preset_sizes = []
    
    for preset in presets:
        factor = preset[2]
        estimated = int(reference_size * (factor / ref_factor))
        preset_sizes.append(estimated)
    
    calibration_time = time.time() - start_time
    
    return {
        'preset_sizes': preset_sizes,
        'reference_size': reference_size,
        'calibration_time': calibration_time,
        'presets_used': presets,
    }


def find_optimal_image_params_for_size(file_path: str, output_format: str, target_size_bytes: int,
                                        status_callback=None, auto_resize: bool = False) -> dict:
    """
    Find optimal image parameters to achieve target file size.
    
    Returns dict with:
        - quality: optimal quality value
        - _resolution_scale: resolution multiplier if auto_resize is used
        - _estimated_size: estimated file size
        - _preset_info: human-readable preset description
    """
    
    def log(msg):
        if status_callback:
            status_callback(msg)
    
    log(f"Image target size: {target_size_bytes / (1024*1024):.2f} MB")
    log(f"Auto-resize: {'enabled' if auto_resize else 'disabled'}")
    
    presets = IMAGE_QUALITY_PRESETS_AUTORESIZE if auto_resize else IMAGE_QUALITY_PRESETS_STANDARD
    
    # Get size estimates
    calibration = estimate_all_image_preset_sizes(file_path, output_format, auto_resize)
    preset_sizes = calibration.get('preset_sizes', [])
    
    if not preset_sizes:
        log("Error: Could not estimate preset sizes")
        return {'quality': 75}  # Default fallback
    
    log(f"✓ Calibration complete in {calibration.get('calibration_time', 0):.1f}s")
    
    # Check max quality size vs target
    max_quality_size = preset_sizes[0]
    size_ratio = max_quality_size / target_size_bytes
    
    if size_ratio < 0.70:
        log(f"✓ Maximum quality fits well below target")
        best_idx = 0
    elif size_ratio <= 1.05:
        log(f"✓ Maximum quality fits target!")
        best_idx = 0
    else:
        # Binary search for best preset
        left, right = 0, len(presets) - 1
        best_idx = right
        
        if preset_sizes[-1] > target_size_bytes * 1.05:
            log(f"⚠ Even minimum preset exceeds target")
            best_idx = len(presets) - 1
        else:
            while left <= right:
                mid = (left + right) // 2
                if preset_sizes[mid] <= target_size_bytes * 1.05:
                    best_idx = mid
                    right = mid - 1
                else:
                    left = mid + 1
    
    # Build output params
    best_preset = presets[best_idx]
    quality, resolution, factor = best_preset
    
    result = {
        'quality': quality,
        '_estimated_size': preset_sizes[best_idx],
        '_preset_index': best_idx,
        '_preset_info': f"Q{quality}",
        '_calibration_time': calibration.get('calibration_time', 0),
        '_auto_resize': auto_resize,
        '_budget_utilization': (preset_sizes[best_idx] / target_size_bytes) * 100,
    }
    
    if resolution != 100:
        result['_resolution_scale'] = resolution / 100.0
        result['_preset_info'] = f"Q{quality} @{resolution}%"
    
    log(f"✓ Selected: {result['_preset_info']}, Est: {preset_sizes[best_idx]/(1024*1024):.2f} MB")
    
    return result


# =============================================================================
# VIDEO MAX SIZE ESTIMATION AND OPTIMIZATION
# =============================================================================

def estimate_video_size_at_preset(file_path: str, preset: tuple, codec: str,
                                   sample_seconds: float = 2.0) -> int:
    """
    Estimate video size by encoding a short sample at a specific preset.
    Returns estimated full video size in bytes.
    """
    crf, resolution, audio_kbps, _ = preset
    
    duration = get_video_duration(file_path)
    if duration <= 0:
        return 0
    
    # Sample a portion of the video
    sample_duration = min(sample_seconds, duration * 0.5)
    if sample_duration < 0.5:
        sample_duration = duration
    
    temp_output = None
    try:
        # Determine output extension based on codec
        if 'webm' in codec.lower() or 'vp9' in codec.lower():
            ext = 'webm'
            vcodec = 'libvpx-vp9'
            acodec = 'libopus'
        elif 'av1' in codec.lower():
            ext = 'webm' if 'webm' in codec.lower() else 'mp4'
            vcodec = 'libaom-av1'
            acodec = 'libopus' if ext == 'webm' else 'aac'
        elif 'h.265' in codec.lower() or 'h265' in codec.lower() or 'hevc' in codec.lower():
            ext = 'mp4'
            vcodec = 'libx265'
            acodec = 'aac'
        else:
            ext = 'mp4'
            vcodec = 'libx264'
            acodec = 'aac'
        
        with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as tmp_file:
            temp_output = tmp_file.name
        
        # Build FFmpeg command
        # Start from middle of video for better representation
        start_time = (duration - sample_duration) / 2
        
        input_stream = ffmpeg.input(file_path, ss=start_time, t=sample_duration)
        video_stream = input_stream.video
        
        # Apply resolution scaling if needed
        if resolution != 100:
            video_stream = video_stream.filter('scale', f'iw*{resolution/100}', f'ih*{resolution/100}')
        
        # Check for audio
        has_audio = has_audio_stream(file_path)
        
        # Output options
        output_args = {
            'vcodec': vcodec,
            'crf': crf,
        }
        
        if vcodec == 'libaom-av1':
            output_args['cpu-used'] = 8  # Fast for estimation
        
        if has_audio and audio_kbps > 0:
            audio_stream = input_stream.audio
            output_args['acodec'] = acodec
            output_args['audio_bitrate'] = f'{audio_kbps}k'
            stream = ffmpeg.output(video_stream, audio_stream, temp_output, **output_args)
        else:
            output_args['an'] = None  # No audio
            stream = ffmpeg.output(video_stream, temp_output, **output_args)
        
        stream = ffmpeg.overwrite_output(stream)
        
        # Run FFmpeg
        ffmpeg_path = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
        cmd = stream.compile(cmd=ffmpeg_path)
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )
        
        if result.returncode == 0 and os.path.exists(temp_output):
            sample_size = os.path.getsize(temp_output)
            # Extrapolate to full video duration
            full_size = int(sample_size * (duration / sample_duration))
            return full_size
        return 0
        
    except Exception as e:
        return 0
    finally:
        if temp_output and os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except:
                pass


def estimate_all_video_preset_sizes(file_path: str, codec: str, base_params: dict,
                                     auto_resize: bool = False) -> dict:
    """
    Estimate video sizes for all presets using single reference encode + extrapolation.
    """
    presets = VIDEO_QUALITY_PRESETS_AUTORESIZE if auto_resize else VIDEO_QUALITY_PRESETS_STANDARD
    
    import time
    start_time = time.time()
    
    # Encode at reference preset
    ref_preset = presets[VIDEO_REFERENCE_PRESET_IDX]
    reference_size = estimate_video_size_at_preset(file_path, ref_preset, codec, sample_seconds=2.0)
    
    if reference_size <= 0:
        # Fallback: estimate based on original file size and duration
        try:
            original_size = os.path.getsize(file_path)
            reference_size = int(original_size * 0.3)  # Assume 30% for reference
        except:
            duration = get_video_duration(file_path)
            reference_size = int(duration * 500000)  # ~500KB per second default
    
    # Extrapolate all preset sizes
    ref_factor = ref_preset[3]  # size_factor of reference preset
    preset_sizes = []
    
    for preset in presets:
        factor = preset[3]
        estimated = int(reference_size * (factor / ref_factor))
        preset_sizes.append(estimated)
    
    calibration_time = time.time() - start_time
    
    return {
        'preset_sizes': preset_sizes,
        'reference_size': reference_size,
        'calibration_time': calibration_time,
        'presets_used': presets,
    }


def find_optimal_video_params_for_size(file_path: str, codec: str, base_params: dict,
                                        target_size_bytes: int, status_callback=None,
                                        auto_resize: bool = False) -> dict:
    """
    Find optimal video parameters to achieve target file size.
    
    Returns dict with:
        - crf: optimal CRF value
        - audio_bitrate: optimal audio bitrate in kbps
        - _resolution_scale: resolution multiplier if auto_resize is used
        - _estimated_size: estimated file size
        - _preset_info: human-readable preset description
    """
    
    def log(msg):
        if status_callback:
            status_callback(msg)
    
    log(f"Video target size: {target_size_bytes / (1024*1024):.2f} MB")
    log(f"Codec: {codec}")
    log(f"Auto-resize: {'enabled' if auto_resize else 'disabled'}")
    
    presets = VIDEO_QUALITY_PRESETS_AUTORESIZE if auto_resize else VIDEO_QUALITY_PRESETS_STANDARD
    
    # Get size estimates
    calibration = estimate_all_video_preset_sizes(file_path, codec, base_params, auto_resize)
    preset_sizes = calibration.get('preset_sizes', [])
    
    if not preset_sizes:
        log("Error: Could not estimate preset sizes")
        return {'crf': 28, 'audio_bitrate': 96}  # Default fallback
    
    log(f"✓ Calibration complete in {calibration.get('calibration_time', 0):.1f}s")
    
    # Check max quality size vs target
    max_quality_size = preset_sizes[0]
    size_ratio = max_quality_size / target_size_bytes
    
    if size_ratio < 0.70:
        log(f"✓ Maximum quality fits well below target")
        best_idx = 0
    elif size_ratio <= 1.05:
        log(f"✓ Maximum quality fits target!")
        best_idx = 0
    else:
        # Binary search for best preset
        left, right = 0, len(presets) - 1
        best_idx = right
        
        if preset_sizes[-1] > target_size_bytes * 1.05:
            log(f"⚠ Even minimum preset exceeds target")
            best_idx = len(presets) - 1
        else:
            while left <= right:
                mid = (left + right) // 2
                if preset_sizes[mid] <= target_size_bytes * 1.05:
                    best_idx = mid
                    right = mid - 1
                else:
                    left = mid + 1
    
    # Build output params
    best_preset = presets[best_idx]
    crf, resolution, audio_kbps, factor = best_preset
    
    result = {
        'crf': crf,
        'audio_bitrate': audio_kbps,
        '_estimated_size': preset_sizes[best_idx],
        '_preset_index': best_idx,
        '_preset_info': f"CRF{crf}",
        '_calibration_time': calibration.get('calibration_time', 0),
        '_auto_resize': auto_resize,
        '_budget_utilization': (preset_sizes[best_idx] / target_size_bytes) * 100,
    }
    
    if resolution != 100:
        result['_resolution_scale'] = resolution / 100.0
        result['_preset_info'] = f"CRF{crf} @{resolution}%"
    
    log(f"✓ Selected: {result['_preset_info']}, Est: {preset_sizes[best_idx]/(1024*1024):.2f} MB")
    
    return result
