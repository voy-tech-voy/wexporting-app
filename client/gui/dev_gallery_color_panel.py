"""
Developer Gallery Color Panel - F12 Gallery Color Editor
Allows real-time gallery color adjustment and saving to theme_variables.py
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QColorDialog, QFrame, QLineEdit, QMessageBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QKeyEvent
import re


class ColorPickerRow(QWidget):
    """Single row with color variable name, preview, and edit button"""
    
    colorChanged = pyqtSignal(str, str)  # (variable_name, hex_color)
    
    def __init__(self, var_name: str, color_hex: str, description: str = "", parent=None):
        super().__init__(parent)
        self.var_name = var_name
        self.current_color = color_hex
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)
        
        # Variable name label
        name_label = QLabel(var_name)
        name_label.setMinimumWidth(180)
        name_label.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-weight: bold;")
        layout.addWidget(name_label)
        
        # Color preview box
        self.color_preview = QFrame()
        self.color_preview.setFixedSize(60, 30)
        self.color_preview.setStyleSheet(f"""
            QFrame {{
                background-color: {color_hex};
                border: 2px solid #555555;
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.color_preview)
        
        # Hex value input
        self.hex_input = QLineEdit(color_hex)
        self.hex_input.setMaximumWidth(100)
        self.hex_input.setStyleSheet("""
            QLineEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                padding: 4px 8px;
                background-color: #2D2D2D;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
            }
        """)
        self.hex_input.textChanged.connect(self._on_hex_changed)
        layout.addWidget(self.hex_input)
        
        # Pick color button
        pick_btn = QPushButton("Pick Color")
        pick_btn.setMaximumWidth(100)
        pick_btn.clicked.connect(self._pick_color)
        pick_btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0066DD;
            }
        """)
        layout.addWidget(pick_btn)
        
        # Description label
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #86868B; font-size: 11px;")
        layout.addWidget(desc_label, 1)
    
    def _on_hex_changed(self, text: str):
        """Validate and apply hex color from text input"""
        text = text.strip()
        if re.match(r'^#[0-9A-Fa-f]{6}$', text):
            self.current_color = text
            self.color_preview.setStyleSheet(f"""
                QFrame {{
                    background-color: {text};
                    border: 2px solid #555555;
                    border-radius: 4px;
                }}
            """)
            self.colorChanged.emit(self.var_name, text)
    
    def _pick_color(self):
        """Open color picker dialog"""
        current = QColor(self.current_color)
        color = QColorDialog.getColor(current, self, f"Pick color for {self.var_name}")
        
        if color.isValid():
            hex_color = color.name().upper()
            self.hex_input.setText(hex_color)



class AlphaRow(QWidget):
    """Row for numeric value with spinbox"""
    
    alphaChanged = pyqtSignal(str, str)  # (variable_name, value_as_string)
    
    def __init__(self, var_name: str, value: str, description: str = "", min_val: int = 0, max_val: int = 255, parent=None):
        super().__init__(parent)
        self.var_name = var_name
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)
        
        # Variable name
        name_label = QLabel(var_name)
        name_label.setMinimumWidth(180)
        name_label.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-weight: bold;")
        layout.addWidget(name_label)
        
        # Numeric spinbox
        self.alpha_spin = QSpinBox()
        self.alpha_spin.setRange(min_val, max_val)
        self.alpha_spin.setValue(int(value))
        self.alpha_spin.setMaximumWidth(100)
        self.alpha_spin.setStyleSheet("""
            QSpinBox {
                padding: 4px 8px;
                background-color: #2D2D2D;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
            }
        """)
        self.alpha_spin.valueChanged.connect(lambda v: self.alphaChanged.emit(self.var_name, str(v)))
        layout.addWidget(self.alpha_spin)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #86868B; font-size: 11px;")
        layout.addWidget(desc_label, 1)


class CheckboxRow(QWidget):
    """Row for boolean toggle with checkbox"""
    
    toggleChanged = pyqtSignal(str, str)  # (variable_name, value_as_string "0" or "1")
    
    def __init__(self, var_name: str, value: str, description: str = "", parent=None):
        super().__init__(parent)
        self.var_name = var_name
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)
        
        # Variable name
        name_label = QLabel(var_name)
        name_label.setMinimumWidth(180)
        name_label.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-weight: bold;")
        layout.addWidget(name_label)
        
        # Checkbox toggle
        from PyQt6.QtWidgets import QCheckBox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(int(value) == 1)
        self.checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
                border: 2px solid #555555;
                border-radius: 4px;
                background-color: #2D2D2D;
            }
            QCheckBox::indicator:checked {
                background-color: #30D158;
                border-color: #30D158;
                image: url(none);
            }
            QCheckBox::indicator:checked:after {
                content: "✓";
                color: white;
            }
        """)
        self.checkbox.stateChanged.connect(lambda state: self.toggleChanged.emit(
            self.var_name, 
            "1" if self.checkbox.isChecked() else "0"
        ))
        layout.addWidget(self.checkbox)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #86868B; font-size: 11px;")
        layout.addWidget(desc_label, 1)



class DevGalleryColorPanel(QWidget):
    """Developer panel for gallery-specific color editing"""
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("[GALLERY] Dev Gallery Color Editor (F12)")
        self.setMinimumSize(900, 500)
        
        # Track color changes
        self.color_changes = {}
        
        # Current theme colors
        self.theme_colors = self._load_current_colors()
        
        # Debounce timer
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(200)
        self._update_timer.timeout.connect(self._broadcast_theme_change)
        
        self._setup_ui()
        
        # Apply dark theme
        self.setStyleSheet("""
            QWidget {
                background-color: #1A1A1A;
                color: #F5F5F7;
                font-size: 13px;
            }
            QScrollArea {
                border: none;
                background-color: #232323;
            }
        """)
    
    def _load_current_colors(self):
        """Load current colors from theme_variables module"""
        from client.gui.theme_variables import DARK_THEME, LIGHT_THEME
        return {
            'DARK_THEME': DARK_THEME.copy(),
            'LIGHT_THEME': LIGHT_THEME.copy()
        }
    
    def _setup_ui(self):
        """Setup the UI layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Header
        header = QLabel("[GALLERY] Preset Gallery Color Editor")
        header.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px;")
        main_layout.addWidget(header)
        
        # Instructions
        info = QLabel("[TIP] Adjust gallery colors in real-time. Press 'Apply & Save' to write changes to theme_variables.py")
        info.setStyleSheet("color: #86868B; padding: 5px; font-size: 12px;")
        info.setWordWrap(True)
        main_layout.addWidget(info)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Container
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(2)
        
        # Dark Theme Section
        dark_header = QLabel("🌙 DARK MODE - GALLERY COLORS")
        dark_header.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            padding: 12px 8px; 
            background-color: #2D2D2D;
            border-radius: 4px;
        """)
        container_layout.addWidget(dark_header)
        
        # Gallery colors for dark mode
        # Format: (var_name, description) for colors
        #         (var_name, description, "alpha") for alpha (0-255)
        #         (var_name, description, "alpha", min, max) for custom range
        #         (var_name, description, "checkbox") for boolean toggle
        gallery_colors_dark = [
            ("presets_bg", "Gallery background"),
            ("gallery_overlay_color", "Blur overlay base color"),
            ("gallery_overlay_alpha", "Overlay transparency (0-255)", "alpha"),
            ("gallery_filter_bg", "Filter bar background"),
            ("gallery_filter_overlay", "Filter bar overlay tint"),
            ("gallery_filter_overlay_alpha", "Filter bar overlay alpha (0-255)", "alpha"),
            ("gallery_filter_blur_radius", "Filter bar blur radius", "alpha", 0, 20),
            ("gallery_filter_blur_scale", "Filter bar downscale factor", "alpha", 1, 8),
            ("gallery_param_bg", "Parameter form input background"),
            ("gallery_param_panel_bg", "Parameter panel window background"),
            # Filter Button Colors
            ("gallery_filter_btn_active_bg", "Button ACTIVE background"),
            ("gallery_filter_btn_active_text", "Button ACTIVE text"),
            ("gallery_filter_btn_inactive_bg", "Button INACTIVE background"),
            ("gallery_filter_btn_inactive_text", "Button INACTIVE text"),
            ("gallery_filter_btn_border", "Button border color"),
            # Mask Controls
            ("gallery_filter_mask_top_alpha", "Gradient Mask TOP Alpha (0-255)", "alpha"),
            ("gallery_filter_mask_bottom_alpha", "Gradient Mask BOTTOM Alpha (0-255)", "alpha"),
            ("gallery_filter_debug_mask", "🔍 Show Gradient Rectangle", "checkbox"),
        ]
        
        for item in gallery_colors_dark:
            var_name = item[0]
            description = item[1]
            item_type = item[2] if len(item) > 2 else "color"
            
            current_value = self.theme_colors['DARK_THEME'].get(var_name, "#FF00FF")
            
            if item_type == "checkbox":
                # Boolean checkbox toggle
                row = CheckboxRow(var_name, current_value, description)
                row.toggleChanged.connect(lambda v, c, mode='dark': self._on_color_changed(mode, v, c))
            elif item_type == "alpha":
                # Numeric value with optional custom range
                if len(item) > 4:
                    min_val, max_val = item[3], item[4]
                    row = AlphaRow(var_name, current_value, description, min_val, max_val)
                else:
                    row = AlphaRow(var_name, current_value, description)
                row.alphaChanged.connect(lambda v, c, mode='dark': self._on_color_changed(mode, v, c))
            else:
                # Color picker
                row = ColorPickerRow(var_name, current_value, description)
                row.colorChanged.connect(lambda v, c, mode='dark': self._on_color_changed(mode, v, c))
            
            container_layout.addWidget(row)
        
        container_layout.addSpacing(20)
        
        # Light Theme Section
        light_header = QLabel("☀️ LIGHT MODE - GALLERY COLORS")
        light_header.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            padding: 12px 8px; 
            background-color: #2D2D2D;
            border-radius: 4px;
        """)
        container_layout.addWidget(light_header)
        
        # Gallery colors for light mode
        for item in gallery_colors_dark:  # Same variables
            var_name = item[0]
            description = item[1]
            item_type = item[2] if len(item) > 2 else "color"
            
            current_value = self.theme_colors['LIGHT_THEME'].get(var_name, "#FF00FF")
            
            if item_type == "checkbox":
                # Boolean checkbox toggle
                row = CheckboxRow(var_name, current_value, description)
                row.toggleChanged.connect(lambda v, c, mode='light': self._on_color_changed(mode, v, c))
            elif item_type == "alpha":
                # Numeric value
                if len(item) > 4:
                    min_val, max_val = item[3], item[4]
                    row = AlphaRow(var_name, current_value, description, min_val, max_val)
                else:
                    row = AlphaRow(var_name, current_value, description)
                row.alphaChanged.connect(lambda v, c, mode='light': self._on_color_changed(mode, v, c))
            else:
                # Color picker
                row = ColorPickerRow(var_name, current_value, description)
                row.colorChanged.connect(lambda v, c, mode='light': self._on_color_changed(mode, v, c))
            
            container_layout.addWidget(row)
        
        container_layout.addStretch()
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Apply button
        apply_btn = QPushButton("[OK] Apply & Save to File")
        apply_btn.clicked.connect(self._save_to_file)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #30D158;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 30px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #28B04A;
            }
        """)
        button_layout.addWidget(apply_btn)
        
        button_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("[X] Close (F12)")
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF3B30;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #E0342A;
            }
        """)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
    
    def _on_color_changed(self, mode: str, var_name: str, color: str):
        """Handle color change (debounced)"""
        if mode not in self.color_changes:
            self.color_changes[mode] = {}
        self.color_changes[mode][var_name] = color
        
        # Apply immediately
        from client.gui.theme_variables import DARK_THEME, LIGHT_THEME
        
        # For debug mask, always update BOTH themes so it works regardless of current mode
        if var_name == "gallery_filter_debug_mask":
            DARK_THEME[var_name] = color
            LIGHT_THEME[var_name] = color
        elif mode == 'dark':
            DARK_THEME[var_name] = color
        else:
            LIGHT_THEME[var_name] = color
        
        # If filter bar parameters changed, trigger refresh
        filter_bar_params = (
            "gallery_filter_blur_radius", "gallery_filter_blur_scale", "gallery_filter_debug_mask",
            "gallery_filter_bg", "gallery_filter_overlay", "gallery_filter_overlay_alpha",
            "gallery_filter_mask_top_alpha", "gallery_filter_mask_bottom_alpha"
        )
        if var_name in filter_bar_params:
            self._trigger_filter_bar_blur_refresh()
        
        # If button colors changed, update button styles
        button_params = (
            "gallery_filter_btn_active_bg", "gallery_filter_btn_active_text",
            "gallery_filter_btn_inactive_bg", "gallery_filter_btn_inactive_text",
            "gallery_filter_btn_border"
        )
        if var_name in button_params:
            self._trigger_filter_bar_button_refresh()
        
        # Debounce broadcast
        self._update_timer.start()
    
    def _trigger_filter_bar_blur_refresh(self):
        """Trigger filter bar to recapture blur with new parameters"""
        try:
            # Find the gallery's filter bar and recapture
            from client.plugins.presets.plugin import PresetPlugin
            plugin = PresetPlugin.instance()
            if plugin and plugin._gallery and hasattr(plugin._gallery, '_filter_bar'):
                filter_bar = plugin._gallery._filter_bar
                if filter_bar:
                    filter_bar.capture_blur()
                    # Force immediate repaint for debug overlay
                    filter_bar.update()
        except Exception:
            pass  # Silently fail if gallery not available
    
    def _trigger_filter_bar_button_refresh(self):
        """Trigger filter bar to update button styles with new colors"""
        try:
            from client.plugins.presets.plugin import PresetPlugin
            plugin = PresetPlugin.instance()
            if plugin and plugin._gallery and hasattr(plugin._gallery, '_filter_bar'):
                filter_bar = plugin._gallery._filter_bar
                if filter_bar:
                    filter_bar._update_button_styles()
        except Exception:
            pass  # Silently fail if gallery not available
    
    def _broadcast_theme_change(self):
        """Broadcast theme change to all components"""
        from client.gui.theme import Theme
        from client.gui.theme_manager import ThemeManager
        
        if self.parent():
            theme_manager = ThemeManager.instance()
            current_is_dark = theme_manager.is_dark_mode()
            Theme.set_dark_mode(current_is_dark)
            theme_manager.theme_changed.emit(current_is_dark)
    
    def _save_to_file(self):
        """Save color changes to theme_variables.py file"""
        if not self.color_changes:
            QMessageBox.information(self, "No Changes", "No color changes to save.")
            return
        
        import os
        file_path = os.path.join(os.path.dirname(__file__), "theme_variables.py")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace dark mode colors
            if 'dark' in self.color_changes:
                for var_name, color in self.color_changes['dark'].items():
                    # Match both hex and alpha values
                    pattern = f'"{var_name}":\\s*"(?:#[0-9A-Fa-f]{{6}}|[0-9]+)"'
                    replacement = f'"{var_name}": "{color}"'
                    
                    match = re.search(pattern, content)
                    if match:
                        content = content[:match.start()] + replacement + content[match.end():]
            
            # Replace light mode colors
            if 'light' in self.color_changes:
                for var_name, color in self.color_changes['light'].items():
                    pattern = f'"{var_name}":\\s*"(?:#[0-9A-Fa-f]{{6}}|[0-9]+)"'
                    matches = list(re.finditer(pattern, content))
                    
                    if len(matches) >= 2:
                        match = matches[1]
                        replacement = f'"{var_name}": "{color}"'
                        content = content[:match.start()] + replacement + content[match.end():]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            QMessageBox.information(
                self,
                "[OK] Saved Successfully",
                f"Gallery colors saved to:\n{file_path}\n\nRestart the app to see all changes take effect."
            )
            
            self.color_changes.clear()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "[X] Save Failed",
                f"Failed to save colors:\n{str(e)}"
            )
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle F12 to close the panel"""
        if event.key() == Qt.Key.Key_F12:
            self.close()
        else:
            super().keyPressEvent(event)
