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
from client.core.progress_manager import ConversionProgressManager



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
    
    def __init__(self, files: list, params: Dict, progress_manager: ConversionProgressManager = None):
        super().__init__()
        self.files = files
        self.params = params
        self.should_stop = False
        self.successful_conversions = 0
        self.failed_conversions = 0
        self.skipped_files = 0
        self.progress_manager = progress_manager or ConversionProgressManager()
        self.completed_outputs = 0  # Track completed output files
        self.total_outputs = 0  # Total output files to generate
        self._current_file_index = 0  # Track current file for progress callback
        
    def _emit_file_progress(self, progress: float):
        """Emit file progress (blue bar) - called by estimators during encoding"""
        self.file_progress_updated.emit(self._current_file_index, progress)
        
    def stop_conversion(self):
        """Stop the conversion process immediately."""
        self.should_stop = True
        
    def run(self):
        """Main conversion thread execution."""
        total_files = len(self.files)
        
        # Determine conversion mode from params
        conversion_mode = self._determine_conversion_mode()
        print(f"[Engine] Conversion mode: {conversion_mode}")
        
        # Calculate total output files (accounting for multi-variants)
        self.total_outputs = self._calculate_total_outputs(conversion_mode)
        print(f"[Engine] Total output files to generate: {self.total_outputs}")
        
        for i, file_path in enumerate(self.files):
            if self.should_stop:
                break
            
            # Set current file index for progress callback
            self._current_file_index = i
            
            # Reset file progress (blue bar starts at 0)
            self.file_progress_updated.emit(i, 0.0)
            
            # Update progress based on completed output files vs total output files
            if self.total_outputs > 0:
                progress = int((self.completed_outputs / self.total_outputs) * 100)
                self.progress_updated.emit(progress)
            
            self.status_updated.emit(f"Processing {Path(file_path).name}...")
            
            # Validate file type matches conversion mode
            if not self._is_compatible_file(file_path, conversion_mode):
                self.status_updated.emit(f"⚠ Skipped {Path(file_path).name} (incompatible file type for {conversion_mode} conversion)")
                self.skipped_files += 1
                continue
            
            # Determine file type and convert based on CONVERSION MODE (not file type!)
            # The user explicitly chooses the conversion type (Image/Video/Loop tab)
            try:
                if conversion_mode == 'loop':
                    success = self._convert_loop(file_path)
                elif conversion_mode == 'image':
                    success = self._convert_image(file_path)
                else:  # 'video' or default
                    success = self._convert_video(file_path)
                
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
        # First check explicit type param (set by tabs)
        if 'conversion_type' in self.params:
            return self.params['conversion_type']
        
        # Otherwise infer from format params
        if self.params.get('loop_format'):
            return 'loop'
        elif self.params.get('image_max_size_mb') is not None:
            return 'image'
        else:
            return 'video'
    
    def _calculate_total_outputs(self, conversion_mode: str) -> int:
        """
        Calculate total number of output files that will be generated.
        Accounts for multi-variant size and resize options.
        
        Returns:
            Total number of output files
        """
        total_input_files = len(self.files)
        
        # Get number of target sizes
        target_sizes = self._get_target_sizes(conversion_mode)
        num_sizes = len(target_sizes) if target_sizes else 1
        
        # Get number of resize variants
        multiple_resize = self.params.get('multiple_resize', False) or self.params.get('multiple_size_variants', False)
        resize_variants = self.params.get('resize_variants', []) or self.params.get('video_variants', [])
        current_resize = self.params.get('current_resize')
        
        if multiple_resize and resize_variants:
            num_resizes = len(resize_variants)
        elif current_resize and current_resize != "No resize":
            num_resizes = 1
        else:
            num_resizes = 1
        
        # Total = input files × size variants × resize variants
        total = total_input_files * num_sizes * num_resizes
        return total
    
    def _determine_conversion_mode_old(self) -> str:
        """
        Determine conversion mode from params.
        
        Returns:
            'image', 'video', or 'loop'
        """
        # First check explicit type param (set by tabs)
        explicit_type = self.params.get('type')
        if explicit_type in ('image', 'video', 'loop'):
            return explicit_type
        
        # Check for image-specific params
        if 'image_max_size_mb' in self.params or 'output_format' in self.params:
            return 'image'
        
        # Check for loop/GIF params (check before video since WebM loops use video_max_size_mb)
        if 'gif_max_size_mb' in self.params or 'loop_format' in self.params:
            return 'loop'
        
        # Check for video-specific params
        if 'codec' in self.params or 'video_max_size_mb' in self.params:
            return 'video'
        
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
            if media_type == 'loop':
                # Loop mode: check format to determine which parameter to use
                # GIF loops use gif_max_size_mb, WebM loops use video_max_size_mb
                loop_format = self.params.get('loop_format', 'GIF')
                if 'webm' in loop_format.lower():
                    default_key = 'video_max_size_mb'
                else:
                    default_key = 'gif_max_size_mb'
            else:
                key_map = {
                    'image': 'image_max_size_mb',
                    'video': 'video_max_size_mb',
                }
                default_key = key_map.get(media_type, 'video_max_size_mb')
            
            return [self.params.get(default_key, 1.0)]
    
    def _get_output_path(self, file_path: str, extension: str, params: Dict = None, target_mb: float = None) -> str:
        """Generate output path using suffix manager."""
        return get_output_path(file_path, self.params, extension, params, target_mb)
    
    def _convert_video(self, file_path: str) -> bool:
        """Convert to video format using self-contained estimator."""
        from .size_estimator_registry import run_video_conversion, get_video_estimator
        from .transform_filter_builder import build_transform_filters
        
        try:
            target_sizes = self._get_target_sizes('video')
            codec = self.params.get('codec', 'MP4 (H.264)')
            auto_resize = self.params.get('video_auto_resize', False)
            rotation = self.params.get('rotation_angle', None)
            estimator_version = self.params.get('estimator_version', None)  # Get version from UI
            
            # Check if multi-variant resize is enabled
            multiple_resize = self.params.get('multiple_resize', False) or self.params.get('multiple_size_variants', False)
            resize_variants = self.params.get('resize_variants', []) or self.params.get('video_variants', [])
            current_resize = self.params.get('current_resize')
            
            # Build list of resize specs to process
            resize_specs = []
            if multiple_resize and resize_variants:
                # Multi-variant mode: use all variants
                resize_specs = resize_variants
            elif current_resize and current_resize != "No resize":
                # Single resize mode: use current_resize
                resize_specs = [current_resize]
            else:
                # No resize: process once with None
                resize_specs = [None]
            
            # Get estimator to determine output extension
            estimator = get_video_estimator(codec, version=estimator_version)
            output_ext = estimator.get_output_extension() if estimator else ('webm' if 'WebM' in codec else 'mp4')
            
            all_success = True
            
            # Iterate over target sizes
            for target_mb in target_sizes:
                if self.should_stop:
                    return False
                
                target_bytes = int(target_mb * 1024 * 1024)
                
                # Iterate over resize variants
                for resize_spec in resize_specs:
                    if self.should_stop:
                        return False
                    
                    # Create modified params with current resize spec
                    variant_params = self.params.copy()
                    variant_params['current_resize'] = resize_spec
                    
                    # Build transform filters for this variant
                    transform_filters = build_transform_filters(variant_params, file_path)
                    
                    # Prepare estimator overrides from transforms
                    est_kwargs = {
                        'transform_filters': transform_filters  # Pass transform filters for duration/dimension calculation
                    }
                    if transform_filters.get('target_dimensions'):
                        w, h = transform_filters['target_dimensions']
                        est_kwargs['override_width'] = w
                        est_kwargs['override_height'] = h
                    
                    # Generate output path (use estimator estimate for params)
                    multiple_max_sizes = self.params.get('multiple_max_sizes', False)
                    params = estimator.estimate(file_path, target_bytes, allow_downscale=auto_resize, **est_kwargs) if estimator else {}
                    
                    # If estimator didn't return resolution (e.g. failure or old version), fallback to transform dims
                    if 'resolution_w' not in params and transform_filters.get('target_dimensions'):
                        w, h = transform_filters['target_dimensions']
                        params['resolution_w'] = w
                        params['resolution_h'] = h
                    
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
                        estimator_version=estimator_version,  # Pass version to run_video_conversion
                        status_callback=self.status_updated.emit,
                        stop_check=lambda: self.should_stop,
                        progress_callback=self._emit_file_progress,
                        rotation=rotation,
                        allow_downscale=auto_resize,
                        transform_filters=transform_filters
                    )
                    
                    if success:
                        self.file_completed.emit(file_path, output_path)
                        self.completed_outputs += 1
                        # Update progress immediately
                        if self.total_outputs > 0:
                            progress = int((self.completed_outputs / self.total_outputs) * 100)
                            self.progress_updated.emit(progress)
                    else:
                        all_success = False
                        # Don't break - continue with other variants
            
            return all_success
            
        except Exception as e:
            self.status_updated.emit(f"Video conversion error: {str(e)}")
            return False
    
    def _convert_image(self, file_path: str) -> bool:
        """Convert image using self-contained estimator."""
        from .size_estimator_registry import run_image_conversion, get_image_estimator
        from client.core.dimension_utils import calculate_target_dimensions
        from client.core.ffmpeg_utils import get_video_dimensions
        
        try:
            target_sizes = self._get_target_sizes('image')
            output_format = self.params.get('format', 'WebP')
            auto_resize = self.params.get('image_auto_resize', False)
            rotation = self.params.get('rotation_angle', None)
            
            # Get original dimensions for resize calculation (ffprobe works for images too)
            try:
                orig_w, orig_h = get_video_dimensions(file_path)
            except:
                orig_w, orig_h = 0, 0
            
            # Check if multi-variant resize is enabled
            multiple_resize = self.params.get('multiple_resize', False) or self.params.get('multiple_size_variants', False)
            resize_variants = self.params.get('resize_variants', []) or self.params.get('video_variants', [])
            current_resize = self.params.get('current_resize')
            allow_upscale = self.params.get('allow_upscaling', False)
            
            # Build list of resize specs to process
            resize_specs = []
            if multiple_resize and resize_variants:
                # Multi-variant mode: use all variants
                resize_specs = resize_variants
            elif current_resize and current_resize != "No resize":
                # Single resize mode: use current_resize
                resize_specs = [current_resize]
            else:
                # No resize: process once with None
                resize_specs = [None]
            
            # Get estimator to determine output extension
            estimator = get_image_estimator(output_format)
            output_ext = estimator.get_output_extension() if estimator else 'webp'
            
            all_success = True
            
            # Iterate over target sizes
            for target_mb in target_sizes:
                if self.should_stop:
                    return False
                
                target_bytes = int(target_mb * 1024 * 1024)
                
                # Iterate over resize variants
                for resize_spec in resize_specs:
                    if self.should_stop:
                        return False
                    
                    # Calculate override dimensions for this variant
                    override_dims = None
                    if resize_spec and orig_w > 0:
                        override_dims = calculate_target_dimensions(
                            file_path="",
                            resize_spec=resize_spec,
                            original_width=orig_w,
                            original_height=orig_h,
                            allow_upscale=allow_upscale
                        )
                    
                    # Prepare estimator kwargs with overrides
                    est_kwargs = {'allow_downscale': auto_resize}
                    if override_dims:
                        est_kwargs['override_width'] = override_dims[0]
                        est_kwargs['override_height'] = override_dims[1]
                    
                    # Generate output path (use estimator estimate for params info)
                    multiple_max_sizes = self.params.get('multiple_max_sizes', False)
                    params = estimator.estimate(file_path, target_bytes, **est_kwargs) if estimator else {}
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
                        progress_callback=self._emit_file_progress,
                        rotation=rotation,
                        allow_downscale=auto_resize,
                        override_width=override_dims[0] if override_dims else None,
                        override_height=override_dims[1] if override_dims else None
                    )
                    
                    if success:
                        self.file_completed.emit(file_path, output_path)
                        self.completed_outputs += 1
                        # Update progress immediately
                        if self.total_outputs > 0:
                            progress = int((self.completed_outputs / self.total_outputs) * 100)
                            self.progress_updated.emit(progress)
                    else:
                        all_success = False
                        # Don't break - continue with other variants
            
            return all_success
            
        except Exception as e:
            self.status_updated.emit(f"Image conversion error: {str(e)}")
            return False
    
    def _convert_loop(self, file_path: str) -> bool:
        """Convert to loop format using self-contained estimator."""
        from .size_estimator_registry import run_loop_conversion, get_loop_estimator
        from .transform_filter_builder import build_transform_filters
        
        try:
            target_sizes = self._get_target_sizes('loop')
            output_format = self.params.get('loop_format', 'GIF')  # LoopTab passes 'loop_format'
            estimator_version = self.params.get('estimator_version', None)  # Get version from UI
            
            # Get auto_resize based on loop format (GIF vs WebM)
            if 'webm' in output_format.lower():
                auto_resize = self.params.get('video_auto_resize', False)
            else:
                auto_resize = self.params.get('gif_auto_resize', False)
            
            # Check if multi-variant resize is enabled
            multiple_resize = self.params.get('multiple_resize', False) or self.params.get('multiple_size_variants', False)
            resize_variants = self.params.get('resize_variants', []) or self.params.get('video_variants', [])
            current_resize = self.params.get('current_resize')
            
            # Build list of resize specs to process
            resize_specs = []
            if multiple_resize and resize_variants:
                # Multi-variant mode: use all variants
                resize_specs = resize_variants
            elif current_resize and current_resize != "No resize":
                # Single resize mode: use current_resize
                resize_specs = [current_resize]
            else:
                # No resize: process once with None
                resize_specs = [None]
            
            # Get estimator to determine output extension
            estimator = get_loop_estimator(output_format, version=estimator_version)
            output_ext = estimator.get_output_extension() if estimator else 'gif'
            
            all_success = True
            
            # Iterate over target sizes
            for target_mb in target_sizes:
                if self.should_stop:
                    return False
                
                target_bytes = int(target_mb * 1024 * 1024)
                
                # Iterate over resize variants
                for resize_spec in resize_specs:
                    if self.should_stop:
                        return False
                    
                    # Create modified params with current resize spec
                    variant_params = self.params.copy()
                    variant_params['current_resize'] = resize_spec
                    
                    # Build transform filters for this variant
                    transform_filters = build_transform_filters(variant_params, file_path)
                    
                    # Prepare estimator overrides from transforms
                    est_kwargs = {
                        'transform_filters': transform_filters  # Pass transform filters for duration/dimension calculation
                    }
                    if transform_filters.get('target_dimensions'):
                        w, h = transform_filters['target_dimensions']
                        est_kwargs['override_width'] = w
                        est_kwargs['override_height'] = h
                    
                    # Generate output path (use estimator estimate for params)
                    multiple_max_sizes = self.params.get('multiple_max_sizes', False)
                    params = estimator.estimate(file_path, target_bytes, allow_downscale=auto_resize, **est_kwargs) if estimator else {}
                    
                    # If estimator didn't return resolution (e.g. failure or old version), fallback to transform dims
                    if 'resolution_w' not in params and transform_filters.get('target_dimensions'):
                        w, h = transform_filters['target_dimensions']
                        params['resolution_w'] = w
                        params['resolution_h'] = h
                    
                    output_path = self._get_output_path(
                        file_path,
                        output_ext,
                        params,
                        target_mb if multiple_max_sizes else None
                    )
                    
                    # Delegate to self-contained estimator
                    success = run_loop_conversion(
                        input_path=file_path,
                        output_path=output_path,
                        target_size_bytes=target_bytes,
                        loop_format=output_format,
                        estimator_version=estimator_version,  # Pass version to run_loop_conversion
                        status_callback=self.status_updated.emit,
                        stop_check=lambda: self.should_stop,
                        progress_callback=self._emit_file_progress,
                        allow_downscale=auto_resize,
                        transform_filters=transform_filters
                    )
                    
                    if success:
                        self.file_completed.emit(file_path, output_path)
                    else:
                        all_success = False
                        # Don't break - continue with other variants
            
            return all_success
            
        except Exception as e:
            self.status_updated.emit(f"Loop conversion error: {str(e)}")
            return False
