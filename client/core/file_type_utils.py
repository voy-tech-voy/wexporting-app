"""
File type detection utilities for conversion engine.

Provides functions to detect file types based on extensions.
"""

import os
from pathlib import Path

# Supported file extensions by type
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}


def is_image_file(file_path: str) -> bool:
    """
    Check if a file is an image based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file is an image, False otherwise
    """
    ext = Path(file_path).suffix.lower()
    return ext in IMAGE_EXTENSIONS


def is_video_file(file_path: str) -> bool:
    """
    Check if a file is a video based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file is a video, False otherwise
    """
    ext = Path(file_path).suffix.lower()
    return ext in VIDEO_EXTENSIONS
