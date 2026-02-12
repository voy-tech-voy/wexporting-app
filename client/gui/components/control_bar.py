"""
Control Bar Component - Mediator-Shell Architecture

Unified control bar with file buttons, preset toggle, and lab mode selector.
Extracted from MainWindow to follow the Mediator-Shell pattern.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QCursor


class ControlBar(QWidget):
    """
    Unified control bar with file buttons, preset toggle, and lab mode selector.
    
    Signals:
        add_files_clicked: Emitted when "Add Files" button is clicked
        add_folder_clicked: Emitted when "Add Folder" button is clicked
        clear_files_clicked: Emitted when "Clear All" button is clicked
        preset_mode_clicked: Emitted when Preset button is clicked
        lab_mode_clicked(int): Emitted when a Lab mode item is clicked (tab index)
    """
    
    # Signals for Mediator routing
    add_files_clicked = pyqtSignal()
    add_folder_clicked = pyqtSignal()
    clear_files_clicked = pyqtSignal()
    preset_mode_clicked = pyqtSignal()
    lab_mode_clicked = pyqtSignal(int)  # Tab index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.setObjectName("ControlBar")
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the control bar UI."""
        from client.gui.custom_widgets import HoverIconButton, PresetStatusButton, MorphingButton

        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)
        
        # --- Left Section: File Buttons ---
        icon_size = QSize(28, 28)
        
        self.add_files_btn = HoverIconButton("addfile.svg", icon_size)
        self.add_files_btn.setFixedSize(48, 48)
        self.add_files_btn.setToolTip("Add Files")
        self.add_files_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_files_btn.clicked.connect(self.add_files_clicked.emit)
        
        self.add_folder_btn = HoverIconButton("addfolder.svg", icon_size)
        self.add_folder_btn.setFixedSize(48, 48)
        self.add_folder_btn.setToolTip("Add Folder")
        self.add_folder_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_folder_btn.clicked.connect(self.add_folder_clicked.emit)
        
        self.clear_files_btn = HoverIconButton("removefile.svg", icon_size)
        self.clear_files_btn.setFixedSize(48, 48)
        self.clear_files_btn.setToolTip("Clear All")
        self.clear_files_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_files_btn.clicked.connect(self.clear_files_clicked.emit)
        
        # Connect to ThemeManager for initial state
        from client.gui.theme_manager import ThemeManager
        theme_manager = ThemeManager.instance()
        self._is_dark = theme_manager.is_dark_mode()
        
        # Apply Styles using the dynamic method
        self._apply_button_styles(self._is_dark)
        
        layout.addWidget(self.add_files_btn)
        layout.addWidget(self.add_folder_btn)
        layout.addWidget(self.clear_files_btn)
        
        # --- Spacer (Left) ---
        layout.addStretch()
        
        # --- Center: Preset Button ---
        self.preset_status_btn = PresetStatusButton()
        self.preset_status_btn.clicked.connect(self.preset_mode_clicked.emit)
        layout.addWidget(self.preset_status_btn)
        
        # --- Spacer (Right) ---
        layout.addStretch()
        
        # --- Right: Lab Button (in fixed-width container) ---
        lab_container = QWidget()
        lab_container.setFixedWidth(220)
        lab_container_layout = QHBoxLayout(lab_container)
        lab_container_layout.setContentsMargins(0, 0, 0, 0)
        lab_container_layout.setSpacing(0)
        lab_container_layout.addStretch()
        
        self.lab_btn = MorphingButton(main_icon_path="client/assets/icons/lab_icon.svg")
        self.lab_btn.add_menu_item(0, "client/assets/icons/pic_icon2.svg", "Image Conversion")
        self.lab_btn.add_menu_item(1, "client/assets/icons/vid_icon.svg", "Video Conversion")
        self.lab_btn.add_menu_item(2, "client/assets/icons/loop_icon3.svg", "Loop Conversion")
        self.lab_btn.itemClicked.connect(self._on_lab_item_clicked)
        lab_container_layout.addWidget(self.lab_btn)
        
        layout.addWidget(lab_container)
    
    def _on_lab_item_clicked(self, item_id: int):
        """Handle lab button menu item click."""
        self.lab_mode_clicked.emit(item_id)
    
    # --- Public API for Mediator ---
    
    def set_preset_active(self, active: bool):
        """Set the preset button to active/inactive state."""
        self.preset_status_btn.set_active(active)
    
    def set_preset_name(self, name: str):
        """Set the preset button display name."""
        self.preset_status_btn.set_preset_name(name)
    
    def set_lab_icon(self, icon_path: str):
        """Set the lab button main icon."""
        self.lab_btn.set_main_icon(icon_path)
    
    def set_lab_solid(self, solid: bool):
        """Set the lab button to solid/ghost style."""
        self.lab_btn.set_style_solid(solid)
    
    def highlight_preset(self):
        """Visual highlight for preset mode active."""
        # Don't automatically set button to active - only activate when preset is selected
        self.set_lab_solid(False)
        self.set_lab_icon("client/assets/icons/lab_icon.svg")
    
    def highlight_lab(self):
        """Visual highlight for lab mode active."""
        self.set_preset_active(False)
        self.set_lab_solid(True)
    
    def update_theme(self, is_dark: bool):
        """Update theme for all child widgets."""
        self.add_files_btn.set_dark_mode(is_dark)
        self.add_folder_btn.set_dark_mode(is_dark)
        self.clear_files_btn.set_dark_mode(is_dark)
        self.preset_status_btn.update_theme(is_dark)
        self.lab_btn.update_theme(is_dark)
        
        # Update button stylesheets
        self._apply_button_styles(is_dark)
        
    def _apply_button_styles(self, is_dark):
        """Apply theme-dependent styles to file buttons."""
        if is_dark:
            # Dark Mode: White glass effect
            bg_normal = "rgba(255, 255, 255, 5)"
            border_normal = "rgba(255, 255, 255, 20)"
            bg_hover = "rgba(255, 255, 255, 10)"
            border_hover = "rgba(255, 255, 255, 50)"
            bg_pressed = "rgba(0, 0, 0, 50)"
            
            clear_border_hover = "#FF4444"
            clear_bg_hover = "rgba(255, 50, 50, 15)"
        else:
            # Light Mode: Black/Dark glass effect
            bg_normal = "rgba(0, 0, 0, 5)"
            border_normal = "rgba(0, 0, 0, 20)"
            bg_hover = "rgba(0, 0, 0, 10)"
            border_hover = "rgba(0, 0, 0, 50)"
            bg_pressed = "rgba(0, 0, 0, 20)"
            
            clear_border_hover = "#FF3B30"
            clear_bg_hover = "rgba(255, 59, 48, 15)"

        base_style = f"""
            QPushButton {{
                background-color: {bg_normal};
                border: 1px solid {border_normal};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
                border: 1px solid {border_hover};
            }}
            QPushButton:pressed {{
                background-color: {bg_pressed};
            }}
        """
        self.add_files_btn.setStyleSheet(base_style)
        self.add_folder_btn.setStyleSheet(base_style)
        
        # Clear Button Style (Red Outline on Hover)
        clear_style = f"""
            QPushButton {{
                background-color: {bg_normal};
                border: 1px solid {border_normal};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {clear_bg_hover};
                border: 1px solid {clear_border_hover};
            }}
            QPushButton:pressed {{
                background-color: {bg_pressed};
            }}
        """
        self.clear_files_btn.setStyleSheet(clear_style)
