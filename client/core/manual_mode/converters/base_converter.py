"""Base converter interface for manual mode"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from pathlib import Path


class BaseConverter(ABC):
    """
    Abstract base class for manual mode converters
    
    Follows the same pattern as target_size estimators but simplified
    for manual mode (no size estimation needed).
    """
    
    def __init__(self, params: Dict[str, Any], status_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize converter
        
        Args:
            params: Conversion parameters from UI
            status_callback: Optional callback for status updates
        """
        self.params = params
        self.status_callback = status_callback
        self.should_stop = False
        self.current_process = None
    
    @abstractmethod
    def convert(self, file_path: str, output_path: str) -> bool:
        """
        Convert a single file
        
        Args:
            file_path: Source file path (absolute)
            output_path: Output file path (absolute, from SuffixManager)
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> set:
        """
        Return set of supported file extensions (lowercase with dot)
        
        Example: {'.jpg', '.jpeg', '.png', '.webp'}
        """
        pass
    
    def emit_status(self, message: str):
        """Emit status update if callback available"""
        if self.status_callback:
            self.status_callback(message)
    
    def stop(self):
        """Request stop and kill current process if running"""
        self.should_stop = True
        if self.current_process:
            try:
                self.current_process.kill()
                self.current_process = None
            except Exception:
                pass
    
    def get_format_extension(self) -> str:
        """
        Get output format extension from params
        
        Returns:
            Format extension without dot (e.g., 'webp', 'mp4')
        """
        return self.params.get('format', 'jpg').lower()
