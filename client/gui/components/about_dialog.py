"""
About Dialog Component
Displays application information, version, and credits.
"""

import os
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from client.utils.font_manager import FONT_FAMILY_APP_NAME
from client.version import APP_NAME, AUTHOR


def show_about_dialog(parent, theme_manager):
    """
    Show the About dialog with application information.
    
    Args:
        parent: Parent widget for the dialog
        theme_manager: ThemeManager instance for styling
    """
    # Get version info
    try:
        from client.version import get_version_info
        version_info = get_version_info()
        version = version_info['version']
    except ImportError:
        version = "1.1.0"
    
    # Get theme-appropriate colors
    current_theme = theme_manager.get_current_theme()
    if current_theme == 'dark':
        bg_color = "#2b2b2b"
        text_color = "#ffffff" 
        accent_color = "#4a9eff"
    else:
        bg_color = "#ffffff"
        text_color = "#000000"
        accent_color = "#0066cc"
    
    about_text = f"""
    <div style="text-align: center; color: {text_color};">
    <h2 style="font-family: '{FONT_FAMILY_APP_NAME}'; color: {accent_color}; margin-bottom: 10px;">{APP_NAME}</h2>
    <p><b>Version:</b> {version}</p>
    <p><b>Author:</b> <span style="color: {text_color};">{AUTHOR}</span></p>
    </div>
    <br>
    <p style="color: {text_color};">Web export simplified.</p>
    <p style="color: {text_color};">Convert files to WebM, WebP, GIF, MP4, and other formats in just a few clicks.</p>
    <p style="color: {text_color};">Built for speed, quality, and ease of use.</p>
    <br>
    <p style="color: {text_color};">[WEB] <a href="" style="color: {accent_color}; text-decoration: none;">Visit our website</a></p>
    <br>
    <p style="color: {text_color};">This software uses FFmpeg (© FFmpeg developers) licensed under the LGPL/GPL.</p>
    <p style="color: {text_color};">© 2025 {AUTHOR}. All rights reserved.</p>
    """
    
    msg = QMessageBox(parent)
    msg.setWindowTitle(f"About {APP_NAME}")
    msg.setText(about_text)
    
    # Set custom icon (app logo)
    try:
        from client.utils.resource_path import get_app_icon_path
        icon_path = get_app_icon_path()
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            msg.setIconPixmap(icon.pixmap(64, 64))
    except Exception as e:
        print(f"Could not set about dialog icon: {e}")
        msg.setIcon(QMessageBox.Icon.Information)
    
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    
    # Frameless window
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.FramelessWindowHint)
    
    # Apply theme styling
    dialog_style = f"""
    QMessageBox {{
        background-color: {bg_color};
        color: {text_color};
        border: 1px solid #555555;
        border-radius: 8px;
    }}
    QMessageBox QLabel {{
        color: {text_color};
        background-color: {bg_color};
    }}
    QMessageBox QPushButton {{
        background-color: #0066cc;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
    }}
    QMessageBox QPushButton:hover {{
        background-color: #0052a3;
    }}
    QMessageBox QPushButton:pressed {{
        background-color: #003d7a;
    }}
    """
    msg.setStyleSheet(dialog_style)
    msg.resize(450, 400)
    msg.exec()
