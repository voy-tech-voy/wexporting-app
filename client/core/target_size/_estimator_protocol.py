"""
Estimator Protocol - Base interface for all estimators.

Each estimator version implements this interface to define its complete
encoding strategy including multi-step operations.
"""
from abc import ABC, abstractmethod
from typing import Callable, Dict, Optional, Any


class EstimatorProtocol(ABC):
    """
    Base interface for size-optimizing estimators.
    
    Each estimator version (v2, v3, etc.) implements this interface to
    define its complete encoding strategy. This allows different versions
    to use different approaches:
    - v2: 2-pass CBR encoding
    - v3: CRF mode with pre-filters
    - v4: Multi-step with denoise + sharpen
    
    Example usage:
        estimator = MP4H264EstimatorV2()
        params = estimator.estimate(input_path, target_bytes)
        success = estimator.execute(input_path, output_path, target_bytes, ...)
    """
    
    @abstractmethod
    def estimate(
        self, 
        input_path: str, 
        target_size_bytes: int, 
        **options
    ) -> Dict[str, Any]:
        """
        Calculate optimal encoding parameters for target size.
        
        This method analyzes the input file and calculates the best
        parameters to achieve the target file size.
        
        Args:
            input_path: Path to input media file
            target_size_bytes: Target file size in bytes
            **options: Additional options (allow_downscale, rotation, etc.)
        
        Returns:
            Dict containing:
                - Calculated parameters (bitrate, quality, etc.)
                - Metadata for logging/UI display
                - Format/codec information
        """
        pass
    
    @abstractmethod
    def execute(
        self,
        input_path: str,
        output_path: str,
        target_size_bytes: int,
        status_callback: Optional[Callable[[str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None,
        **options
    ) -> bool:
        """
        Execute the complete encoding pipeline.
        
        This method runs the full encoding process, which may include
        multiple passes, filter chains, or other operations specific
        to this estimator version.
        
        Args:
            input_path: Path to input media file
            output_path: Path for output file
            target_size_bytes: Target file size in bytes
            status_callback: Optional callback for status messages
            stop_check: Optional callback that returns True to stop
            **options: Additional options (rotation, allow_downscale, etc.)
        
        Returns:
            True if encoding succeeded, False otherwise
        """
        pass
    
    def get_output_extension(self) -> str:
        """
        Return the file extension for outputs from this estimator.
        
        Override this if the estimator produces a specific format.
        Default implementation should be overridden by subclasses.
        """
        return ""
    
    @property
    def version(self) -> str:
        """Return version string (e.g., 'v2', 'v3')."""
        return "v1"
    
    @property
    def description(self) -> str:
        """Human-readable description of this estimator's approach."""
        return "Base estimator"
