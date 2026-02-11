"""
Dev Panel for Noise Gradient Parameters (F11)

Provides a floating panel with sliders to adjust noise gradient parameters
for file list items in real-time.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from client.gui.theme import Theme
from client.gui.noise_params import NoiseParams


class NoiseDevPanel(QWidget):
    """
    Developer panel for adjusting noise gradient parameters.
    
    Accessible via F11 key. Provides real-time control over:
    - Noise texture generation
    - Gradient fade parameters
    - Noise mask distribution
    """
    
    params_changed = pyqtSignal()  # Emitted when any parameter changes
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Noise Gradient Dev Panel (F11)")
        self.setMinimumWidth(400)
        self.setMaximumWidth(500)
        self.setMinimumHeight(600)
        
        self._setup_ui()
        self._load_current_values()
        
    def _setup_ui(self):
        """Build the dev panel UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # Title
        title = QLabel("🎨 Noise Gradient Parameters")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)
        
        # Scroll area for parameters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(16)
        
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
        scroll_layout.addWidget(texture_group)
        
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
        scroll_layout.addWidget(gradient_group)
        
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
        scroll_layout.addWidget(mask_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)
        
        # === Action Buttons ===
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        close_btn = QPushButton("Close (F11)")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
        
        self._apply_theme()
    
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
        row_layout.addWidget(value_label)
        
        # Connect slider to update label and parameters
        def on_value_changed(value):
            value_label.setText(f"{int(value * scale)}{suffix}")
            self._update_params()
        
        slider.valueChanged.connect(on_value_changed)
        
        parent_layout.addLayout(row_layout)
        return slider
    
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
        
        self.params_changed.emit()
    
    def _apply_theme(self):
        """Apply theme styling to the panel."""
        is_dark = True  # Assume dark for now
        Theme.set_dark_mode(is_dark)
        
        bg_color = Theme.surface_element()
        text_color = Theme.text()
        border_color = Theme.border()
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QGroupBox {{
                border: 1px solid {border_color};
                border-radius: {Theme.RADIUS_MD}px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {text_color};
            }}
            QPushButton {{
                background-color: {Theme.color('button_bg')};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Theme.color('button_hover')};
            }}
            QPushButton:pressed {{
                background-color: {Theme.color('button_pressed')};
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {border_color};
                height: 6px;
                background: {Theme.color('input_bg')};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {Theme.accent()};
                border: 1px solid {Theme.border_focus()};
                width: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {Theme.color('accent_hover') if hasattr(Theme, 'color') else Theme.accent()};
            }}
        """)
