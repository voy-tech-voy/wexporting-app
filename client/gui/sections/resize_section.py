"""
ResizeSection - Reusable resize UI component.

Provides a consistent resize interface across Image, Video, and Loop tabs.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Signal

from client.gui.custom_spinbox import CustomSpinBox
from client.gui.custom_widgets import CustomComboBox, ThemedCheckBox, UnifiedVariantInput
from client.gui.theme import get_combobox_style


class ResizeSection(QWidget):
    """
    Reusable resize section component.
    
    Provides:
    - Resize mode selection (No resize, By width, By longer edge, By ratio)
    - Single value or multiple variant modes
    - Automatic default value management
    - Consistent UI interactions across tabs
    """
    
    # Signal emitted when any resize parameter changes
    paramChanged = Signal()
    
    def __init__(self, parent=None, focus_callback=None, variant_label="Size variants"):
        """
        Initialize ResizeSection.
        
        Args:
            parent: Parent widget
            focus_callback: Callback for focus management
            variant_label: Label text for the variants input (default: "Size variants")
        """
        super().__init__(parent)
        self._focus_callback = focus_callback or (lambda: None)
        self._variant_label_text = variant_label
        self._setup_ui()
    
    def _setup_ui(self):
        """Create the resize UI elements."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Resize mode dropdown
        self.resize_mode = CustomComboBox()
        self.resize_mode.addItems([
            "No resize", 
            "By width (pixels)", 
            "By longer edge (pixels)", 
            "By ratio (percent)"
        ])
        self.resize_mode.setStyleSheet(get_combobox_style(True))
        self.resize_mode.currentTextChanged.connect(self._on_resize_mode_changed)
        layout.addWidget(self.resize_mode)
        
        # Multiple variants checkbox
        self.multiple_variants = ThemedCheckBox("Multiple variants")
        self.multiple_variants.toggled.connect(self._on_multiple_toggled)
        layout.addWidget(self.multiple_variants)
        
        # Single value row
        single_val_row = QHBoxLayout()
        self.resize_value_label = QLabel("Width (pixels)")
        self.resize_value = CustomSpinBox(on_enter_callback=self._focus_callback)
        self.resize_value.setRange(1, 10000)
        self.resize_value.setValue(720)
        self.resize_value.valueChanged.connect(self._emit_change)
        single_val_row.addWidget(self.resize_value_label)
        single_val_row.addWidget(self.resize_value)
        layout.addLayout(single_val_row)
        
        # Variants row
        variants_row = QHBoxLayout()
        self.size_variants_label = QLabel(self._variant_label_text)
        self.size_variants = UnifiedVariantInput()
        self.size_variants.setPlaceholderText("e.g., 480,720,1080 or 33,66")
        self.size_variants.setText("480,720,1280")
        self.size_variants.textChanged.connect(self._emit_change)
        variants_row.addWidget(self.size_variants_label)
        variants_row.addWidget(self.size_variants)
        layout.addLayout(variants_row)
        
        # Initial visibility
        self.resize_value.setVisible(False)
        self.resize_value_label.setVisible(False)
        self.size_variants.setVisible(False)
        self.size_variants_label.setVisible(False)
    
    def get_params(self):
        """
        Get resize parameters formatted for the conversion engine.
        
        Returns:
            dict: Resize parameters including:
                - resize_mode: Current resize mode text
                - resize_value: Single resize value
                - current_resize: Formatted resize string (e.g., "720", "L720", "50%")
                - multiple_resize/multiple_size_variants: Whether multiple variants are enabled
                - resize_variants/video_variants: List of formatted variant strings
        """
        resize_mode = self.resize_mode.currentText()
        resize_value = self.resize_value.value()
        
        # Format current_resize based on mode
        if resize_mode == "No resize":
            current_resize = None
        elif resize_mode == "By longer edge (pixels)":
            current_resize = f"L{resize_value}"
        elif resize_mode == "By ratio (percent)":
            current_resize = f"{resize_value}%"
        else:  # "By width (pixels)"
            current_resize = str(resize_value)
        
        # Format resize variants based on resize_mode
        raw_variants = self._parse_variants(self.size_variants.text())
        formatted_variants = []
        if raw_variants:
            for variant in raw_variants:
                if resize_mode == "By longer edge (pixels)":
                    formatted_variants.append(f"L{variant}")
                elif resize_mode == "By ratio (percent)":
                    formatted_variants.append(f"{variant}%")
                else:  # "By width (pixels)" or "No resize"
                    formatted_variants.append(str(variant))
        
        return {
            'resize_mode': resize_mode,
            'resize_value': resize_value,
            'current_resize': current_resize,
            'multiple_resize': self.multiple_variants.isChecked(),
            'multiple_size_variants': self.multiple_variants.isChecked(),  # Alias for VideoTab
            'resize_variants': formatted_variants,
            'video_variants': formatted_variants,  # Alias for VideoTab
        }
    
    def update_theme(self, is_dark: bool):
        """Apply theme styling to all elements."""
        # CustomComboBox and ThemedCheckBox widgets auto-update via ThemeManager signal
        # No manual updates needed
        pass
    
    def restore_settings(self, settings: dict):
        """
        Restore resize settings from saved parameters.
        
        Args:
            settings: Dictionary with resize parameters
        """
        # Restore resize mode
        if 'resize_mode' in settings and settings['resize_mode']:
            self.resize_mode.setCurrentText(settings['resize_mode'])
        
        # Restore resize value
        if 'resize_value' in settings and settings['resize_value'] is not None:
            self.resize_value.setValue(settings['resize_value'])
        
        # Restore multiple variants checkbox
        if 'multiple_resize' in settings:
            self.multiple_variants.setChecked(settings['multiple_resize'])
        
        # Restore variant values
        if 'resize_variants' in settings and settings['resize_variants']:
            variants = settings['resize_variants']
            if isinstance(variants, list):
                # Strip formatting (L prefix, % suffix) to get raw values
                raw_values = []
                for v in variants:
                    v_str = str(v)
                    if v_str.startswith('L'):
                        raw_values.append(v_str[1:])
                    elif v_str.endswith('%'):
                        raw_values.append(v_str[:-1])
                    else:
                        raw_values.append(v_str)
                self.size_variants.setText(','.join(raw_values))
    
    def _on_multiple_toggled(self, multiple: bool):
        """Handle multiple variants checkbox toggle."""
        # Auto-switch to "By width" if currently "No resize"
        if multiple and self.resize_mode.currentText() == "No resize":
            self.resize_mode.setCurrentIndex(1)  # "By width (pixels)"
        
        # Update visibility
        self.resize_value.setVisible(not multiple)
        self.resize_value_label.setVisible(not multiple)
        self.size_variants.setVisible(multiple)
        self.size_variants_label.setVisible(multiple)
        
        self._emit_change()
    
    def _on_resize_mode_changed(self, mode: str):
        """Handle resize mode dropdown change."""
        # Auto-disable multiple variants if "No resize" selected
        if mode == "No resize" and self.multiple_variants.isChecked():
            self.multiple_variants.setChecked(False)
        
        show_value = (mode != "No resize")
        
        # Update visibility based on mode and multiple variants state
        if self.multiple_variants.isChecked():
            self.size_variants.setVisible(show_value)
            self.size_variants_label.setVisible(show_value)
            self.resize_value.setVisible(False)
            self.resize_value_label.setVisible(False)
        else:
            self.resize_value.setVisible(show_value)
            self.resize_value_label.setVisible(show_value)
            self.size_variants.setVisible(False)
            self.size_variants_label.setVisible(False)
        
        # Update label and defaults based on mode
        if "width" in mode.lower():
            self.resize_value_label.setText("Width (pixels)")
            if self.resize_value.value() < 100:
                self.resize_value.setValue(720)
            if "33,66" in self.size_variants.text():
                self.size_variants.setText("480,720,1280")
        
        elif "longer" in mode.lower():
            self.resize_value_label.setText("Longer edge (pixels)")
            if self.resize_value.value() < 100:
                self.resize_value.setValue(720)
            if "33,66" in self.size_variants.text():
                self.size_variants.setText("480,720,1080")
        
        elif "ratio" in mode.lower():
            self.resize_value_label.setText("Ratio (%)")
            self.resize_value.setValue(50)
            self.size_variants.setText("33,66")
        
        self._emit_change()
    
    def _parse_variants(self, text: str):
        """Parse comma-separated variant values."""
        try:
            return [v.strip() for v in text.split(',') if v.strip()]
        except:
            return []
    
    def _emit_change(self):
        """Emit parameter changed signal."""
        self.paramChanged.emit()
