"""
ConversionProgressManager - Modular progress tracking for all conversion modes.

Handles:
- App Mode: Preset vs Lab
- Lab Sub-mode: Max Size vs Manual
- Lab Tab: Image/Video/Loop
- Format validation per mode
- Multi-variant output calculation

Usage Example (Lab Mode - Max Size):
    from client.core.progress_manager import (
        ConversionProgressManager, AppMode, LabTab, LabSubMode
    )
    
    manager = ConversionProgressManager()
    
    # Calculate for Lab Max Size mode (Video tab)
    result = manager.calculate(
        file_list=['video1.mp4', 'video2.mov', 'image.png'],
        app_mode=AppMode.LAB,
        lab_tab=LabTab.VIDEO,
        lab_sub_mode=LabSubMode.MAX_SIZE,
        size_variants=[5.0, 10.0, 15.0],  # 3 target sizes
        resize_variants=['1920x1080', '1280x720']  # 2 resize options
    )
    
    print(result.valid_files)  # ['video1.mp4', 'video2.mov']
    print(result.total_outputs)  # 12 (2 files × 3 sizes × 2 resizes)
    print(manager.get_preview_text())  # "2 valid / 3 total → 12 outputs"

Usage Example (Lab Mode - Manual):
    result = manager.calculate(
        file_list=['video1.mp4', 'video2.mov'],
        app_mode=AppMode.LAB,
        lab_tab=LabTab.VIDEO,
        lab_sub_mode=LabSubMode.MANUAL,
        quality_variants=[18, 23, 28],  # 3 CRF values
        resize_variants=['1920x1080']  # 1 resize option
    )
    
    print(result.total_outputs)  # 6 (2 files × 3 qualities × 1 resize)

Usage Example (Preset Mode):
    from client.plugins.presets.logic.models import PresetDefinition
    
    preset = load_preset('youtube_shorts.yaml')
    
    result = manager.calculate(
        file_list=['video1.mp4', 'video2.mov', 'audio.mp3'],
        app_mode=AppMode.PRESET,
        preset=preset  # Has accepted_extensions=['.mp4', '.mov']
    )
    
    print(result.valid_files)  # ['video1.mp4', 'video2.mov']
    print(result.total_outputs)  # 2 (no variants in preset mode)

Integration with UI:
    # Connect signal to update UI
    manager.totals_changed.connect(update_preview_label)
    
    # On file list change or setting change
    result = manager.calculate(...)
    # Signal emits: totals_changed(valid_count, skipped_count, total_outputs)
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Set, TYPE_CHECKING
import os
from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from client.plugins.presets.logic.models import PresetDefinition


class AppMode(Enum):
    """Top-level application mode."""
    PRESET = "preset"
    LAB = "lab"


class LabSubMode(Enum):
    """Lab mode sub-modes (controlled by side buttons)."""
    MAX_SIZE = "max_size"
    MANUAL = "manual"


class LabTab(Enum):
    """Lab tabs with their indices."""
    IMAGE = 0
    VIDEO = 1
    LOOP = 2


@dataclass
class CalculationResult:
    """Result of progress calculation."""
    valid_files: List[str]           # Files that match format criteria
    skipped_files: List[str]         # Files that don't match format criteria
    total_outputs: int               # Total output files to be generated
    valid_count: int                 # Number of valid input files
    skipped_count: int               # Number of skipped files
    variant_multiplier: int          # How many outputs per valid file


class ConversionProgressManager(QObject):
    """
    Manages progress calculation across all conversion modes.
    
    Responsibilities:
    - Validate files against mode-specific format constraints
    - Calculate total output count based on variants
    - Provide real-time preview of conversion scope
    """
    
    # Signal emitted when totals are recalculated
    totals_changed = pyqtSignal(int, int, int)  # valid_count, skipped_count, total_outputs
    
    # Format mappings for Lab mode tabs
    TAB_FORMATS: Dict[LabTab, Set[str]] = {
        LabTab.IMAGE: {
            '.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'
        },
        LabTab.VIDEO: {
            '.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v', '.wmv'
        },
        LabTab.LOOP: {
            # Loops accept videos + gif
            '.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v', '.wmv', '.gif'
        }
    }
    
    # Type-to-format mapping for preset fallback
    TYPE_FORMATS: Dict[str, Set[str]] = {
        'video': {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v', '.wmv'},
        'image': {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'},
        'audio': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
    }
    
    def __init__(self):
        """Initialize the progress manager."""
        super().__init__()
        self.completed_outputs = 0
        self.total_outputs = 0
        self.valid_files: List[str] = []
        self.skipped_files: List[str] = []
        self._last_result: Optional[CalculationResult] = None
    
    def calculate(
        self,
        file_list: List[str],
        app_mode: AppMode,
        # Lab mode params (optional)
        lab_tab: Optional[LabTab] = None,
        lab_sub_mode: Optional[LabSubMode] = None,
        size_variants: Optional[List] = None,
        resize_variants: Optional[List] = None,
        quality_variants: Optional[List] = None,
        # GIF-specific variants (Loop tab, Manual mode)
        gif_fps_variants: Optional[List] = None,
        gif_colors_variants: Optional[List] = None,
        gif_dither_variants: Optional[List] = None,
        # Preset mode params (optional)
        preset: Optional['PresetDefinition'] = None
    ) -> CalculationResult:
        """
        Calculate valid files and total outputs based on current mode.
        
        Args:
            file_list: List of file paths to process
            app_mode: PRESET or LAB
            lab_tab: IMAGE, VIDEO, or LOOP (required if app_mode=LAB)
            lab_sub_mode: MAX_SIZE or MANUAL (required if app_mode=LAB)
            size_variants: List of size variants (Max Size mode only)
            resize_variants: List of resize variants (both Lab sub-modes)
            quality_variants: List of quality variants (Manual mode only)
            gif_fps_variants: List of FPS variants (Loop tab Manual mode only)
            gif_colors_variants: List of color variants (Loop tab Manual mode only)
            gif_dither_variants: List of dither variants (Loop tab Manual mode only)
            preset: PresetDefinition object (required if app_mode=PRESET)
        
        Returns:
            CalculationResult with valid/skipped files and total outputs
        """
        if app_mode == AppMode.LAB:
            result = self._calculate_lab_mode(
                file_list=file_list,
                lab_tab=lab_tab,
                lab_sub_mode=lab_sub_mode,
                size_variants=size_variants or [],
                resize_variants=resize_variants or [],
                quality_variants=quality_variants or [],
                gif_fps_variants=gif_fps_variants or [],
                gif_colors_variants=gif_colors_variants or [],
                gif_dither_variants=gif_dither_variants or []
            )
        elif app_mode == AppMode.PRESET:
            result = self._calculate_preset_mode(
                file_list=file_list,
                preset=preset
            )
        else:
            raise ValueError(f"Unknown app_mode: {app_mode}")
        
        # Store result and emit signal
        self._last_result = result
        self.total_outputs = result.total_outputs
        self.valid_files = result.valid_files
        self.skipped_files = result.skipped_files
        self.totals_changed.emit(result.valid_count, result.skipped_count, result.total_outputs)
        
        return result
    
    def calculate_from_params(self, file_list: List[str], params: Dict) -> CalculationResult:
        """
        Calculate totals from raw conversion params dict (smart extraction).
        Automatically detects mode, tab, sub-mode, and variants from params.
        
        Args:
            file_list: List of file paths to process
            params: Conversion parameters dictionary from CommandPanel
        
        Returns:
            CalculationResult with valid/skipped files and total outputs
        """
        # Always reset before new calculation to ensure clean state
        self.reset()
        
        # Determine conversion mode (tab)
        conversion_type = params.get('conversion_type', params.get('type', 'video'))
        lab_tab_map = {'image': LabTab.IMAGE, 'video': LabTab.VIDEO, 'loop': LabTab.LOOP}
        lab_tab = lab_tab_map.get(conversion_type, LabTab.VIDEO)
        
        # Determine sub-mode (Max Size vs Manual)
        size_mode = params.get('video_size_mode') or params.get('image_size_mode') or params.get('gif_size_mode')
        lab_sub_mode = LabSubMode.MAX_SIZE if size_mode == 'max_size' else LabSubMode.MANUAL
        
        # Extract variants
        size_variants = []
        if lab_sub_mode == LabSubMode.MAX_SIZE:
            # Max Size mode variants
            if params.get('multiple_max_sizes'):
                size_variants = params.get('max_size_variants', [])
            elif params.get('multiple_size_variants'):
                size_variants = params.get('size_variants', [])
            elif params.get('gif_multiple_max_sizes'):
                size_variants = params.get('gif_max_size_variants', [])
            else:
                # Single size
                size_mb = params.get('video_max_size_mb') or params.get('image_max_size_mb') or params.get('gif_max_size_mb')
                if size_mb:
                    size_variants = [size_mb]
        
        quality_variants = []
        if lab_sub_mode == LabSubMode.MANUAL:
            # Manual mode variants - check both image and video param names
            # Images use: multiple_qualities, quality_variants
            # Videos use: webm_multiple_variants, webm_quality_variants
            if params.get('multiple_qualities'):
                quality_variants = params.get('quality_variants', [])
            elif params.get('webm_multiple_variants'):
                quality_variants = params.get('webm_quality_variants', [])
            else:
                quality = params.get('webm_quality') or params.get('quality') or params.get('crf')
                if quality is not None:
                    quality_variants = [quality]
        
        # Extract resize variants (available in both modes)
        resize_variants = []
        if params.get('multiple_resize') or params.get('multiple_size_variants'):
            resize_variants = params.get('resize_variants', []) or params.get('video_variants', [])
        elif params.get('current_resize') and params.get('current_resize') != "No resize":
            resize_variants = [params.get('current_resize')]
        
        # GIF-specific variants (Manual mode only, for Loop tab)
        gif_fps_variants = []
        gif_colors_variants = []
        gif_dither_variants = []
        
        if lab_tab == LabTab.LOOP and lab_sub_mode == LabSubMode.MANUAL:
            if params.get('gif_multiple_variants'):
                # Multiple GIF variants enabled
                fps_list = params.get('gif_fps_variants', [])
                colors_list = params.get('gif_colors_variants', [])
                dither_list = params.get('gif_dither_variants', [])
                
                gif_fps_variants = [int(x) for x in fps_list] if fps_list else []
                gif_colors_variants = [int(x) for x in colors_list] if colors_list else []
                gif_dither_variants = [int(x) for x in dither_list] if dither_list else []
        
        # Delegate to main calculate method
        return self.calculate(
            file_list=file_list,
            app_mode=AppMode.LAB,
            lab_tab=lab_tab,
            lab_sub_mode=lab_sub_mode,
            size_variants=size_variants,
            resize_variants=resize_variants,
            quality_variants=quality_variants,
            gif_fps_variants=gif_fps_variants,
            gif_colors_variants=gif_colors_variants,
            gif_dither_variants=gif_dither_variants
        )
    
    def _calculate_lab_mode(
        self,
        file_list: List[str],
        lab_tab: LabTab,
        lab_sub_mode: LabSubMode,
        size_variants: List,
        resize_variants: List,
        quality_variants: List,
        gif_fps_variants: List,
        gif_colors_variants: List,
        gif_dither_variants: List
    ) -> CalculationResult:
        """
        Calculate for Lab mode (tab-specific formats + sub-mode variants).
        
        Lab Sub-modes:
        - MAX_SIZE: total = valid_files × len(size_variants) × len(resize_variants)
        - MANUAL: total = valid_files × len(quality_variants) × len(resize_variants)
        - MANUAL (Loop/GIF with variants): total = valid_files × len(fps) × len(colors) × len(dither) × len(resize)
        """
        if lab_tab is None:
            raise ValueError("lab_tab is required for Lab mode")
        if lab_sub_mode is None:
            raise ValueError("lab_sub_mode is required for Lab mode")
        
        # Get valid formats for this tab
        valid_formats = self.TAB_FORMATS.get(lab_tab, set())
        
        # Filter files by format
        valid_files = []
        skipped_files = []
        
        for file_path in file_list:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in valid_formats:
                valid_files.append(file_path)
            else:
                skipped_files.append(file_path)
        
        valid_count = len(valid_files)
        
        # Calculate variant multiplier based on sub-mode
        if lab_sub_mode == LabSubMode.MAX_SIZE:
            # Max Size: size_variants × resize_variants
            num_sizes = max(len(size_variants), 1)
            num_resizes = max(len(resize_variants), 1)
            variant_multiplier = num_sizes * num_resizes
        
        elif lab_sub_mode == LabSubMode.MANUAL:
            # Check if this is GIF with multiple variants
            has_gif_variants = (lab_tab == LabTab.LOOP and 
                              gif_fps_variants and 
                              gif_colors_variants and 
                              gif_dither_variants)
            
            if has_gif_variants:
                # GIF Manual: fps × colors × dither × resize
                num_fps = max(len(gif_fps_variants), 1)
                num_colors = max(len(gif_colors_variants), 1)
                num_dither = max(len(gif_dither_variants), 1)
                num_resizes = max(len(resize_variants), 1)
                variant_multiplier = num_fps * num_colors * num_dither * num_resizes
            else:
                # Standard Manual: quality_variants × resize_variants
                num_qualities = max(len(quality_variants), 1)
                num_resizes = max(len(resize_variants), 1)
                variant_multiplier = num_qualities * num_resizes
        
        else:
            variant_multiplier = 1
        
        total_outputs = valid_count * variant_multiplier
        
        return CalculationResult(
            valid_files=valid_files,
            skipped_files=skipped_files,
            total_outputs=total_outputs,
            valid_count=valid_count,
            skipped_count=len(skipped_files),
            variant_multiplier=variant_multiplier
        )
    
    def _calculate_preset_mode(
        self,
        file_list: List[str],
        preset: Optional['PresetDefinition']
    ) -> CalculationResult:
        """
        Calculate for Preset mode (uses preset.constraints.accepted_extensions).
        
        Presets have no multi-variant support, so total = valid_count × 1.
        """
        if preset is None:
            raise ValueError("preset is required for Preset mode")
        
        # Get accepted extensions from preset constraints
        constraints = preset.constraints
        accepted_extensions = constraints.accepted_extensions
        accepted_types = constraints.accepted_types
        
        # Build valid format set
        valid_formats = set()
        
        if accepted_extensions:
            # Use explicit extensions from preset
            valid_formats = {ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
                           for ext in accepted_extensions}
        elif accepted_types:
            # Fallback: use type-based format mapping
            for type_name in accepted_types:
                type_formats = self.TYPE_FORMATS.get(type_name.lower(), set())
                valid_formats.update(type_formats)
        else:
            # No constraints - accept all common formats
            for formats in self.TYPE_FORMATS.values():
                valid_formats.update(formats)
        
        # Filter files by format
        valid_files = []
        skipped_files = []
        
        for file_path in file_list:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in valid_formats:
                valid_files.append(file_path)
            else:
                skipped_files.append(file_path)
        
        valid_count = len(valid_files)
        
        # Presets don't have variants - 1 output per input
        variant_multiplier = 1
        total_outputs = valid_count * variant_multiplier
        
        return CalculationResult(
            valid_files=valid_files,
            skipped_files=skipped_files,
            total_outputs=total_outputs,
            valid_count=valid_count,
            skipped_count=len(skipped_files),
            variant_multiplier=variant_multiplier
        )
    
    def reset(self):
        """Reset progress tracking."""
        self.completed_outputs = 0
        self.total_outputs = 0
        self.valid_files = []
        self.skipped_files = []
        self._last_result = None
    
    def increment_progress(self, count: int = 1) -> int:
        """
        Increment completed outputs and return current progress percentage.
        
        Args:
            count: Number of outputs completed (default 1)
        
        Returns:
            Progress percentage (0-100)
        """
        self.completed_outputs += count
        if self.total_outputs == 0:
            return 0
        return min(int((self.completed_outputs / self.total_outputs) * 100), 100)
    
    def get_progress_percentage(self) -> int:
        """Get current progress as percentage (0-100)."""
        if self.total_outputs == 0:
            return 0
        return min(int((self.completed_outputs / self.total_outputs) * 100), 100)
    
    def get_overall_progress(self, current_file_progress: float = 0.0) -> float:
        """
        Get overall progress as a fraction (0.0-1.0) for the green progress bar.
        Includes completed outputs plus fractional progress of current output.
        
        Args:
            current_file_progress: Progress of current file/output (0.0-1.0)
        
        Returns:
            Overall progress as float 0.0-1.0
        """
        if self.total_outputs == 0:
            return 0.0
        
        # Completed outputs + fractional progress of current output
        total_with_current = self.completed_outputs + current_file_progress
        overall = total_with_current / self.total_outputs
        
        return min(max(overall, 0.0), 1.0)  # Clamp to 0.0-1.0
    
    def get_preview_text(self, result: CalculationResult = None) -> str:
        """
        Generate user-friendly preview text from calculation result.
        
        Args:
            result: CalculationResult to format (uses last result if None)
        
        Returns text like:
        - "5 valid / 8 total → 15 outputs" (with variants)
        - "5 valid / 8 total" (no variants)
        - "All 8 files valid → 24 outputs" (all valid with variants)
        - "No compatible files" (none valid)
        """
        if result is None:
            result = self._last_result
        
        if result is None or result.valid_count == 0:
            return "No compatible files"
        
        # Format: "X valid / Y total"
        if result.skipped_count > 0:
            preview = f"{result.valid_count} valid / {result.valid_count + result.skipped_count} total"
        else:
            preview = f"All {result.valid_count} files valid"
        
        # Add output count if variants present
        if result.variant_multiplier > 1:
            preview += f" → {result.total_outputs} outputs"
        
        return preview
