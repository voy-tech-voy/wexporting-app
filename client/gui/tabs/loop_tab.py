"""
LoopTab - Loop conversion tab component (GIF/WebM).

Extracted from CommandPanel as part of the Mediator-Shell refactoring.
This tab handles GIF and WebM loop conversion with format-specific settings.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QSizePolicy, QFormLayout, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from client.gui.tabs.base_tab import BaseTab
from client.gui.command_group import CommandGroup
from client.gui.custom_spinbox import CustomSpinBox
from client.gui.custom_widgets import (
    CustomComboBox, RotationButtonRow, ThemedCheckBox,
    CustomTargetSizeSpinBox, LoopFormatSelector, TimeRangeSlider,
    UnifiedVariantInput
)
from client.gui.sections import ResizeSection
from client.gui.theme import get_combobox_style

COMBOBOX_STYLE = get_combobox_style(True)


class LoopTab(BaseTab):
    """
    Loop conversion settings tab (GIF and WebM).
    
    Provides controls for:
    - Format selection (GIF vs WebM)
    - GIF-specific: FPS, colors, dither quality, blur
    - WebM-specific: quality slider/variants
    - Resize options
    - Rotation angle
    - Time cutting and retiming
    """
    
    # Signal when format changes (GIF <-> WebM)
    format_changed = pyqtSignal(str)
    
    def __init__(self, parent=None, focus_callback=None, is_dark_mode=True):
        """
        Initialize LoopTab.
        
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
        """Create the loop tab UI elements."""
        # Track current mode explicitly (don't infer from widget visibility)
        # Default to "Max Size" to match CommandPanel._init_state() default
        self._current_mode = "Max Size"
        
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
        
        self.settings_group = CommandGroup("")
        self.settings_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.settings_group.get_content_layout().setContentsMargins(16, 16, 16, 16)
        self.settings_group.setMinimumHeight(180)
        settings_h.addWidget(self.settings_group, 1)
        
        layout.addWidget(settings_row)
        
        # --- Format Selector (GIF/WebM) ---
        self.format_selector = LoopFormatSelector()
        self.format_selector.formatChanged.connect(self._on_format_changed)
        self.settings_group.get_content_layout().insertRow(0, self.format_selector)
        
        # --- Max Size ---
        self.max_size_spinbox = CustomTargetSizeSpinBox(
            default_value=2.0,
            on_enter_callback=self._focus_callback
        )
        self.max_size_spinbox.setToolTip("Target maximum file size in megabytes")
        self.max_size_spinbox.setVisible(False)
        self.max_size_label = QLabel("Max Size")
        self.max_size_label.setVisible(False)
        self.settings_group.add_row(self.max_size_label, self.max_size_spinbox)
        
        # --- Auto-resize ---
        self.auto_resize_checkbox = ThemedCheckBox("Auto-resize")
        self.auto_resize_checkbox.setChecked(True)
        self.auto_resize_checkbox.setVisible(False)
        self.settings_group.add_row(self.auto_resize_checkbox)
        
        # --- Estimator Version Dropdown (Dev Mode Only) ---
        self.estimator_version_combo = QComboBox()
        self._populate_estimator_versions('loop')
        self.estimator_version_combo.setToolTip("[DEV] Switch size estimation algorithm")
        self.estimator_version_combo.setVisible(False)
        self.estimator_version_combo.currentIndexChanged.connect(self._on_estimator_version_changed)
        self.estimator_version_label = QLabel("Estimator [DEV]")
        self.estimator_version_label.setVisible(False)
        self.settings_group.add_row(self.estimator_version_label, self.estimator_version_combo)
        
        # ============ GIF CONTROLS CONTAINER ============
        self.gif_controls_container = QWidget()
        gif_layout = QFormLayout(self.gif_controls_container)
        gif_layout.setContentsMargins(0, 0, 0, 0)
        gif_layout.setVerticalSpacing(14)
        
        # Multiple variants toggle
        self.gif_variants_checkbox = ThemedCheckBox("Multiple Variants (FPS, Colors, Qualities)")
        self.gif_variants_checkbox.toggled.connect(self._toggle_gif_variants)
        gif_layout.addRow(self.gif_variants_checkbox)
        
        # FPS
        self.gif_fps = CustomComboBox()
        self.gif_fps.addItems(["10", "12", "15", "18", "24"])
        self.gif_fps.setCurrentText("15")
        self.gif_fps_label = QLabel("FPS")
        gif_layout.addRow(self.gif_fps_label, self.gif_fps)
        
        # FPS Variants
        self.gif_fps_variants = UnifiedVariantInput()
        # self.gif_fps_variants.setPlaceholderText("e.g., 10,15,24")
        self.gif_fps_variants.setText("10,15,24")
        self.gif_fps_variants.setVisible(False)
        self.gif_fps_variants_label = QLabel("FPS variants")
        self.gif_fps_variants_label.setVisible(False)
        gif_layout.addRow(self.gif_fps_variants_label, self.gif_fps_variants)
        
        # Colors
        self.gif_colors = CustomComboBox()
        self.gif_colors.addItems(["8", "16", "32", "64", "128", "256"])
        self.gif_colors.setCurrentText("256")
        self.gif_colors_label = QLabel("Colors")
        gif_layout.addRow(self.gif_colors_label, self.gif_colors)
        
        # Colors Variants
        self.gif_colors_variants = UnifiedVariantInput()
        self.gif_colors_variants.setPlaceholderText("e.g., 64,128,256")
        self.gif_colors_variants.setText("32,64,128")
        self.gif_colors_variants.setVisible(False)
        self.gif_colors_variants_label = QLabel("Colors variants")
        self.gif_colors_variants_label.setVisible(False)
        gif_layout.addRow(self.gif_colors_variants_label, self.gif_colors_variants)
        
        # Dither Quality
        self.gif_dither_slider = QSlider(Qt.Orientation.Horizontal)
        self.gif_dither_slider.setRange(0, 5)
        self.gif_dither_slider.setValue(3)
        self.gif_dither_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.gif_dither_slider.setTickInterval(1)
        self.gif_dither_value = QLabel("3")
        self.gif_dither_slider.valueChanged.connect(lambda v: self.gif_dither_value.setText(str(v)))
        self.gif_dither_label = QLabel("Quality")
        
        dither_layout = QHBoxLayout()
        dither_layout.addWidget(self.gif_dither_slider)
        dither_layout.addWidget(self.gif_dither_value)
        gif_layout.addRow(self.gif_dither_label, dither_layout)
        
        # Dither Variants
        self.gif_dither_variants = UnifiedVariantInput()
        self.gif_dither_variants.setPlaceholderText("e.g., 0,3,5")
        self.gif_dither_variants.setText("0,3,5")
        self.gif_dither_variants.setVisible(False)
        self.gif_dither_variants_label = QLabel("Quality variants (0-5)")
        self.gif_dither_variants_label.setVisible(False)
        gif_layout.addRow(self.gif_dither_variants_label, self.gif_dither_variants)
        
        # Blur
        self.gif_blur = ThemedCheckBox("Reduce banding")
        gif_layout.addRow(self.gif_blur)
        
        # Add GIF container to main layout
        self.settings_group.add_row(self.gif_controls_container)
        
        # ============ WEBM CONTROLS CONTAINER ============
        self.webm_controls_container = QWidget()
        webm_layout = QFormLayout(self.webm_controls_container)
        webm_layout.setContentsMargins(0, 0, 0, 0)
        webm_layout.setVerticalSpacing(14)
        
        # WebM variants toggle
        self.webm_variants_checkbox = ThemedCheckBox("Multiple quality variants")
        self.webm_variants_checkbox.toggled.connect(self._toggle_webm_variants)
        webm_layout.addRow(self.webm_variants_checkbox)
        
        # WebM Quality
        self.webm_quality = QSlider(Qt.Orientation.Horizontal)
        self.webm_quality.setRange(0, 63)
        self.webm_quality.setValue(30)
        self.webm_quality_value = QLabel("30")
        self.webm_quality.valueChanged.connect(lambda v: self.webm_quality_value.setText(str(v)))
        self.webm_quality_label = QLabel("Quality")
        
        webm_quality_layout = QHBoxLayout()
        webm_quality_layout.addWidget(self.webm_quality)
        webm_quality_layout.addWidget(self.webm_quality_value)
        webm_layout.addRow(self.webm_quality_label, webm_quality_layout)
        
        # WebM Quality Variants
        self.webm_quality_variants = UnifiedVariantInput()
        self.webm_quality_variants.setPlaceholderText("e.g., 20,30,40")
        self.webm_quality_variants.setText("20,30,40")  
        self.webm_quality_variants.setVisible(False)
        self.webm_quality_variants_label = QLabel("Quality variants")
        self.webm_quality_variants_label.setVisible(False)
        webm_layout.addRow(self.webm_quality_variants_label, self.webm_quality_variants)
        
        # Add WebM container to main layout
        self.webm_controls_container.setVisible(False)  # Hidden by default
        self.settings_group.add_row(self.webm_controls_container)
        
        # ============================================================
        # TRANSFORM FOLDER (Bottom)
        # ============================================================
        transform_row = QWidget()
        transform_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        transform_h = QHBoxLayout(transform_row)
        transform_h.setContentsMargins(0, 0, 0, 0)
        transform_h.setSpacing(0)
        
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
        
        self.enable_time_cutting = ThemedCheckBox("Time range")
        self.enable_time_cutting.toggled.connect(self._toggle_time_cutting)
        
        self.time_range_slider = TimeRangeSlider(is_dark_mode=self._initial_is_dark)
        self.time_range_slider.setRange(0.0, 1.0)
        self.time_range_slider.setStartValue(0.0)
        self.time_range_slider.setEndValue(1.0)
        self.time_range_slider.setVisible(False)
        
        time_row = QHBoxLayout()
        time_row.addWidget(self.enable_time_cutting)
        time_row.addSpacing(8)
        time_row.addWidget(self.time_range_slider, 1)
        time_layout.addLayout(time_row)
        
        self.enable_retime = ThemedCheckBox("Retime")
        self.enable_retime.toggled.connect(self._toggle_retime)
        
        self.retime_slider = QSlider(Qt.Orientation.Horizontal)
        self.retime_slider.setRange(10, 30)
        self.retime_slider.setValue(10)
        self.retime_slider.setVisible(False)
        self.retime_value_label = QLabel("1.0x")
        self.retime_value_label.setVisible(False)
        self.retime_slider.valueChanged.connect(lambda v: self.retime_value_label.setText(f"{v/10:.1f}x"))
        
        retime_row = QHBoxLayout()
        retime_row.addWidget(self.enable_retime)
        retime_row.addWidget(self.retime_slider)
        retime_row.addWidget(self.retime_value_label)
        time_layout.addLayout(retime_row)
        
        self.transform_group.add_row(self.time_container)
        
        # Initially show resize, hide others
        self.rotate_container.setVisible(False)
        self.time_container.setVisible(False)
        
        # Call _on_format_changed initially to set correct GIF/WebM visibility
        self._on_format_changed(self.format_selector.currentText())
    
    def get_params(self) -> dict:
        """Collect loop conversion parameters from UI."""
        is_gif = self.format_selector.currentText() == "GIF"
        
        # Get resize params from ResizeSection
        resize_params = self.resize_section.get_params()
        
        # Determine if Max Size mode is active
        is_max_size_mode = self.max_size_spinbox.isVisible()
        
        # Common parameters for both formats
        params = {
            'type': 'loop',
            'loop_format': self.format_selector.currentText(),
            'rotation_angle': self.rotation_angle.currentText(),
            'enable_time_cutting': self.enable_time_cutting.isChecked(),
            'time_start': self.time_range_slider.startValue() if self.enable_time_cutting.isChecked() else 0.0,
            'time_end': self.time_range_slider.endValue() if self.enable_time_cutting.isChecked() else 1.0,
            'retime_enabled': self.enable_retime.isChecked(),
            'retime_speed': self.retime_slider.value() / 10.0 if self.enable_retime.isChecked() else 1.0,
        }
        
        # Add format-specific max size parameters
        if is_gif:
            # GIF format uses gif_ prefix
            params.update({
                'gif_max_size_mb': self.max_size_spinbox.value() if is_max_size_mode else None,
                'gif_auto_resize': self.auto_resize_checkbox.isChecked(),
                'gif_size_mode': 'max_size' if is_max_size_mode else 'manual',
            })
        else:
            # WebM format uses video_ prefix (processed as video)
            params.update({
                'video_max_size_mb': self.max_size_spinbox.value() if is_max_size_mode else None,
                'video_auto_resize': self.auto_resize_checkbox.isChecked(),
                'video_size_mode': 'max_size' if is_max_size_mode else 'manual',
            })
        
        # Merge resize params
        params.update(resize_params)
        
        # Add format-specific parameters only
        if is_gif:
            # GIF format: only include gif_* parameters
            params.update({
                'gif_fps': int(self.gif_fps.currentText()),
                'gif_colors': int(self.gif_colors.currentText()),
                'gif_dither': self.gif_dither_slider.value(),
                'gif_blur': self.gif_blur.isChecked(),
                'gif_multiple_variants': self.gif_variants_checkbox.isChecked(),
                'gif_fps_variants': self._parse_variants(self.gif_fps_variants.text()),
                'gif_colors_variants': self._parse_variants(self.gif_colors_variants.text()),
                'gif_dither_variants': self._parse_variants(self.gif_dither_variants.text()),
            })
        else:
            # WebM format: only include webm_* parameters
            params.update({
                'webm_quality': self.webm_quality.value(),
                'webm_multiple_variants': self.webm_variants_checkbox.isChecked(),
                'webm_quality_variants': self._parse_variants(self.webm_quality_variants.text()),
            })
        
        return params
    
    def update_theme(self, is_dark: bool):
        """Apply theme styling to all elements."""
        self._is_dark_theme = is_dark
        
        # Update ResizeSection (doesn't auto-connect to ThemeManager)
        self.resize_section.update_theme(is_dark)
        
        # Note: CustomComboBox widgets auto-update via ThemeManager signal
        # No need to manually update: gif_fps, gif_colors
        
        # Note: ThemedCheckBox widgets auto-update via ThemeManager signal
        # No need to manually update: auto_resize_checkbox, gif_variants_checkbox, 
        # gif_blur, webm_variants_checkbox, enable_time_cutting, enable_retime
        
        # Update time range slider (doesn't auto-connect to ThemeManager)
        if hasattr(self.time_range_slider, 'update_theme'):
            self.time_range_slider.update_theme(is_dark)
    
    def _update_format_visibility(self):
        """
        Centralized method to update format-specific control visibility.
        Uses container widgets for clean, reliable visibility switching.
        Also handles single vs variant control visibility within each container.
        """
        # Determine current format
        current_format = self.format_selector.currentText()
        is_gif = (current_format == "GIF")
        
        # Use stored mode instead of inferring from widget visibility
        is_manual = (self._current_mode == "Manual")
        
        # Show/hide entire containers based on format and mode
        self.gif_controls_container.setVisible(is_gif and is_manual)
        self.webm_controls_container.setVisible(not is_gif and is_manual)
        
        # Handle GIF variant controls (single vs multi-variant)
        if is_gif and is_manual:
            gif_variants_on = self.gif_variants_checkbox.isChecked()
            
            # FPS: show single OR variant, never both
            self.gif_fps_label.setVisible(not gif_variants_on)
            self.gif_fps.setVisible(not gif_variants_on)
            self.gif_fps_variants_label.setVisible(gif_variants_on)
            self.gif_fps_variants.setVisible(gif_variants_on)
            
            # Colors: show single OR variant, never both
            self.gif_colors_label.setVisible(not gif_variants_on)
            self.gif_colors.setVisible(not gif_variants_on)
            self.gif_colors_variants_label.setVisible(gif_variants_on)
            self.gif_colors_variants.setVisible(gif_variants_on)
            
            # Dither/Quality: show single OR variant, never both
            self.gif_dither_label.setVisible(not gif_variants_on)
            self.gif_dither_slider.setVisible(not gif_variants_on)
            self.gif_dither_value.setVisible(not gif_variants_on)
            self.gif_dither_variants_label.setVisible(gif_variants_on)
            self.gif_dither_variants.setVisible(gif_variants_on)
        
        # Handle WebM variant controls (single vs multi-variant)
        if not is_gif and is_manual:
            webm_variants_on = self.webm_variants_checkbox.isChecked()
            
            # Quality: show single OR variant, never both
            self.webm_quality.setVisible(not webm_variants_on)
            self.webm_quality_value.setVisible(not webm_variants_on)
            self.webm_quality_variants.setVisible(webm_variants_on)
    
    def set_mode(self, mode: str):
        """Set the size mode (Max Size, Presets, Manual)."""
        # Store mode explicitly
        self._current_mode = mode
        self._is_max_size_mode = (mode == "Max Size")  # Track for dev mode features
        
        is_max_size = (mode == "Max Size")
        
        # Max size controls (only these visible in Max Size mode)
        self.max_size_label.setVisible(is_max_size)
        self.max_size_spinbox.setVisible(is_max_size)
        self.auto_resize_checkbox.setVisible(is_max_size)
        
        # Estimator version dropdown (only in dev mode AND max_size mode)
        is_dev = getattr(self, '_is_dev_mode', False)
        self.estimator_version_label.setVisible(is_max_size and is_dev)
        self.estimator_version_combo.setVisible(is_max_size and is_dev)
        
        # Delegate format-specific visibility to centralized method
        self._update_format_visibility()
    
    def set_transform_mode(self, mode: str):
        """Set which transform section is visible."""
        self.resize_section.setVisible(mode == 'resize')
        self.rotate_container.setVisible(mode == 'rotate')
        self.time_container.setVisible(mode == 'time')
    
    def current_format(self) -> str:
        """Get current format (GIF or WebM)."""
        return self.format_selector.currentText()
    
    def _on_format_changed(self, format_name: str):
        """Handle format change between GIF and WebM."""
        # Delegate all visibility logic to centralized method
        self._update_format_visibility()
        
        # Emit signal
        self.format_changed.emit(format_name)
        self._notify_param_change()
    
    # -------------------------------------------------------------------------
    # PRIVATE METHODS
    # -------------------------------------------------------------------------
    
    def _toggle_gif_variants(self, enabled: bool):
        """Toggle GIF variant controls."""
        # Delegate to centralized visibility method
        self._update_format_visibility()
        self._notify_param_change()
    
    def _toggle_webm_variants(self, enabled: bool):
        """Toggle WebM variant controls."""
        # Delegate to centralized visibility method
        self._update_format_visibility()
        self._notify_param_change()
    
    
    def _toggle_time_cutting(self, enabled: bool):
        """Toggle time range slider."""
        self.time_range_slider.setVisible(enabled)
        self._notify_param_change()
    
    def _toggle_retime(self, enabled: bool):
        """Toggle retime slider."""
        self.retime_slider.setVisible(enabled)
        self.retime_value_label.setVisible(enabled)
        self._notify_param_change()
    
    def _parse_variants(self, text: str) -> list:
        """Parse comma-separated variant values."""
        try:
            return [v.strip() for v in text.split(',') if v.strip()]
        except:
            return []
    
    def _populate_estimator_versions(self, type_prefix: str):
        """Populate estimator version dropdown with available versions."""
        from client.core.target_size.size_estimator_registry import get_available_versions, get_estimator_version
        
        self.estimator_version_combo.clear()
        
        versions = get_available_versions(type_prefix)
        if not versions:
            # Fallback to default if no versions found
            self.estimator_version_combo.addItem("v2 (Deterministic 2-Pass)", "v2")
        else:
            for display_name, version_key in versions:
                self.estimator_version_combo.addItem(display_name, version_key)
        
        # Set current selection to active version
        current_version = get_estimator_version()
        for i in range(self.estimator_version_combo.count()):
            if self.estimator_version_combo.itemData(i) == current_version:
                self.estimator_version_combo.setCurrentIndex(i)
                break
    
    def _on_estimator_version_changed(self, index: int):
        """Handle estimator version dropdown change."""
        from client.core.target_size.size_estimator_registry import set_estimator_version
        version = self.estimator_version_combo.itemData(index)
        if version:
            set_estimator_version(version)
            print(f"[LoopTab] Estimator version changed to: {version}")
    
    def set_dev_mode(self, is_dev: bool):
        """Enable/disable dev mode features like estimator version selector."""
        self._is_dev_mode = is_dev
        # Estimator dropdown only shows in dev mode AND max_size mode
        if hasattr(self, '_is_max_size_mode') and self._is_max_size_mode:
            self.estimator_version_label.setVisible(is_dev)
            self.estimator_version_combo.setVisible(is_dev)
