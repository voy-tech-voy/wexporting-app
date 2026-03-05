from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QSlider, QFrame, QHBoxLayout, QGroupBox, QPushButton
)
from PySide6.QtCore import Qt, Signal

from .base import BaseDevPanel
from .sequence_params import SequenceParams
from client.gui.theme import Theme

class SequenceDevPanel(BaseDevPanel):
    """Developer panel for tuning sequence visualization (F11)"""
    
    paramsChanged = Signal()
    
    def __init__(self, parent=None):
        super().__init__(
            title="📚 Sequence Stack Tuner (F11)",
            parent=parent,
            width=400,
            height=500
        )
        self._setup_ui()
        
        # Add Footer Buttons
        self.add_footer_button("Save Changes", self._save_changes, primary=True, color="#30D158")
        
    def _save_changes(self):
        if SequenceParams.save():
            # Show brief visual feedback or just print (BaseDevPanel doesn't have toast built-in yet)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Saved", "Sequence parameters saved successfully.")
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Failed to save parameters.")
            
    def _setup_ui(self):
        # 1. Stack Count
        self._add_slider_row(
            "Stack Count", 
            "items", 
            1, 6, 
            SequenceParams.stack_count,
            lambda v: setattr(SequenceParams, 'stack_count', v)
        )
        
        self.content_layout.addSpacing(10)
        
        # 2. X Offset
        self._add_slider_row(
            "X Offset", 
            "px", 
            0, 20, 
            SequenceParams.offset_x,
            lambda v: setattr(SequenceParams, 'offset_x', v)
        )
        
        # 3. Y Offset
        self._add_slider_row(
            "Y Offset", 
            "px", 
            -20, 20, 
            SequenceParams.offset_y,
            lambda v: setattr(SequenceParams, 'offset_y', v)
        )
        
        self.content_layout.addSpacing(10)
        
        # 4. Scale Step
        # Slider 0-20 -> 0.00 - 0.20
        self._add_float_slider_row(
            "Scale Reduction", 
            " (per item)", 
            0, 20, 
            int(SequenceParams.scale_step * 100),
            lambda v: setattr(SequenceParams, 'scale_step', v / 100.0)
        )
        
        self.content_layout.addStretch()
        
        # Reset Button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet(f"background-color: {Theme.surface_element()}; color: {Theme.text()}; border: 1px solid {Theme.border()}; padding: 8px; border-radius: 4px;")
        reset_btn.clicked.connect(self._reset_params)
        self.content_layout.addWidget(reset_btn)

    def _add_slider_row(self, label, unit, min_val, max_val, current_val, callback):
        container = QGroupBox(label)
        container.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {Theme.text()}; border: 1px solid {Theme.border()}; border-radius: 4px; margin-top: 6px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 3px; }}")
        layout = QVBoxLayout(container)
        
        value_label = QLabel(f"{current_val} {unit}")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(current_val)
        
        def on_change(val):
            value_label.setText(f"{val} {unit}")
            callback(val)
            self.paramsChanged.emit()
            
        slider.valueChanged.connect(on_change)
        
        layout.addWidget(value_label)
        layout.addWidget(slider)
        self.content_layout.addWidget(container)
        
    def _add_float_slider_row(self, label, unit, min_val, max_val, current_int_val, callback):
        container = QGroupBox(label)
        container.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {Theme.text()}; border: 1px solid {Theme.border()}; border-radius: 4px; margin-top: 6px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 3px; }}")
        layout = QVBoxLayout(container)
        
        # Display as float
        current_float = current_int_val / 100.0
        value_label = QLabel(f"{current_float:.2f}{unit}")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(current_int_val)
        
        def on_change(val):
            float_val = val / 100.0
            value_label.setText(f"{float_val:.2f}{unit}")
            callback(val) # Callback handles conversion
            self.paramsChanged.emit()
            
        slider.valueChanged.connect(on_change)
        
        layout.addWidget(value_label)
        layout.addWidget(slider)
        self.content_layout.addWidget(container)

    def _reset_params(self):
        SequenceParams.reset()
        # Re-build UI or just close/reopen (simpler for now)
        self.close()
