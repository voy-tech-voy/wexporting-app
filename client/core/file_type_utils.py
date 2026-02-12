"""
File type detection utilities for conversion engine.

Provides functions to detect file types based on extensions and folder scanning.
"""

import os
from pathlib import Path
from typing import List

# Supported file extensions by type
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif', '.svg', '.exr'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}

# Combined dictionary for easy lookup
SUPPORTED_EXTENSIONS = {
    'images': list(IMAGE_EXTENSIONS),
    'videos': list(VIDEO_EXTENSIONS),
    'audio': list(AUDIO_EXTENSIONS)
}


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


def is_audio_file(file_path: str) -> bool:
    """
    Check if a file is an audio file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file is an audio file, False otherwise
    """
    ext = Path(file_path).suffix.lower()
    return ext in AUDIO_EXTENSIONS


def is_supported_file(extension: str) -> bool:
    """
    Check if a file extension is supported for conversion.
    
    Args:
        extension: File extension (with or without leading dot)
        
    Returns:
        True if the extension is supported, False otherwise
    """
    ext = extension if extension.startswith('.') else f'.{extension}'
    ext = ext.lower()
    return ext in IMAGE_EXTENSIONS or ext in VIDEO_EXTENSIONS or ext in AUDIO_EXTENSIONS


def get_file_size(file_path: str) -> str:
    """
    Get human-readable file size.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Formatted file size string (e.g., "1.5 MB")
    """
    try:
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    except:
        return "Unknown size"


def count_supported_files(folder_path: str, include_subfolders: bool = False) -> int:
    """
    Count supported files in a folder.
    
    Args:
        folder_path: Path to the folder
        include_subfolders: If True, search recursively
        
    Returns:
        Number of supported files found
    """
    count = 0
    folder = Path(folder_path)
    
    try:
        if include_subfolders:
            # Recursive search
            for file_path in folder.rglob('*'):
                if file_path.is_file() and is_supported_file(file_path.suffix):
                    count += 1
        else:
            # Only direct files in folder
            for file_path in folder.iterdir():
                if file_path.is_file() and is_supported_file(file_path.suffix):
                    count += 1
    except (PermissionError, OSError):
        pass
        
    return count


def get_supported_files_from_folder(folder_path: str, include_subfolders: bool = False) -> List[str]:
    """
    Get list of supported files from a folder.
    
    Args:
        folder_path: Path to the folder
        include_subfolders: If True, search recursively
        
    Returns:
        List of file paths (as strings)
    """
    files = []
    folder = Path(folder_path)
    
    try:
        if include_subfolders:
            # Recursive search
            for file_path in folder.rglob('*'):
                if file_path.is_file() and is_supported_file(file_path.suffix):
                    files.append(str(file_path))
        else:
            # Only direct files in folder
            for file_path in folder.iterdir():
                if file_path.is_file() and is_supported_file(file_path.suffix):
                    files.append(str(file_path))
                    
        # Sort files for consistent ordering
        files.sort()
        
    except (PermissionError, OSError):
        pass
        
    return files
