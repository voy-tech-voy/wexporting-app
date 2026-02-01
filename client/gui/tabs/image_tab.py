"""
ImageTab - Image conversion tab component.

Extracted from CommandPanel as part of the Mediator-Shell refactoring.
This tab handles image format, quality, resize, and rotation settings.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QSizePolicy, QComboBox, QDoubleSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt

from client.gui.tabs.base_tab import BaseTab
from client.gui.command_group import CommandGroup
from client.gui.custom_spinbox import CustomSpinBox
from client.gui.custom_widgets import (
    FormatButtonRow, RotationButtonRow, 
    ThemedCheckBox, CustomTargetSizeSpinBox, UnifiedVariantInput
)
from client.gui.sections import ResizeSection, TargetSizeSection
from client.gui.theme import get_combobox_style

COMBOBOX_STYLE = get_combobox_style(True)  # Default dark mode

# Format-specific defaults for max size variants (in MB)
DEFAULT_MAX_SIZE_VARIANTS = {
    'WebP': '0.1, 0.2, 0.3',
    'JPEG': '0.1, 0.2, 0.3',
    'PNG': '0.1, 0.2, 0.3',
}


class ImageTab(BaseTab):
    """
    Image conversion settings tab.
    
    Provides controls for:
    - Output format (WebP, JPG, PNG)
    - Quality settings (single or multiple variants)
    - Max file size targeting
    - Resize options (by width, longer edge, ratio)
    - Rotation angle
    """
    
    def __init__(self, parent=None, focus_callback=None):
        """
        Initialize ImageTab.
        
        Args:
            parent: Parent widget
            focus_callback: Callback to invoke when focusing the active tab
        """
        super().__init__(parent)
        self._focus_callback = focus_callback or (lambda: None)
        self.setup_ui()
    
    def setup_ui(self):
        """Create the image tab UI elements."""
        # Use the layout from BaseTab
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
        self.format_group = CommandGroup("")
        self.format_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.format_group.get_content_layout().setContentsMargins(16, 16, 16, 16)
        self.format_group.setMinimumHeight(180)
        settings_h.addWidget(self.format_group, 1)
        
        layout.addWidget(settings_row)
        
        # Format Selection
        self.format = FormatButtonRow(["WebP", "JPG", "PNG"])
        self.format_group.get_content_layout().insertRow(0, self.format)
        
        # Connect format change to refresh estimator versions
        self.format.currentTextChanged.connect(self._on_format_changed)
        
        # Target Size Section
        self.target_size_section = TargetSizeSection(
            parent=self,
            focus_callback=self._focus_callback,
            default_value=0.15,
            sensitivity=0.001,
            variant_defaults_map=DEFAULT_MAX_SIZE_VARIANTS
        )
        self.target_size_section.paramChanged.connect(self._notify_param_change)
        self.format_group.add_row(self.target_size_section)
        
        # Estimator Version Selection
        self.estimator_version_label = QLabel("Estimator Version:")
        self.estimator_version_combo = QComboBox()
        self._populate_estimator_versions()  # Populate based on current format
        self.estimator_version_combo.currentIndexChanged.connect(self._on_estimator_version_changed)
        self.estimator_version_label.setVisible(False)
        self.format_group.add_row(self.estimator_version_label, self.estimator_version_combo)
        
        # --- Multiple qualities ---
        self.multiple_qualities = ThemedCheckBox("Multiple variants")
        self.multiple_qualities.toggled.connect(self._toggle_quality_mode)
        self.format_group.add_row(self.multiple_qualities)
        
        # --- Quality slider ---
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(1, 100)
        self.quality.setValue(40)
        self.quality_label = QLabel("40")
        self.quality.valueChanged.connect(lambda v: self.quality_label.setText(str(v)))
        
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(self.quality)
        quality_layout.addWidget(self.quality_label)
        self.quality_row_label = QLabel("Quality")
        self.format_group.add_row(self.quality_row_label, quality_layout)
        
        # --- Quality variants ---
        self.quality_variants = UnifiedVariantInput()
        self.quality_variants.setPlaceholderText("e.g., 40, 60, 80, 95")
        self.quality_variants.setText("40, 60, 80, 95")
        self.quality_variants.setVisible(False)
        self.quality_variants_label = QLabel("Quality variants")
        self.quality_variants_label.setVisible(False)
        self.format_group.add_row(self.quality_variants_label, self.quality_variants)
        
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
            variant_label="Resize values"
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
        
        # Initially show resize, hide rotate
        self.rotate_container.setVisible(False)
    
    def get_params(self) -> dict:
        """Collect image conversion parameters from UI."""
        # Get resize params from ResizeSection
        resize_params = self.resize_section.get_params()
        
        # Get target size params from TargetSizeSection
        target_params = self.target_size_section.get_params()
        
        # Determine if Max Size mode is active
        is_max_size_mode = self.target_size_section.isVisible()
        
        params = {
            'type': 'image',
            'format': self.format.currentText(),
            'quality': self.quality.value(),
            'multiple_qualities': self.multiple_qualities.isChecked(),
            'quality_variants': self._parse_variants(self.quality_variants.text()),
            'image_max_size_mb': target_params['target_size_mb'],
            'image_auto_resize': target_params['auto_resize'],
            'image_size_mode': 'max_size' if is_max_size_mode else 'manual',
            'multiple_max_sizes': target_params['multiple_variants'],
            'max_size_variants': target_params['size_variants'],
            'rotation_angle': self.rotation_angle.currentText(),
            'estimator_version': self.estimator_version_combo.currentText() if self.estimator_version_combo.isVisible() else None,
        }
        # Merge resize params
        params.update(resize_params)
        return params
    
    def update_theme(self, is_dark: bool):
        """Apply theme styling to all elements."""
        self._is_dark_theme = is_dark
        
        # Update sections (don't auto-connect to ThemeManager)
        self.resize_section.update_theme(is_dark)
        self.target_size_section.update_theme(is_dark)
        
        # Note: ThemedCheckBox widgets auto-update via ThemeManager signal
    
    def set_mode(self, mode: str):
        """
        Set the size mode (Max Size, Presets, Manual).
        
        Args:
            mode: "Max Size", "Presets", or "Manual"
        """
        is_max_size = (mode == "Max Size")
        is_manual = (mode == "Manual")
        self._is_max_size_mode = is_max_size  # Track for dev mode features
        
        # Target size section (only visible in Max Size mode)
        self.target_size_section.setVisible(is_max_size)
        
        # Estimator version dropdown (only in dev mode AND max_size mode)
        is_dev = getattr(self, '_is_dev_mode', False)
        self.estimator_version_label.setVisible(is_max_size and is_dev)
        self.estimator_version_combo.setVisible(is_max_size and is_dev)
        
        # Quality controls (only visible in Manual mode, hidden in Max Size)
        self.quality_row_label.setVisible(is_manual and not self.multiple_qualities.isChecked())
        self.quality.setVisible(is_manual and not self.multiple_qualities.isChecked())
        self.quality_label.setVisible(is_manual and not self.multiple_qualities.isChecked())
        
        # Multiple qualities checkbox (only visible in Manual mode)
        self.multiple_qualities.setVisible(is_manual)
        self.quality_variants_label.setVisible(is_manual and self.multiple_qualities.isChecked())
        self.quality_variants.setVisible(is_manual and self.multiple_qualities.isChecked())
    
    def set_transform_mode(self, mode: str):
        """Set which transform section is visible (resize or rotate)."""
        self.resize_section.setVisible(mode == 'resize')
        self.rotate_container.setVisible(mode == 'rotate')
    
    # -------------------------------------------------------------------------
    # PRIVATE METHODS
    # -------------------------------------------------------------------------
    
    def _toggle_quality_mode(self, multiple: bool):
        """Toggle between single quality slider and multiple quality variants."""
        self.quality.setVisible(not multiple)
        self.quality_label.setVisible(not multiple)
        self.quality_row_label.setVisible(not multiple)
        self.quality_variants.setVisible(multiple)
        self.quality_variants_label.setVisible(multiple)
        self._notify_param_change()
    

    
    def _toggle_resize_mode(self, multiple: bool):
        """Toggle between single resize value and multiple variants."""
        self.resize_value.setVisible(not multiple)
        self.resize_value_label.setVisible(not multiple)
        self.resize_variants.setVisible(multiple)
        self.resize_variants_label.setVisible(multiple)
        self._notify_param_change()
    
    def _on_resize_mode_changed(self, mode: str):
        """Handle resize mode dropdown change."""
        show_value = (mode != "No resize")
        
        if self.multiple_resize.isChecked():
            self.resize_variants.setVisible(show_value)
            self.resize_variants_label.setVisible(show_value)
            self.resize_value.setVisible(False)
            self.resize_value_label.setVisible(False)
        else:
            self.resize_value.setVisible(show_value)
            self.resize_value_label.setVisible(show_value)
            self.resize_variants.setVisible(False)
            self.resize_variants_label.setVisible(False)
        
        # Update label based on mode
        if "width" in mode.lower():
            self.resize_value_label.setText("Width (pixels)")
        elif "longer" in mode.lower():
            self.resize_value_label.setText("Longer edge (pixels)")
        elif "ratio" in mode.lower():
            self.resize_value_label.setText("Ratio (%)")
        
        self._notify_param_change()
    
    def _parse_variants(self, text: str) -> list:
        """Parse comma-separated variant values as numbers (floats or integers)."""
        try:
            result = []
            for v in text.split(','):
                v = v.strip()
                if v:
                    try:
                        # Try float first to support decimal values (e.g., 0.15, 0.25)
                        result.append(float(v))
                    except ValueError:
                        # Skip non-numeric values
                        continue
            return result
        except:
            return []
    
    def _populate_estimator_versions(self):
        """Populate estimator version dropdown with available versions for current format."""
        from client.core.target_size.size_estimator_registry import get_available_versions_for_format, get_estimator_version
        
        # Get current format
        current_format = self.format.currentText()
        
        self.estimator_version_combo.clear()
        
        # Get format-specific versions
        versions = get_available_versions_for_format('image', current_format)
        if not versions:
            # Fallback to default if no versions found
            self.estimator_version_combo.addItem(f"v5 ({current_format})", "v5")
        else:
            for display_name, version_key in versions:
                self.estimator_version_combo.addItem(display_name, version_key)
        
        # Set current selection to active version
        current_version = get_estimator_version()
        for i in range(self.estimator_version_combo.count()):
            if self.estimator_version_combo.itemData(i) == current_version:
                self.estimator_version_combo.setCurrentIndex(i)
                break
    
    def _on_format_changed(self, new_format: str):
        """Handle format dropdown change."""
        print(f"[ImageTab] Format changed to: {new_format}")
        self._populate_estimator_versions()
        
        # Update target size variant defaults based on format
        if hasattr(self, 'target_size_section'):
            self.target_size_section.update_variant_defaults(new_format)
    
    def _on_estimator_version_changed(self, index: int):
        """Handle estimator version dropdown change."""
        from client.core.target_size.size_estimator_registry import set_estimator_version
        version = self.estimator_version_combo.itemData(index)
        if version:
            set_estimator_version(version)
            print(f"[ImageTab] Estimator version changed to: {version}")
    
    def set_dev_mode(self, is_dev: bool):
        """Enable/disable dev mode features like estimator version selector."""
        self._is_dev_mode = is_dev
        # Estimator dropdown only shows in dev mode AND max_size mode
        if hasattr(self, '_is_max_size_mode') and self._is_max_size_mode:
            self.estimator_version_label.setVisible(is_dev)
            self.estimator_version_combo.setVisible(is_dev)
