"""
Developer Theme Panel - F12 Interactive Color Editor
Allows real-time theme color adjustment and saving to theme_variables.py
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QColorDialog, QFrame, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
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
        name_label.setMinimumWidth(150)
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
            self.current_color = hex_color
            self.color_preview.setStyleSheet(f"""
                QFrame {{
                    background-color: {hex_color};
                    border: 2px solid #555555;
                    border-radius: 4px;
                }}
            """)
            self.colorChanged.emit(self.var_name, hex_color)


class DevThemePanel(QWidget):
    """Developer panel for interactive theme color editing"""
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("[COLOR] Dev Theme Editor (F12)")
        self.setMinimumSize(900, 700)
        
        # Track color changes
        self.color_changes = {}
        
        # Current theme colors from theme_variables.py
        self.theme_colors = self._load_current_colors()
        
        # Debounce timer for theme updates (prevents lag during rapid changes)
        from PyQt6.QtCore import QTimer
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(200)  # 200ms debounce
        self._update_timer.timeout.connect(self._broadcast_theme_change)
        
        self._setup_ui()
        
        # Apply dark theme to this panel
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
        header = QLabel("[COLOR] Interactive Theme Color Editor")
        header.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px;")
        main_layout.addWidget(header)
        
        # Instructions
        info = QLabel("[TIP] Change colors in real-time. Press 'Apply & Save' to write changes to theme_variables.py")
        info.setStyleSheet("color: #86868B; padding: 5px; font-size: 12px;")
        info.setWordWrap(True)
        main_layout.addWidget(info)
        
        # Scroll area for color pickers
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Container for all color rows
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(2)
        
        # Dark Theme Section
        dark_header = QLabel("🌙 DARK MODE COLORS")
        dark_header.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            padding: 12px 8px; 
            background-color: #2D2D2D;
            border-radius: 4px;
        """)
        container_layout.addWidget(dark_header)
        
        # Add dark theme color pickers
        dark_colors = [
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
        ]
        
        for var_name, description in dark_colors:
            current_color = self.theme_colors['DARK_THEME'].get(var_name, "#FF00FF")
            row = ColorPickerRow(var_name, current_color, description)
            row.colorChanged.connect(lambda v, c, mode='dark': self._on_color_changed(mode, v, c))
            container_layout.addWidget(row)
        
        container_layout.addSpacing(20)
        
        # Light Theme Section
        light_header = QLabel("☀️ LIGHT MODE COLORS")
        light_header.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            padding: 12px 8px; 
            background-color: #2D2D2D;
            border-radius: 4px;
        """)
        container_layout.addWidget(light_header)
        
        # Add light theme color pickers
        for var_name, description in dark_colors:  # Same variables for light mode
            current_color = self.theme_colors['LIGHT_THEME'].get(var_name, "#FF00FF")
            row = ColorPickerRow(var_name, current_color, description)
            row.colorChanged.connect(lambda v, c, mode='light': self._on_color_changed(mode, v, c))
            container_layout.addWidget(row)
        
        container_layout.addStretch()
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Reset button
        reset_btn = QPushButton("[SYNC] Reset All")
        reset_btn.clicked.connect(self._reset_colors)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9500;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #E68600;
            }
        """)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
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
        
        # Debounce the expensive broadcast operation
        # This prevents lag when typing hex codes or dragging sliders
        self._update_timer.start()  # Restart timer on each change
    
    def _broadcast_theme_change(self):
        """Broadcast theme change to all components (called after debounce delay)"""
        from client.gui.theme import Theme
        from client.gui.theme_manager import ThemeManager
        
        if self.parent():
            # Force theme refresh through ThemeManager to update all components
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
            # Reopen to refresh
            QMessageBox.information(self, "Reset", "Colors reset. Please reopen the panel (F12) to see changes.")
    
    def _save_to_file(self):
        """Save color changes to theme_variables.py file"""
        if not self.color_changes:
            QMessageBox.information(self, "No Changes", "No color changes to save.")
            return
        
        import os
        file_path = os.path.join(os.path.dirname(__file__), "theme_variables.py")
        
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
                "[OK] Saved Successfully",
                f"Theme colors saved to:\n{file_path}\n\nRestart the app to see all changes take effect."
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
