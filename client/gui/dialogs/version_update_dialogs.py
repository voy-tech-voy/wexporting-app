"""
Version Update Dialogs

Dialogs for handling app version updates (Version Gateway Pattern).
Separate from content update dialogs (UpdateDialog).
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                              QHBoxLayout, QWidget, QApplication)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from client.gui.theme_manager import ThemeManager
import webbrowser


class OptionalVersionUpdateDialog(QDialog):
    """
    Dialog for optional app version updates.
    User can dismiss and continue using the app.
    """
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowTitle("Update Available")
        self.setFixedWidth(450)
        self.setFixedHeight(300)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)
        
        # Get theme manager
        self.theme_manager = ThemeManager.instance()
        colors = self.theme_manager.get_colors()
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header
        header = QLabel(f"Version {result.latest_version} Available")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"color: {colors['text']};")
        layout.addWidget(header)
        
        # Current version info
        current_label = QLabel(f"Current version: {self._get_current_version()}")
        current_label.setStyleSheet(f"color: {colors['text_secondary']};")
        current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(current_label)
        
        # Release notes
        if result.release_notes:
            notes_label = QLabel("What's New:")
            notes_label.setStyleSheet(f"font-weight: bold; margin-top: 10px; color: {colors['text']};")
            layout.addWidget(notes_label)
            
            notes_text = QLabel(result.release_notes)
            notes_text.setWordWrap(True)
            notes_text.setStyleSheet(f"color: {colors['text']}; padding: 10px; background-color: {colors['surface']}; border-radius: 4px;")
            layout.addWidget(notes_text)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 10, 0, 0)
        
        self.btn_later = QPushButton("Later")
        self.btn_later.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_later.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {colors['border']};
                color: {colors['text']};
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {colors['surface']};
                border-color: {colors['border_hover']};
            }}
        """)
        self.btn_later.clicked.connect(self.reject)
        
        self.btn_update = QPushButton("Update Now")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['primary']};
                color: {colors['text_on_primary']};
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {colors['primary_hover']};
            }}
            QPushButton:pressed {{
                background-color: {colors['primary_pressed']};
            }}
        """)
        self.btn_update.clicked.connect(self._open_store)
        
        btn_layout.addWidget(self.btn_later)
        btn_layout.addWidget(self.btn_update)
        
        layout.addLayout(btn_layout)
        
    def _get_current_version(self):
        """Get current app version."""
        try:
            from client.version import get_version
            return get_version()
        except:
            return "Unknown"
            
    def _open_store(self):
        """Open store URL and close dialog."""
        if self.result.update_url:
            webbrowser.open(self.result.update_url)
        self.accept()


class MandatoryVersionUpdateScreen(QWidget):
    """
    Full-screen blocking widget for mandatory updates.
    User cannot dismiss - must update to continue.
    """
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | 
                           Qt.WindowType.WindowStaysOnTopHint)
        
        # Get theme manager
        self.theme_manager = ThemeManager.instance()
        colors = self.theme_manager.get_colors()
        self.setStyleSheet(f"background-color: {colors['background']};")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        # Icon/Warning
        warning = QLabel("⚠️")
        warning.setStyleSheet("font-size: 64px;")
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning)
        
        # Title
        title = QLabel("Update Required")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {colors['text']};")
        layout.addWidget(title)
        
        # Message
        message = QLabel(
            f"This version of the app is no longer supported.\n"
            f"Please update to version {result.latest_version} to continue."
        )
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet(f"color: {colors['text']}; font-size: 14px;")
        message.setWordWrap(True)
        layout.addWidget(message)
        
        # Current vs Required
        version_info = QLabel(
            f"Current: {self._get_current_version()} | "
            f"Required: {result.min_required_version}+"
        )
        version_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_info.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 12px; margin-top: 10px;")
        layout.addWidget(version_info)
        
        # Release notes
        if result.release_notes:
            notes = QLabel(result.release_notes)
            notes.setAlignment(Qt.AlignmentFlag.AlignCenter)
            notes.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 12px; margin-top: 20px; max-width: 400px;")
            notes.setWordWrap(True)
            layout.addWidget(notes)
        
        # Update button
        self.btn_update = QPushButton("Update Now")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setFixedSize(200, 50)
        self.btn_update.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['error']};
                color: {colors['text_on_error']};
                border: none;
                border-radius: 25px;
                font-weight: bold;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {colors['error_hover']};
            }}
            QPushButton:pressed {{
                background-color: {colors['error_pressed']};
            }}
        """)
        self.btn_update.clicked.connect(self._open_store)
        layout.addWidget(self.btn_update, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Quit button (small, subtle)
        self.btn_quit = QPushButton("Quit App")
        self.btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quit.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {colors['text_tertiary']};
                border: none;
                padding: 5px 10px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {colors['text_secondary']};
            }}
        """)
        self.btn_quit.clicked.connect(QApplication.instance().quit)
        layout.addWidget(self.btn_quit, alignment=Qt.AlignmentFlag.AlignCenter)
        
    def _get_current_version(self):
        """Get current app version."""
        try:
            from client.version import get_version
            return get_version()
        except:
            return "Unknown"
            
    def _open_store(self):
        """Open store URL."""
        if self.result.update_url:
            webbrowser.open(self.result.update_url)
            
    def closeEvent(self, event):
        """Prevent closing the window."""
        event.ignore()
        
    def keyPressEvent(self, event):
        """Prevent Escape key from closing."""
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
        else:
            super().keyPressEvent(event)
