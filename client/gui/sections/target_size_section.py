"""
TargetSizeSection - Reusable target size UI component.

Provides a consistent target size interface across Image, Video, and Loop tabs.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal

from client.gui.custom_widgets import CustomTargetSizeSpinBox, ThemedCheckBox, UnifiedVariantInput


class TargetSizeSection(QWidget):
    """
    Reusable target size section component.
    
    Provides:
    - Single target size spinbox (drag-adjustable)
    - Multiple variants checkbox
    - Variant input field with format/codec-specific defaults
    - Auto-resize checkbox
    """
    
    # Signal emitted when any parameter changes
    paramChanged = pyqtSignal()
    
    def __init__(
        self, 
        parent=None,
        focus_callback=None,
        default_value=1.0,
        sensitivity=0.01,
        unit_suffix="MB",
        variant_defaults_map=None
    ):
        """
        Initialize TargetSizeSection.
        
        Args:
            parent: Parent widget
            focus_callback: Callback for focus management
            default_value: Default target size value in MB
            sensitivity: Drag sensitivity for spinbox
            unit_suffix: Display unit (default: "MB")
            variant_defaults_map: Dict mapping format/codec -> default variants, e.g.:
                {'WebP': '0.08, 0.11, 0.18', 'JPEG': '0.15, 0.25, 0.35'}
                or a single string for all formats: '0.5, 1.0, 2.0'
        """
        super().__init__(parent)
        self._focus_callback = focus_callback or (lambda: None)
        self._default_value = default_value
        self._sensitivity = sensitivity
        self._unit_suffix = unit_suffix
        
        # Store variant defaults map
        if isinstance(variant_defaults_map, str):
            # Single default string for all formats
            self._variant_defaults_map = {'_default': variant_defaults_map}
        elif isinstance(variant_defaults_map, dict):
            self._variant_defaults_map = variant_defaults_map
        else:
            self._variant_defaults_map = {'_default': '0.5, 1.0, 2.0'}
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Create the target size UI elements."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Single target size spinbox
        self.target_size_label = QLabel(f"Target Size ({self._unit_suffix}):")
        self.target_size_spinbox = CustomTargetSizeSpinBox(
            default_value=self._default_value,
            decimals=3,
            on_enter_callback=self._focus_callback
        )
        self.target_size_spinbox.setSensitivity(self._sensitivity)
        self.target_size_spinbox.valueChanged.connect(self._emit_change)
        
        spinbox_row = QHBoxLayout()
        spinbox_row.addWidget(self.target_size_label)
        spinbox_row.addWidget(self.target_size_spinbox)
        layout.addLayout(spinbox_row)
        
        # Auto-resize checkbox
        self.auto_resize_checkbox = ThemedCheckBox("Auto-resize")
        self.auto_resize_checkbox.setChecked(False)
        self.auto_resize_checkbox.toggled.connect(self._emit_change)
        layout.addWidget(self.auto_resize_checkbox)
        
        # Multiple variants checkbox
        self.multiple_variants_checkbox = ThemedCheckBox("Multiple variants")
        self.multiple_variants_checkbox.toggled.connect(self._on_multiple_toggled)
        layout.addWidget(self.multiple_variants_checkbox)
        
        # Variant input field
        self.variants_label = QLabel(f"Variant sizes ({self._unit_suffix}):")
        self.variants_input = UnifiedVariantInput()
        self.variants_input.setPlaceholderText("e.g., 0.5, 1.0, 2.0")
        
        # Set initial default from map
        if '_default' in self._variant_defaults_map:
            default_variants = self._variant_defaults_map['_default']
        elif self._variant_defaults_map:
            # Use first value from dict if _default doesn't exist
            default_variants = next(iter(self._variant_defaults_map.values()))
        else:
            default_variants = '0.5, 1.0, 2.0'
        self.variants_input.setText(default_variants)
        
        self.variants_input.setVisible(False)
        self.variants_input.textChanged.connect(self._emit_change)
        self.variants_label.setVisible(False)
        
        variants_row = QHBoxLayout()
        variants_row.addWidget(self.variants_label)
        variants_row.addWidget(self.variants_input)
        layout.addLayout(variants_row)
    
    def get_params(self) -> dict:
        """
        Get target size parameters formatted for the conversion engine.
        
        Returns:
            dict: Target size parameters including:
                - target_size_mb: Single target size value or None if using variants
                - auto_resize: Whether auto-resize is enabled
                - multiple_variants: Whether multiple variants mode is enabled
                - size_variants: List of variant values as floats (empty if not using variants)
        """
        # Determine target size value
        if self.multiple_variants_checkbox.isChecked():
            target_size_mb = None  # Will use variants instead
            size_variants = self._parse_variants(self.variants_input.text())
        else:
            target_size_mb = self.target_size_spinbox.value()
            size_variants = []  # Don't return variants when not in multiple mode
        
        return {
            'target_size_mb': target_size_mb,
            'auto_resize': self.auto_resize_checkbox.isChecked(),
            'multiple_variants': self.multiple_variants_checkbox.isChecked(),
            'size_variants': size_variants
        }
    
    def update_variant_defaults(self, format_or_codec: str):
        """
        Update variant defaults based on format/codec change.
        
        Looks up the key in variant_defaults_map and updates the input field.
        Only updates if multiple variants checkbox is NOT checked.
        
        Args:
            format_or_codec: Format or codec name to look up in defaults map
        """
        # Only update if user hasn't manually enabled multiple variants
        if not self.multiple_variants_checkbox.isChecked():
            # Look up defaults for this format/codec
            defaults = self._variant_defaults_map.get(
                format_or_codec,
                self._variant_defaults_map.get('_default', '0.5, 1.0, 2.0')
            )
            self.variants_input.setText(defaults)
    
    def update_theme(self, is_dark: bool):
        """Apply theme styling to all elements."""
        # ThemedCheckBox widgets auto-update via ThemeManager signal
        # No manual updates needed
        pass
    
    def _on_multiple_toggled(self, multiple: bool):
        """Handle multiple variants checkbox toggle."""
        # Hide/show single spinbox
        self.target_size_label.setVisible(not multiple)
        self.target_size_spinbox.setVisible(not multiple)
        
        # Hide/show variants input
        self.variants_label.setVisible(multiple)
        self.variants_input.setVisible(multiple)
        
        self._emit_change()
    
    def _parse_variants(self, text: str) -> list:
        """Parse comma-separated variant values as floats."""
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
    
    def _emit_change(self):
        """Emit parameter changed signal."""
        self.paramChanged.emit()
