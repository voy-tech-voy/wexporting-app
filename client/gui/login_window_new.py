"""
New Login Window for ImgApp
Modern split-layout with media display and login section
"""

import os
import json
import sys
import socket
import platform
from datetime import datetime
from datetime import timedelta
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QCheckBox, QMessageBox, QApplication, QWidget
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QPoint, QByteArray, QUrl, QThread
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QPainter, QPalette, QImage
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtSvg import QSvgRenderer
from client.utils.font_manager import AppFonts, FONT_FAMILY
from client.utils.server_health import ServerHealthChecker
from client.utils.resource_path import get_resource_path
from client.version import APP_NAME
import requests

# Development mode detection
DEVELOPMENT_MODE = getattr(sys, '_called_from_test', False) or __debug__ and not getattr(sys, 'frozen', False)

# Helper function to detect dark mode
def is_dark_mode():
    """Check if system is in dark mode"""
    if sys.platform == 'win32':
        try:
            import winreg
            registry_path = r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path)
            value, _ = winreg.QueryValueEx(registry_key, 'AppsUseLightTheme')
            return value == 0
        except Exception:
            return True
    return True

def get_toggle_style(is_dark=None):
    """Get toggle style matching main app style"""
    if is_dark is None:
        is_dark = is_dark_mode()
    bg_color = "#2b2b2b" if is_dark else "#ffffff"
    text_color = "white" if is_dark else "black"
    
    return (
        f"QCheckBox {{ color: {text_color}; }} "
        f"QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 8px;"
        f" border: 2px solid #43a047; background: {bg_color}; }}"
        "QCheckBox::indicator:checked { background: #43a047; border: 2px solid #2e7d32; }"
        "QCheckBox::indicator:unchecked:hover { border: 2px solid #2e7d32; }"
    )


class EmailInput(QLineEdit):
    """Specialized input with validation and error display - shows placeholder even when focused"""
    def __init__(self, placeholder_text="Enter your email", validate_as_email=True, error_message="required", parent=None):
        super().__init__(parent)
        self.original_placeholder = placeholder_text
        self.validate_as_email = validate_as_email  # If False, only checks if empty (for license keys)
        self.empty_error_message = error_message  # Error message for empty field
        self.setPlaceholderText(placeholder_text)
        self.setFixedSize(350, 50)
        self.setFont(QFont(FONT_FAMILY, 14))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_timer = QTimer()
        self.error_timer.setSingleShot(True)
        self.error_timer.timeout.connect(self._reset_error_state)
        self.validation_handler = None  # Will be set to handle validation
        self.bypass_validation_for = []  # List of emails that bypass validation (for dev mode)
        
        # Apply styling with visible placeholder
        self.apply_theme_style(is_dark_mode())
        
        # Ensure text is empty so placeholder shows
        self.setText("")
    
    def paintEvent(self, event):
        """Override to draw placeholder even when focused"""
        super().paintEvent(event)
        
        # Draw placeholder text when field is empty, even if focused
        if not self.text() and self.placeholderText():
            from PyQt6.QtGui import QPainter, QColor
            
            painter = QPainter(self)
            
            # Get placeholder color based on theme - darker in dark mode, brighter in light mode
            is_dark = is_dark_mode()
            placeholder_color = QColor("#dddddd" if is_dark else "#444444")
            
            # Set font and color
            painter.setPen(placeholder_color)
            painter.setFont(self.font())
            
            # Draw centered placeholder text
            rect = self.rect()
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.placeholderText())
            
            painter.end()
    
    def keyPressEvent(self, event):
        """Override to handle Enter key with validation"""
        print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Key pressed: {event.key()}")
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            email = self.text().strip()
            print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Enter pressed with email='{email}'")
            print(f"🔵 DEBUG [EmailInput.keyPressEvent]: bypass_validation_for list: {self.bypass_validation_for}")
            
            # Check if empty - DON'T call handler, just show error
            if not email:
                print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Empty field, calling show_error('{self.empty_error_message}')")
                self.show_error(self.empty_error_message)
                print(f"🔵 DEBUG [EmailInput.keyPressEvent]: show_error() returned, accepting event")
                event.accept()  # Consume the event - don't propagate
                print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Event accepted, returning WITHOUT calling handler")
                return
            
            # Check if this value bypasses validation (dev mode test values)
            if email.lower() in self.bypass_validation_for:
                print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Value '{email}' bypasses validation (dev mode)")
                if self.validation_handler:
                    print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Calling validation_handler")
                    self.validation_handler()
                event.accept()
                return
            
            # Validate format before calling handler (only if validate_as_email is True)
            if self.validate_as_email:
                print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Calling validate_email() for '{email}'")
                is_valid = self.validate_email()
                print(f"🔵 DEBUG [EmailInput.keyPressEvent]: validate_email() returned: {is_valid}")
                
                if not is_valid:
                    print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Invalid format, calling show_error('incorrect mail format')")
                    self.show_error("incorrect mail format")
                    print(f"🔵 DEBUG [EmailInput.keyPressEvent]: show_error() returned, accepting event")
                    event.accept()  # Consume the event
                    print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Event accepted, returning")
                    return
            
            # Value is valid - call handler
            if self.validation_handler:
                print(f"🔵 DEBUG [EmailInput.keyPressEvent]: Value valid, calling validation_handler")
                self.validation_handler()
                event.accept()  # Always consume the event - handler will decide what to do
                return
        
        # For other keys, use default behavior
        super().keyPressEvent(event)
    
    def validate_email(self):
        """
        Validate email format: {text}@{text}.{domain}
        Returns True if valid, False if invalid
        """
        email = self.text().strip()
        
        if not email:
            return False
        
        # Check basic structure: must have @ and .
        if '@' not in email:
            return False
        
        # Split by @
        parts = email.split('@')
        if len(parts) != 2:
            return False
        
        local_part, domain_part = parts
        
        # Local part must not be empty
        if not local_part:
            return False
        
        # Domain must have at least one dot
        if '.' not in domain_part:
            return False
        
        # Split domain by last dot to get domain name and TLD
        domain_parts = domain_part.rsplit('.', 1)
        if len(domain_parts) != 2:
            return False
        
        domain_name, tld = domain_parts
        
        # Domain name and TLD must not be empty
        if not domain_name or not tld:
            return False
        
        return True
    
    def show_error(self, message="incorrect mail format"):
        """Show error state with red border and error message as placeholder"""
        print(f"🔴 DEBUG [EmailInput.show_error]: CALLED with message='{message}'")
        print(f"🔴 DEBUG [EmailInput.show_error]: Has focus: {self.hasFocus()}")
        
        # Clear focus first so placeholder will be visible
        if self.hasFocus():
            print(f"🔴 DEBUG [EmailInput.show_error]: Clearing focus to show placeholder")
            self.clearFocus()
        
        # Clear text
        self.setText("")
        print(f"🔴 DEBUG [EmailInput.show_error]: Text cleared")
        
        # Set error styling with visible placeholder
        is_dark = is_dark_mode()
        self.setStyleSheet(
            f"QLineEdit {{"
            f"  border: 2px solid #ff0000;"
            f"  border-radius: 8px;"
            f"  padding: 10px;"
            f"  background-color: {'#2b2b2b' if is_dark else '#e8e8e8'};"
            f"  color: {'white' if is_dark else 'black'};"
            f"}}"
            f"QLineEdit::placeholder {{"
            f"  color: {'#ff8888' if is_dark else '#ff4444'};"
            f"}}"
        )
        print(f"🔴 DEBUG [EmailInput.show_error]: Red border applied")
        
        self.setPlaceholderText(message)
        print(f"🔴 DEBUG [EmailInput.show_error]: Placeholder set to: '{message}'")
        
        self.setReadOnly(True)  # Disable input
        print(f"🔴 DEBUG [EmailInput.show_error]: ReadOnly set to True")
        
        # Process events to ensure UI updates
        QApplication.processEvents()
        print(f"🔴 DEBUG [EmailInput.show_error]: UI processed")
        
        self.error_timer.start(2000)  # Reset after 2 seconds
        print(f"🔴 DEBUG [EmailInput.show_error]: Timer started, COMPLETED")
    
    def _reset_error_state(self):
        """Reset to normal state after error display"""
        print(f"🟢 DEBUG [EmailInput._reset_error_state]: CALLED - resetting after error")
        
        # Re-enable input
        self.setReadOnly(False)
        print(f"🟢 DEBUG [EmailInput._reset_error_state]: ReadOnly set to False")
        
        # Restore normal styling
        self.apply_theme_style(is_dark_mode())
        print(f"🟢 DEBUG [EmailInput._reset_error_state]: Theme style applied")
        
        # Restore original placeholder
        self.setPlaceholderText(self.original_placeholder)
        print(f"🟢 DEBUG [EmailInput._reset_error_state]: Placeholder reset to: '{self.original_placeholder}'")
        
        # Return focus to input so user can type again
        self.setFocus()
        print(f"🟢 DEBUG [EmailInput._reset_error_state]: Focus restored, COMPLETED")
    
    def apply_theme_style(self, is_dark):
        """Apply theme-aware styling - placeholder stays visible until typing"""
        
        if is_dark:
            bg_color = "#2b2b2b"
            text_color = "white"
            border_color = "#555555"
            placeholder_color = "#dddddd"  # Darker/brighter in dark mode (more visible)
        else:
            bg_color = "#e8e8e8"
            text_color = "black"
            border_color = "#cccccc"
            placeholder_color = "#444444"  # Brighter/darker in light mode (more visible)
        
        # Use stylesheet with explicit placeholder styling
        self.setStyleSheet(
            f"QLineEdit {{"
            f"  border: 2px solid {border_color};"
            f"  border-radius: 8px;"
            f"  padding: 10px;"
            f"  background-color: {bg_color};"
            f"  color: {text_color};"
            f"  selection-background-color: transparent;"
            f"  selection-color: {text_color};"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border: 2px solid #2196f3;"
            f"}}"
            f"QLineEdit[text=\"\"]::placeholder {{"
            f"  color: {placeholder_color};"
            f"  opacity: 1;"
            f"}}"
        )


class LoginLineEdit(QLineEdit):
    """Unified line edit for login window inputs"""
    def __init__(self, placeholder_text="", is_password=False, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder_text)
        self.setFixedSize(350, 50)
        self.setFont(QFont(FONT_FAMILY, 14))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if is_password:
            self.setEchoMode(QLineEdit.Password)
        
        # Apply styling
        self.apply_theme_style(is_dark_mode())
    
    def apply_theme_style(self, is_dark):
        """Apply theme-aware styling"""
        if is_dark:
            bg_color = "#2b2b2b"
            text_color = "white"
            border_color = "#555555"
        else:
            bg_color = "#ffffff"
            text_color = "black"
            border_color = "#cccccc"
        
        style = f"""
            QLineEdit {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 10px;
            }}
            QLineEdit::placeholder {{
                color: #999;
            }}
        """
        self.setStyleSheet(style)


class StoreButton(QPushButton):
    """Reusable store button component with SVG icon"""
    def __init__(self, svg_filename, store_url, parent=None):
        super().__init__(parent)
        self.svg_filename = svg_filename
        self.store_url = store_url
        self.setFixedSize(350, 65)
        self.setFlat(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton { "
            "border: 2px solid #ccc; "
            "border-radius: 8px; "
            "background-color: transparent; "
            "} "
            "QPushButton:hover { border: 2px solid #999; background-color: rgba(0, 0, 0, 0.05); }"
        )
        self.clicked.connect(self.open_store)
        
        # Load SVG icon
        self.reload_icon()
    
    def reload_icon(self):
        """Reload SVG icon with current theme colors"""
        icon_path = get_resource_path(f"client/assets/icons/{self.svg_filename}")
        if os.path.exists(icon_path):
            # Determine fill color based on dark mode
            dark_mode = is_dark_mode()
            fill_color = "white" if dark_mode else "black"
            
            # Read SVG and inject fill color
            with open(icon_path, 'r') as f:
                svg_content = f.read()
            
            # Replace all fill="..." with the desired color using regex
            import re
            import tempfile
            # Replace both double and single quoted fill attributes
            svg_content = re.sub(r'fill="[^"]*"', f'fill="{fill_color}"', svg_content)
            svg_content = re.sub(r"fill='[^']*'", f"fill='{fill_color}'", svg_content)
            
            # Also check for any path/other elements without explicit fill and add it
            # This ensures all elements get the right color even if they don't have fill attribute
            svg_content = re.sub(r'<path([^>]*?)>', lambda m: f'<path{m.group(1)} fill="{fill_color}">' if 'fill=' not in m.group(1) else f'<path{m.group(1)}>', svg_content)
            
            # Write modified SVG to temporary file (QSvgRenderer works better with files)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as tmp:
                tmp.write(svg_content)
                tmp_path = tmp.name
            
            try:
                # Create renderer from temporary file
                renderer = QSvgRenderer(tmp_path)
                svg_size = renderer.defaultSize()
                aspect = svg_size.width() / svg_size.height()
                
                # Calculate size maintaining aspect ratio (max width 225px, max height 38px = 75% of original)
                if aspect > 6:  # Wide logo
                    pixmap = QPixmap(225, int(225 / aspect))
                else:
                    pixmap = QPixmap(int(38 * aspect), 38)
                
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                
                self.setIcon(QIcon(pixmap))
                self.setIconSize(pixmap.size())
            finally:
                # Clean up temporary file
                import os as os_module
                try:
                    os_module.unlink(tmp_path)
                except:
                    pass
    
    def open_store(self):
        """Open store URL in browser"""
        import webbrowser
        webbrowser.open(self.store_url)


class LoginMessage(QWidget):
    """Reusable message display widget that clears section and shows message"""
    def __init__(self, title, subtitle="", is_dark=True, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self.setFixedWidth(350)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))  # Unified size with subtitle
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setFixedWidth(350)
        title_color = "white" if is_dark else "#333333"
        title_label.setStyleSheet(f"color: {title_color}; line-height: 1.4;")
        layout.addWidget(title_label)
        
        # Subtitle (if provided)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setFont(QFont(FONT_FAMILY, 14))  # Same size as title for consistency
            subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtitle_label.setWordWrap(True)
            subtitle_label.setFixedWidth(350)
            subtitle_color = "#bbbbbb" if is_dark else "#777777"
            subtitle_label.setStyleSheet(f"color: {subtitle_color}; line-height: 1.4;")
            layout.addWidget(subtitle_label)
        
        self.setLayout(layout)
    
    def add_content(self, widget):
        """Add custom content widget to the message"""
        self.layout().addWidget(widget)


class VideoPlaybackThread(QThread):
    """Thread for playing video frames using OpenCV"""
    finished = pyqtSignal()
    frame_ready = pyqtSignal(object)  # Emit QPixmap for thread-safe display
    last_frame_captured = pyqtSignal(object)  # Emit last frame when video ends
    
    def __init__(self, video_path, video_widget, duration_ms=None, frame_size=(422, 750)):
        super().__init__()
        self.video_path = video_path
        self.video_widget = video_widget
        self.duration_ms = duration_ms  # None means loop forever
        self.frame_size = frame_size  # (width, height) for frame resizing
        self.is_running = True
        self.last_frame = None  # Store the last frame to emit when video ends
        # Note: Signal connection should be done externally by the parent widget
        # to avoid multiple connections. Internal connection removed.
    
    def run(self):
        """Play video for specified duration or loop indefinitely"""
        try:
            import cv2
            import time
            
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                print(f"[X] Failed to open video: {self.video_path}")
                self.finished.emit()
                return
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_delay = 1000 / fps if fps > 0 else 33  # milliseconds
            start_time = time.time() * 1000  # current time in ms
            
            if self.duration_ms:
                print(f"▶️  Video playback started - FPS: {fps}, Frame delay: {frame_delay}ms, Duration: {self.duration_ms}ms")
            else:
                print(f"▶️  Video playback started (looping) - FPS: {fps}, Frame delay: {frame_delay}ms")
            
            while self.is_running:
                elapsed_ms = (time.time() * 1000) - start_time if self.duration_ms else 0
                
                # Stop if we've exceeded the duration (if duration is specified)
                if self.duration_ms and elapsed_ms > self.duration_ms:
                    print(f"⏹️  Video playback duration complete ({self.duration_ms}ms)")
                    break
                
                ret, frame = cap.read()
                if not ret:
                    # Loop video if it ends
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        break
                
                # Resize frame to fit the video widget
                frame = cv2.resize(frame, self.frame_size)
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Convert to QPixmap
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                q_frame = QPixmap.fromImage(
                    QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                )
                
                # Store as last frame (will emit when video ends)
                self.last_frame = q_frame
                
                # Emit signal to update frame safely in GUI thread
                self.frame_ready.emit(q_frame)
                
                # Small delay to maintain FPS
                time.sleep(frame_delay / 1000)
            
            # Emit the last frame so it stays displayed after video ends
            if self.last_frame:
                print(f"📸 Holding last video frame")
                self.last_frame_captured.emit(self.last_frame)
            
            cap.release()
            print(f"[OK] Video playback thread completed")
        except ImportError:
            print(f"[X] OpenCV (cv2) not installed. Install with: pip install opencv-python")
        except Exception as e:
            print(f"[X] Error in video playback: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.finished.emit()
    
    def stop(self):
        """Stop video playback"""
        self.is_running = False


class ModernLoginWindow(QDialog):
    """Modern login window with split layout"""
    login_requested = pyqtSignal(str, str)  # email, license_key
    trial_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.authenticated = False
        self.is_trial = False
        self.show_forgot_mode = False
        self.drag_position = None
        self.waiting_for_response = False
        self.message_stable = True  # Flag to prevent premature Enter resets
        self.server_health_checker = ServerHealthChecker()
        self.media_player = None  # Video player reference
        self.video_widget = None  # Video display widget
        self.final_image_pixmap = None  # Store final image after video
        self._elements_hidden = False  # Track if login elements are hidden
        
        self.setWindowTitle("ImgApp - Login")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setGeometry(100, 100, 872, 750)
        self.setMinimumSize(872, 750)
        self.setMaximumSize(872, 750)
        
        # Center window on screen
        self.center_on_screen()
        
        self.setup_ui()
        self.apply_theme()
        self.load_saved_credentials()
        
        # Connect Esc key
        self.esc_timer = QTimer()

        # Install global event filter to intercept Enter when messages are shown
        self._global_filter_installed = False
        try:
            QApplication.instance().installEventFilter(self)
            self._global_filter_installed = True
        except:
            pass

        self.overlay_widget = None

    def _remove_message_overlay(self):
        try:
            if hasattr(self, 'overlay_widget') and self.overlay_widget:
                self.overlay_widget.setParent(None)
                self.overlay_widget.deleteLater()
                self.overlay_widget = None
            # DON'T reset message_stable here - let the new message control it
        except:
            self.overlay_widget = None

    def _hide_login_elements(self):
        """Hide all login elements except logo and store buttons"""
        # Hide email, license key inputs
        self.email_input.setVisible(False)
        self.license_input.setVisible(False)
        
        # Hide checkbox, forgot button, login button, trial button
        self.auto_login_cb.setVisible(False)
        self.forgot_btn.setVisible(False)
        self.login_btn.setVisible(False)
        self.trial_btn.setVisible(False)
        
        # Keep app name label visible (don't hide it)
        # self.app_name_label.setVisible(False)
        
        # Store visibility state for restoration
        self._elements_hidden = True
    
    def _show_login_elements(self):
        """Show all hidden login elements"""
        # Show email, license key inputs
        self.email_input.setVisible(True)
        self.license_input.setVisible(True)
        
        # Show checkbox, forgot button, login button, trial button
        self.auto_login_cb.setVisible(True)
        self.forgot_btn.setVisible(True)
        self.login_btn.setVisible(True)
        self.trial_btn.setVisible(True)
        
        # App name label stays visible (never was hidden)
        # self.app_name_label.setVisible(True)
        
        # Update visibility state
        self._elements_hidden = False

    def _show_centered_message(self, message_widget):
        """Show a message centered within the login section using an overlay.
        Hides all login elements except logo and store buttons."""
        self._remove_message_overlay()
        
        # Hide login form elements
        self._hide_login_elements()
        
        overlay = QWidget(self.login_section)
        overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        overlay.setStyleSheet("background: transparent;")
        overlay.setGeometry(self.login_section.rect())
        
        # Make overlay clickable to dismiss
        overlay.mousePressEvent = lambda event: self.reset_trial_to_login_mode()
        
        v = QVBoxLayout(overlay)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(message_widget, 0, Qt.AlignmentFlag.AlignCenter)
        overlay.show()
        self.overlay_widget = overlay
    
    def center_on_screen(self):
        """Center the window on the screen, shifted to the right"""
        geometry = self.frameGeometry()
        screen = QApplication.primaryScreen().availableGeometry()
        center_point = screen.center()
        geometry.moveCenter(center_point)
        # Shift 150px to the right
        self.move(geometry.topLeft().x() + 150, geometry.topLeft().y())
        
    def setup_ui(self):
        """Setup the main UI layout"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # LEFT SECTION - Media Display with Video Player (422x750)
        self.media_section = QFrame()
        self.media_section.setFixedSize(422, 750)
        self.media_section.setStyleSheet("background-color: #000000;")
        media_layout = QVBoxLayout(self.media_section)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.setSpacing(0)
        
        # Create video widget for displaying MP4 animation using QLabel
        self.video_widget = QLabel()
        self.video_widget.setStyleSheet("background-color: #000000;")
        self.video_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        media_layout.addWidget(self.video_widget)
        
        # Load and play the animation video
        self.load_media_animation()
        
        main_layout.addWidget(self.media_section)
        
        # RIGHT SECTION - Login (450x750)
        self.login_section = QFrame()
        self.login_section.setFixedSize(450, 750)
        login_layout = QVBoxLayout(self.login_section)
        login_layout.setContentsMargins(30, 25, 30, 30)  # Increased top margin from 5 to 25 (20px padding)
        login_layout.setSpacing(0)
        
        # Top bar with theme toggle (left) and close button (right)
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, -40, 0)  # Right margin to move close button to corner
        
        # Dark mode toggle button - will be positioned at main window level
        
        # Stretch in middle
        top_bar_layout.addStretch()
        
        login_layout.addLayout(top_bar_layout)
        # login_layout.addSpacing()
        
        # App icon and name - fixed at top
        app_header_layout = QHBoxLayout()
        app_header_layout.setContentsMargins(0, 10, 0, 20)
        app_header_layout.addStretch()
        
        try:
            from client.utils.resource_path import get_app_icon_path
            icon_path = get_app_icon_path()
            if os.path.exists(icon_path):
                app_icon_label = QLabel()
                icon = QIcon(icon_path)
                app_icon_label.setPixmap(icon.pixmap(64, 64))
                app_header_layout.addWidget(app_icon_label)
                app_header_layout.addSpacing(15)
        except:
            pass
        
        self.app_name_label = QLabel(APP_NAME)
        self.app_name_label.setFont(AppFonts.get_app_name_font(96))
        app_header_layout.addWidget(self.app_name_label)
        app_header_layout.addStretch()
        
        login_layout.addLayout(app_header_layout)
        login_layout.addSpacing(20)
        
        # Email input using unified EmailInput class
        self.email_input = EmailInput("e-mail", validate_as_email=True, error_message="email required")
        self.email_input.validation_handler = self.handle_login
        self.email_input.bypass_validation_for = ['dev']  # Dev mode bypass
        self.email_input.focusInEvent = lambda event: self.clear_message_display() or EmailInput.focusInEvent(self.email_input, event)
        email_container = QHBoxLayout()
        email_container.addStretch()
        email_container.addWidget(self.email_input)
        email_container.addStretch()
        login_layout.addLayout(email_container)
        
        # Spacing between input fields
        login_layout.addSpacing(20)
        
        # License key input using same EmailInput class but without email validation
        self.license_input = EmailInput("license key", validate_as_email=False, error_message="license key required")
        self.license_input.validation_handler = self.handle_login
        self.license_input.focusInEvent = lambda event: self.clear_message_display() or EmailInput.focusInEvent(self.license_input, event)
        license_container = QHBoxLayout()
        license_container.addStretch()
        license_container.addWidget(self.license_input)
        license_container.addStretch()
        login_layout.addLayout(license_container)
        
        # Spacing before checkbox and forgot button
        login_layout.addSpacing(20)
        
        # Checkbox and Forgot button on same line - aligned with input field width (350px)
        controls_container = QHBoxLayout()
        controls_container.addStretch()
        
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)
        
        # Auto-login checkbox on left
        self.auto_login_cb = QCheckBox("Auto-login")
        self.auto_login_cb.setChecked(True)
        self.auto_login_cb.setFont(QFont(FONT_FAMILY, 11))
        # Custom toggle style with grey text
        is_dark = self.is_dark_mode()
        bg_color = "#2b2b2b" if is_dark else "#e8e8e8"
        auto_login_style = (
            f"QCheckBox {{ color: {'#cccccc' if is_dark else '#333333'}; }} "
            f"QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 8px;"
            f" border: 2px solid #43a047; background: {bg_color}; }}"
            "QCheckBox::indicator:checked { background: #43a047; border: 2px solid #2e7d32; }"
            "QCheckBox::indicator:unchecked:hover { border: 2px solid #2e7d32; }"
        )
        self.auto_login_cb.setStyleSheet(auto_login_style)
        # Connect toggle to fill saved credentials
        self.auto_login_cb.stateChanged.connect(self.on_auto_login_toggled)
        controls_layout.addWidget(self.auto_login_cb)
        
        # Stretch between checkbox and forgot button
        controls_layout.addStretch()
        
        # Forgot button on right
        self.forgot_btn = QPushButton("Forgot license key?")
        self.forgot_btn.setFlat(True)
        self.forgot_btn.setFont(QFont(FONT_FAMILY, 11))
        self.forgot_btn.setStyleSheet(
            "QPushButton { color: #999999; text-decoration: underline; border: none; } "
            "QPushButton:hover { color: #2196f3; text-decoration: underline; }"
        )
        self.forgot_btn.clicked.connect(self.show_forgot_mode_ui)
        controls_layout.addWidget(self.forgot_btn)
        
        # Create fixed-width widget to match input field width (350px)
        controls_widget = QWidget()
        controls_widget.setFixedWidth(350)
        controls_widget.setLayout(controls_layout)
        controls_container.addWidget(controls_widget)
        controls_container.addStretch()
        
        login_layout.addLayout(controls_container)
        
        # Spacing before login button
        login_layout.addSpacing(20)
        
        # Login button
        login_btn_layout = QHBoxLayout()
        login_btn_layout.addStretch()
        self.login_btn = QPushButton("Login")
        self.login_btn.setFixedSize(350, 65)
        self.login_btn.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        self.login_btn.setAutoDefault(False)  # Prevent Enter from triggering this button
        self.login_btn.setDefault(False)  # Explicitly set not default
        self.login_btn.setStyleSheet(
            "QPushButton { "
            "background-color: transparent; "
            "color: white; "
            "border: 2px solid #43a047; "
            "border-radius: 8px; "
            "} "
            "QPushButton:hover { background-color: #43a047; }"
        )
        self.login_btn.clicked.connect(self.handle_login)
        login_btn_layout.addWidget(self.login_btn)
        login_btn_layout.addStretch()
        login_layout.addLayout(login_btn_layout)
        
        # Spacing between buttons
        login_layout.addSpacing(20)
        
        # Trial button
        trial_btn_layout = QHBoxLayout()
        trial_btn_layout.addStretch()
        self.trial_btn = QPushButton("Try Free Trial")
        self.trial_btn.setFixedSize(350, 65)
        self.trial_btn.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        self.trial_btn.setStyleSheet(
            "QPushButton { "
            "background-color: transparent; "
            "color: white; "
            "border: 2px solid #2196f3; "
            "border-radius: 8px; "
            "} "
            "QPushButton:hover { background-color: rgba(33, 150, 243, 0.2); }"
        )
        self.trial_btn.clicked.connect(self.handle_trial)
        trial_btn_layout.addWidget(self.trial_btn)
        trial_btn_layout.addStretch()
        login_layout.addLayout(trial_btn_layout)
        
        # Space to bottom
        login_layout.addStretch()
        
        # Buy license section
        self.buy_layout = QVBoxLayout()
        # Replace label with a delicate grey divider bar, centered with even side margins
        self.buy_label = QFrame()
        self.buy_label.setFrameShape(QFrame.Shape.HLine)
        self.buy_label.setFrameShadow(QFrame.Shadow.Plain)
        self.buy_label.setFixedHeight(2)
        # Theme-aware subtle color
        _is_dark = self.is_dark_mode()
        divider_color = "#555555" if _is_dark else "#DDDDDD"
        self.buy_label.setStyleSheet(f"QFrame {{ background-color: {divider_color}; border: none; }}")
        # Container to apply compensating right margin so left/right appear equal
        divider_container = QWidget()
        divider_h = QHBoxLayout(divider_container)
        divider_h.setContentsMargins(0, 0, 0, 0)
        # Compute additional right padding to match left margin of the section
        try:
            m = login_layout.contentsMargins()
            add_right = max(0, m.left() - m.right())
        except:
            add_right = 0
        # Apply padding with stretches and a spacer on the right if needed
        padded_h = QHBoxLayout()
        padded_h.setContentsMargins(0, 0, add_right, 0)
        padded_h.addWidget(self.buy_label)
        divider_h.addLayout(padded_h)
        # Add some vertical spacing around the divider and the container
        self.buy_layout.addSpacing(10)
        self.buy_layout.addWidget(divider_container)
        self.buy_layout.addSpacing(10)
        self.buy_layout.addSpacing(10)
        
        # Store buttons - using StoreButton component
        store_buttons_layout = QVBoxLayout()
        
        # Microsoft Store button
        self.msstore_btn = StoreButton("msstore.svg", "https://apps.microsoft.com/")
        
        # Store buttons container - CENTER BUTTONS PROPERLY
        # Microsoft Store button - horizontally centered
        msstore_h_layout = QHBoxLayout()
        msstore_h_layout.addStretch()
        msstore_h_layout.addWidget(self.msstore_btn)
        msstore_h_layout.addStretch()
        store_buttons_layout.addLayout(msstore_h_layout)
        
        # Spacing between store buttons
        store_buttons_layout.addSpacing(20)
        
        # Gumroad button
        self.gumroad_btn = StoreButton("gumroad.svg", "https://gumroad.com/")
        
        # Gumroad button - horizontally centered
        gumroad_h_layout = QHBoxLayout()
        gumroad_h_layout.addStretch()
        gumroad_h_layout.addWidget(self.gumroad_btn)
        gumroad_h_layout.addStretch()
        store_buttons_layout.addLayout(gumroad_h_layout)
        
        self.buy_layout.addLayout(store_buttons_layout)
        
        login_layout.addLayout(self.buy_layout)
        
        main_layout.addWidget(self.login_section)
        self.setLayout(main_layout)
        
        # Create dark mode toggle button at main window level (COMMENTED OUT)
        # self.theme_toggle_btn = QPushButton(self)
        # self.theme_toggle_btn.setFixedSize(30, 30)
        # self.theme_toggle_btn.setFlat(True)
        # self.theme_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # self.theme_toggle_btn.setStyleSheet(
        #     "QPushButton { background: transparent; border: none; }"
        #     "QPushButton:hover { background: rgba(0, 0, 0, 0.1); border-radius: 4px; }"
        # )
        
        # Create close button at main window level (outside login_section)
        # This allows it to be positioned in the top-right corner of the entire window
        close_btn = QPushButton("×", self)
        close_btn.setFixedSize(30, 30)
        close_btn.setFont(QFont(FONT_FAMILY, 18, QFont.Weight.Bold))
        close_btn.setFlat(True)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { color: #999; background: transparent; border: none; }"
            "QPushButton:hover { color: #ccc; }"
        )
        close_btn.clicked.connect(self.reject)
        # Position at top-right corner of main window (10px from edges)
        self.close_btn = close_btn  # Store reference for dynamic repositioning
        self._update_close_button_position()
        
        # Set focus to email input by default so Enter always has a target
        QTimer.singleShot(0, lambda: self.email_input.setFocus())
        
        # Set focus to email input by default so Enter has a target
        QTimer.singleShot(0, lambda: self.email_input.setFocus())
    
    def apply_theme(self):
        """Apply theme based on system dark mode"""
        is_dark = self.is_dark_mode()
        
        if is_dark:
            login_bg = "#2b2b2b"
            text_color = "white"
        else:
            login_bg = "#e8e8e8"
            text_color = "black"
        
        self.login_section.setStyleSheet(f"background-color: {login_bg};")
        
        # Update app name to white in dark mode
        if hasattr(self, 'app_name_label'):
            self.app_name_label.setStyleSheet(f"color: {text_color}; font-weight: bold; font-size: 18pt;")
        
        # Update input fields
        input_style = f"""
            QLineEdit {{
                background-color: {login_bg};
                color: {text_color};
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 10px;
            }}
            QLineEdit::placeholder {{
                color: #999;
            }}
        """
        self.email_input.setStyleSheet(input_style)
        self.license_input.setStyleSheet(input_style)
        
        # Update buttons
        if hasattr(self, 'remember_cb'):
            self.remember_cb.setStyleSheet(f"color: {text_color};")
        if hasattr(self, 'auto_login_cb'):
            # Update auto-login checkbox background and text color
            bg_color = "#2b2b2b" if is_dark else "#e8e8e8"
            auto_login_style = (
                f"QCheckBox {{ color: {text_color}; }} "
                f"QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 8px;"
                f" border: 2px solid #43a047; background: {bg_color}; }}"
                "QCheckBox::indicator:checked { background: #43a047; border: 2px solid #2e7d32; }"
                "QCheckBox::indicator:unchecked:hover { border: 2px solid #2e7d32; }"
            )
            self.auto_login_cb.setStyleSheet(auto_login_style)
        if hasattr(self, 'close_btn'):
            self.close_btn.setStyleSheet(f"color: {text_color}; background-color: transparent; border: none;")
        
        login_btn_style = (
            f"QPushButton {{ "
            f"background-color: transparent; "
            f"color: {text_color}; "
            f"border: 2px solid #43a047; "
            f"border-radius: 8px; "
            f"}} "
            f"QPushButton:hover {{ background-color: #43a047; color: white; }}"
        )
        if hasattr(self, 'login_btn'):
            self.login_btn.setStyleSheet(login_btn_style)
        
        trial_btn_style = (
            f"QPushButton {{ "
            f"background-color: transparent; "
            f"color: {text_color}; "
            f"border: 2px solid #2196f3; "
            f"border-radius: 8px; "
            f"}} "
            f"QPushButton:hover {{ background-color: rgba(33, 150, 243, 0.2); }}"
        )
        if hasattr(self, 'trial_btn'):
            self.trial_btn.setStyleSheet(trial_btn_style)
        
        # Update send button styling (forgot password flow)
        send_btn_style = (
            f"QPushButton {{ "
            f"background-color: transparent; "
            f"color: {text_color}; "
            f"border: 2px solid #2196f3; "
            f"border-radius: 8px; "
            f"}} "
            f"QPushButton:hover {{ background-color: #2196f3; color: white; }}"
        )
        if hasattr(self, 'send_btn'):
            self.send_btn.setStyleSheet(send_btn_style)
        
        # Update trial send button styling (trial flow)
        if hasattr(self, 'trial_send_btn'):
            self.trial_send_btn.setStyleSheet(send_btn_style)
        
        # Update store button icons for both light and dark modes
        if hasattr(self, 'msstore_btn'):
            self.msstore_btn.reload_icon()
        if hasattr(self, 'gumroad_btn'):
            self.gumroad_btn.reload_icon()
        
        # Update store buttons styling
        if hasattr(self, 'msstore_btn'):
            hover_bg = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(0, 0, 0, 0.05)"
            self.msstore_btn.setStyleSheet(
                f"QPushButton {{ "
                f"border: 2px solid {'#555' if is_dark else '#ccc'}; "
                f"border-radius: 8px; "
                f"background-color: transparent; "
                f"}} "
                f"QPushButton:hover {{ border: 2px solid {'#777' if is_dark else '#999'}; background-color: {hover_bg}; }}"
            )
        if hasattr(self, 'gumroad_btn'):
            hover_bg = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(0, 0, 0, 0.05)"
            self.gumroad_btn.setStyleSheet(
                f"QPushButton {{ "
                f"border: 2px solid {'#555' if is_dark else '#ccc'}; "
                f"border-radius: 8px; "
                f"background-color: transparent; "
                f"}} "
                f"QPushButton:hover {{ border: 2px solid {'#777' if is_dark else '#999'}; background-color: {hover_bg}; }}"
            )
    
    def _load_svg_with_color(self, svg_path, color, size):
        """Load SVG and replace fill color"""
        try:
            with open(svg_path, 'r') as f:
                svg_content = f.read()
            
            # Replace fill colors with the desired color
            hex_color = color.name()
            # Replace various fill patterns
            svg_content = svg_content.replace('fill="black"', f'fill="{hex_color}"')
            svg_content = svg_content.replace('fill="#000000"', f'fill="{hex_color}"')
            svg_content = svg_content.replace('fill="#000"', f'fill="{hex_color}"')
            # If no fill found, add fill to path elements
            if 'fill=' not in svg_content:
                svg_content = svg_content.replace('<path', f'<path fill="{hex_color}"')
            
            # Create pixmap from modified SVG
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            # Use QSvgWidget to render (alternative: use QPainter with QSvgRenderer)
            from PyQt6.QtSvg import QSvgRenderer
            renderer = QSvgRenderer()
            
            # Load from string
            from PyQt6.QtCore import QByteArray
            renderer.load(QByteArray(svg_content.encode('utf-8')))
            
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            return pixmap
        except:
            return None
    def is_dark_mode(self):
        """Check if Windows is in dark mode"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            apps_use_light_theme, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return apps_use_light_theme == 0
        except:
            return False
    
    # def toggle_dark_mode(self):
    #     """Toggle between light and dark mode (COMMENTED OUT)"""
    #     try:
    #         import winreg
    #         key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
    #                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
    #                            0, winreg.KEY_WRITE)
    #         current = self.is_dark_mode()
    #         # Set to opposite: if dark (True), set to light (1); if light (False), set to dark (0)
    #         new_value = 1 if current else 0
    #         winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new_value)
    #         winreg.CloseKey(key)
    #         
    #         # Update UI immediately
    #         self.apply_theme()
    #         
    #         # Update theme toggle button emoji
    #         self._update_theme_toggle_button()
    #         
    #         print(f"[OK] Theme toggled to {'dark' if self.is_dark_mode() else 'light'} mode")
    #     except Exception as e:
    #         print(f"[WARN]  Could not toggle dark mode: {e}")
    
    
    def get_config_path(self):
        """Get path for local user config"""
        try:
            if os.name == 'nt':
                app_data = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA')
            else:
                app_data = os.path.expanduser('~/.config')
            config_dir = os.path.join(app_data, 'ImageWave', 'config')
            os.makedirs(config_dir, exist_ok=True)
            return os.path.join(config_dir, 'user_session.json')
        except:
            return None
    
    def load_saved_credentials(self):
        """Pre-fill email and license key if saved"""
        try:
            path = self.get_config_path()
            if path and os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    if 'email' in data:
                        self.email_input.setText(data['email'])
                    if 'license_key' in data:
                        self.license_input.setText(data['license_key'])
                    if data.get('remember', False):
                        self.remember_cb.setChecked(True)
                    # Set auto-login checkbox based on saved state
                    if data.get('auto_login', True):
                        self.auto_login_cb.setChecked(True)
        except:
            pass
    
    def on_auto_login_toggled(self, state):
        """Handle auto-login checkbox toggle - fill with last successful login credentials"""
        if self.auto_login_cb.isChecked():
            # When toggled ON, fill in the last saved successful login credentials
            try:
                path = self.get_config_path()
                if path and os.path.exists(path):
                    with open(path, 'r') as f:
                        data = json.load(f)
                        email = data.get('email', '')
                        license_key = data.get('license_key', '')
                        if email:
                            self.email_input.setText(email)
                        if license_key:
                            self.license_input.setText(license_key)
            except:
                pass
        else:
            # When toggled OFF, clear the input fields
            self.email_input.clear()
            self.license_input.clear()
    

    def save_credentials(self, email, license_key):
        """Save credentials locally on every successful login (for auto-login feature)"""
        try:
            path = self.get_config_path()
            if not path:
                return
            data = {
                'email': email,
                'license_key': license_key,
                'auto_login': True,
                'remember': True,
                'last_login': datetime.now().isoformat()
            }
            with open(path, 'w') as f:
                json.dump(data, f)
        except:
            pass
    
    def handle_login(self):
        """Handle login with server validation"""
        # Suppress Enter-triggered login briefly after trial success transition
        try:
            if hasattr(self, 'enter_suppressed_until') and self.enter_suppressed_until:
                if datetime.now() < self.enter_suppressed_until:
                    return
        except:
            pass
        
        # EmailInput class now handles validation automatically
        # Only called if both fields are valid
        email = self.email_input.text().strip()
        license_key = self.license_input.text().strip()
        
        # Development bypass
        if DEVELOPMENT_MODE and email == "dev":
            self.authenticated = True
            self.is_trial = False
            self.save_credentials(email, license_key)
            self.accept()
            return
        
        # Check server health BEFORE attempting login
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Checking server...")
        QApplication.processEvents()
        
        try:
            from client.config.config import API_BASE_URL
            status, details = self.server_health_checker.check_server_health(API_BASE_URL, timeout=5)
            
            if status != 'online':
                # Server is not available
                message_info = self.server_health_checker.get_user_message(status, details)
                
                self._show_server_error_message(
                    title=message_info['title'],
                    message=message_info['message'],
                    action=message_info['action']
                )
                
                # Re-enable button
                self.login_btn.setEnabled(True)
                self.login_btn.setText("Login")
                return
            
            # Server is online - show slow connection warning if needed
            if status == 'slow':
                self.login_btn.setText("Login (slow connection...)")
            else:
                self.login_btn.setText("Logging in...")
            
            QApplication.processEvents()
            
        except Exception as e:
            # If health check fails, continue anyway (don't block login)
            print(f"Health check error (continuing): {e}")
        
        # Validate with server
        self.validate_login_with_server(email, license_key)
    
    def validate_login_with_server(self, email, license_key):
        """Validate login credentials with the server"""
        try:
            from client.config.config import VALIDATE_URL
            
            # Get hardware ID for validation
            hardware_id = self.get_hardware_id()
            device_name = f"{platform.system()}-{socket.gethostname()}"
            
            # Show loading state
            self.login_btn.setEnabled(False)
            self.login_btn.setText("Validating...")
            QApplication.processEvents()
            
            # Send validation request to server
            response = requests.post(VALIDATE_URL, json={
                'email': email,
                'license_key': license_key,
                'hardware_id': hardware_id,
                'device_name': device_name
            }, timeout=10)
            
            result = response.json()
            
            if result.get('success'):
                # Login successful
                self.authenticated = True
                self.is_trial = result.get('is_trial', False)
                self.save_credentials(email, license_key)
                self.accept()
            else:
                # Login failed - show visual feedback only (no popup)
                error = result.get('error', 'Unknown error')
                
                # Determine placeholder text based on error
                placeholder_text = "Invalid login or password"
                if error == 'email_mismatch':
                    placeholder_text = "Email doesn't match license"
                elif error == 'license_expired':
                    placeholder_text = "License expired"
                elif error == 'license_deactivated':
                    placeholder_text = "License deactivated"
                elif error == 'bound_to_other_device':
                    placeholder_text = "Bound to another device"
                elif error == 'invalid_license':
                    placeholder_text = "Invalid license key"
                
                # Visual feedback: Red outline and placeholder text
                self._show_login_error_visual(placeholder_text)
                
                # Reset button
                self.login_btn.setEnabled(True)
                self.login_btn.setText("Login")
                
        except requests.exceptions.Timeout:
            # Visual feedback for timeout
            self._show_login_error_visual("Connection timeout")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Login")
        except requests.exceptions.ConnectionError:
            # Visual feedback for connection error
            self._show_login_error_visual("No internet connection")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Login")
        except Exception as e:
            self._show_inline_message("Login Error", f"An error occurred: {str(e)}", message_type="error")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Login")

    def accept(self):
        """Override dialog accept to avoid closing when a transient message is shown."""
        try:
            has_inline = (
                (hasattr(self, 'overlay_widget') and self.overlay_widget) or
                (hasattr(self, 'message_container') and self.message_container) or
                (hasattr(self, 'success_message_container') and self.success_message_container)
            )
            if has_inline:
                # Dismiss message and restore login instead of closing the dialog
                self.reset_trial_to_login_mode()
                return
        except:
            pass
        # Remove global event filter before closing
        self._remove_global_event_filter()
        super().accept()
    
    def reject(self):
        """Override dialog reject to remove event filter before closing."""
        self._remove_global_event_filter()
        super().reject()
    
    def closeEvent(self, event):
        """Remove global event filter when window is closed."""
        self._remove_global_event_filter()
        super().closeEvent(event)
    
    def _remove_global_event_filter(self):
        """Remove the global event filter from QApplication."""
        if getattr(self, '_global_filter_installed', False):
            try:
                QApplication.instance().removeEventFilter(self)
                self._global_filter_installed = False
            except:
                pass
    
    def handle_trial(self):
        """Show trial mode UI"""
        self.show_trial_mode_ui()
    
    def _show_login_error_visual(self, error_message="Invalid login or password"):
        """Show visual feedback for failed login - red outline and placeholder"""
        # Store original placeholders
        original_email_placeholder = self.email_input.placeholderText()
        original_license_placeholder = self.license_input.placeholderText()
        
        # Get current style to preserve dark/light mode colors
        is_dark = self.is_dark_mode()
        if is_dark:
            login_bg = "#2b2b2b"
            text_color = "white"
        else:
            login_bg = "#e8e8e8"
            text_color = "black"
        
        # Apply red border style
        error_style = f"""
            QLineEdit {{
                background-color: {login_bg};
                color: {text_color};
                border: 2px solid red;
                border-radius: 4px;
                padding: 10px;
            }}
            QLineEdit::placeholder {{
                color: #ff6b6b;
            }}
        """
        
        self.email_input.setStyleSheet(error_style)
        self.email_input.setPlaceholderText(error_message)
        
        self.license_input.setStyleSheet(error_style)
        self.license_input.setPlaceholderText(error_message)
        
        # Reset after 2 seconds
        def restore_original():
            self.reset_input_styles()
            self.email_input.setPlaceholderText(original_email_placeholder)
            self.license_input.setPlaceholderText(original_license_placeholder)
        
        QTimer.singleShot(2000, restore_original)
    
    def _show_server_error_message(self, title, message, action=None):
        """Show server error message with user-friendly styling"""
        # Create message widget
        is_dark = self.is_dark_mode()
        
        message_widget = LoginMessage(title, message, is_dark=is_dark)
        
        # Add action button if provided
        if action:
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            retry_button = QPushButton(action)
            retry_button.setFixedSize(150, 40)
            retry_button.clicked.connect(self._close_centered_message)
            
            button_layout.addWidget(retry_button)
            button_layout.addStretch()
            
            message_widget.layout().addSpacing(10)
            message_widget.layout().addLayout(button_layout)
        
        # Show centered overlay
        self._show_centered_message(message_widget)
        self.message_widget = message_widget
    
    def _close_centered_message(self):
        """Close the centered message overlay"""
        self._remove_message_overlay()
    
    def reset_input_styles(self):
        """Reset input field styles to normal"""
        is_dark = self.is_dark_mode()
        if is_dark:
            login_bg = "#2b2b2b"
            text_color = "white"
        else:
            login_bg = "#e8e8e8"
            text_color = "black"
        
        input_style = f"""
            QLineEdit {{
                background-color: {login_bg};
                color: {text_color};
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 10px;
            }}
            QLineEdit::placeholder {{
                color: #999;
            }}
        """
        self.email_input.setStyleSheet(input_style)
        self.license_input.setStyleSheet(input_style)
    
    def show_forgot_mode_ui(self):
        """Show forgot license key UI"""
        self.show_forgot_mode = True
        
        # Store references to track what we add
        self.forgot_inserted_indices = []
        
        # Hide original inputs and buttons
        try:
            self.email_input.hide()
        except:
            pass
        try:
            self.license_input.hide()
        except:
            pass
        try:
            self.auto_login_cb.hide()
        except:
            pass
        try:
            self.forgot_btn.hide()
        except:
            pass
        try:
            self.login_btn.hide()
        except:
            pass
        try:
            self.trial_btn.hide()
        except:
            pass
        if hasattr(self, 'msstore_btn'):
            try:
                self.msstore_btn.hide()
            except:
                pass
        if hasattr(self, 'gumroad_btn'):
            try:
                self.gumroad_btn.hide()
            except:
                pass
        if hasattr(self, 'buy_label'):
            try:
                self.buy_label.hide()
            except:
                pass
        
        # Get the login layout
        login_layout = self.login_section.layout()
        
        # Create resend input using EmailInput class for validation
        self.resend_input = EmailInput("send license key to the email", validate_as_email=True, error_message="email required")
        self.resend_input.validation_handler = self.handle_resend
        self.resend_input.bypass_validation_for = ['f@f.com', 'n@n.com', 'invalid']  # Dev mode test emails

        # Forgot block wrapper to keep spacing self-contained
        self.forgot_block_widget = QWidget()
        forgot_block_v = QVBoxLayout(self.forgot_block_widget)
        forgot_block_v.setContentsMargins(0, 0, 0, 0)
        
        # Set focus to input field after a short delay (with safety check)
        QTimer.singleShot(100, lambda: self.resend_input.setFocus() if hasattr(self, 'resend_input') else None)

        # Centered resend input
        self.resend_container = QHBoxLayout()
        self.resend_container.addStretch()
        self.resend_container.addWidget(self.resend_input)
        self.resend_container.addStretch()
        forgot_block_v.addLayout(self.resend_container)
        forgot_block_v.addSpacing(20)

        # Find the email input position and insert forgot block in the same place
        email_index = None
        for i in range(login_layout.count()):
            item = login_layout.itemAt(i)
            if item and item.widget() == self.email_input:
                email_index = i
                break
        
        if email_index is not None:
            # Track the starting position for cleanup
            self.forgot_start_index = email_index
            # Insert whole forgot block widget at same index as email input
            login_layout.insertWidget(email_index, self.forgot_block_widget)
        else:
            # Fallback: insert at position 4
            self.forgot_start_index = 4
            login_layout.insertWidget(4, self.forgot_block_widget)
        
        # Add send button
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedSize(350, 65)
        self.send_btn.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        is_dark = is_dark_mode()
        btn_text_color = "white" if is_dark else "black"
        self.send_btn.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: transparent; "
            f"color: {btn_text_color}; "
            f"border: 2px solid #2196f3; "
            f"border-radius: 8px; "
            f"}} "
            f"QPushButton:hover {{ background-color: #2196f3; color: white; }}"
        )
        self.send_btn.clicked.connect(self.handle_resend)
        
        self.send_btn_layout = QHBoxLayout()
        self.send_btn_layout.addStretch()
        self.send_btn_layout.addWidget(self.send_btn)
        self.send_btn_layout.addStretch()
        # Add into block
        forgot_block_v.addLayout(self.send_btn_layout)
        forgot_block_v.addSpacing(20)
        
        # Add back button as proper button class under send button
        self.back_btn = QPushButton("back")
        self.back_btn.setFixedSize(350, 50)
        self.back_btn.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        self.back_btn.setStyleSheet(
            "QPushButton { "
            "background-color: transparent; "
            "color: #999999; "
            "border: 2px solid #999999; "
            "border-radius: 8px; "
            "} "
            "QPushButton:hover { "
            "background-color: transparent; "
            "color: #2196f3; "
            "border: 2px solid #2196f3; "
            "}"
        )
        self.back_btn.clicked.connect(self.reset_to_login_mode)
        
        self.back_btn_layout = QHBoxLayout()
        self.back_btn_layout.addStretch()
        self.back_btn_layout.addWidget(self.back_btn)
        self.back_btn_layout.addStretch()
        # Add into block
        forgot_block_v.addLayout(self.back_btn_layout)
    
    def show_trial_mode_ui(self):
        """Show trial mode UI"""
        self.show_trial_mode = True
        
        # Get the login layout
        login_layout = self.login_section.layout()
        
        # Store original layout item count before we add trial items
        self.original_layout_count = login_layout.count()
        
        # Hide original inputs and buttons
        self.email_input.hide()
        self.license_input.hide()
        self.auto_login_cb.hide()
        self.forgot_btn.hide()
        self.login_btn.hide()
        self.trial_btn.hide()
        if hasattr(self, 'msstore_btn'):
            self.msstore_btn.hide()
        if hasattr(self, 'gumroad_btn'):
            self.gumroad_btn.hide()
        if hasattr(self, 'buy_label'):
            self.buy_label.hide()
        
        # Create trial email input using EmailInput class for validation
        self.trial_email_input = EmailInput("e-mail", validate_as_email=True, error_message="email required")
        self.trial_email_input.validation_handler = self.handle_trial_send
        self.trial_email_input.bypass_validation_for = ['a@a.com', 'b@b.com', 'off']  # Dev mode test emails
        
        # Set focus to input field after a short delay (with safety check)
        QTimer.singleShot(100, lambda: self.trial_email_input.setFocus() if hasattr(self, 'trial_email_input') else None)

        # Trial block wrapper to keep spacing self-contained
        self.trial_block_widget = QWidget()
        trial_block_v = QVBoxLayout(self.trial_block_widget)
        trial_block_v.setContentsMargins(0, 0, 0, 0)

        # Centered trial email input
        self.trial_email_container = QHBoxLayout()
        self.trial_email_container.addStretch()
        self.trial_email_container.addWidget(self.trial_email_input)
        self.trial_email_container.addStretch()
        trial_block_v.addLayout(self.trial_email_container)
        trial_block_v.addSpacing(20)
        
        # Find the email input position and insert trial block in the same place
        email_index = None
        for i in range(self.original_layout_count):
            item = login_layout.itemAt(i)
            if item and item.widget() == self.email_input:
                email_index = i
                break
        
        if email_index is not None:
            self.trial_start_index = email_index
            login_layout.insertWidget(email_index, self.trial_block_widget)
        else:
            self.trial_start_index = 4
            login_layout.insertWidget(4, self.trial_block_widget)
        
        # Add trial send button
        self.trial_send_btn = QPushButton("enter trial mode")
        self.trial_send_btn.setFixedSize(350, 65)
        self.trial_send_btn.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        is_dark = is_dark_mode()
        btn_text_color = "white" if is_dark else "black"
        self.trial_send_btn.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: transparent; "
            f"color: {btn_text_color}; "
            f"border: 2px solid #2196f3; "
            f"border-radius: 8px; "
            f"}} "
            f"QPushButton:hover {{ background-color: #2196f3; color: white; }}"
        )
        self.trial_send_btn.clicked.connect(self.handle_trial_send)
        
        self.trial_send_btn_layout = QHBoxLayout()
        self.trial_send_btn_layout.addStretch()
        self.trial_send_btn_layout.addWidget(self.trial_send_btn)
        self.trial_send_btn_layout.addStretch()
        trial_block_v.addLayout(self.trial_send_btn_layout)
        trial_block_v.addSpacing(20)
        
        # Add trial back button
        self.trial_back_btn = QPushButton("back")
        self.trial_back_btn.setFixedSize(350, 50)
        self.trial_back_btn.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        self.trial_back_btn.setStyleSheet(
            "QPushButton { "
            "background-color: transparent; "
            "color: #999999; "
            "border: 2px solid #999999; "
            "border-radius: 8px; "
            "} "
            "QPushButton:hover { "
            "background-color: transparent; "
            "color: #2196f3; "
            "border: 2px solid #2196f3; "
            "}"
        )
        self.trial_back_btn.clicked.connect(self.reset_to_login_mode)
        
        self.trial_back_btn_layout = QHBoxLayout()
        self.trial_back_btn_layout.addStretch()
        self.trial_back_btn_layout.addWidget(self.trial_back_btn)
        self.trial_back_btn_layout.addStretch()
        trial_block_v.addLayout(self.trial_back_btn_layout)
    
    def handle_trial_send(self):
        """Handle trial mode email submission"""
        try:
            email = self.trial_email_input.text().strip()
            
            if not email:
                self.trial_email_input.show_error("email required")
                return
            
            # Validate email format using EmailInput validation (except for dev mode test emails)
            if email not in ['a@a.com', 'b@b.com', 'off']:
                if not self.trial_email_input.validate_email():
                    print(f"[SEARCH] DEBUG [handle_trial_send]: Invalid email format, showing error")
                    self.trial_email_input.show_error("incorrect mail format")
                    return
        except Exception as e:
            print(f"[SEARCH] DEBUG [handle_trial_send]: Exception during validation: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Mark waiting state; disable button and show waiting style
        self.waiting_for_response = True
        self.trial_send_btn.setEnabled(False)
        self.trial_send_btn.setText("Processing...")
        self.trial_send_btn.setStyleSheet(
            "QPushButton { background-color: transparent; color: #bbbbbb; border: 2px solid #666666; border-radius: 8px; }"
        )
        QApplication.processEvents()
        
        try:
            # Dev mode simulation - ALWAYS short-circuit these test inputs, no server calls
            email_norm = (email or "").strip().lower()
            print(f"DEBUG: handle_trial_send called with email: {email_norm}")
            if email_norm in ['a@a.com', 'b@b.com', 'off']:
                print(f"[SEARCH] DEBUG [handle_trial_send]: Dev mode detected for '{email_norm}', simulating delay")
                if email_norm == 'off':
                    # Immediate offline message
                    print(f"[SEARCH] DEBUG [handle_trial_send]: Showing offline message immediately")
                    self.show_trial_warning_dialog(
                        "No Internet Connection",
                        "An internet connection is required to activate a trial.\n\nPlease check your connection and try again."
                    )
                    self.trial_send_btn.setEnabled(True)
                    self.trial_send_btn.setText("enter trial mode")
                    self.trial_send_btn.setStyleSheet(
                        "QPushButton { background-color: transparent; color: white; border: 2px solid #2196f3; border-radius: 8px; }"
                    )
                    print(f"[SEARCH] DEBUG [handle_trial_send]: Setting waiting_for_response=False (offline)")
                    self.waiting_for_response = False
                    return
                # Simulate 2s server wait before showing message
                print(f"[SEARCH] DEBUG [handle_trial_send]: Scheduling 2s delay for '{email_norm}'")
                def _finish_dev():
                    print(f"[SEARCH] DEBUG [_finish_dev]: Delay complete for '{email_norm}', showing dialog")
                    if email_norm == 'a@a.com':
                        self.show_trial_success_dialog(email_norm, 'x-x-x')
                    else:
                        self.show_trial_error_dialog(
                            "Server Trial Failure",
                            "The server reported a trial activation failure for this email/device."
                        )
                    # Re-enable button after message shown (reset happens in message cleanup)
                    print(f"[SEARCH] DEBUG [_finish_dev]: Re-enabling trial button")
                    self.trial_send_btn.setEnabled(True)
                    self.trial_send_btn.setText("enter trial mode")
                    self.trial_send_btn.setStyleSheet(
                        "QPushButton { background-color: transparent; color: white; border: 2px solid #2196f3; border-radius: 8px; }"
                    )
                    print(f"[SEARCH] DEBUG [_finish_dev]: Setting waiting_for_response=False")
                    self.waiting_for_response = False
                QTimer.singleShot(2000, _finish_dev)
                return
            
            # Get hardware ID
            hardware_id = self.get_hardware_id()
            
            # Check trial eligibility first
            # Wait for server response: do not show messages until after checks complete
            if not self.check_trial_eligibility(email, hardware_id):
                self.trial_send_btn.setEnabled(True)
                self.trial_send_btn.setText("enter trial mode")
                self.trial_send_btn.setStyleSheet(
                    "QPushButton { background-color: transparent; color: white; border: 2px solid #2196f3; border-radius: 8px; }"
                )
                self.waiting_for_response = False
                return
            
            # Create trial license
            trial_license = self.create_trial_license(email, hardware_id)
            
            if trial_license:
                self.show_trial_success_dialog(email, trial_license)
            else:
                self.trial_send_btn.setEnabled(True)
                self.trial_send_btn.setText("enter trial mode")
                self.trial_send_btn.setStyleSheet(
                    "QPushButton { background-color: transparent; color: white; border: 2px solid #2196f3; border-radius: 8px; }"
                )
                self.waiting_for_response = False
                
        except Exception as e:
            # Immediate offline or error: display message now and restore button state
            self.show_trial_error_dialog("Failed to activate trial", str(e))
            self.trial_send_btn.setEnabled(True)
            self.trial_send_btn.setText("enter trial mode")
            self.trial_send_btn.setStyleSheet(
                "QPushButton { background-color: transparent; color: white; border: 2px solid #2196f3; border-radius: 8px; }"
            )
            self.waiting_for_response = False
    
    def get_hardware_id(self):
        """Get hardware ID for trial tracking"""
        try:
            import hashlib
            machine_id = f"{socket.gethostname()}-{platform.platform()}"
            return hashlib.sha256(machine_id.encode()).hexdigest()[:16]
        except:
            return "unknown"
    
    def check_trial_eligibility(self, email, hardware_id):
        """Check if user is eligible for a trial"""
        try:
            from client.config.config import TRIAL_CHECK_ELIGIBILITY_URL
            
            response = requests.post(TRIAL_CHECK_ELIGIBILITY_URL, json={
                'email': email,
                'hardware_id': hardware_id
            }, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('eligible'):
                    return True
                else:
                    reason = result.get('reason', 'unknown')
                    message = result.get('message', 'You are not eligible for a trial')
                    
                    if reason == 'trial_already_used_email':
                        self.show_trial_warning_dialog(
                            "Trial Already Used",
                            "You have used your free trial with this email address."
                        )
                    elif reason == 'trial_already_used_hardware':
                        self.show_trial_warning_dialog(
                            "Trial Already Used",
                            "This device has been used for a free trial."
                        )
                    else:
                        self.show_trial_warning_dialog("Not Eligible", message)
                    return False
            else:
                self.show_trial_warning_dialog("Error", "Failed to check trial eligibility")
                return False
                
        except requests.exceptions.ConnectionError:
            self.show_trial_warning_dialog(
                "No Internet Connection",
                "An internet connection is required to activate a trial.\n\nPlease check your connection and try again."
            )
            return False
        except Exception as e:
            self.show_trial_error_dialog("Failed to check eligibility", str(e))
            return False
    
    def create_trial_license(self, email, hardware_id):
        """Create a trial license"""
        try:
            from client.config.config import TRIAL_CREATE_URL
            
            device_name = f"{platform.system()}-{socket.gethostname()}"
            
            response = requests.post(TRIAL_CREATE_URL, json={
                'email': email,
                'hardware_id': hardware_id,
                'device_name': device_name
            }, timeout=10)
            
            # Accept both 200 (OK) and 201 (Created)
            if response.status_code in [200, 201]:
                result = response.json()
                if result.get('success'):
                    license_key = result.get('license_key')
                    return license_key
                else:
                    error = result.get('error', 'Unknown error')
                    self.show_trial_warning_dialog("Error", f"Failed to create trial: {error}")
                    return None
            else:
                error_msg = f"Server returned status {response.status_code}"
                try:
                    error_msg = response.json().get('error', error_msg)
                except:
                    pass
                self.show_trial_warning_dialog("Error", f"Failed to create trial: {error_msg}")
                return None
                
        except Exception as e:
            self.show_trial_error_dialog("Error", f"Failed to create trial: {str(e)}")
            return None
    
    def show_trial_success_dialog(self, email, license_key):
        """Show success message inline in the login section"""
        print(f"DEBUG: show_trial_success_dialog called with email={email}")
        # Remove any transient trial/forgot block widgets cleanly
        try:
            if hasattr(self, 'trial_block_widget') and self.trial_block_widget:
                self.trial_block_widget.setParent(None)
                self.trial_block_widget.deleteLater()
                del self.trial_block_widget
            if hasattr(self, 'forgot_block_widget') and self.forgot_block_widget:
                self.forgot_block_widget.setParent(None)
                self.forgot_block_widget.deleteLater()
                del self.forgot_block_widget
        except:
            pass
        
        # Create success message using LoginMessage class
        is_dark = self.is_dark_mode()
        success_message = LoginMessage(
            "trial version created.\nLet's webatchify!",
            is_dark=is_dark
        )
        
        # Show centered overlay message
        self._show_centered_message(success_message)
        self.success_message = success_message
        
        # Auto-transition after 3 seconds
        QTimer.singleShot(3000, lambda: self.transition_trial_to_login(email, license_key))
    
    def show_trial_error_dialog(self, title, message):
        """Show error message inline in the login section using LoginMessage"""
        self._show_inline_message(title, message, message_type="error")
    
    def show_trial_warning_dialog(self, title, message):
        """Show warning message inline in the login section using LoginMessage"""
        self._show_inline_message(title, message, message_type="warning")
    
    def _show_inline_message(self, title, subtitle, message_type="info"):
        """Display message inline in the login section using LoginMessage class"""
        # Remove any transient trial/forgot block widgets cleanly
        try:
            if hasattr(self, 'trial_block_widget') and self.trial_block_widget:
                self.trial_block_widget.setParent(None)
                self.trial_block_widget.deleteLater()
                del self.trial_block_widget
            if hasattr(self, 'forgot_block_widget') and self.forgot_block_widget:
                self.forgot_block_widget.setParent(None)
                self.forgot_block_widget.deleteLater()
                del self.forgot_block_widget
        except:
            pass
        
        # Create message using LoginMessage class
        is_dark = self.is_dark_mode()
        message_widget = LoginMessage(title, subtitle, is_dark=is_dark)
        
        # Add a back button below the message
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        back_btn = QPushButton("back")
        back_btn.setFixedSize(100, 40)
        back_btn.setFont(QFont(FONT_FAMILY, 12, QFont.Weight.Bold))
        back_btn.setStyleSheet(
            "QPushButton { "
            "background-color: transparent; "
            "color: #999999; "
            "border: 2px solid #999999; "
            "border-radius: 8px; "
            "} "
            "QPushButton:hover { "
            "background-color: transparent; "
            "color: #2196f3; "
            "border: 2px solid #2196f3; "
            "}"
        )
        back_btn.clicked.connect(self.reset_trial_to_login_mode)
        button_layout.addWidget(back_btn)
        button_layout.addStretch()
        
        message_widget.add_content(QWidget())  # Add spacing
        message_layout = message_widget.layout()
        message_layout.addLayout(button_layout)
        
        # Show centered overlay
        self._show_centered_message(message_widget)
        self.message_widget = message_widget
        
        # Hide trial buttons if they exist
        if hasattr(self, 'trial_send_btn'):
            self.trial_send_btn.setEnabled(True)
            self.trial_send_btn.setText("enter trial mode")

        # Auto-clear message after 3 seconds and return to login window
        QTimer.singleShot(3000, self.reset_trial_to_login_mode)
    
    
    def transition_trial_to_login(self, email, trial_license):
        """Transition from trial mode back to login with pre-filled credentials"""
        # Clear any displayed messages first
        self.clear_message_display()

        # Reset to login mode (removes trial UI)
        self.reset_trial_to_login_mode()
        
        # Pre-fill email and license key
        # Pre-fill email and license key
        if hasattr(self, 'email_input'):
            self.email_input.setText(email)
        if hasattr(self, 'license_input'):
            self.license_input.setText(trial_license)
        
        # Highlight login button with green animation
        self.highlight_login_button()

        # Temporarily suppress Enter key login for 3 seconds to avoid accidental close
        try:
            self.enter_suppressed_until = datetime.now() + timedelta(seconds=3)
            QTimer.singleShot(3100, lambda: setattr(self, 'enter_suppressed_until', None))
        except:
            pass
    
    def highlight_login_button(self):
        """Highlight the login button"""
        original_style = self.login_btn.styleSheet()
        
        # Change to highlighted state
        self.login_btn.setStyleSheet(
            "QPushButton { "
            "background-color: #43a047; "
            "color: white; "
            "border: 2px solid #2e7d32; "
            "border-radius: 8px; "
            "} "
            "QPushButton:hover { background-color: #2e7d32; }"
        )
        
        # Restore after 2 seconds (with safety check)
        def restore_style():
            try:
                if hasattr(self, 'login_btn') and self.login_btn:
                    self.login_btn.setStyleSheet(original_style)
            except:
                pass  # Widget was destroyed, ignore
        
        QTimer.singleShot(2000, restore_style)
    
    def reset_trial_input_styles(self):
        """Reset trial input field styles to normal"""
        is_dark = self.is_dark_mode()
        if is_dark:
            login_bg = "#2b2b2b"
            text_color = "white"
        else:
            login_bg = "#e8e8e8"
            text_color = "black"
        
        input_style = f"""
            QLineEdit {{
                background-color: {login_bg};
                color: {text_color};
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 10px;
            }}
            QLineEdit::placeholder {{
                color: #999;
            }}
        """
        self.trial_email_input.setStyleSheet(input_style)
    
    def clear_message_display(self):
        """Clear any displayed message (success/error/warning)"""
        # Remove overlay if present
        self._remove_message_overlay()
        if hasattr(self, 'message_widget'):
            self.message_widget = None
    
    def reset_trial_to_login_mode(self):
        """Reset UI from trial mode back to normal login mode"""
        # Helper to remove a layout item safely
        def _remove_item(item):
            if not item:
                return
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
                return
            lay = item.layout()
            if lay:
                while lay.count():
                    nested = lay.takeAt(0)
                    if nested and nested.widget():
                        nw = nested.widget()
                        nw.setParent(None)
                        nw.deleteLater()
                lay.setParent(None)

        # Get the login layout
        login_layout = self.login_section.layout()

        # Remove overlay message if present
        self._remove_message_overlay()

        # Remove block widgets if present
        for widget_attr in ['trial_block_widget', 'forgot_block_widget']:
            if hasattr(self, widget_attr):
                w = getattr(self, widget_attr)
                if w:
                    try:
                        w.setParent(None)
                        w.deleteLater()
                    except:
                        pass

        # Do NOT remove arbitrary items near trial_start_index to avoid deleting original widgets.
        
        # Clean up all trial/forgot and message references
        for attr in ['trial_email_container', 'trial_send_btn_layout', 'trial_back_btn_layout',
                 'trial_email_input', 'trial_send_btn', 'trial_back_btn',
                 'resend_container', 'send_btn_layout', 'back_btn_layout',
                 'resend_input', 'send_btn', 'back_btn',
                 'trial_block_widget', 'forgot_block_widget',
                 'success_message', 'message_widget', 'trial_start_index', 'forgot_start_index',
                 'original_layout_count']:
            if hasattr(self, attr):
                delattr(self, attr)
        
        self.show_trial_mode = False
        self.show_forgot_mode = False
        self.waiting_for_response = False
        
        # Restore all hidden login elements
        self._show_login_elements()
        
        # Show all original widgets (with safety checks)
        if hasattr(self, 'email_input'):
            try:
                self.email_input.show()
            except: pass
        if hasattr(self, 'license_input'):
            try:
                self.license_input.show()
            except: pass
        if hasattr(self, 'auto_login_cb'):
            try:
                self.auto_login_cb.show()
            except: pass
        if hasattr(self, 'forgot_btn'):
            try:
                self.forgot_btn.show()
            except: pass
        if hasattr(self, 'login_btn'):
            try:
                self.login_btn.show()
            except: pass
        if hasattr(self, 'trial_btn'):
            try:
                self.trial_btn.show()
            except: pass
        if hasattr(self, 'msstore_btn'):
            try:
                self.msstore_btn.show()
            except: pass
        if hasattr(self, 'gumroad_btn'):
            try:
                self.gumroad_btn.show()
            except: pass
        if hasattr(self, 'buy_label'):
            try:
                self.buy_label.show()
            except: pass
        
        # Set focus to email input when returning to login
        if hasattr(self, 'email_input'):
            QTimer.singleShot(100, lambda: self.email_input.setFocus() if hasattr(self, 'email_input') else None)

    def handle_resend(self):
        """Handle forgot license - retrieve license key from server"""
        try:
            print(f"[SEARCH] DEBUG [handle_resend]: START - waiting_for_response={getattr(self, 'waiting_for_response', False)}")
            
            # Clear any existing messages/overlays first to ensure consistent behavior
            self._remove_message_overlay()
            
            email = self.resend_input.text().strip()
            print(f"[SEARCH] DEBUG [handle_resend]: Email entered: '{email}'")
            
            if not email:
                print(f"[SEARCH] DEBUG [handle_resend]: Empty email, showing error")
                self.resend_input.show_error("email required")
                return
            
            # Validate email format using EmailInput validation
            if not self.resend_input.validate_email():
                print(f"[SEARCH] DEBUG [handle_resend]: Invalid email format, showing error")
                self.resend_input.show_error("incorrect mail format")
                return
        except Exception as e:
            print(f"[SEARCH] DEBUG [handle_resend]: Exception during validation: {e}")
            import traceback
            traceback.print_exc()
            return

        # Grey out and disable send button while waiting
        try:
            print(f"[SEARCH] DEBUG [handle_resend]: Setting waiting_for_response=True")
            self.waiting_for_response = True
            self.send_btn.setEnabled(False)
            self.send_btn.setText("Processing...")
            self.send_btn.setStyleSheet(
                "QPushButton { background-color: transparent; color: #bbbbbb; border: 2px solid #666666; border-radius: 8px; }"
            )
        except:
            pass

        # Development mode simulation: f@f.com success, n@n.com fail, invalid = error
        email_norm = (email or "").strip().lower()
        if email_norm in ["f@f.com", "n@n.com", "invalid"]:
            print(f"[SEARCH] DEBUG [handle_resend]: Dev mode detected for '{email_norm}', simulating 2s delay")
            def _finish_dev_resend():
                print(f"[SEARCH] DEBUG [_finish_dev_resend]: Delay complete, showing message for '{email_norm}'")
                if email_norm == "f@f.com":
                    self._show_inline_forgot_message(
                        "License key sent! ✉️",
                        "Check your mail box.",
                        message_type="success"
                    )
                elif email_norm == "n@n.com":
                    self._show_inline_forgot_message(
                        "License Not Found",
                        "No license found for this email address",
                        message_type="error"
                    )
                else:  # invalid
                    self._show_inline_forgot_message(
                        "Error",
                        "An error occurred processing your request",
                        message_type="error"
                    )
                try:
                    print(f"[SEARCH] DEBUG [_finish_dev_resend]: Re-enabling send button")
                    self.send_btn.setEnabled(True)
                    self.send_btn.setText("Send")
                    # Restore original style
                    self.send_btn.setStyleSheet(
                        "QPushButton { background-color: transparent; color: white; border: 2px solid #2196f3; border-radius: 8px; }"
                    )
                except:
                    pass
                print(f"[SEARCH] DEBUG [_finish_dev_resend]: Setting waiting_for_response=False")
                self.waiting_for_response = False
            QTimer.singleShot(2000, _finish_dev_resend)
            return

        # Real server request
        self.request_forgot_license(email)
    
    def request_forgot_license(self, email):
        """Request forgot license from server - ALWAYS shows result"""
        try:
            from client.config.config import FORGOT_LICENSE_URL
            
            print(f"[SEARCH] DEBUG: Sending forgot license request to {FORGOT_LICENSE_URL} for {email}")
            
            response = requests.post(FORGOT_LICENSE_URL, json={
                'email': email
            }, timeout=10)
            
            print(f"[OK] DEBUG: Server response received: {response.status_code}")
            
            result = response.json()
            
            print(f"[OK] DEBUG: Response JSON: {result}")
            
            if result.get('success'):
                # License found and email sent
                self._show_inline_forgot_message(
                    "License key sent! ✉️",
                    "Check your mail box.",
                    message_type="success"
                )
            else:
                # License not found or error
                error = result.get('error', 'unknown')
                message = result.get('message', 'Failed to find license')
                title = "License Not Found"
                
                if error == 'no_license_found':
                    message = 'No license found for this email address'
                elif error == 'rate_limit_exceeded':
                    title = "🔒 Too Many Requests"
                    retry_after = result.get('retry_after', 60)
                    minutes = int(retry_after / 60)
                    seconds = retry_after % 60
                    
                    if minutes > 0:
                        message = (
                            f"You've reached the maximum number of requests.\n\n"
                            f"[WAIT] Please wait {minutes} minute(s)"
                        )
                        if seconds > 0:
                            message += f" and {seconds} second(s)"
                        message += " before trying again."
                    else:
                        message = (
                            f"You've reached the maximum number of requests.\n\n"
                            f"[WAIT] Please wait {retry_after} seconds before trying again."
                        )
                
                self._show_inline_forgot_message(
                    title,
                    message,
                    message_type="error"
                )
            
        except requests.exceptions.Timeout:
            self._show_inline_forgot_message(
                "Connection Timeout",
                "The server took too long to respond. Please try again.",
                message_type="error"
            )
        except requests.exceptions.ConnectionError:
            self._show_inline_forgot_message(
                "No Internet Connection",
                "Unable to connect to the server. Please check your internet connection and try again.",
                message_type="error"
            )
        except Exception as e:
            self._show_inline_forgot_message(
                "Error",
                f"An error occurred: {str(e)}",
                message_type="error"
            )
        finally:
            # ALWAYS re-enable button and reset state
            try:
                self.send_btn.setEnabled(True)
                self.send_btn.setText("Send")
                self.send_btn.setStyleSheet(
                    "QPushButton { background-color: transparent; color: white; border: 2px solid #2196f3; border-radius: 8px; }"
                )
            except:
                pass
            self.waiting_for_response = False

    def _show_inline_forgot_message(self, title, subtitle, message_type="info"):
        """Display message inline for Forgot flow, replacing Forgot UI and adding a back button."""
        print(f"[SEARCH] DEBUG [_show_inline_forgot_message]: Showing message - title='{title}', type={message_type}")
        
        # Mark message as not yet stable (prevents premature Enter reset)
        self.message_stable = False
        print(f"[SEARCH] DEBUG [_show_inline_forgot_message]: Set message_stable=False")
        
        # Clear any existing overlays/messages first
        self._remove_message_overlay()
        
        # Remove forgot/trial block widgets if they exist
        try:
            if hasattr(self, 'forgot_block_widget') and self.forgot_block_widget:
                self.forgot_block_widget.setParent(None)
                self.forgot_block_widget.deleteLater()
                del self.forgot_block_widget
            if hasattr(self, 'trial_block_widget') and self.trial_block_widget:
                self.trial_block_widget.setParent(None)
                self.trial_block_widget.deleteLater()
                del self.trial_block_widget
        except:
            pass

        # Create message widget
        is_dark = self.is_dark_mode()
        message_widget = LoginMessage(title, subtitle, is_dark=is_dark)

        # No back button needed - message auto-closes with Enter key

        # Show centered overlay
        self._show_centered_message(message_widget)
        self.message_widget = message_widget
        
        # Mark message as stable after a short delay (500ms) to prevent premature reset
        def _mark_stable():
            self.message_stable = True
            print(f"[SEARCH] DEBUG [_show_inline_forgot_message]: Message now stable, Enter key will reset")
        QTimer.singleShot(500, _mark_stable)
        
        # Auto-dismiss success messages after 3 seconds
        if message_type == "success":
            QTimer.singleShot(3000, lambda: self.reset_trial_to_login_mode() if hasattr(self, 'overlay_widget') and self.overlay_widget else None)
    
    def reset_to_login_mode(self):
        """Reset UI to the initial login state reliably from any mode."""
        self.reset_trial_to_login_mode()
    
    def close_window(self):
        """Close the window"""
        self.reject()
    
    def keyPressEvent(self, event):
        """Handle key press events - prevent Enter from closing dialog"""
        if event.key() == Qt.Key.Key_Escape:
            self.close_window()
            event.accept()
            return
        
        # Intercept Enter/Return key - NEVER let it reach QDialog's default handler
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            print(f"[SEARCH] DEBUG [keyPressEvent]: Enter pressed at dialog level")
            
            # If there's a message overlay, close it
            if hasattr(self, 'overlay_widget') and self.overlay_widget:
                print(f"[SEARCH] DEBUG [keyPressEvent]: Closing overlay")
                self.reset_trial_to_login_mode()
                event.accept()
                return
            if hasattr(self, 'success_message_container') and self.success_message_container:
                print(f"[SEARCH] DEBUG [keyPressEvent]: Closing success message")
                self.reset_trial_to_login_mode()
                event.accept()
                return
            
            # Otherwise, just consume the Enter - do NOT close the dialog
            print(f"[SEARCH] DEBUG [keyPressEvent]: Consuming Enter to prevent dialog close")
            event.accept()  # Accept and return - do NOT call super()
            return
        
        # For all other keys, use default behavior
        super().keyPressEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        # Only allow dragging from non-interactive areas (media section)
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.drag_position = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        """Ensure overlay always covers the login section for proper centering, and reposition buttons."""
        try:
            if hasattr(self, 'overlay_widget') and self.overlay_widget:
                self.overlay_widget.setGeometry(self.login_section.rect())
        except:
            pass
        
        # Update button positions relative to window size
        self._update_close_button_position()
        
        super().resizeEvent(event)
    
    def _update_close_button_position(self):
        """Position close button and theme toggle button relative to top-right corner of window"""
        if hasattr(self, 'close_btn') and self.close_btn:
            # Close button: 10px from right edge, 10px from top
            x = self.width() - self.close_btn.width() - 10
            y = 10
            self.close_btn.move(x, y)
    
    # def _update_theme_toggle_button(self):
    #     """Update theme toggle button based on current mode (COMMENTED OUT)"""
    #     if hasattr(self, 'theme_toggle_btn') and self.theme_toggle_btn:
    #         # Only update if using emoji (not SVG icon)
    #         try:
    #             svg_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'icons', 'sun-moon.svg')
    #             if not os.path.exists(svg_path):
    #                 # SVG not found, use emoji instead
    #                 is_dark = self.is_dark_mode()
    #                 self.theme_toggle_btn.setText("☀️" if is_dark else "🌙")
    #         except:
    #             # If any error, try emoji
    #             is_dark = self.is_dark_mode()
    #             self.theme_toggle_btn.setText("☀️" if is_dark else "🌙")

    def eventFilter(self, obj, event):
        """Globally intercept Enter/Return while transient messages are visible."""
        try:
            from PyQt6.QtCore import QEvent
            if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Check waiting state
                is_waiting = getattr(self, 'waiting_for_response', False)
                
                # Check inline state
                has_overlay = hasattr(self, 'overlay_widget') and self.overlay_widget
                has_message = hasattr(self, 'message_container') and self.message_container
                has_success = hasattr(self, 'success_message_container') and self.success_message_container
                has_inline = has_overlay or has_message or has_success
                
                # Check message stability (prevents reset during message creation)
                message_stable = getattr(self, 'message_stable', True)  # Default True for backward compat
                
                print(f"[SEARCH] DEBUG [eventFilter]: Enter pressed - waiting={is_waiting}, has_inline={has_inline}, message_stable={message_stable}")
                
                # Consume Enter while waiting for server response to avoid accidental actions
                if is_waiting:
                    print(f"[SEARCH] DEBUG [eventFilter]: Consuming Enter (still waiting for server)")
                    return True
                
                # Only reset to login if message is stable AND not waiting
                if has_inline and message_stable:
                    print(f"[SEARCH] DEBUG [eventFilter]: Message stable, resetting to login")
                    self.reset_trial_to_login_mode()
                    return True  # consume event
                elif has_inline and not message_stable:
                    print(f"[SEARCH] DEBUG [eventFilter]: Message not yet stable, consuming Enter")
                    return True  # consume but don't reset
        except Exception as e:
            print(f"[SEARCH] DEBUG [eventFilter]: Exception: {e}")
        return super().eventFilter(obj, event)

    def load_media_animation(self):
        """Load and start playing the login animation video using OpenCV"""
        try:
            # Get path to the animation file
            animation_path = get_resource_path('client/assets/animations/login_anim.mp4')
            
            animation_path = os.path.abspath(animation_path)
            
            if os.path.exists(animation_path):
                print(f"[FILE] Animation path: {animation_path}")
                print(f"[FILE] File exists: {os.path.exists(animation_path)}")
                
                # Calculate video duration using OpenCV
                import cv2
                cap = cv2.VideoCapture(animation_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                cap.release()
                
                duration_ms = int((frame_count / fps) * 1000) if fps > 0 else None
                print(f"📹 Video duration: {duration_ms}ms ({duration_ms/1000:.1f}s)")
                
                # Start video playback in a separate thread with calculated duration
                self.video_thread = VideoPlaybackThread(animation_path, self.video_widget, duration_ms=duration_ms)
                # Connect frame signal manually for thread-safe updates
                self.video_thread.frame_ready.connect(self._on_login_frame_ready)
                self.video_thread.last_frame_captured.connect(self._on_login_frame_ready)  # Keep last frame
                self.video_thread.finished.connect(self._on_video_playback_finished)
                self.video_thread.start()
                print(f"[OK] Login animation started")
            else:
                print(f"[WARN]  Animation file not found: {animation_path}")
                self.show_placeholder_image()
        except Exception as e:
            print(f"[X] Error loading animation: {e}")
            import traceback
            traceback.print_exc()
            self.show_placeholder_image()
    
    def _on_video_playback_finished(self):
        """Called when video playback finishes - last frame should already be displayed"""
        try:
            print(f"⏹️  Video playback finished - last frame is held")
            # Last frame is already being displayed by last_frame_captured signal
            # No need to show placeholder image anymore
        except Exception as e:
            print(f"[X] Error after video playback: {e}")
            self.show_placeholder_image()
    
    def _on_login_frame_ready(self, pixmap):
        """Slot to handle frame display updates from video thread for login animation"""
        if pixmap and isinstance(self.video_widget, QLabel):
            self.video_widget.setPixmap(pixmap)
    
    
    def on_video_status_changed(self, status):
        """Handle video status changes (deprecated - using OpenCV now)"""
        pass
    
    def on_playback_state_changed(self, state):
        """Handle playback state changes (deprecated - using OpenCV now)"""
        pass
    
    def show_placeholder_image(self):
        """Display a static placeholder image after video ends"""
        try:
            # Try to load a placeholder image from assets
            placeholder_path = os.path.join(
                os.path.dirname(__file__), 
                '..', 'assets', 'images', 'login_placeholder.png'
            )
            
            placeholder_path = os.path.abspath(placeholder_path)
            
            if os.path.exists(placeholder_path):
                # Create label with image
                image_label = QLabel()
                pixmap = QPixmap(placeholder_path)
                # Scale to fit the media section exactly (422x750)
                scaled_pixmap = pixmap.scaledToHeight(750, Qt.TransformationMode.SmoothTransformation)
                image_label.setPixmap(scaled_pixmap)
                image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Replace video widget with image label
                media_layout = self.media_section.layout()
                media_layout.replaceWidget(self.video_widget, image_label)
                self.video_widget.hide()
                image_label.show()
                
                print(f"[OK] Placeholder image displayed: {placeholder_path}")
            else:
                # Show black background with a simple label
                print(f"[WARN]  Placeholder image not found: {placeholder_path}")
                self.show_simple_placeholder()
        except Exception as e:
            print(f"[X] Error displaying placeholder: {e}")
            self.show_simple_placeholder()
    
    def show_simple_placeholder(self):
        """Show a simple text placeholder"""
        try:
            label = QLabel("ImgApp")
            label.setFont(QFont(FONT_FAMILY, 48, QFont.Weight.Bold))
            label.setStyleSheet("color: #ffffff;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            media_layout = self.media_section.layout()
            media_layout.replaceWidget(self.video_widget, label)
            self.video_widget.hide()
            label.show()
            
            print(f"[OK] Simple placeholder displayed")
        except Exception as e:
            print(f"[X] Error showing simple placeholder: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernLoginWindow()
    window.show()
    sys.exit(app.exec())


















