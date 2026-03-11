"""
Login Window for ImgApp
Simple authentication dialog that appears before the main application
Supports both Gumroad and Microsoft Store distribution.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame, QApplication, QMessageBox, QInputDialog, QWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QPalette, QPixmap
import sys
import winreg
import os
import requests
from client.utils.font_manager import AppFonts
from client.utils.platform_detection import (
    AppPlatform, get_cached_platform, should_show_gumroad_ui, 
    should_use_store_license, MSStoreLicenseChecker, get_platform_display_name
)
import hashlib
import uuid
import platform
import socket
import json
from datetime import datetime, timedelta
from client.version import APP_NAME
import logging

logger = logging.getLogger(__name__)

# Development mode detection
DEVELOPMENT_MODE = getattr(sys, '_called_from_test', False) or __debug__ and not getattr(sys, 'frozen', False)

class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.authenticated = False
        self.is_trial = False
        
        # Detect distribution platform
        self.app_platform = get_cached_platform()
        self.is_msstore = self.app_platform == AppPlatform.MSSTORE
        logger.info(f"LoginWindow initialized for platform: {self.app_platform.value}")
        
        # MS Store license checker (only available in Store apps)
        self.msstore_license_checker = MSStoreLicenseChecker() if self.is_msstore else None
        
        self.setup_ui()
        self.apply_styles()
        
        # For MS Store apps, try silent license check first
        if self.is_msstore:
            self._try_msstore_silent_auth()
        
        # Load saved credentials
        self.load_saved_credentials()

    def get_config_path(self):
        """Get path for local user config"""
        try:
            if os.name == 'nt':
                app_data = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA')
            else:
                app_data = os.path.expanduser('~/.config')
                
            config_dir = os.path.join(app_data, APP_NAME, 'config')
            os.makedirs(config_dir, exist_ok=True)
            return os.path.join(config_dir, 'user_session.json')
        except Exception:
            return None

    def save_credentials(self, email, license_key):
        """Save credentials locally for auto-login"""
        try:
            path = self.get_config_path()
            if not path:
                return
                
            data = {
                'email': email,
                'license_key': license_key,
                'last_login': datetime.now().isoformat()
            }
            with open(path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Failed to save credentials: {e}")

    def load_saved_credentials(self):
        """Pre-fill email if saved"""
        try:
            path = self.get_config_path()
            if path and os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    if 'email' in data:
                        self.username_input.setText(data['email'])
                    if 'license_key' in data:
                        self.password_input.setText(data['license_key'])
        except Exception:
            pass
    
    def _try_msstore_silent_auth(self):
        """
        Attempt silent authentication for MS Store apps.
        
        MS Store apps can check license status without user interaction
        using Windows.Services.Store APIs.
        """
        if not self.is_msstore or not self.msstore_license_checker:
            return
        
        try:
            logger.info("Attempting MS Store silent license check...")
            result = self.msstore_license_checker.check_license()
            
            if result.get('success') and result.get('is_active'):
                logger.info("MS Store license valid - proceeding with silent auth")
                
                # Store is active - auto-authenticate
                self.authenticated = True
                self.is_trial = result.get('is_trial', False)
                
                # Save pseudo-credentials for offline use
                self._save_msstore_session(result)
                
                # Close dialog and proceed
                self.accept()
            else:
                logger.info(f"MS Store license not active: {result.get('error', 'unknown')}")
                # Show login UI for trial or purchase
                
        except Exception as e:
            logger.error(f"MS Store silent auth failed: {e}")
            # Fall back to standard login UI
    
    def _save_msstore_session(self, license_result: dict):
        """Save MS Store license session for offline verification"""
        try:
            path = self.get_config_path()
            if not path:
                return
            
            data = {
                'platform': 'msstore',
                'is_active': license_result.get('is_active', False),
                'is_trial': license_result.get('is_trial', False),
                'sku_store_id': license_result.get('sku_store_id'),
                'expiry_date': license_result.get('expiry_date'),
                'last_check': datetime.now().isoformat()
            }
            
            with open(path, 'w') as f:
                json.dump(data, f)
                
        except Exception as e:
            logger.error(f"Failed to save MS Store session: {e}")

    def attempt_auto_login(self):
        """
        Attempt to login using saved credentials.
        Returns True if successful, False otherwise.
        """
        try:
            path = self.get_config_path()
            if not path or not os.path.exists(path):
                return False
                
            with open(path, 'r') as f:
                data = json.load(f)
                
            email = data.get('email')
            key = data.get('license_key')
            
            if not email or not key:
                return False
                
            # Development bypass
            if DEVELOPMENT_MODE and email == "dev":
                self.authenticated = True
                self.is_trial = False
                return True
            
            # Real server validation (silent - no UI feedback)
            try:
                result = self.validate_with_server(email, key)
                
                if result.get('success'):
                    self.authenticated = True
                    self.is_trial = result.get('is_trial', False)
                    return True
                else:
                    # Clear invalid credentials
                    if result.get('error') in ['invalid_license', 'license_deactivated', 'license_expired']:
                        self.clear_saved_credentials()
                    return False
                    
            except Exception as e:
                # Network error - allow offline grace period for previously validated licenses
                if DEVELOPMENT_MODE:
                    print(f"Auto-login network error: {e}")
                return False
                
        except Exception as e:
            if DEVELOPMENT_MODE:
                print(f"Auto-login error: {e}")
            return False
    
    def clear_saved_credentials(self):
        """Clear saved credentials when they become invalid"""
        try:
            path = self.get_config_path()
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        
    def setup_ui(self):
        """Setup the login window UI"""
        title_text = f"{APP_NAME} - Login"
        if DEVELOPMENT_MODE:
            title_text += " [DEV MODE]"
        self.setWindowTitle(title_text)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setFixedSize(500, 360)
        
        # Set window icon
        try:
            from PySide6.QtGui import QIcon
            from client.utils.resource_path import get_app_icon_path
            
            icon_path = get_app_icon_path()
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Could not set window icon: {e}")
        
        # Center the window on screen
        self.center_window()
        
        # Main layout with zero margins for full-width image
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)
        
        # Image Area (Top) - 40% of height (500x144)
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedHeight(144)
        
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
        logo_path = os.path.join(assets_dir, 'login_pic.jpg')
        
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                # Scale to cover width, crop height
                scaled = pixmap.scaled(500, 144, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                # Crop center
                x = (scaled.width() - 500) // 2
                y = (scaled.height() - 144) // 2
                logo_label.setPixmap(scaled.copy(x, y, 500, 144))
        else:
            logo_label.setText(APP_NAME)
            logo_label.setStyleSheet("background-color: #333; color: white; font-size: 16px; font-weight: bold;")
            
        main_layout.addWidget(logo_label)
        
        # Form Container (Bottom)
        form_frame = QFrame()
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(30, 20, 30, 30)
        form_layout.setSpacing(15)
        
        # Email field
        username_layout = QHBoxLayout()
        username_label = QLabel("Email:")
        username_label.setFixedWidth(100)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your email")
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        form_layout.addLayout(username_layout)
        
        # License key field
        password_layout = QHBoxLayout()
        password_label = QLabel("License Key:")
        password_label.setFixedWidth(100)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter license key")
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        form_layout.addLayout(password_layout)
        
        # Platform indicator for MS Store users
        if self.is_msstore:
            platform_label = QLabel(f"📦 {get_platform_display_name()}")
            platform_label.setStyleSheet("color: #0078D4; font-size: 11px;")
            platform_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            form_layout.addWidget(platform_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.exit_button = QPushButton("Exit")
        self.exit_button.setFixedSize(80, 30)
        self.exit_button.clicked.connect(self.exit_app)
        
        button_layout.addWidget(self.exit_button)
        button_layout.addStretch()
        
        # Trial button - show for both platforms (MS Store trials handled differently)
        self.trial_button = QPushButton("Trial")
        self.trial_button.setFixedSize(80, 30)
        self.trial_button.clicked.connect(self.handle_trial)
        self.trial_button.setObjectName("trial_button")
        
        button_layout.addWidget(self.trial_button)
        
        self.login_button = QPushButton("Login")
        self.login_button.setFixedSize(80, 30)
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self.handle_login)
        
        button_layout.addWidget(self.login_button)
        form_layout.addLayout(button_layout)
        
        main_layout.addWidget(form_frame)
        
        # Connect Enter key to login from both input fields
        self.username_input.returnPressed.connect(self.handle_login)
        self.password_input.returnPressed.connect(self.handle_login)
        
        # Set email input as focused by default (not the button)
        self.username_input.setFocus()
        
        # Set login button as default (visually highlighted)
        self.login_button.setDefault(True)
        
        # Bind Esc key to exit
        self.exit_button.setShortcut("Esc")

    def handle_login(self):
        """Handle login button click"""
        email = self.username_input.text().strip()
        key = self.password_input.text().strip()
        
        if not email or not key:
            QMessageBox.warning(self, "Error", "Please enter email and license key")
            return
            
        self.login_button.setEnabled(False)
        self.login_button.setText("Verifying...")
        QApplication.processEvents()
        
        try:
            # Development bypass
            if DEVELOPMENT_MODE and email == "dev":
                self.authenticated = True
                self.is_trial = False
                self.save_credentials(email, key)
                self.accept()
                return

            # Real server validation
            validation_result = self.validate_with_server(email, key)
            
            if validation_result.get('success'):
                self.authenticated = True
                self.is_trial = validation_result.get('is_trial', False)
                self.save_credentials(email, key)
                self.accept()
            else:
                error = validation_result.get('error', 'unknown')
                message = self.get_error_message(error, validation_result)
                QMessageBox.warning(self, "Login Failed", message)
                
        except requests.exceptions.ConnectionError:
            QMessageBox.warning(
                self, 
                "No Internet Connection",
                "Unable to connect to the license server.\n\nPlease check your internet connection and try again."
            )
        except requests.exceptions.Timeout:
            QMessageBox.warning(
                self,
                "Connection Timeout",
                "The server took too long to respond.\n\nPlease try again later."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
        finally:
            self.login_button.setEnabled(True)
            self.login_button.setText("Login")
    
    def validate_with_server(self, email, license_key):
        """
        Validate license with the server.
        
        Args:
            email: User's email
            license_key: License key to validate
        
        Returns:
            dict: Server response with success/error status
        """
        try:
            from client.config.config import VALIDATE_URL
            
            hardware_id = self.get_hardware_id()
            device_name = socket.gethostname()
            
            response = requests.post(
                VALIDATE_URL,
                json={
                    'email': email,
                    'license_key': license_key,
                    'hardware_id': hardware_id,
                    'device_name': device_name
                },
                timeout=15
            )
            
            result = response.json()
            
            # Log validation attempt (for debugging)
            if DEVELOPMENT_MODE:
                print(f"Validation response: {result}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            raise  # Re-raise to be handled by caller
        except json.JSONDecodeError:
            return {'success': False, 'error': 'invalid_response', 'message': 'Invalid server response'}
        except Exception as e:
            return {'success': False, 'error': 'validation_failed', 'message': str(e)}
    
    def get_error_message(self, error_code, result):
        """
        Convert error codes to user-friendly messages.
        
        Args:
            error_code: Error code from server
            result: Full result dict for additional context
        
        Returns:
            str: User-friendly error message
        """
        error_messages = {
            'invalid_license': 'Invalid license key. Please check and try again.',
            'email_mismatch': 'The email address does not match this license.',
            'license_expired': 'Your license has expired. Please renew to continue.',
            'license_deactivated': 'This license has been deactivated.',
            'bound_to_other_device': f"This license is already activated on another device: {result.get('bound_device', 'Unknown')}.\n\nUse 'Transfer License' to move it to this device.",
            'trial_requires_online': 'Trial licenses require an internet connection.',
            'trial_converted': result.get('message', 'Your trial has been upgraded. Please use your full license key.'),
            'offline_grace_expired': 'Please connect to the internet to validate your license.',
            'requires_online_validation': 'First-time activation requires an internet connection.',
            'validation_failed': 'Failed to validate license. Please try again.',
        }
        
        return error_messages.get(error_code, result.get('message', f'Login failed: {error_code}'))
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
        finally:
            self.login_button.setEnabled(True)
            self.login_button.setText("Login")
    
    def center_window(self):
        """Center the window on the screen"""
        screen = QApplication.primaryScreen().geometry()
        window = self.frameGeometry()
        window.moveCenter(screen.center())
        self.move(window.topLeft())
    
    def showEvent(self, event):
        """Override showEvent to apply dark title bar after window is shown"""
        super().showEvent(event)
        # Apply dark title bar with a small delay to ensure window is fully rendered
        if self.is_dark_mode():
            QTimer.singleShot(50, self.set_dark_title_bar)
    
    def set_dark_title_bar(self):
        """Set dark title bar on Windows"""
        try:
            from ctypes import windll, byref, sizeof, c_int
            
            # Get window handle
            hwnd = int(self.winId())
            
            # Set dark title bar (Windows 10 build 17763+)
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = c_int(1)
            windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                byref(value),
                sizeof(value)
            )
        except Exception as e:
            print(f"Could not set dark title bar: {e}")
    
    def is_dark_mode(self):
        """Detect if Windows is in dark mode using registry"""
        try:
            # Check Windows registry for dark mode setting
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            apps_use_light_theme, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            
            # 0 = Dark mode, 1 = Light mode
            is_dark = apps_use_light_theme == 0
            print(f"Windows dark mode detected: {is_dark} (AppsUseLightTheme={apps_use_light_theme})")
            return is_dark
            
        except Exception as e:
            print(f"Could not detect Windows theme, defaulting to light mode. Error: {e}")
            return False
    
    def apply_styles(self):
        """Apply styling to the login window based on system theme"""
        if self.is_dark_mode():
            # Dark mode styling
            self.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    border: 1px solid #555;
                    color: #ffffff;
                }
                
                QLabel {
                    color: #ffffff;
                    font-weight: bold;
                }
                
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #555;
                    border-radius: 3px;
                    font-size: 12px;
                    background-color: #3c3c3c;
                    color: #ffffff;
                }
                
                QLineEdit:focus {
                    border: 2px solid #4CAF50;
                }
                
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 12px;
                }
                
                QPushButton:hover {
                    background-color: #45a049;
                }
                
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
                
                QPushButton#exit_button {
                    background-color: transparent;
                    border: 2px solid #f44336;
                    color: #ffffff;
                }
                
                QPushButton#exit_button:hover {
                    background-color: rgba(244, 67, 54, 0.1);
                }

                QPushButton#trial_button {
                    background-color: transparent;
                    border: 2px solid #2196F3;
                    color: #2196F3;
                }
                
                QPushButton#trial_button:hover {
                    background-color: #2196F3;
                    color: white;
                }
                
                QFrame {
                    color: #666;
                }
            """)
        else:
            # Light mode styling (original)
            self.setStyleSheet("""
                QDialog {
                    background-color: #f0f0f0;
                    border: 1px solid #ccc;
                }
                
                QLabel {
                    color: #333;
                    font-weight: bold;
                }
                
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    font-size: 12px;
                }
                
                QLineEdit:focus {
                    border: 2px solid #4CAF50;
                }
                
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 12px;
                }
                
                QPushButton:hover {
                    background-color: #45a049;
                }
                
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
                
                QPushButton#exit_button {
                    background-color: transparent;
                    border: 2px solid #f44336;
                    color: #333333;
                }
                
                QPushButton#exit_button:hover {
                    background-color: rgba(244, 67, 54, 0.1);
                }

                QPushButton#trial_button {
                    background-color: transparent;
                    border: 2px solid #2196F3;
                    color: #2196F3;
                }
                
                QPushButton#trial_button:hover {
                    background-color: #2196F3;
                    color: white;
                }
            """)
        
        # Apply object names for specific styling
        self.exit_button.setObjectName("exit_button")
    
    def handle_trial(self):
        """Handle trial activation - show email dialog with custom styling"""
        
        # For MS Store apps, check if Store trial is available first
        if self.is_msstore:
            msstore_trial_result = self._try_msstore_trial()
            if msstore_trial_result:
                return  # MS Store trial handled
        
        # Standard Gumroad trial flow (server-based)
        self._show_gumroad_trial_dialog()
    
    def _try_msstore_trial(self) -> bool:
        """
        Try to start MS Store trial.
        
        Returns True if MS Store trial was handled, False to fall back to standard trial.
        """
        if not self.msstore_license_checker:
            return False
        
        try:
            # Check current license status
            license_result = self.msstore_license_checker.check_license()
            
            if license_result.get('success'):
                if license_result.get('is_trial') and license_result.get('is_active'):
                    # Already on trial - proceed
                    self.authenticated = True
                    self.is_trial = True
                    self._save_msstore_session(license_result)
                    self.accept()
                    return True
                elif license_result.get('is_active'):
                    # Already licensed - no trial needed
                    self.authenticated = True
                    self.is_trial = False
                    self._save_msstore_session(license_result)
                    self.accept()
                    return True
            
            # No active license - prompt to get trial from Store
            reply = QMessageBox.question(
                self,
                "Microsoft Store Trial",
                "Would you like to start a free trial through the Microsoft Store?\n\n"
                "This will open the Store app where you can activate your trial.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Open Store to app page for trial
                import subprocess
                subprocess.run(['start', 'ms-windows-store://pdp/?ProductId=YOUR_APP_ID'], shell=True)
                QMessageBox.information(
                    self,
                    "Trial Activation",
                    "Please complete the trial activation in the Microsoft Store,\n"
                    "then restart the application."
                )
                return True
            
            return False  # Fall back to server trial
            
        except Exception as e:
            logger.error(f"MS Store trial check failed: {e}")
            return False  # Fall back to server trial
    
    def _show_gumroad_trial_dialog(self):
        """Standard Gumroad/server-based trial activation dialog"""
        dialog = QDialog(self)
        # Remove window decorations (title bar and frame) and set modal
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        dialog.setModal(True)
        dialog.setFixedWidth(400)
        
        # Detect dark mode
        palette = self.palette()
        bg_color = palette.color(QPalette.Base).name()
        text_color = palette.color(QPalette.Text).name()
        button_bg = "#667eea"
        button_hover = "#5568d3"
        cancel_bg = "#666666" if bg_color.lower() == "#ffffff" else "#444444"
        cancel_hover = "#555555" if bg_color.lower() == "#ffffff" else "#333333"
        
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border-radius: 10px;
            }}
            QLabel {{
                color: {text_color};
                font-size: 13px;
            }}
            QLineEdit {{
                padding: 6px;
                border: 1px solid {text_color};
                border-radius: 5px;
                font-size: 12px;
                background-color: {bg_color};
                color: {text_color};
            }}
            QPushButton {{
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
                min-width: 80px;
                min-height: 30px;
            }}
            QPushButton#okBtn {{
                background-color: {button_bg};
                color: white;
                border: none;
            }}
            QPushButton#okBtn:hover {{
                background-color: {button_hover};
            }}
            QPushButton#cancelBtn {{
                background-color: {cancel_bg};
                color: {text_color};
                border: 2px solid #ff0000;
            }}
            QPushButton#cancelBtn:hover {{
                background-color: {cancel_hover};
                border: 2px solid #ff6666;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Start Your Free Trial")
        title.setFont(AppFonts.get_custom_font(14, bold=True))
        layout.addWidget(title)
        
        # Description
        description = QLabel("Enter your email to activate your 1-day free trial:")
        layout.addWidget(description)
        
        # Email input
        email_input = QLineEdit()
        email_input.setPlaceholderText("your.email@example.com")
        layout.addWidget(email_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setFixedSize(80, 30)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("Activate Trial")
        ok_btn.setObjectName("okBtn")
        ok_btn.setFixedSize(120, 30)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        # Connect buttons
        ok_clicked = False
        def on_ok():
            nonlocal ok_clicked
            ok_clicked = True
            dialog.accept()
        
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dialog.reject)
        
        # Focus on email input
        email_input.setFocus()
        
        # Dim the main window visually while dialog is open
        # Save original palette
        original_palette = self.palette()
        dimmed_palette = QPalette(original_palette)
        
        # Reduce brightness of all colors by ~50%
        for role in [QPalette.Window, QPalette.Base, QPalette.Button, QPalette.Text, QPalette.ButtonText]:
            color = dimmed_palette.color(role)
            if role in [QPalette.Text, QPalette.ButtonText]:
                # Reduce text color opacity
                color.setAlpha(120)
            else:
                # Darken background colors
                color = color.darker(150)
            dimmed_palette.setColor(role, color)
        
        self.setPalette(dimmed_palette)
        
        # Show dialog
        dialog.exec()
        
        # Restore original appearance
        self.setPalette(original_palette)
        
        if not ok_clicked:
            return  # User cancelled
        
        email = email_input.text().strip()
        
        if not email:
            QMessageBox.warning(self, "Email Required", "Please enter your email address")
            return
        
        # Validate email format
        if '@' not in email or '.' not in email.split('@')[-1]:
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address")
            return
        
        self.trial_button.setEnabled(False)
        self.trial_button.setText("Activating...")
        QApplication.processEvents()
        
        try:
            hardware_id = self.get_hardware_id()
            
            # Check trial eligibility
            if not self.check_trial_eligibility(email, hardware_id):
                return
            
            # Create trial license
            trial_license = self.create_trial_license(email, hardware_id)
            
            if trial_license:
                # Auto-fill the license key
                self.password_input.setText(trial_license)
                
                # Show custom success dialog
                self.show_trial_success_dialog(email, trial_license)
                
                # Auto-login with trial license
                self.handle_login()
                
        except Exception as e:
            self.show_trial_error_dialog("Failed to activate trial", str(e))
        finally:
            self.trial_button.setEnabled(True)
            self.trial_button.setText("Trial")
    
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
                            "You have already used your free trial with this email address."
                        )
                    elif reason == 'trial_already_used_hardware':
                        self.show_trial_warning_dialog(
                            "Trial Already Used",
                            "This device has already been used for a free trial."
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
                    print(f"Trial license created successfully")
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
            QMessageBox.critical(self, "Error", f"Failed to create trial: {str(e)}")
            return None

    def mousePressEvent(self, event):
        """Enable dragging the frameless window"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Enable dragging the frameless window"""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def handle_login(self):
        """Handle login attempt"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        # Development mode bypass
        if DEVELOPMENT_MODE and (username.lower() == "dev" or username.lower() == "developer"):
            print("🔓 DEVELOPMENT MODE: Bypassing license authentication")
            self.authenticated = True
            self.accept()  # Close dialog with success
            return
        
        # Simple authentication (you can modify this logic)
        if self.authenticate(username, password):
            self.authenticated = True
            self.accept()  # Close dialog with success
        else:
            # Show error by changing input styles
            self.show_login_error()
    
    def authenticate(self, email, license_key):
        """
        Hardware-bound license authentication with online validation and offline fallback
        """
        # Validate input parameters
        if not email.strip() or not license_key.strip():
            print("ERROR: Email and license key cannot be empty")
            return False
        
        # Get hardware ID for license binding
        hardware_id = self.get_hardware_id()
        
        # Try online validation first
        if self.validate_online(email, license_key, hardware_id):
            return True
        
        # Try offline token validation (cached from previous login)
        if self.validate_offline(email, license_key, hardware_id):
            print("Authenticated via offline token")
            return True

        # Fallback to local file validation (enterprise/bundled)
        return self.validate_local_file(email, license_key, hardware_id)
    
    def validate_local_file(self, email, license_key, hardware_id):
        """Validate license against local licenses.json file"""
        import json
        
        try:
            # Handle PyInstaller bundle path
            if getattr(sys, 'frozen', False):
                # Running in a PyInstaller bundle
                bundle_dir = sys._MEIPASS
                licenses_path = os.path.join(bundle_dir, 'licenses.json')
            else:
                # Running in development
                licenses_path = 'licenses.json'
            
            with open(licenses_path, 'r') as f:
                licenses = json.load(f)
            
            if license_key not in licenses:
                return False
            
            license_data = licenses[license_key]
            
            # Check if license is active
            if not license_data.get('active', False):
                return False
            
            # Check if email matches
            if license_data['email'] != email:
                return False
            
            # Check expiration
            from datetime import datetime
            if datetime.fromisoformat(license_data['expires']) < datetime.now():
                return False
            
            # Handle device binding
            if license_data['bound_device_id'] is None:
                # First time activation - bind to this device
                license_data['bound_device_id'] = hardware_id
                device_name = f"{platform.system()}-{socket.gethostname()}"
                license_data['bound_device_name'] = device_name
                license_data['last_validation'] = datetime.now().isoformat()
                license_data['validation_count'] = license_data.get('validation_count', 0) + 1
                
                # Save updated license data
                with open('licenses.json', 'w') as f:
                    json.dump(licenses, f, indent=2)
                
                # Store offline token
                self.store_offline_token(email, license_key, hardware_id)
                print("License validated and bound to device (local file)")
                return True
                
            elif license_data['bound_device_id'] != hardware_id:
                # License is bound to different device - use offline validation instead
                return False
            else:
                # License is bound to this device
                license_data['last_validation'] = datetime.now().isoformat()
                license_data['validation_count'] = license_data.get('validation_count', 0) + 1
                
                # Save updated license data
                with open('licenses.json', 'w') as f:
                    json.dump(licenses, f, indent=2)
                
                # Store offline token
                self.store_offline_token(email, license_key, hardware_id)
                print("License validated (local file)")
                return True
                
        except FileNotFoundError:
            print("licenses.json not found")
            return False
        except Exception as e:
            print(f"Local file validation error: {e}")
            return False
    
    def get_hardware_id(self):
        """Generate unique hardware fingerprint"""
        try:
            # Combine multiple hardware identifiers
            mac = hex(uuid.getnode())
            cpu_info = platform.processor() or 'unknown'
            system = platform.system() + platform.release()
            hostname = socket.gethostname()
            
            # Create composite fingerprint
            combined = f"{mac}-{cpu_info}-{system}-{hostname}"
            return hashlib.md5(combined.encode()).hexdigest()[:16]
            # return "FAKE-HARDWARE-ID"  # For testing purposes, return a fixed ID
        except:
            # Fallback fingerprint
            return hashlib.md5(f"{platform.system()}-fallback".encode()).hexdigest()[:16]
    
    def validate_online(self, email, license_key, hardware_id):
        """Validate license with online API"""
        try:
            from client.config.config import VALIDATE_URL
            
            device_name = f"{platform.system()}-{socket.gethostname()}"
            
            response = requests.post(VALIDATE_URL, json={
                'email': email,
                'license_key': license_key,
                'hardware_id': hardware_id,
                'device_name': device_name,
                'app_version': '1.1.0'
            }, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success', False):
                    # Check if it's a trial license
                    is_trial = result.get('is_trial', False)
                    
                    if is_trial:
                        self.is_trial = True
                        print("Trial license validated")
                    
                    # Store token for offline use (paid licenses only)
                    if not is_trial:
                        self.store_offline_token(email, license_key, hardware_id)
                    
                    return True
                else:
                    # Handle specific errors
                    error = result.get('error', '')
                    if error == 'trial_requires_online':
                        QMessageBox.warning(
                            self,
                            "Trial Requires Internet",
                            "Trial licenses require an active internet connection.\n\n"
                            "Please connect to the internet to use your trial."
                        )
                    elif error == 'license_expired':
                        QMessageBox.warning(
                            self,
                            "License Expired",
                            "Your license has expired.\n\nPlease purchase a full license to continue."
                        )
                    return False
            else:
                print(f"Online validation failed with status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            print("No internet connection - will try offline validation")
            return False
        except Exception as e:
            print(f"Online validation failed: {e}")
            return False
    
    def validate_offline(self, email, license_key, hardware_id):
        """Validate license using stored offline token"""
        try:
            token_file = os.path.join(os.getenv('APPDATA', '.'), 'ImageWave', 'license.dat')
            
            if not os.path.exists(token_file):
                return False
            
            with open(token_file, 'r') as f:
                stored_data = json.load(f)
            
            # Verify stored credentials match
            if (stored_data.get('email') != email or 
                stored_data.get('license_key') != license_key or
                stored_data.get('hardware_id') != hardware_id):
                return False
            
            # Check if this was a trial license (trials don't support offline)
            is_trial = stored_data.get('is_trial', False)
            if is_trial:
                QMessageBox.warning(
                    self,
                    "Trial Requires Internet",
                    "Trial licenses require an active internet connection.\n\n"
                    "Please connect to the internet to use your trial."
                )
                return False
            
            # Check if offline grace period has expired (3 days for paid licenses)
            last_validation = datetime.fromisoformat(stored_data['last_validation'])
            grace_period = timedelta(days=3)
            
            if datetime.now() - last_validation > grace_period:
                QMessageBox.warning(
                    self,
                    "Offline Period Expired",
                    "Your 3-day offline grace period has expired.\n\n"
                    "Please connect to the internet to validate your license."
                )
                return False
            
            days_remaining = (grace_period - (datetime.now() - last_validation)).days
            print(f"Using offline validation ({days_remaining} days remaining in grace period)")
            return True
            
        except Exception as e:
            print(f"Offline validation failed: {e}")
            return False
    
    def store_offline_token(self, email, license_key, hardware_id, is_trial=False):
        """Store successful validation for offline use (paid licenses only)"""
        try:
            # Don't store offline token for trial licenses
            if is_trial:
                return
            
            app_data_dir = os.path.join(os.getenv('APPDATA', '.'), APP_NAME)
            os.makedirs(app_data_dir, exist_ok=True)
            
            token_file = os.path.join(app_data_dir, 'license.dat')
            
            token_data = {
                'email': email,
                'license_key': license_key,
                'hardware_id': hardware_id,
                'last_validation': datetime.now().isoformat(),
                'is_trial': is_trial
            }
            
            with open(token_file, 'w') as f:
                json.dump(token_data, f)
                
        except Exception as e:
            print(f"Could not store offline token: {e}")
    
    def handle_device_conflict(self, validation_result):
        """Handle case where license is bound to different device"""
        bound_device = validation_result.get('bound_device_name', 'Unknown Device')
        
        reply = QMessageBox.question(
            self,
            'License Already Registered',
            f'This license is already registered to:\n"{bound_device}"\n\n'
            f'Would you like to transfer the license to this device?\n'
            f'(This will deactivate the license on the other device)',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            return self.transfer_license()
        return False
    
    def transfer_license(self):
        """Transfer license to current device"""
        try:
            email = self.username_input.text().strip()
            license_key = self.password_input.text().strip()
            hardware_id = self.get_hardware_id()
            
            from client.config.config import TRANSFER_URL
            device_name = f"{platform.system()}-{socket.gethostname()}"
            
            response = requests.post(TRANSFER_URL, json={
                'email': email,
                'license_key': license_key,
                'new_hardware_id': hardware_id,
                'new_device_name': device_name
            }, timeout=10)
            
            result = response.json()
            if result.get('success'):
                self.store_offline_token(email, license_key, hardware_id)
                QMessageBox.information(self, 'Success', 'License transferred successfully!')
                return True
            else:
                QMessageBox.warning(self, 'Transfer Failed', result.get('error', 'Unknown error'))
                return False
                
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'License transfer failed: {str(e)}')
            return False
    
    def show_login_error(self):
        """Show login error by styling inputs red"""
        if self.is_dark_mode():
            error_style = """
                QLineEdit {
                    border: 2px solid #f44336;
                    background-color: #4a1f1f;
                    color: #ffffff;
                }
            """
        else:
            error_style = """
                QLineEdit {
                    border: 2px solid #f44336;
                    background-color: #ffebee;
                }
            """
        self.username_input.setStyleSheet(error_style)
        self.password_input.setStyleSheet(error_style)
        
        # Clear password field
        self.password_input.clear()
        self.password_input.setFocus()
        
        # Reset style after 2 seconds
        QTimer.singleShot(2000, self.reset_input_styles)
    
    def reset_input_styles(self):
        """Reset input field styles to normal"""
        self.username_input.setStyleSheet("")
        self.password_input.setStyleSheet("")
    
    def show_trial_success_dialog(self, email, license_key):
        """Show custom success dialog with copyable license key"""
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        dialog.setModal(True)
        dialog.setFixedWidth(450)
        
        # Detect dark mode
        palette = self.palette()
        bg_color = palette.color(QPalette.Base).name()
        text_color = palette.color(QPalette.Text).name()
        
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border-radius: 10px;
            }}
            QLabel {{
                color: {text_color};
            }}
            QLineEdit {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {text_color};
                border-radius: 5px;
                padding: 8px;
                font-family: monospace;
            }}
            QPushButton {{
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
                background-color: #667eea;
                color: white;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #5568d3;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Title
        title = QLabel("[DONE] Trial Activated!")
        title.setFont(AppFonts.get_custom_font(14, bold=True))
        layout.addWidget(title)
        
        # Message
        msg = QLabel(f"Your 1-day free trial has been activated!\n\nA confirmation email has been sent to:\n{email}")
        layout.addWidget(msg)
        
        # License key section
        key_label = QLabel("License Key (Click to select, Ctrl+C to copy):")
        layout.addWidget(key_label)
        
        key_input = QLineEdit()
        key_input.setText(license_key)
        key_input.setReadOnly(True)
        key_input.selectAll()  # Auto-select text
        layout.addWidget(key_input)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        copy_btn = QPushButton("Copy License Key")
        def copy_to_clipboard():
            QApplication.clipboard().setText(license_key)
            copy_btn.setText("Copied! [OK]")
            QApplication.processEvents()
            # Use QTimer instead of sleep to avoid blocking
            from functools import partial
            QTimer.singleShot(1000, partial(lambda: copy_btn.setText("Copy License Key")))
        copy_btn.clicked.connect(copy_to_clipboard)
        button_layout.addWidget(copy_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(100, 35)
        ok_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        # Dim main window
        original_palette = self.palette()
        dimmed_palette = QPalette(original_palette)
        for role in [QPalette.Window, QPalette.Base, QPalette.Button, QPalette.Text, QPalette.ButtonText]:
            color = dimmed_palette.color(role)
            if role in [QPalette.Text, QPalette.ButtonText]:
                color.setAlpha(120)
            else:
                color = color.darker(150)
            dimmed_palette.setColor(role, color)
        
        self.setPalette(dimmed_palette)
        dialog.exec()
        self.setPalette(original_palette)
    
    def show_trial_error_dialog(self, title, message):
        """Show custom error dialog"""
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        dialog.setModal(True)
        dialog.setFixedWidth(400)
        
        # Detect dark mode
        palette = self.palette()
        bg_color = palette.color(QPalette.Base).name()
        text_color = palette.color(QPalette.Text).name()
        
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border-radius: 10px;
            }}
            QLabel {{
                color: {text_color};
            }}
            QPushButton {{
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
                background-color: #ff6b6b;
                color: white;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #ff5252;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Title
        title_label = QLabel(f"[WARN] {title}")
        title_label.setFont(AppFonts.get_custom_font(12, bold=True))
        layout.addWidget(title_label)
        
        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        
        # OK button
        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(100, 35)
        ok_btn.clicked.connect(dialog.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # Dim main window
        original_palette = self.palette()
        dimmed_palette = QPalette(original_palette)
        for role in [QPalette.Window, QPalette.Base, QPalette.Button, QPalette.Text, QPalette.ButtonText]:
            color = dimmed_palette.color(role)
            if role in [QPalette.Text, QPalette.ButtonText]:
                color.setAlpha(120)
            else:
                color = color.darker(150)
            dimmed_palette.setColor(role, color)
        
        self.setPalette(dimmed_palette)
        dialog.exec()
        self.setPalette(original_palette)
    
    def show_trial_warning_dialog(self, title, message):
        """Show custom warning dialog for trial-related issues"""
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        dialog.setModal(True)
        dialog.setFixedWidth(400)
        
        # Detect dark mode
        palette = self.palette()
        bg_color = palette.color(QPalette.Base).name()
        text_color = palette.color(QPalette.Text).name()
        
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border-radius: 10px;
            }}
            QLabel {{
                color: {text_color};
            }}
            QPushButton {{
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
                background-color: #ffa500;
                color: white;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #ff8c00;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Title
        title_label = QLabel(f"[WARN] {title}")
        title_label.setFont(AppFonts.get_custom_font(12, bold=True))
        layout.addWidget(title_label)
        
        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        
        # OK button
        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(100, 35)
        ok_btn.clicked.connect(dialog.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # Dim main window
        original_palette = self.palette()
        dimmed_palette = QPalette(original_palette)
        for role in [QPalette.Window, QPalette.Base, QPalette.Button, QPalette.Text, QPalette.ButtonText]:
            color = dimmed_palette.color(role)
            if role in [QPalette.Text, QPalette.ButtonText]:
                color.setAlpha(120)
            else:
                color = color.darker(150)
            dimmed_palette.setColor(role, color)
        
        self.setPalette(dimmed_palette)
        dialog.exec()
        self.setPalette(original_palette)
    
    def exit_app(self):
        """Exit the application"""
        self.reject()  # Close dialog with cancel
        sys.exit(0)
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Escape:
            self.exit_app()
        super().keyPressEvent(event)
