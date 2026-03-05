"""
TimeSection - Reusable time manipulation UI component.

Provides time cutting and retiming controls for video/loop tabs.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider
from PySide6.QtCore import Signal, Qt

from client.gui.custom_widgets import ThemedCheckBox, TimeRangeSlider
from client.gui.command_group import CommandGroup
from client.gui.theme import Theme


class TimeSection(QWidget):
    """
    Reusable time section component.
    
    Provides:
    - Time cutting (trim start/end with TimeRangeSlider)
    - Retiming (speed adjustment 0.1x-3.0x)
    - Enable/disable toggles for both features
    """
    
    # Signal emitted when any parameter changes
    paramChanged = Signal()
    
    def __init__(self, parent=None):
        """
        Initialize TimeSection.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._setup_ui()
        self._connect_theme()
    
    def _setup_ui(self):
        """Create the time section UI elements."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Time cutting checkbox
        self.enable_time_cutting = ThemedCheckBox("Time range")
        self.enable_time_cutting.stateChanged.connect(self._on_time_cutting_toggled)
        layout.addWidget(self.enable_time_cutting)
        
        # Time range slider
        self.time_range_slider = TimeRangeSlider()
        self.time_range_slider.setVisible(False)
        self.time_range_slider.rangeChanged.connect(self._emit_change)
        layout.addWidget(self.time_range_slider)
        
        # Retime checkbox
        self.enable_retime = ThemedCheckBox("Retime")
        self.enable_retime.stateChanged.connect(self._on_retime_toggled)
        layout.addWidget(self.enable_retime)
        
        # Retime speed slider container
        retime_container = QWidget()
        retime_layout = QHBoxLayout(retime_container)
        retime_layout.setContentsMargins(0, 0, 0, 0)
        retime_layout.setSpacing(8)
        
        # Speed slider
        self.retime_slider = QSlider(Qt.Orientation.Horizontal)
        self.retime_slider.setMinimum(1)  # 0.1x (stored as 1)
        self.retime_slider.setMaximum(30)  # 3.0x (stored as 30)
        self.retime_slider.setValue(10)  # 1.0x default (stored as 10)
        self.retime_slider.setVisible(False)
        self.retime_slider.valueChanged.connect(self._on_retime_speed_changed)
        
        # Speed label
        self.retime_value_label = QLabel("1.0x")
        self.retime_value_label.setMinimumWidth(50)
        self.retime_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.retime_value_label.setVisible(False)
        
        retime_layout.addWidget(self.retime_slider)
        retime_layout.addWidget(self.retime_value_label)
        
        layout.addWidget(retime_container)
    
    def _connect_theme(self):
        """Connect to theme manager for automatic theme updates."""
        from client.gui.theme_manager import ThemeManager
        theme_manager = ThemeManager.instance()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        self._on_theme_changed(theme_manager.is_dark_mode())
    
    def _on_theme_changed(self, is_dark: bool):
        """Update styles for current theme."""
        Theme.set_dark_mode(is_dark)
        
        # Colors for slider
        if is_dark:
            handle_color = "#4CAF50"
            handle_hover = "#45a049"
        else:
            handle_color = "#4CAF50"
            handle_hover = "#45a049"
        
        # Update slider style
        slider_style = f"""
            QSlider::groove:horizontal {{
                border: 1px solid {Theme.border()};
                height: 6px;
                background: {Theme.surface_element()};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {handle_color};
                border: 1px solid {handle_color};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {handle_hover};
                border-color: {handle_hover};
            }}
        """
        self.retime_slider.setStyleSheet(slider_style)
        
        # Update label style
        self.retime_value_label.setStyleSheet(f"color: {Theme.text()};")
    
    def _on_time_cutting_toggled(self, state):
        """Handle time cutting checkbox toggle."""
        enabled = (state == 2)  # Qt.CheckState.Checked
        self.time_range_slider.setVisible(enabled)
        self._emit_change()
    
    def _on_retime_toggled(self, state):
        """Handle retime checkbox toggle."""
        enabled = (state == 2)  # Qt.CheckState.Checked
        self.retime_slider.setVisible(enabled)
        self.retime_value_label.setVisible(enabled)
        self._emit_change()
    
    def _on_retime_speed_changed(self, value):
        """Handle retime speed slider change."""
        speed = value / 10.0
        self.retime_value_label.setText(f"{speed:.1f}x")
        self._emit_change()
    
    def _emit_change(self):
        """Emit parameter changed signal."""
        self.paramChanged.emit()
    
    def get_params(self) -> dict:
        """
        Get time section parameters.
        
        Returns dict with keys expected by transform_filter_builder.py:
        - enable_time_cutting: bool
        - time_start: float (0-1, normalized)
        - time_end: float (0-1, normalized)
        - retime_enabled: bool (using 'retime_enabled' to match existing code)
        - retime_speed: float (0.1-3.0)
        """
        return {
            'enable_time_cutting': self.enable_time_cutting.isChecked(),
            'time_start': self.time_range_slider.start_value if self.enable_time_cutting.isChecked() else 0.0,
            'time_end': self.time_range_slider.end_value if self.enable_time_cutting.isChecked() else 1.0,
            'retime_enabled': self.enable_retime.isChecked(),
            'retime_speed': self.retime_slider.value() / 10.0 if self.enable_retime.isChecked() else 1.0
        }
    
    def set_params(self, params: dict):
        """Set time section parameters from dict."""
        # Time cutting
        enable_cutting = params.get('enable_time_cutting', False)
        self.enable_time_cutting.setChecked(enable_cutting)
        
        time_start = params.get('time_start', 0.0)
        time_end = params.get('time_end', 1.0)
        if hasattr(self.time_range_slider, 'set_range'):
            self.time_range_slider.set_range(time_start, time_end)
        
        # Retime
        enable_retime = params.get('retime_enabled', False)
        self.enable_retime.setChecked(enable_retime)
        
        retime_speed = params.get('retime_speed', 1.0)
        self.retime_slider.setValue(int(retime_speed * 10))
    
    def reset_to_defaults(self):
        """Reset all parameters to defaults."""
        self.enable_time_cutting.setChecked(False)
        if hasattr(self.time_range_slider, 'set_range'):
            self.time_range_slider.set_range(0.0, 1.0)
        self.enable_retime.setChecked(False)
        self.retime_slider.setValue(10)  # 1.0x
