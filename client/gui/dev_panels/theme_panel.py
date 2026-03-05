"""
Developer Theme Panel (F12)
Allows real-time theme color adjustment and saving to theme_variables.py
"""

import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QColorDialog, QFrame, QLineEdit, QMessageBox, QGroupBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor


class AlphaRow(QWidget):
    """Row for numeric value with spinbox"""
    
    alphaChanged = Signal(str, str)  # (variable_name, value_as_string)
    
    def __init__(self, var_name: str, value_str: str, description: str = "", min_val: int = 0, max_val: int = 255, parent=None):
        super().__init__(parent)
        self.var_name = var_name
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)
        
        # Variable name
        name_label = QLabel(var_name)
        name_label.setMinimumWidth(180)
        name_label.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-weight: bold; color: #F5F5F7;")
        layout.addWidget(name_label)
        
        # Numeric spinbox
        self.alpha_spin = QGroupBox() # Placeholder for type compatibility if needed, but using SpinBox direct
        from PySide6.QtWidgets import QSpinBox
        self.alpha_spin = QSpinBox()
        self.alpha_spin.setRange(min_val, max_val)
        
        # Handle potential hex or empty values gracefully by defaulting to max
        try:
            val = int(value_str)
        except (ValueError, TypeError):
            val = max_val
            
        self.alpha_spin.setValue(val)
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
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label, 1)


from .base import BaseDevPanel



class ColorPickerRow(QWidget):
    """Single row with color variable name, preview, and edit button"""
    
    colorChanged = Signal(str, str)  # (variable_name, hex_color)
    
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
        name_label.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-weight: bold; color: #F5F5F7;")
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
        pick_btn = QPushButton("Pick")
        pick_btn.setMaximumWidth(60)
        pick_btn.clicked.connect(self._pick_color)
        pick_btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px;
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
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label, 1)
    
    def _on_hex_changed(self, text: str):
        """Validate and apply hex color from text input"""
        text = text.strip()
        if re.match(r'^#[0-9A-Fa-f]{6}$', text):
            self.current_color = text
            self._update_preview(text)
            self.colorChanged.emit(self.var_name, text)
    
    def _pick_color(self):
        """Open color picker dialog"""
        current = QColor(self.current_color)
        color = QColorDialog.getColor(current, self, f"Pick color for {self.var_name}")
        
        if color.isValid():
            hex_color = color.name().upper()
            self.hex_input.setText(hex_color)
            self.current_color = hex_color
            self._update_preview(hex_color)
            self.colorChanged.emit(self.var_name, hex_color)
            
    def _update_preview(self, color_hex):
        self.color_preview.setStyleSheet(f"""
            QFrame {{
                background-color: {color_hex};
                border: 2px solid #555555;
                border-radius: 4px;
            }}
        """)


class DevThemePanel(BaseDevPanel):
    """Developer panel for interactive theme color editing"""
    
    def __init__(self, parent=None):
        super().__init__(
            title="🎨 Theme Color Editor (F12)",
            parent=parent,
            width=900,
            height=800
        )
        
        # Track color changes
        self.color_changes = {}
        
        # Current theme colors from theme_variables.py
        self.theme_colors = self._load_current_colors()
        
        # Debounce timer for theme updates
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(200)  # 200ms debounce
        self._update_timer.timeout.connect(self._broadcast_theme_change)
        
        self._setup_content()
        
        # Add Footer Buttons
        self.add_footer_button("Save Changes to File", self._save_to_file, primary=True, color="#30D158")
        self.add_footer_button("Reset All", self._reset_colors, color="#FF9500")
        
    def _load_current_colors(self):
        """Load current colors from theme_variables module"""
        from client.gui.theme_variables import DARK_THEME, LIGHT_THEME
        return {
            'DARK_THEME': DARK_THEME.copy(),
            'LIGHT_THEME': LIGHT_THEME.copy()
        }
        
    def _setup_content(self):
        """Setup the UI layout"""
        # Instructions
        info = QLabel("TIP: Change colors in real-time. Press 'Save Changes' to write to theme_variables.py")
        info.setStyleSheet("color: #86868B; padding-bottom: 10px; font-size: 12px;")
        info.setWordWrap(True)
        self.content_layout.addWidget(info)
        
        # Dark Theme Section
        dark_group = QGroupBox("🌙 DARK MODE COLORS")
        dark_group.setStyleSheet("QGroupBox { font-weight: bold; color: #F5F5F7; margin-top: 10px; }")
        dark_layout = QVBoxLayout()
        dark_layout.setSpacing(2)
        
        # Add dark theme color pickers
        dark_colors_list = [
            ("app_bg", "Deepest Void (Window Background)"),
            ("surface_main", "Drop Zone / Panels"),
            ("surface_element", "Buttons / Inputs"),
            ("surface_drop_area", "Drop area file item background"),
            ("surface_hover", "Hover state for surfaces"),
            ("surface_pressed", "Pressed state"),
            ("input_bg", "Text input background"),
            ("translucent_bg", "Translucent title bar with blur"),
            ("presets_bg", "Preset gallery overlay background"),
            ("border_dim", "Subtle Separation"),
            ("border_focus", "Hover/Focus State"),
            ("text_primary", "Main Readability"),
            ("text_secondary", "Labels / Meta Data"),
            ("accent_primary", "Standard Action"),
            ("accent_turbo", "GPU Active (Electric Cyan)"),
            ("accent_success", "Success State"),
            ("error", "Error/Danger (iOS Red)"),
            ("warning", "Warning (iOS Orange)"),
            ("info", "Info (iOS Blue)"),
            ("scrollbar_bg", "Scrollbar track"),
            ("scrollbar_thumb", "Scrollbar handle"),
            ("tooltip_bg", "Tooltip Background"),
            
            # Header Button Colors
            ("btn_preset_active", "Preset button active (green)"),
            ("btn_preset_ghost", "Preset button ghost/inactive"),
            ("btn_lab_solid", "Lab button solid (blue)"),
            ("btn_lab_ghost", "Lab button ghost/inactive"),
            ("btn_file_normal", "File button normal (grey)"),
            ("btn_file_hover", "File button hover (white)"),
            ("titlebar_btn_bg", "Title bar button background"),
            ("titlebar_btn_hover", "Title bar button hover"),
            
            # Gallery Filter Colors (for tuning gradients)
            ("gallery_filter_bg", "Filter Gradient Color (Start)"),
            ("gallery_filter_overlay", "Filter Overlay Color"),
            ("gallery_filter_overlay_alpha", "Filter Overlay Alpha (0-255)", "alpha"),
            ("gallery_filter_mask_top_alpha", "Gradient Mask Top Alpha (0-255)", "alpha"),
            ("gallery_filter_mask_bottom_alpha", "Gradient Mask Bottom Alpha (0-255)", "alpha"),
            ("gallery_filter_noise_opacity", "Filter Noise Opacity (0-255)", "alpha"),
        ]
        
        for item in dark_colors_list:
            var_name = item[0]
            description = item[1]
            item_type = item[2] if len(item) > 2 else "color"
            
            current_value = self.theme_colors['DARK_THEME'].get(var_name, "#FF00FF")
            
            if item_type == "alpha":
                row = AlphaRow(var_name, str(current_value), description)
                row.alphaChanged.connect(lambda v, c, mode='dark': self._on_color_changed(mode, v, c))
            else:
                row = ColorPickerRow(var_name, current_value, description)
                row.colorChanged.connect(lambda v, c, mode='dark': self._on_color_changed(mode, v, c))
                
            dark_layout.addWidget(row)
            
        dark_group.setLayout(dark_layout)
        self.content_layout.addWidget(dark_group)
        
        self.content_layout.addSpacing(20)
        
        # Light Theme Section
        light_group = QGroupBox("☀️ LIGHT MODE COLORS")
        light_group.setStyleSheet("QGroupBox { font-weight: bold; color: #F5F5F7; margin-top: 10px; }")
        light_layout = QVBoxLayout()
        light_layout.setSpacing(2)
        
        # Add light theme color pickers
        for item in dark_colors_list:  # Same variables for light mode
            var_name = item[0]
            description = item[1]
            item_type = item[2] if len(item) > 2 else "color"
            
            current_value = self.theme_colors['LIGHT_THEME'].get(var_name, "#FF00FF")
            
            if item_type == "alpha":
                row = AlphaRow(var_name, str(current_value), description)
                row.alphaChanged.connect(lambda v, c, mode='light': self._on_color_changed(mode, v, c))
            else:
                row = ColorPickerRow(var_name, current_value, description)
                row.colorChanged.connect(lambda v, c, mode='light': self._on_color_changed(mode, v, c))
            
            light_layout.addWidget(row)
            
        light_group.setLayout(light_layout)
        self.content_layout.addWidget(light_group)
        
        self.content_layout.addStretch()

    def _on_color_changed(self, mode: str, var_name: str, color: str):
        """Handle color change and apply in real-time (debounced)"""
        # Store the change
        if mode not in self.color_changes:
            self.color_changes[mode] = {}
        self.color_changes[mode][var_name] = color
        
        # Apply to current theme dictionary immediately (fast)
        from client.gui.theme_variables import DARK_THEME, LIGHT_THEME
        
        if mode == 'dark':
            DARK_THEME[var_name] = color
        else:
            LIGHT_THEME[var_name] = color
        
        # If filter parameters changed, we should notify the gallery if possible
        # This is a bit of a hack to reach across modules, but updates are broadcast via theme_manager anyway
        # The specific gallery redraw trigger happens in DevGalleryColorPanel but here we rely on standard theme updates
        
        # Debounce the expensive broadcast operation
        self._update_timer.start()
    
    def _broadcast_theme_change(self):
        """Broadcast theme change to all components"""
        from client.gui.theme import Theme
        from client.gui.theme_manager import ThemeManager
        
        # Force theme refresh through ThemeManager
        theme_manager = ThemeManager.instance()
        current_is_dark = theme_manager.is_dark_mode()
        Theme.set_dark_mode(current_is_dark)
        theme_manager.theme_changed.emit(current_is_dark)
    
    def _reset_colors(self):
        """Reset all colors to original values"""
        reply = QMessageBox.question(
            self,
            "Reset Colors",
            "Reset all colors to their original values?\nThis will reload the file but NOT save.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.color_changes.clear()
            self.theme_colors = self._load_current_colors()
            self.close()
            # Reopen to refresh logic would be handled by manager if needed, 
            # but usually close + repoen by user is fine.
            QMessageBox.information(self, "Reset", "Colors reset. Please reopen the panel (F12) to see changes.")
    
    def _save_to_file(self):
        """Save color changes to theme_variables.py file"""
        if not self.color_changes:
            QMessageBox.information(self, "No Changes", "No color changes to save.")
            return
        
        # Path adjustment for new location: dev_panels -> gui -> theme_variables.py
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "theme_variables.py")
        
        try:
            # Read the current file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace dark mode colors
            if 'dark' in self.color_changes:
                for var_name, color in self.color_changes['dark'].items():
                    # Match both hex colors (#RRGGBB) and rgba values (rgba(...))
                    pattern = f'"{var_name}":\\s*"(?:#[0-9A-Fa-f]{{6}}|rgba\\([^)]+\\))"'
                    replacement = f'"{var_name}": "{color}"'
                    
                    # Find the first occurrence (dark mode section)
                    match = re.search(pattern, content)
                    if match:
                        content = content[:match.start()] + replacement + content[match.end():]
            
            # Replace light mode colors
            if 'light' in self.color_changes:
                for var_name, color in self.color_changes['light'].items():
                    # Match both hex colors and rgba values
                    pattern = f'"{var_name}":\\s*"(?:#[0-9A-Fa-f]{{6}}|rgba\\([^)]+\\))"'
                    matches = list(re.finditer(pattern, content))
                    
                    if len(matches) >= 2:
                        # Replace the second occurrence (light mode)
                        match = matches[1]
                        replacement = f'"{var_name}": "{color}"'
                        content = content[:match.start()] + replacement + content[match.end():]
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            QMessageBox.information(
                self,
                "Saved Successfully",
                f"Theme colors saved to:\n{file_path}\n\nRestart the app to see all changes take effect."
            )
            
            self.color_changes.clear()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Failed to save colors:\n{str(e)}"
            )
