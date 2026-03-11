"""
Noise Gradient Dev Panel (F11)
Provides real-time control over noise gradient parameters for file list items.
"""

from PySide6.QtWidgets import QSlider, QLabel, QHBoxLayout, QGroupBox, QVBoxLayout, QMessageBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from .base import BaseDevPanel
from .noise_params import NoiseParams


class NoiseDevPanel(BaseDevPanel):
    """Developer panel for adjusting noise gradient parameters."""
    
    params_changed = Signal()  # Emitted when any parameter changes
    
    def __init__(self, parent=None):
        super().__init__(
            title="🎨 Noise Gradient Parameters (F11)",
            parent=parent,
            width=450,
            height=700
        )
        
        # Add buttons to footer
        # Green Save Button (Primary)
        self.add_footer_button("Save Changes", self._save_params, primary=True, color="#30D158")
        
        # Reset Button
        self.add_footer_button("Reset to Defaults", self._reset_to_defaults)
        
        self._setup_content()
        self._load_current_values()
    
    def _setup_content(self):
        """Build the parameter controls."""
        # === Texture Generation Group ===
        texture_group = self._create_group("Texture Generation")
        texture_layout = QVBoxLayout()
        
        self.texture_size_slider = self._create_slider_row(
            "Texture Size", 16, 128, NoiseParams.texture_size,
            texture_layout, suffix="px"
        )
        
        self.max_alpha_slider = self._create_slider_row(
            "Max Alpha", 0, 50, NoiseParams.max_alpha,
            texture_layout
        )
        
        self.void_passes_slider = self._create_slider_row(
            "Blue Noise Passes", 0, 10, NoiseParams.void_cluster_passes,
            texture_layout
        )
        
        texture_group.setLayout(texture_layout)
        self.content_layout.addWidget(texture_group)
        
        # === Base Gradient Group ===
        gradient_group = self._create_group("Base Gradient (Color Fade)")
        gradient_layout = QVBoxLayout()
        
        self.grad_start_slider = self._create_slider_row(
            "Start Alpha", 0, 255, NoiseParams.gradient_start_alpha,
            gradient_layout
        )
        
        self.grad_mid_slider = self._create_slider_row(
            "Mid Alpha", 0, 255, NoiseParams.gradient_mid_alpha,
            gradient_layout
        )
        
        self.grad_mid_pos_slider = self._create_slider_row(
            "Mid Position", 0, 100, int(NoiseParams.gradient_mid_position * 100),
            gradient_layout, suffix="%", scale=0.01
        )
        
        gradient_group.setLayout(gradient_layout)
        self.content_layout.addWidget(gradient_group)
        
        # === Noise Mask Group ===
        mask_group = self._create_group("Noise Mask (Distribution)")
        mask_layout = QVBoxLayout()
        
        self.mask_ramp_pos_slider = self._create_slider_row(
            "Ramp Start", 0, 100, int(NoiseParams.mask_ramp_pos * 100),
            mask_layout, suffix="%", scale=0.01
        )
        
        self.mask_ramp_alpha_slider = self._create_slider_row(
            "Ramp Alpha", 0, 255, NoiseParams.mask_ramp_alpha,
            mask_layout
        )
        
        self.mask_peak_pos_slider = self._create_slider_row(
            "Peak Position", 0, 100, int(NoiseParams.mask_peak_pos * 100),
            mask_layout, suffix="%", scale=0.01
        )
        
        self.mask_peak_alpha_slider = self._create_slider_row(
            "Peak Alpha", 0, 255, NoiseParams.mask_peak_alpha,
            mask_layout
        )
        
        mask_group.setLayout(mask_layout)
        self.content_layout.addWidget(mask_group)

        # === Behavior Group ===
        behavior_group = self._create_group("Behavior")
        behavior_layout = QVBoxLayout()
        
        self.persistence_checkbox = self._create_checkbox_row(
            "Keep Gradient After Click", 
            NoiseParams.persistence_enabled,
            behavior_layout
        )
        
        self.flat_completed_checkbox = self._create_checkbox_row(
            "Flat Completed Status",
            NoiseParams.flat_completed_enabled,
            behavior_layout
        )
        
        behavior_group.setLayout(behavior_layout)
        self.content_layout.addWidget(behavior_group)
        
        self.content_layout.addStretch()
    
    def _create_group(self, title):
        """Create a styled group box."""
        group = QGroupBox(title)
        font = QFont()
        font.setBold(True)
        group.setFont(font)
        return group
    
    def _create_slider_row(self, label_text, min_val, max_val, current_val, parent_layout, suffix="", scale=1.0):
        """Create a labeled slider with value display."""
        row_layout = QHBoxLayout()
        
        label = QLabel(label_text)
        label.setMinimumWidth(120)
        label.setStyleSheet("color: #8E8E93;")
        row_layout.addWidget(label)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(current_val)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setTickInterval((max_val - min_val) // 10 if max_val - min_val > 10 else 1)
        row_layout.addWidget(slider, 1)
        
        value_label = QLabel(f"{int(current_val * scale)}{suffix}")
        value_label.setMinimumWidth(60)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_label.setStyleSheet("color: #F5F5F7; font-weight: bold;")
        row_layout.addWidget(value_label)
        
        # Connect slider to update label and parameters
        def on_value_changed(value):
            value_label.setText(f"{int(value * scale)}{suffix}")
            self._update_params()
        
        slider.valueChanged.connect(on_value_changed)
        
        parent_layout.addLayout(row_layout)
        return slider
    
    def _create_checkbox_row(self, label_text, current_val, parent_layout):
        """Create a labeled checkbox."""
        from PySide6.QtWidgets import QCheckBox
        
        row_layout = QHBoxLayout()
        
        label = QLabel(label_text)
        label.setMinimumWidth(180)
        label.setStyleSheet("color: #8E8E93;")
        row_layout.addWidget(label)
        
        checkbox = QCheckBox()
        checkbox.setChecked(current_val)
        # Checkbox styling
        checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #555;
                border-radius: 4px;
                background: #333;
            }
            QCheckBox::indicator:checked {
                background: #30D158;
                border-color: #30D158;
            }
        """)
        
        checkbox.stateChanged.connect(lambda: self._update_params())
        row_layout.addWidget(checkbox)
        row_layout.addStretch()
        
        parent_layout.addLayout(row_layout)
        return checkbox
    
    def _load_current_values(self):
        """Load current parameter values into sliders."""
        # Already done in _create_slider_row
        pass
    
    def _update_params(self):
        """Update NoiseParams from slider values."""
        # Texture parameters
        NoiseParams.texture_size = self.texture_size_slider.value()
        NoiseParams.max_alpha = self.max_alpha_slider.value()
        NoiseParams.void_cluster_passes = self.void_passes_slider.value()
        
        # Gradient parameters
        NoiseParams.gradient_start_alpha = self.grad_start_slider.value()
        NoiseParams.gradient_mid_alpha = self.grad_mid_slider.value()
        NoiseParams.gradient_mid_position = self.grad_mid_pos_slider.value() / 100.0
        
        # Mask parameters
        NoiseParams.mask_ramp_pos = self.mask_ramp_pos_slider.value() / 100.0
        NoiseParams.mask_ramp_alpha = self.mask_ramp_alpha_slider.value()
        NoiseParams.mask_peak_pos = self.mask_peak_pos_slider.value() / 100.0
        NoiseParams.mask_peak_alpha = self.mask_peak_alpha_slider.value()
        
        # Behavior parameters
        NoiseParams.persistence_enabled = self.persistence_checkbox.isChecked()
        NoiseParams.flat_completed_enabled = self.flat_completed_checkbox.isChecked()
        
        # Invalidate cache and notify
        NoiseParams.invalidate_cache()
        self.params_changed.emit()
    
    def _reset_to_defaults(self):
        """Reset all parameters to default values."""
        NoiseParams.reset_to_defaults()
        
        # Update sliders
        self.texture_size_slider.setValue(32)
        self.max_alpha_slider.setValue(12)
        self.void_passes_slider.setValue(3)
        
        self.grad_start_slider.setValue(80)
        self.grad_mid_slider.setValue(20)
        self.grad_mid_pos_slider.setValue(40)
        
        self.mask_ramp_pos_slider.setValue(20)
        self.mask_ramp_alpha_slider.setValue(200)
        self.mask_peak_pos_slider.setValue(60)
        self.mask_peak_alpha_slider.setValue(255)
        
        self.persistence_checkbox.setChecked(False)
        self.flat_completed_checkbox.setChecked(True)
        
        self.params_changed.emit()

    def _save_params(self):
        """Save current parameters to file."""
        if NoiseParams.save():
            QMessageBox.information(
                self, 
                "Saved", 
                f"Noise parameters saved successfully to:\n{NoiseParams.get_config_path()}"
            )
        else:
            QMessageBox.critical(self, "Error", "Failed to save parameters.")
