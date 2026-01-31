"""
Target Size Module - V2 Size Estimators and Conversion Engine.

This module provides dedicated size estimation and conversion for target file sizes.
Separate from the main conversion engine, optimized for 2-pass bitrate encoding.
"""

from .video_estimator import optimize_video_params
from .image_estimator import optimize_image_params
from .loop_estimator import optimize_gif_params
from .suffix_manager import generate_target_size_suffix, get_output_path
from .conversion_engine import TargetSizeConversionEngine

__all__ = [
    'optimize_video_params',
    'optimize_image_params',
    'optimize_gif_params',
    'generate_target_size_suffix',
    'get_output_path',
    'TargetSizeConversionEngine',
]
