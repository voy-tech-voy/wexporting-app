"""
VideoTab - Video conversion tab component.

Extracted from CommandPanel as part of the Mediator-Shell refactoring.
This tab handles video codec, quality, resize, rotation, and time settings.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt

from client.gui.tabs.base_tab import BaseTab
from client.gui.command_group import CommandGroup
from client.gui.custom_spinbox import CustomSpinBox
from client.gui.custom_widgets import (
    RotationButtonRow, ThemedCheckBox,
    CustomTargetSizeSpinBox, VideoCodecSelector, TimeRangeSlider,
    UnifiedVariantInput
)
from client.gui.widgets import EstimatorVersionSelector, CustomPresetGallery
from client.gui.sections import ResizeSection, TargetSizeSection
from client.gui.theme import get_combobox_style
from client.gui.components.info_tooltip import TooltipHoverFilter
from client.gui.components.tooltips.codec_info import CODEC_COMPARISONS

COMBOBOX_STYLE = get_combobox_style(True)  # Default dark mode


class VideoTab(BaseTab):
    """
    Video conversion settings tab.
    
    Provides controls for:
    - Output codec (MP4/H.264, WebM/VP9, etc.)
    - Quality settings (CRF slider or multiple variants)
    - Max file size targeting
    - Resize options (by width, longer edge, ratio)
    - Rotation angle
    - Time cutting (trim start/end)
    - Retiming (speed change)
    """
    
    def __init__(self, parent=None, focus_callback=None, is_dark_mode=True):
        """
        Initialize VideoTab.
        
        Args:
            parent: Parent widget
            focus_callback: Callback for focus management
            is_dark_mode: Initial theme state
        """
        self._focus_callback = focus_callback or (lambda: None)
        self._initial_is_dark = is_dark_mode
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Create the video tab UI elements."""
        layout = self._layout
        layout.setSpacing(8)
        
        # ============================================================
        # SETTINGS FOLDER (Top)
        # ============================================================
        settings_row = QWidget()
        settings_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        settings_h = QHBoxLayout(settings_row)
        settings_h.setContentsMargins(0, 0, 0, 0)
        settings_h.setSpacing(0)
        
        # Settings CommandGroup
        self.codec_group = CommandGroup("")
        self.codec_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.codec_group.get_content_layout().setContentsMargins(16, 16, 16, 16)
        self.codec_group.setMinimumHeight(180)
        settings_h.addWidget(self.codec_group, 1)
        
        layout.addWidget(settings_row)
        
        # --- Codec Selection ---
        self.codec = VideoCodecSelector()
        self.codec.codecChanged.connect(self._on_codec_changed)
        self.codec_group.get_content_layout().insertRow(0, self.codec)
        
        # Add efficiency tooltip
        self.codec_tooltip = TooltipHoverFilter(self.codec, CODEC_COMPARISONS["video"])
        
        # Target Size Section
        self.target_size_section = TargetSizeSection(
            parent=self,
            focus_callback=self._focus_callback,
            default_value=1.0,
            sensitivity=0.01,
            variant_defaults_map="0.5, 1.0, 2.0"  # Single default for all codecs
        )
        self.target_size_section.paramChanged.connect(self._notify_param_change)
        self.target_size_section.setVisible(False)
        self.codec_group.add_row(self.target_size_section)
        
        # Estimator Version Selection (reusable component)
        self.version_selector = EstimatorVersionSelector('video', self)
        self.version_selector.set_format(self.codec.currentText())
        self.codec_group.add_row(self.version_selector)
        
        # --- Multiple qualities ---
        self.multiple_qualities = ThemedCheckBox("Multiple variants")
        self.multiple_qualities.toggled.connect(self._toggle_quality_mode)
        self.codec_group.add_row(self.multiple_qualities)
        
        # --- Quality slider ---
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(0, 100)
        self.quality.setValue(30)
        self.quality.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.quality.setTickInterval(10)
        self.quality.setToolTip("Quality: 100=best quality, 0=worst quality\nRecommended: 70-85 for good balance")
        self.quality_label = QLabel("Quality")
        self.quality_value = QLabel("30")
        self.quality.valueChanged.connect(lambda v: self.quality_value.setText(str(v)))
        
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(self.quality)
        quality_layout.addWidget(self.quality_value)
        self.codec_group.add_row(self.quality_label, quality_layout)
        
        # --- Quality variants ---
        self.quality_variants = UnifiedVariantInput()
        self.quality_variants.setPlaceholderText("e.g., 25,40,70 (quality values 0-100)")
        self.quality_variants.setText("15,23,31")
        self.quality_variants.setVisible(False)
        self.quality_variants_label = QLabel("Quality variants")
        self.quality_variants_label.setVisible(False)
        self.codec_group.add_row(self.quality_variants_label, self.quality_variants)
        
        # --- Spacer to push button to bottom ---
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.codec_group.add_row(spacer)
        
        # --- Custom Preset Button (bottom of settings group) ---
        self._create_preset_button(self.codec_group)

        self._custom_preset_gallery = CustomPresetGallery(['video'], tab_ref=self)
        self._custom_preset_gallery.setVisible(False)
        self.codec_group.main_layout.addWidget(self._custom_preset_gallery)

        # ============================================================
        # TRANSFORM FOLDER (Bottom)
        # ============================================================
        transform_row = QWidget()
        transform_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        transform_h = QHBoxLayout(transform_row)
        transform_h.setContentsMargins(0, 0, 0, 0)
        transform_h.setSpacing(0)
        
        # Transform CommandGroup
        self.transform_group = CommandGroup("")
        self.transform_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.transform_group.get_content_layout().setContentsMargins(16, 16, 16, 16)
        self.transform_group.get_content_layout().setVerticalSpacing(12)
        self.transform_group.setFixedHeight(198)
        transform_h.addWidget(self.transform_group, 1)
        
        layout.addWidget(transform_row)
        
        # === RESIZE SECTION ===
        self.resize_section = ResizeSection(
            parent=self,
            focus_callback=self._focus_callback,
            variant_label="Size variants"
        )
        self.resize_section.paramChanged.connect(self._notify_param_change)
        self.transform_group.add_row(self.resize_section)
        
        # === ROTATION SECTION ===
        self.rotate_container = QWidget()
        rotate_layout = QVBoxLayout(self.rotate_container)
        rotate_layout.setContentsMargins(0, 0, 0, 0)
        
        self.rotation_angle = RotationButtonRow()
        self.rotation_angle.currentTextChanged.connect(lambda _: self._notify_param_change())
        rotate_layout.addWidget(self.rotation_angle)
        
        self.transform_group.add_row(self.rotate_container)
        
        # === TIME SECTION ===
        self.time_container = QWidget()
        time_layout = QVBoxLayout(self.time_container)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(12)
        
        # Time range row
        self.enable_time_cutting = ThemedCheckBox("Time range")
        self.enable_time_cutting.toggled.connect(self._toggle_time_cutting)
        
        self.time_range_slider = TimeRangeSlider(is_dark_mode=self._initial_is_dark)
        self.time_range_slider.setRange(0.0, 1.0)
        self.time_range_slider.setStartValue(0.0)
        self.time_range_slider.setEndValue(1.0)
        self.time_range_slider.setToolTip("Drag handles to set start/end times (0%=beginning, 100%=end)")
        self.time_range_slider.setVisible(False)
        
        time_range_row = QHBoxLayout()
        time_range_row.addWidget(self.enable_time_cutting)
        time_range_row.addSpacing(8)
        time_range_row.addWidget(self.time_range_slider, 1)
        time_layout.addLayout(time_range_row)
        
        # Retime row
        self.enable_retime = ThemedCheckBox("Retime")
        self.enable_retime.toggled.connect(self._toggle_retime)
        
        self.retime_slider = QSlider(Qt.Orientation.Horizontal)
        self.retime_slider.setRange(10, 30)
        self.retime_slider.setValue(10)
        self.retime_slider.setSingleStep(1)
        self.retime_slider.setVisible(False)
        self.retime_value_label = QLabel("1.0x")
        self.retime_value_label.setVisible(False)
        self.retime_slider.valueChanged.connect(lambda v: self.retime_value_label.setText(f"{v/10:.1f}x"))
        
        retime_row = QHBoxLayout()
        retime_row.addWidget(self.enable_retime)
        retime_row.addSpacing(8)
        retime_row.addWidget(self.retime_slider, 1)
        retime_row.addWidget(self.retime_value_label)
        time_layout.addLayout(retime_row)
        
        self.transform_group.add_row(self.time_container)
        
        # Initially show resize, hide rotate and time
        self.rotate_container.setVisible(False)
        self.time_container.setVisible(False)
    
    def get_params(self) -> dict:
        """Collect video conversion parameters from UI."""
        # Get resize params from ResizeSection
        resize_params = self.resize_section.get_params()
        
        # Get target size params from TargetSizeSection
        target_params = self.target_size_section.get_params()
        
        # Determine if Max Size mode is active
        is_max_size_mode = self.target_size_section.isVisible()
        
        params = {
            'type': 'video',
            'codec': self.codec.currentText(),
            'quality': self.quality.value(),
            # Manual-mode quality params are only valid in manual mode
            'multiple_qualities': False if is_max_size_mode else self.multiple_qualities.isChecked(),
            'quality_variants': [] if is_max_size_mode else self._parse_variants(self.quality_variants.text()),
            'video_max_size_mb': target_params['target_size_mb'],
            'video_auto_resize': target_params['auto_resize'],
            'video_size_mode': 'max_size' if is_max_size_mode else 'manual',
            'multiple_max_sizes': target_params['multiple_variants'],
            'max_size_variants': target_params['size_variants'],
            'rotation_angle': self.rotation_angle.currentText(),
            'enable_time_cutting': self.enable_time_cutting.isChecked(),
            'time_start': self.time_range_slider.getStartValue() if self.enable_time_cutting.isChecked() else 0.0,
            'time_end': self.time_range_slider.getEndValue() if self.enable_time_cutting.isChecked() else 1.0,
            'retime_enabled': self.enable_retime.isChecked(),
            'retime_speed': self.retime_slider.value() / 10.0 if self.enable_retime.isChecked() else 1.0
        }
        # Merge resize params
        params.update(resize_params)
        
        # Add estimator version from version selector (dev mode)
        version = self.version_selector.get_selected_version()
        if version:
            params['estimator_version'] = version
        
        return params

    def restore_settings(self, settings: dict, switch_mode: bool = True):
        """
        Restore Lab Mode settings to UI controls.

        Args:
            settings: Dictionary of saved Lab Mode settings
            switch_mode: If True (default), automatically switch the UI mode
                         to Max Size or Manual based on the settings. Pass False
                         when called from the preset gallery to keep the gallery
                         visible after applying settings.
        """
        # Restore codec
        if 'codec' in settings:
            self.codec.setCurrentText(settings['codec'])
            
        # Restore quality settings
        if 'quality' in settings:
            self.quality.setValue(int(settings['quality']))
            
        if 'multiple_qualities' in settings:
            self.multiple_qualities.setChecked(settings['multiple_qualities'])
            
        if 'quality_variants' in settings:
            variants = settings['quality_variants']
            if isinstance(variants, list):
                variants_str = ", ".join(map(str, variants))
                self.quality_variants.setText(variants_str)
            else:
                self.quality_variants.setText(str(variants))
            
        # Restore rotation
        if 'rotation_angle' in settings:
            self.rotation_angle.setCurrentText(settings['rotation_angle'])
            
        # Restore time cutting
        if 'enable_time_cutting' in settings:
            enabled = settings['enable_time_cutting']
            self.enable_time_cutting.setChecked(enabled)
            if enabled:
                start = settings.get('time_start', 0.0)
                end = settings.get('time_end', 1.0)
                if hasattr(self.time_range_slider, 'setStartValue'):
                    self.time_range_slider.setStartValue(start)
                if hasattr(self.time_range_slider, 'setEndValue'):
                    self.time_range_slider.setEndValue(end)

        # Restore retime
        if 'retime_enabled' in settings:
            enabled = settings['retime_enabled']
            self.enable_retime.setChecked(enabled)
            if enabled and 'retime_speed' in settings:
                speed = settings['retime_speed']
                # Slider is speed * 10
                self.retime_slider.setValue(int(speed * 10))
            
        # Restore estimator version
        if 'estimator_version' in settings:
            version = settings['estimator_version']
            for i in range(self.version_selector.combo.count()):
                if self.version_selector.combo.itemData(i) == version:
                    self.version_selector.combo.setCurrentIndex(i)
                    break

        # Restore resize section parameters
        resize_params = {
            'resize_mode': settings.get('resize_mode'),
            'resize_value': settings.get('resize_value'),
            'current_resize': settings.get('current_resize'),
            'multiple_resize': settings.get('multiple_resize', False),
            'resize_variants': settings.get('resize_variants', [])
        }
        if any(v is not None for v in resize_params.values()):
            self.resize_section.restore_settings(resize_params)
            
        # Restore target size section
        target_params = {
            'target_size_mb': settings.get('video_max_size_mb'),
            'auto_resize': settings.get('video_auto_resize', False),
            'multiple_variants': settings.get('multiple_max_sizes', False),
            'size_variants': settings.get('max_size_variants', [])
        }
        
        # Restore if we have either a target size OR variants
        if target_params['target_size_mb'] is not None or target_params['size_variants']:
            self.target_size_section.restore_settings(target_params)
            
        # Set visualization mode (Max Size vs Manual) — only when not in gallery
        if switch_mode:
            size_mode = settings.get('video_size_mode', 'manual')
            if size_mode == 'max_size':
                self.set_mode("Max Size")
            else:
                self.set_mode("Manual")
    
    def update_theme(self, is_dark: bool):
        """Apply theme styling to all elements."""
        self._is_dark_theme = is_dark
        
        # Update sections (don't auto-connect to ThemeManager)
        self.resize_section.update_theme(is_dark)
        self.target_size_section.update_theme(is_dark)
        
        # Note: ThemedCheckBox widgets auto-update via ThemeManager signal
        
        # Update time range slider (doesn't auto-connect to ThemeManager)
        if hasattr(self.time_range_slider, 'update_theme'):
            self.time_range_slider.update_theme(is_dark)
    
    def set_mode(self, mode: str):
        """Set the size mode (Max Size, Presets, Manual)."""
        is_max_size = (mode == "Max Size")
        is_manual = (mode == "Manual")
        is_lab_presets = (mode == "Presets") # "Presets" mode triggers the custom lab presets gallery
        is_presets = is_lab_presets
        self._is_max_size_mode = is_max_size  # Track for dev mode features

        if hasattr(self, '_custom_preset_gallery'):
            self._custom_preset_gallery.setVisible(is_lab_presets)
            if is_lab_presets:
                self._custom_preset_gallery.refresh()

        # In Presets mode: show only gallery inside the folder, hide all other rows
        if hasattr(self, 'codec_group'):
            self.codec_group.content_widget.setVisible(not is_lab_presets)

        # Target size section (only visible in Max Size mode)
        self.target_size_section.setVisible(is_max_size)
        
        # Custom preset button hidden when viewing Lab Presets (which have their own presets)
        if hasattr(self, 'custom_preset_btn'):
            self.custom_preset_btn.setVisible(not is_presets)
        
        # Estimator version selector visibility handled by component itself
        
        # Quality controls (only visible in Manual mode, hidden in Max Size)
        self.quality_label.setVisible(is_manual and not self.multiple_qualities.isChecked())
        self.quality.setVisible(is_manual and not self.multiple_qualities.isChecked())
        self.quality_value.setVisible(is_manual and not self.multiple_qualities.isChecked())
        
        # Multiple qualities checkbox (only visible in Manual mode)
        self.multiple_qualities.setVisible(is_manual)
        self.quality_variants_label.setVisible(is_manual and self.multiple_qualities.isChecked())
        self.quality_variants.setVisible(is_manual and self.multiple_qualities.isChecked())


    def set_transform_mode(self, mode: str):
        """Set which transform section is visible (resize, rotate, or time)."""
        self.resize_section.setVisible(mode == 'resize')
        self.rotate_container.setVisible(mode == 'rotate')
        self.time_container.setVisible(mode == 'time')
    
    # -------------------------------------------------------------------------
    # PRIVATE METHODS
    # -------------------------------------------------------------------------
    
    def _on_codec_changed(self, codec: str):
        """Handle codec change - update UI and refresh estimator versions."""
        print(f"[VideoTab] Codec changed to: {codec}")
        
        # Update version selector for new codec
        self.version_selector.set_format(codec)
        
        # Keep label as "Quality" for all codecs
        # Note: The slider value (0-100) is inverted to CRF internally by the converter
        # (100 quality = low CRF, 0 quality = high CRF)
        # Restore visibility state based on current checkbox
        is_multiple = self.multiple_qualities.isChecked()
        self.quality_variants.setVisible(is_multiple and not self._is_max_size_mode)
        self.quality_variants_label.setVisible(is_multiple and not self._is_max_size_mode)
        self._notify_param_change()
    

    
    def _toggle_quality_mode(self, multiple: bool):
        """Toggle between single quality slider and multiple variants."""
        self.quality.setVisible(not multiple)
        self.quality_value.setVisible(not multiple)
        self.quality_label.setVisible(not multiple)
        self.quality_variants.setVisible(multiple)
        self.quality_variants_label.setVisible(multiple)
        self._notify_param_change()
    

    
    def _toggle_time_cutting(self, enabled: bool):
        """Toggle time range slider visibility."""
        self.time_range_slider.setVisible(enabled)
        self._notify_param_change()
    
    def _toggle_retime(self, enabled: bool):
        """Toggle retime slider visibility."""
        self.retime_slider.setVisible(enabled)
        self.retime_value_label.setVisible(enabled)
        self._notify_param_change()
    
    def _parse_variants(self, text: str) -> list:
        """Parse comma-separated variant values as numbers."""
        try:
            result = []
            for v in text.split(','):
                v = v.strip()
                if v:
                    try:
                        result.append(float(v))
                    except ValueError:
                        continue
            return result
        except:
            return []
    

    
    def set_dev_mode(self, is_dev: bool):
        """Enable/disable dev mode features like estimator version selector."""
        self._is_dev_mode = is_dev
        # Version selector handles its own visibility
        self.version_selector.set_dev_mode(is_dev)
