"""
Target Size Conversion Engine - Pure Orchestrator
Delegates to format-specific estimators for actual conversion.
"""
from pathlib import Path
from typing import Dict
from PyQt6.QtCore import QThread, pyqtSignal

from .size_estimator_registry import optimize_gif_params
from .suffix_manager import get_output_path
from client.core.file_type_utils import is_image_file, is_video_file



class TargetSizeConversionEngine(QThread):
    """
    Pure orchestrator for target size conversions.
    Handles file iteration, variant iteration, and progress reporting.
    Delegates actual encoding to format-specific encoder modules.
    """
    
    # Signals
    progress_updated = pyqtSignal(int)
    file_progress_updated = pyqtSignal(int, float)
    status_updated = pyqtSignal(str)
    file_completed = pyqtSignal(str, str)
    conversion_completed = pyqtSignal(int, int, int, int)  # successful, failed, skipped, stopped
    
    def __init__(self, files: list, params: Dict):
        super().__init__()
        self.files = files
        self.params = params
        self.should_stop = False
        self.successful_conversions = 0
        self.failed_conversions = 0
        self.skipped_files = 0
        
    def stop_conversion(self):
        """Stop the conversion process immediately."""
        self.should_stop = True
        
    def run(self):
        """Main conversion thread execution."""
        total_files = len(self.files)
        
        # Determine conversion mode from params
        conversion_mode = self._determine_conversion_mode()
        
        for i, file_path in enumerate(self.files):
            if self.should_stop:
                break
            
            # Update progress
            progress = int((i / total_files) * 100)
            self.progress_updated.emit(progress)
            self.status_updated.emit(f"Processing {Path(file_path).name}...")
            
            # Validate file type matches conversion mode
            if not self._is_compatible_file(file_path, conversion_mode):
                self.status_updated.emit(f"⚠ Skipped {Path(file_path).name} (incompatible file type for {conversion_mode} conversion)")
                self.skipped_files += 1
                continue
            
            # Determine file type and convert
            try:
                if is_video_file(file_path):
                    success = self._convert_video(file_path)
                elif is_image_file(file_path):
                    success = self._convert_image(file_path)
                else:
                    # Assume GIF/loop
                    success = self._convert_loop(file_path)
                
                if success:
                    self.successful_conversions += 1
                else:
                    self.failed_conversions += 1
                    
            except Exception as e:
                self.status_updated.emit(f"Error: {str(e)}")
                self.failed_conversions += 1
        
        # Emit completion
        stopped_count = total_files - (self.successful_conversions + self.failed_conversions + self.skipped_files)
        self.conversion_completed.emit(
            self.successful_conversions,
            self.failed_conversions,
            self.skipped_files,
            stopped_count if self.should_stop else 0
        )
    
    def _determine_conversion_mode(self) -> str:
        """
        Determine conversion mode from params.
        
        Returns:
            'image', 'video', or 'loop'
        """
        # Check for image-specific params
        if 'image_max_size_mb' in self.params or 'output_format' in self.params:
            return 'image'
        
        # Check for video-specific params
        if 'codec' in self.params or 'video_max_size_mb' in self.params:
            return 'video'
        
        # Check for loop/GIF params
        if 'gif_max_size_mb' in self.params or self.params.get('format', '').upper() == 'GIF':
            return 'loop'
        
        # Default to video (most common)
        return 'video'
    
    def _is_compatible_file(self, file_path: str, conversion_mode: str) -> bool:
        """
        Check if file type is compatible with conversion mode.
        
        Args:
            file_path: Path to the file
            conversion_mode: 'image', 'video', or 'loop'
        
        Returns:
            True if compatible, False otherwise
        """
        if conversion_mode == 'image':
            return is_image_file(file_path)
        elif conversion_mode == 'video':
            return is_video_file(file_path)
        elif conversion_mode == 'loop':
            # Loop mode accepts both videos and GIFs
            return is_video_file(file_path) or file_path.lower().endswith('.gif')
        
        # If mode is unknown, allow all files (fallback)
        return True
    
    def _get_target_sizes(self, media_type: str = 'video') -> list:
        """Get list of target sizes to process."""
        multiple_max_sizes = self.params.get('multiple_max_sizes', False)
        max_size_variants = self.params.get('max_size_variants', [])
        
        if multiple_max_sizes and max_size_variants:
            return [float(v) for v in max_size_variants if v is not None]
        else:
            # Get appropriate default based on media type
            key_map = {
                'image': 'image_max_size_mb',
                'video': 'video_max_size_mb',
                'loop': 'gif_max_size_mb',  # LoopTab uses gif_max_size_mb for GIF
            }
            default_key = key_map.get(media_type, 'video_max_size_mb')
            return [self.params.get(default_key, 1.0)]
    
    def _get_output_path(self, file_path: str, extension: str, params: Dict = None, target_mb: float = None) -> str:
        """Generate output path using suffix manager."""
        return get_output_path(file_path, self.params, extension, params, target_mb)
    
    def _convert_video(self, file_path: str) -> bool:
        """Convert video using self-contained estimator."""
        from .size_estimator_registry import run_video_conversion, get_video_estimator
        
        try:
            target_sizes = self._get_target_sizes('video')
            codec = self.params.get('codec', 'MP4 (H.264)')
            auto_resize = self.params.get('video_auto_resize', False)
            rotation = self.params.get('rotation_angle', None)
            
            # Get estimator to determine output extension
            estimator = get_video_estimator(codec)
            output_ext = estimator.get_output_extension() if estimator else ('webm' if 'WebM' in codec else 'mp4')
            
            all_success = True
            for target_mb in target_sizes:
                if self.should_stop:
                    return False
                
                target_bytes = int(target_mb * 1024 * 1024)
                
                # Generate output path (use estimator estimate for params)
                multiple_max_sizes = self.params.get('multiple_max_sizes', False)
                params = estimator.estimate(file_path, target_bytes, allow_downscale=auto_resize) if estimator else {}
                output_path = self._get_output_path(
                    file_path,
                    output_ext,
                    params,
                    target_mb if multiple_max_sizes else None
                )
                
                # Delegate to self-contained estimator
                success = run_video_conversion(
                    input_path=file_path,
                    output_path=output_path,
                    target_size_bytes=target_bytes,
                    codec_pref=codec,
                    status_callback=self.status_updated.emit,
                    stop_check=lambda: self.should_stop,
                    rotation=rotation,
                    allow_downscale=auto_resize
                )
                
                if success:
                    self.file_completed.emit(file_path, output_path)
                else:
                    all_success = False
                    break
            
            return all_success
            
        except Exception as e:
            self.status_updated.emit(f"Video conversion error: {str(e)}")
            return False
    
    def _convert_image(self, file_path: str) -> bool:
        """Convert image using self-contained estimator."""
        from .size_estimator_registry import run_image_conversion, get_image_estimator
        
        try:
            target_sizes = self._get_target_sizes('image')
            output_format = self.params.get('format', 'WebP')
            auto_resize = self.params.get('image_auto_resize', False)
            rotation = self.params.get('rotation_angle', None)
            
            # Get estimator to determine output extension
            estimator = get_image_estimator(output_format)
            output_ext = estimator.get_output_extension() if estimator else 'webp'
            
            all_success = True
            for target_mb in target_sizes:
                if self.should_stop:
                    return False
                
                target_bytes = int(target_mb * 1024 * 1024)
                
                # Generate output path (use estimator estimate for params info)
                multiple_max_sizes = self.params.get('multiple_max_sizes', False)
                params = estimator.estimate(file_path, target_bytes, allow_downscale=auto_resize) if estimator else {}
                output_path = self._get_output_path(
                    file_path,
                    output_ext,
                    params,
                    target_mb if multiple_max_sizes else None
                )
                
                # Delegate to self-contained estimator
                success = run_image_conversion(
                    input_path=file_path,
                    output_path=output_path,
                    target_size_bytes=target_bytes,
                    output_format=output_format,
                    status_callback=self.status_updated.emit,
                    stop_check=lambda: self.should_stop,
                    rotation=rotation,
                    allow_downscale=auto_resize
                )
                
                if success:
                    self.file_completed.emit(file_path, output_path)
                else:
                    all_success = False
                    break
            
            return all_success
            
        except Exception as e:
            self.status_updated.emit(f"Image conversion error: {str(e)}")
            return False
    
    def _convert_loop(self, file_path: str) -> bool:
        """Convert to loop format by delegating to loop encoder."""
        from .loop_estimators.loop_encoder import encode_loop
        
        try:
            target_sizes = self._get_target_sizes('loop')
            output_format = self.params.get('loop_format', 'GIF')  # LoopTab passes 'loop_format'
            auto_resize = self.params.get('loop_auto_resize', False)
            
            all_success = True
            for target_mb in target_sizes:
                if self.should_stop:
                    return False
                
                target_bytes = int(target_mb * 1024 * 1024)
                
                # Get optimal params from estimator
                params = optimize_gif_params(
                    file_path,
                    target_bytes,
                    format=output_format,
                    allow_downscale=auto_resize
                )
                
                # Determine output extension
                output_ext = 'gif' if 'GIF' in output_format else 'webm'
                
                # Generate output path
                multiple_max_sizes = self.params.get('multiple_max_sizes', False)
                output_path = self._get_output_path(
                    file_path,
                    output_ext,
                    params,
                    target_mb if multiple_max_sizes else None
                )
                
                # Delegate to encoder
                success = encode_loop(
                    input_path=file_path,
                    output_path=output_path,
                    params=params,
                    output_format=output_format,
                    status_callback=self.status_updated.emit,
                    stop_check=lambda: self.should_stop
                )
                
                if success:
                    self.file_completed.emit(file_path, output_path)
                else:
                    all_success = False
                    break
            
            return all_success
            
        except Exception as e:
            self.status_updated.emit(f"Loop conversion error: {str(e)}")
            return False
