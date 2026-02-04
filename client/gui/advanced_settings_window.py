"""
Advanced Settings Window for FFmpeg Configuration
"""

import os
import sys
import subprocess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QRadioButton, QLineEdit, QPushButton, QLabel,
    QFileDialog, QMessageBox, QWidget, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPalette
from client.utils.ffmpeg_settings import get_ffmpeg_settings
from client.core.conversion_engine_validation import (
    validate_ffmpeg_executable,
    validate_system_ffmpeg,
    validate_and_apply_ffmpeg,
    get_all_valid_ffmpeg_paths
)


class AdvancedSettingsWindow(QDialog):
    """Advanced settings dialog for configuring FFmpeg path"""
    
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setWindowTitle("Advanced Settings")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setMinimumWidth(300)
        self.setMaximumWidth(800)
        self.setMinimumHeight(300)
        
        # Get FFmpeg settings manager
        self.ffmpeg_settings = get_ffmpeg_settings()
        
        # Store original settings to allow cancel
        self.original_mode = self.ffmpeg_settings.get_mode()
        self.original_custom_path = self.ffmpeg_settings.get_custom_path()
        
        # Get default ffmpeg path for display
        self.default_ffmpeg_path = self.ffmpeg_settings.get_bundled_ffmpeg_path()
        
        self.setup_ui()
        self.apply_theme()
        
        
    def setup_ui(self):
        """Setup the UI layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title bar
        title_bar = self.create_title_bar()
        main_layout.addWidget(title_bar)
        
        # Conversion Engine Group
        engine_group = QGroupBox("Conversion Engine")
        engine_layout = QVBoxLayout(engine_group)
        engine_layout.setSpacing(10)
        
        # Radio button 1: Use bundled ffmpeg
        self.radio_bundled = QRadioButton("Use ffmpeg file")
        self.radio_bundled.setChecked(self.original_mode in ['bundled', 'custom'])
        self.radio_bundled.toggled.connect(self.on_radio_toggled)
        engine_layout.addWidget(self.radio_bundled)
        
        # Path input for bundled ffmpeg
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(30, 0, 0, 0)
        
        self.path_input = QLineEdit()
        # Show custom path or default path as placeholder
        if self.original_mode == 'custom' and self.original_custom_path:
            self.path_input.setText(self.original_custom_path)
        else:
            self.path_input.setPlaceholderText(self.default_ffmpeg_path)
        self.path_input.setEnabled(self.original_mode == 'custom')
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setMaximumWidth(100)
        self.browse_btn.clicked.connect(self.browse_ffmpeg)
        self.browse_btn.setEnabled(self.original_mode == 'custom')
        
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)
        engine_layout.addLayout(path_layout)
        
        # Radio button 2: Use system ffmpeg
        self.radio_system = QRadioButton("Use system's ffmpeg engine")
        self.radio_system.setChecked(self.original_mode == 'system')
        self.radio_system.toggled.connect(self.on_radio_toggled)
        engine_layout.addWidget(self.radio_system)
        
        # System ffmpeg dropdown selector
        system_path_layout = QHBoxLayout()
        system_path_layout.setContentsMargins(30, 0, 0, 0)
        
        self.system_ffmpeg_combo = QComboBox()
        self.system_ffmpeg_combo.setEnabled(False)
        self.system_ffmpeg_combo.setPlaceholderText("Select FFmpeg installation...")
        
        system_path_layout.addWidget(self.system_ffmpeg_combo)
        engine_layout.addLayout(system_path_layout)
        
        # Status label (must be created before populate_ffmpeg_dropdown)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        engine_layout.addWidget(self.status_label)
        
        # Populate dropdown if system mode is selected (after status_label exists)
        if self.original_mode == 'system':
            self.populate_ffmpeg_dropdown()

        
        main_layout.addWidget(engine_group)
        
        # Spacer
        main_layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.clicked.connect(self.on_cancel)
        
        self.accept_btn = QPushButton("Accept")
        self.accept_btn.setMinimumWidth(100)
        self.accept_btn.clicked.connect(self.on_accept)
        self.accept_btn.setDefault(True)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.accept_btn)
        
        main_layout.addLayout(button_layout)
        
    def create_title_bar(self):
        """Create custom title bar"""
        title_bar = QWidget()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(0, 0, 0, 10)
        
        # Add space after title for better font matching
        title_label = QLabel("Advanced Settings ")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setMaximumWidth(30)
        close_btn.setMaximumHeight(30)
        close_btn.clicked.connect(self.on_cancel)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        title_layout.addWidget(close_btn)
        
        self.title_close_btn = close_btn
        
        return title_bar
        
    def on_radio_toggled(self):
        """Handle radio button toggle"""
        if self.radio_bundled.isChecked():
            self.path_input.setEnabled(True)
            self.browse_btn.setEnabled(True)
            # Show default path if no custom path set
            if not self.path_input.text():
                self.path_input.setPlaceholderText(self.default_ffmpeg_path)
            self.status_label.setText("")
            # Clear and disable system dropdown
            self.system_ffmpeg_combo.clear()
            self.system_ffmpeg_combo.setEnabled(False)
        else:
            self.path_input.setEnabled(False)
            self.browse_btn.setEnabled(False)
            # Check system ffmpeg and populate dropdown
            if self.radio_system.isChecked():
                self.populate_ffmpeg_dropdown()
                if self.system_ffmpeg_combo.count() == 0:
                    # No valid FFmpeg found, revert to bundled
                    self.radio_bundled.setChecked(True)
                    
                    msg = QMessageBox(
                        QMessageBox.Icon.Warning,
                        "System FFmpeg Not Found",
                        "Could not find a valid FFmpeg executable in your system PATH.\n\nReverting to 'Use ffmpeg file'.",
                        parent=self
                    )
                    msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.FramelessWindowHint)
                    if self.theme_manager:
                        msg.setStyleSheet(self.theme_manager.get_dialog_styles())
                    msg.exec()

    def browse_ffmpeg(self):
        """Open file dialog to browse for ffmpeg executable"""
        # Allow any file containing 'ffmpeg' in the name, but only .exe on Windows
        if os.name == 'nt':  # Windows
            file_filter = "FFmpeg Executable (*ffmpeg*.exe);;All Files (*.*)"
        else:  # Unix-like
            file_filter = "FFmpeg Executable (*ffmpeg*);;All Files (*)"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FFmpeg Executable",
            "",
            file_filter
        )
        
        if file_path:
            # Validate the selected file using validation module
            is_valid, error_msg, version_info = validate_ffmpeg_executable(file_path)
            if is_valid:
                self.path_input.setText(file_path)
                self.status_label.setText(f"[OK] Valid FFmpeg executable selected")
                self.status_label.setStyleSheet("color: green;")
                
                # Auto-switch to "Use ffmpeg file" if currently in system mode
                if self.radio_system.isChecked():
                    self.radio_bundled.setChecked(True)
            else:
                self.status_label.setText(f"[X] {error_msg}")
                self.status_label.setStyleSheet("color: red;")
                
    def populate_ffmpeg_dropdown(self):
        """Populate dropdown with all valid FFmpeg installations"""
        self.system_ffmpeg_combo.clear()
        
        # Get all valid FFmpeg paths
        ffmpeg_list = get_all_valid_ffmpeg_paths()
        
        if not ffmpeg_list:
            self.status_label.setText("[X] No valid FFmpeg found in PATH")
            self.status_label.setStyleSheet("color: red;")
            self.system_ffmpeg_combo.setEnabled(False)
            return
        
        
        # Populate dropdown - only show FFmpeg with all required codecs
        valid_count = 0
        for path, version_info, has_all_codecs, missing_codecs in ffmpeg_list:
            # Skip FFmpeg installations missing required codecs
            if not has_all_codecs:
                continue
            
            # Extract just the version number from version_info
            version_short = version_info.split()[2] if len(version_info.split()) > 2 else "unknown"
            
            # Create display text
            display_text = f"{path} - v{version_short} ([OK] all codecs)"
            
            # Add to dropdown with path as user data
            self.system_ffmpeg_combo.addItem(display_text, userData=path)
            valid_count += 1
        
        # Enable dropdown and select first item
        self.system_ffmpeg_combo.setEnabled(True)
        self.system_ffmpeg_combo.setCurrentIndex(0)
        
        # Update status
        self.status_label.setText(f"[OK] Found {valid_count} valid FFmpeg installation(s)")

        self.status_label.setStyleSheet("color: green;")
            
    def on_accept(self):
        """Accept and save settings"""
        if self.radio_bundled.isChecked():
            # Using bundled or custom ffmpeg file
            ffmpeg_path = self.path_input.text().strip()
            
            if ffmpeg_path:
                # Custom path specified - validate using validation module
                is_valid, error_msg, version_info = validate_ffmpeg_executable(ffmpeg_path)
                
                if not is_valid:
                    msg = QMessageBox(
                        QMessageBox.Icon.Warning,
                        "Invalid FFmpeg",
                        f"The selected file is not a valid FFmpeg executable.\n\n{error_msg}\n\nSettings will not be saved.",
                        parent=self
                    )
                    msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.FramelessWindowHint)
                    if self.theme_manager:
                        msg.setStyleSheet(self.theme_manager.get_dialog_styles())
                    msg.exec()
                    return
                
                # Save custom mode and path
                self.ffmpeg_settings.set_mode('custom')
                self.ffmpeg_settings.set_custom_path(ffmpeg_path)
                
                # Apply to environment using validation module
                success, error, applied_path = validate_and_apply_ffmpeg('custom', ffmpeg_path)
                if not success:
                    print(f"Warning: Failed to apply custom FFmpeg: {error}")
            else:
                # Use default bundled ffmpeg
                self.ffmpeg_settings.set_mode('bundled')
                self.ffmpeg_settings.set_custom_path('')
                
                # Apply to environment using validation module
                success, error, applied_path = validate_and_apply_ffmpeg('bundled')
                if not success:
                    print(f"Warning: Failed to apply bundled FFmpeg: {error}")
                
        elif self.radio_system.isChecked():
            # Using system ffmpeg - get selected path from dropdown
            if self.system_ffmpeg_combo.count() == 0:
                # No FFmpeg in dropdown, revert to bundled
                msg = QMessageBox(
                    QMessageBox.Icon.Warning,
                    "System FFmpeg Not Available",
                    "No valid system FFmpeg found. Reverting to bundled FFmpeg.",
                    parent=self
                )
                msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.FramelessWindowHint)
                if self.theme_manager:
                    msg.setStyleSheet(self.theme_manager.get_dialog_styles())
                msg.exec()
                
                # Revert to bundled
                self.radio_bundled.setChecked(True)
                self.ffmpeg_settings.set_mode('bundled')
                
                # Apply bundled settings
                success, error, applied_path = validate_and_apply_ffmpeg('bundled')
                if not success:
                    print(f"Warning: Failed to apply bundled FFmpeg: {error}")
                return
            else:
                # Get selected FFmpeg path from dropdown
                selected_path = self.system_ffmpeg_combo.currentData()
                
                if not selected_path:
                    print("Warning: No FFmpeg path selected from dropdown")
                    return
                
                # Save system mode with the selected path
                self.ffmpeg_settings.set_mode('system')
                self.ffmpeg_settings.set_custom_path(selected_path)  # Store selected path
                
                # Apply to environment using validation module
                success, error, applied_path = validate_and_apply_ffmpeg('system')
                if not success:
                    print(f"Warning: Failed to apply system FFmpeg: {error}")
        
        
        self.accept()
        
    def on_cancel(self):
        """Cancel and close without saving"""
        # Restore original settings if they were changed
        if self.ffmpeg_settings.get_mode() != self.original_mode:
            self.ffmpeg_settings.set_mode(self.original_mode)
        if self.ffmpeg_settings.get_custom_path() != self.original_custom_path:
            self.ffmpeg_settings.set_custom_path(self.original_custom_path)
        self.reject()
        
    def apply_theme(self):
        """Apply theme to the dialog"""
        if not self.theme_manager:
            return
            
        # Get base dialog styles from theme manager (centralized)
        # This now includes pill-shaped radio button styling
        base_styles = self.theme_manager.get_dialog_styles()
        
        # Add Advanced Settings-specific styles
        from client.gui.theme import Theme
        
        # Ensure theme is set correctly
        Theme.set_dark_mode(self.theme_manager.is_dark_mode())
        
        # Additional styles specific to Advanced Settings window
        advanced_styles = f"""
            QDialog {{
                background-color: {Theme.surface()};
                border-radius: 8px;
            }}
            QGroupBox {{
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                background-color: transparent;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: {Theme.text()};
            }}
            QLineEdit {{
                background-color: {Theme.color('input_bg')};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 5px;
                font-family: '{Theme.FONT_BODY}';
            }}
            QLineEdit::placeholder {{
                color: {Theme.text_muted()};
            }}
            QLineEdit:disabled {{
                color: {Theme.text_muted()};
                background-color: {Theme.surface()};
            }}
            QComboBox {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 5px;
                min-height: 20px;
                font-family: '{Theme.FONT_BODY}';
            }}
            QComboBox:hover {{
                border-color: {Theme.success()};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {Theme.text()};
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                selection-background-color: {Theme.color('surface_hover')};
                selection-color: {Theme.text()};
            }}
            QComboBox:disabled {{
                color: {Theme.text_muted()};
                background-color: {Theme.surface()};
            }}
            QPushButton:default {{
                background-color: {Theme.color('info')};
                color: white;
                border: 1px solid {Theme.color('info')};
            }}
            QPushButton:default:hover {{
                background-color: {Theme.accent()};
                border: 1px solid {Theme.accent()};
            }}
        """
        
        # Combine base and advanced styles
        self.setStyleSheet(base_styles + advanced_styles)
        
        # Title bar close button specific styling (red hover)
        close_style = f"""
            QPushButton {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: none;
                border-radius: 3px;
                padding: 2px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #cc0000;
                color: #ffffff;
            }}
        """
        self.title_close_btn.setStyleSheet(close_style)

