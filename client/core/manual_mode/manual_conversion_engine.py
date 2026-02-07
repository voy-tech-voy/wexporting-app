"""Manual Mode Conversion Engine - Main Orchestrator"""

from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
from typing import List, Dict, Any, Optional

from .converters.image_converter import ImageConverter
from .converters.video_converter import VideoConverter
from .converters.gif_converter import GifConverter
from client.core.suffix_manager import SuffixManager
from client.core.progress_manager import ConversionProgressManager


class ManualModeConversionEngine(QThread):
    """
    Manual mode conversion orchestrator
    
    Pure orchestrator following target_size pattern:
    - File iteration and validation
    - Progress tracking via signals
    - Variant iteration (quality/resize variants)
    - Delegates actual conversion to specialized converters
    
    Does NOT contain conversion logic - that's in converter modules.
    """
    
    # Signals matching target_size and old ConversionEngine
    progress_updated = pyqtSignal(int)                    # Overall percentage (0-100)
    file_progress_updated = pyqtSignal(int, float)        # (file_index, 0.0-1.0) - BLUE bar: single file encoding progress
    status_updated = pyqtSignal(str)                      # Status messages
    file_completed = pyqtSignal(str, str)                 # (source_path, output_path)
    conversion_completed = pyqtSignal(int, int, int, int) # (successful, failed, skipped, stopped)
    
    # Current file index for progress callbacks
    _current_file_index = 0
    
    def __init__(self, files: List[str], params: Dict[str, Any], progress_manager: Optional[ConversionProgressManager] = None):
        """
        Initialize manual mode conversion engine
        
        Args:
            files: List of file paths to convert
            params: Conversion parameters from UI
            progress_manager: Optional progress manager for accurate progress tracking
        """
        super().__init__()
        self.files = files
        self.params = params
        self.progress_manager = progress_manager
        self.should_stop = False
        
        # Initialize converters for all media types
        # Pass progress callback for real-time FFmpeg progress
        self.converters = {
            'image': ImageConverter(params, self._emit_status, self._emit_file_progress),
            'gif': GifConverter(params, self._emit_status, self._emit_file_progress),
            'video': VideoConverter(params, self._emit_status, self._emit_file_progress),
        }
    
    def _emit_file_progress(self, progress: float):
        """Emit file progress (blue bar) - called by converters during encoding"""
        self.file_progress_updated.emit(self._current_file_index, progress)
    
    def run(self):
        """Main conversion loop - file iteration and variant handling"""
        total_files = len(self.files)
        successful = 0
        failed = 0
        skipped = 0
        stopped = 0
        
        print(f"[ManualModeEngine] Starting conversion with {total_files} files")
        print(f"[ManualModeEngine] Params: {self.params}")
        
        # Calculate total outputs for accurate overall progress
        total_outputs = 0
        if self.progress_manager:
            total_outputs = self.progress_manager.total_outputs
        else:
            # Fallback: estimate from params
            total_outputs = total_files
        
        completed_outputs = 0
        
        try:
            for i, file_path in enumerate(self.files):
                if self.should_stop:
                    stopped = total_files - i
                    print(f"[ManualModeEngine] Stopped by user, {stopped} files remaining")
                    break
                
                # Set current file index for progress callbacks (blue bar)
                self._current_file_index = i
                
                # Reset file progress (blue bar starts at 0)
                self.file_progress_updated.emit(i, 0.0)
                self._emit_status(f"Processing: {Path(file_path).name}")
                
                # Route file to appropriate converter
                converter = self._get_converter_for_file(file_path)
                
                if converter is None:
                    skipped += 1
                    self._emit_status(f"Skipped: {Path(file_path).name}")
                    self.file_progress_updated.emit(i, 1.0)
                    continue
                
                # Check if multiple variants are needed
                result = self._convert_with_variants(converter, file_path, i, completed_outputs, total_outputs)
                
                if result['successful'] > 0:
                    successful += result['successful']
                    completed_outputs += result['successful']
                if result['failed'] > 0:
                    failed += result['failed']
                    completed_outputs += result['failed']
                
                # Update overall progress (green bar) based on total outputs
                if total_outputs > 0:
                    progress_pct = int((completed_outputs / total_outputs) * 100)
                    self.progress_updated.emit(progress_pct)
                else:
                    # Fallback to file-based progress
                    progress_pct = int((i + 1) / total_files * 100)
                    self.progress_updated.emit(progress_pct)
            
            # Emit completion
            print(f"[ManualModeEngine] Conversion complete: {successful} successful, {failed} failed, {skipped} skipped, {stopped} stopped")
            self.conversion_completed.emit(successful, failed, skipped, stopped)
            
        except Exception as e:
            self._emit_status(f"Engine error: {str(e)}")
            print(f"[ManualModeEngine] Engine error: {str(e)}")
            import traceback
            traceback.print_exc()
            self.conversion_completed.emit(successful, failed, skipped, stopped)
    
    def _get_converter_for_file(self, file_path: str):
        """
        Route file to appropriate converter based on extension and conversion type
        
        Returns:
            Converter instance or None if file should be skipped
        """
        file_ext = Path(file_path).suffix.lower()
        conversion_type = self.params.get('type', 'image')
        
        # Get converter for conversion type
        converter = self.converters.get(conversion_type)
        if converter and file_ext in converter.get_supported_extensions():
            return converter
        
        # File type doesn't match selected conversion type - skip it
        # (e.g., video file when converting to image format)
        return None
    
    def _convert_with_variants(self, converter, file_path: str, file_index: int, completed_outputs: int, total_outputs: int) -> Dict[str, int]:
        """
        Convert file with quality/resize/GIF variants if enabled
        
        Args:
            converter: Converter instance
            file_path: Source file path
            file_index: Index for progress updates (blue bar - current file)
            completed_outputs: Number of outputs completed so far
            total_outputs: Total number of outputs across all files
            
        Returns:
            Dict with 'successful' and 'failed' counts
        """
        format_ext = converter.get_format_extension()
        
        # Check for multiple variants - support both image and video param names
        # Images use: multiple_qualities, quality_variants
        # Videos use: webm_multiple_variants, webm_quality_variants
        has_quality_variants = (
            (self.params.get('multiple_qualities', False) and self.params.get('quality_variants')) or
            (self.params.get('webm_multiple_variants', False) and self.params.get('webm_quality_variants'))
        )
        has_resize_variants = self.params.get('multiple_resize', False) and self.params.get('resize_variants')
        has_gif_variants = self.params.get('gif_multiple_variants', False)
        
        # DEBUG: Print variant detection
        print(f"[ManualModeEngine] Format: {format_ext}")
        print(f"[ManualModeEngine] multiple_qualities: {self.params.get('multiple_qualities')}, quality_variants: {self.params.get('quality_variants')}")
        print(f"[ManualModeEngine] webm_multiple_variants: {self.params.get('webm_multiple_variants')}, webm_quality_variants: {self.params.get('webm_quality_variants')}")
        print(f"[ManualModeEngine] has_quality_variants: {has_quality_variants}")
        
        # Get variant lists - check both image and video param names
        if has_quality_variants:
            quality_variants = self.params.get('quality_variants') or self.params.get('webm_quality_variants') or [self.params.get('quality', 85)]
        else:
            # Use webm_quality for videos, quality for images
            default_quality = self.params.get('webm_quality') or self.params.get('quality', 85)
            quality_variants = [default_quality]
        
        resize_variants = self.params.get('resize_variants', [None]) if has_resize_variants else [None]
        
        print(f"[ManualModeEngine] quality_variants list: {quality_variants}")
        
        # GIF-specific variants
        fps_variants = [self.params.get('gif_fps', 15)]
        colors_variants = [self.params.get('gif_colors', 256)]
        dither_variants = [self.params.get('gif_dither', 'bayer')]
        
        if has_gif_variants:
            fps_list = self.params.get('gif_fps_variants', [])
            colors_list = self.params.get('gif_colors_variants', [])
            dither_list = self.params.get('gif_dither_variants', [])
            
            if fps_list:
                fps_variants = [int(x) for x in fps_list]
            if colors_list:
                colors_variants = [int(x) for x in colors_list]
            if dither_list:
                dither_variants = [int(x) for x in dither_list]
        
        successful = 0
        failed = 0
        
        # Calculate total variants
        if format_ext == 'gif' and has_gif_variants:
            total_variants = len(fps_variants) * len(colors_variants) * len(dither_variants) * len(resize_variants)
        else:
            total_variants = len(quality_variants) * len(resize_variants)
        
        print(f"[ManualModeEngine] total_variants: {total_variants}")
        
        current_variant = 0
        
        # Store original params
        orig_quality = self.params.get('quality')
        orig_resize = self.params.get('current_resize')
        orig_fps = self.params.get('gif_fps')
        orig_colors = self.params.get('gif_colors')
        orig_dither = self.params.get('gif_dither')
        
        # For GIF, iterate through GIF variants instead of quality
        if format_ext == 'gif' and has_gif_variants:
            for fps in fps_variants:
                if self.should_stop:
                    break
                for colors in colors_variants:
                    if self.should_stop:
                        break
                    for dither in dither_variants:
                        if self.should_stop:
                            break
                        for resize in resize_variants:
                            if self.should_stop:
                                break
                            
                            current_variant += 1
                            
                            # Set GIF params for this variant
                            self.params['gif_fps'] = fps
                            self.params['gif_colors'] = colors
                            self.params['gif_dither'] = dither
                            self.params['current_resize'] = resize
                            
                            # Build variant list for SuffixManager
                            variants = []
                            variants.append({'type': 'fps', 'value': fps})
                            variants.append({'type': 'colors', 'value': colors})
                            variants.append({'type': 'dither', 'value': dither})
                            if has_resize_variants and resize:
                                variants.append({'type': 'resize', 'value': resize})
                            
                            # Generate output path with variants
                            output_path = SuffixManager.get_output_path(
                                file_path,
                                self.params,
                                format_ext,
                                variants
                            )
                            
                            # Convert
                            # Note: File progress (blue bar) is now updated in real-time via converter's progress_callback
                            # The converter calls emit_progress() during FFmpeg encoding
                            
                            # Update overall progress (green bar - across all outputs)
                            if total_outputs > 0:
                                overall_progress = int(((completed_outputs + current_variant) / total_outputs) * 100)
                                self.progress_updated.emit(overall_progress)
                            
                            success = converter.convert(file_path, output_path)
                            
                            # Mark file progress complete for this variant
                            self.file_progress_updated.emit(file_index, 1.0)
                            
                            if success:
                                successful += 1
                                self.file_completed.emit(file_path, output_path)
                                
                                # Update progress manager if available
                                if self.progress_manager:
                                    self.progress_manager.increment_progress(1)
                            else:
                                failed += 1
        else:
            # Standard quality/resize variants for non-GIF (video, image)
            for quality in quality_variants:
                if self.should_stop:
                    break
                
                for resize in resize_variants:
                    if self.should_stop:
                        break
                    
                    current_variant += 1
                    
                    # Set params for this variant
                    self.params['quality'] = quality
                    # Only override current_resize if we're iterating through resize variants
                    if has_resize_variants and resize:
                        self.params['current_resize'] = resize
                    
                    # Build variant list for SuffixManager
                    variants = []
                    if has_quality_variants:
                        variants.append({'type': 'quality', 'value': quality})
                    if has_resize_variants and resize:
                        variants.append({'type': 'resize', 'value': resize})
                    
                    # Generate output path with variants
                    output_path = SuffixManager.get_output_path(
                        file_path,
                        self.params,
                        format_ext,
                        variants if variants else None
                    )
                    
                    # Convert
                    # Note: File progress (blue bar) is now updated in real-time via converter's progress_callback
                    # The converter calls emit_progress() during FFmpeg encoding
                    
                    # Update overall progress (green bar - across all outputs)
                    if total_outputs > 0:
                        overall_progress = int(((completed_outputs + current_variant) / total_outputs) * 100)
                        self.progress_updated.emit(overall_progress)
                    
                    success = converter.convert(file_path, output_path)
                    
                    # Mark file progress complete for this variant
                    self.file_progress_updated.emit(file_index, 1.0)
                    
                    if success:
                        successful += 1
                        self.file_completed.emit(file_path, output_path)
                        
                        # Update progress manager if available
                        if self.progress_manager:
                            self.progress_manager.increment_progress(1)
                    else:
                        failed += 1
        
        # Restore original params
        self.params['quality'] = orig_quality
        self.params['current_resize'] = orig_resize
        self.params['gif_fps'] = orig_fps
        self.params['gif_colors'] = orig_colors
        self.params['gif_dither'] = orig_dither
        
        return {'successful': successful, 'failed': failed}
    
    def _emit_status(self, message: str):
        """Emit status update"""
        self.status_updated.emit(message)
    
    def stop_conversion(self):
        """Request stop and propagate to converters"""
        print("[ManualModeEngine] Stop requested")
        self.should_stop = True
        for converter in self.converters.values():
            converter.stop()
