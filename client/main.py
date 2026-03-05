#!/usr/bin/env python3
"""
Graphics Conversion App
A Qt-based application for converting graphics files using FFmpeg and ImageMagick
"""

import sys
import time
import os
import shutil
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QMessageBox, QDialog
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont
from PySide6.QtCore import Qt, QRect, QTimer
from client.gui.main_window import MainWindow
from client.utils.font_manager import AppFonts
from client.version import get_version, APP_NAME
from client.core.tool_manager import init_bundled_tools

# Setup logger for main module
import logging
logger = logging.getLogger(__name__)

# Import MessageManager for centralized message handling
try:
    from client.utils.message_manager import get_message_manager
    from client.config.config import API_BASE_URL as SERVER_BASE_URL
    MESSAGE_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: MessageManager not available: {e}")
    MESSAGE_MANAGER_AVAILABLE = False

# Import crash reporting
try:
    from client.utils.crash_reporter import run_with_crash_protection
    from client.utils.error_reporter import get_error_reporter, log_info, log_error
    CRASH_REPORTING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Crash reporting not available: {e}")
    CRASH_REPORTING_AVAILABLE = False

def set_dark_title_bar(window):
    """Set dark title bar for any window"""
    try:
        from ctypes import windll, byref, sizeof, c_int
        import winreg
        
        # Check if dark mode is enabled
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                           r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        apps_use_light_theme, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        
        if apps_use_light_theme == 0:  # Dark mode
            hwnd = int(window.winId())
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


class ToolLoadingWindow(QWidget):
    """Super simple splash window - just displays splash_pic.jpg with version info"""

    def __init__(self, version_text: str):
        super().__init__()
        
        # Load splash image
        from client.utils.resource_path import get_resource_path
        img_path = get_resource_path('client/assets/images/splash_pic.jpg')
        
        if not os.path.exists(img_path):
            print(f"[X] Splash image not found: {img_path}")
            sys.exit(1)
        
        pixmap = QPixmap(img_path)
        if pixmap.isNull():
            print(f"[X] Failed to load splash image")
            sys.exit(1)
        
        print(f"[CAM] Pixmap loaded: {pixmap.width()}x{pixmap.height()}, isNull: {pixmap.isNull()}")
        
        # Scale to 50% size
        scale_factor = .8
        width = int(pixmap.width() * scale_factor)
        height = int(pixmap.height() * scale_factor)
        scaled_pixmap = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.setFixedSize(width, height)
        
        # Frameless, always on top
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - width) // 2,
            (screen.height() - height) // 2
        )
        
        # Create label to display the pixmap
        label = QLabel(self)
        label.setFixedSize(width, height)
        label.setPixmap(scaled_pixmap)
        label.setScaledContents(False)  # Don't scale, show at exact size
        
        # Add version text in bottom right corner
        version_label = QLabel(self)
        version_label.setText(f"{APP_NAME} v{version_text}")
        version_label.setStyleSheet(
            "color: #999999; font-size: 11px; font-weight: normal;"
        )
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        
        # Position in bottom right corner with small padding
        padding = 8
        version_label.setGeometry(
            # Move slightly higher to make room for progress bar
            width - 150,
            height - 35,
            145,
            20
        )
        
        # Create indeterminate progress bar
        # Create dual progress bar container
        # Increased height to accommodate two bars stacked
        self.progress_bar = ProgressBarWidget(self)
        self.progress_bar.setGeometry(0, height - 8, width, 8)
        self.progress_bar.show()
        self.progress_bar.raise_()  # Ensure it is on top of the label
        
        # Start "loading" the main progress
        self.progress_bar.start_main_loading(total_time_ms=2500)

class ProgressBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")
        
        # Blue bar (top) state
        self.blue_progress = 0.0  # 0.0 to 1.0
        self.blue_duration = 300  # Initial duration in ms
        self.blue_start_time = 0
        
        # Green bar (bottom) state
        self.green_progress = 0.0 # 0.0 to 1.0
        self.green_duration = 3.0 # Default total load time
        self.green_start_time = 0
        
        # Import random for blue bar timing
        import random
        self.random = random
        
        # Timer for animation
        from PySide6.QtCore import QTimer
        import time
        self.time = time
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_progress)
        self.anim_timer.start(16)  # ~60fps
        
        self.blue_start_time = self.time.time()
        
    def start_main_loading(self, total_time_ms=2500):
        """Start the main green progress bar loading"""
        self.green_duration = total_time_ms / 1000.0
        self.green_start_time = self.time.time()
        
    def _animate_progress(self):
        current_time = self.time.time()
        
        # Update Blue Bar (Rapid cyclic loading with random duration)
        # "random time 300-500ms" as requested
        elapsed_blue = (current_time - self.blue_start_time) * 1000
        if elapsed_blue >= self.blue_duration:
            # Cycle complete, reset with new random duration
            self.blue_start_time = current_time
            self.blue_duration = self.random.randint(300, 500)
            self.blue_progress = 0.0
        else:
            self.blue_progress = elapsed_blue / self.blue_duration
            
        # Update Green Bar (Overall loading)
        if self.green_start_time > 0:
            elapsed_green = current_time - self.green_start_time
            self.green_progress = min(1.0, elapsed_green / self.green_duration)
            
        self.update()
        
    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        
        width = self.width()
        height = self.height()
        bar_height = height // 2
        
        # Draw Green Bar (Bottom, overall progress)
        painter.setBrush(QColor("#4CAF50"))  # Green
        green_width = int(width * self.green_progress)
        painter.drawRect(0, bar_height, green_width, bar_height)
        
        # Draw Blue Bar (Top, rapid indeterminate)
        # "Shooting" effect (left to right fill)
        painter.setBrush(QColor("#2196F3"))  # Blue
        blue_width = int(width * self.blue_progress)
        painter.drawRect(0, 0, blue_width, bar_height)




# ----------------------------------------------------------------------------
# Background Worker for Startup Operations
# ----------------------------------------------------------------------------
from PySide6.QtCore import QThread
class StartupWorker(QThread):
    def __init__(self):
        super().__init__()
        self.success = False
        
    def run(self):
        try:
            # Initialize ToolRegistry (handles all tool resolution)
            from client.core.tool_registry import get_registry
            registry = get_registry()
            registry.resolve_all()
            
            # Log which FFmpeg is being used
            ffmpeg_path = registry.get_tool_path('ffmpeg')
            if ffmpeg_path:
                print(f"DEBUG: Using FFmpeg: {ffmpeg_path}")
                if CRASH_REPORTING_AVAILABLE:
                    log_info(f"FFmpeg resolved: {ffmpeg_path}", "startup")
            else:
                print("Warning: No valid FFmpeg found")
            
            # Fallback: if registry didn't set FFMPEG_BINARY, try system
            if not os.environ.get('FFMPEG_BINARY'):
                system_ffmpeg = shutil.which('ffmpeg')
                if system_ffmpeg:
                    os.environ['FFMPEG_BINARY'] = system_ffmpeg
                    if CRASH_REPORTING_AVAILABLE:
                        log_info(f"Using system FFmpeg fallback: {system_ffmpeg}", "startup")
            
            self.success = True
            
        except Exception as e:
            print(f"Startup validation error: {e}")
            import traceback
            traceback.print_exc()
            self.success = False

# ----------------------------------------------------------------------------

def initialize_main_window(is_trial=False, skip_splash=False):
    """
    Initialize the main window with splash screen and tool validation.
    This logic is extracted so it can be reused during re-login.
    
    Args:
        is_trial (bool): Whether to start in trial mode
        skip_splash (bool): Whether to skip the splash screen (e.g. in dev mode)
        
    Returns:
        MainWindow: The initialized main window (not yet shown)
    """
    splash = None
    if not skip_splash:
        # Show a lightweight splash while bundled tools initialize
        version_text = get_version()
        splash = ToolLoadingWindow(version_text)
        splash.show()
        splash.raise_()
        splash.activateWindow()
        
        # Force the splash to render
        splash.update()
        splash.repaint()
        for _ in range(5):
            QApplication.processEvents()
        
        print(f"[WIN] Splash visible: {splash.isVisible()}")
        
        # Record start time
        splash_start_time = time.time()
    
    # ------------------------------------------------------------------------
    # Start background validation
    # ------------------------------------------------------------------------
    worker = StartupWorker()
    worker.start()
    
    # Wait for worker to complete while keeping UI responsive
    while worker.isRunning():
        QApplication.processEvents()
        time.sleep(0.01)  # Yield CPU (10ms)
        
    # Check worker results (if we need to act on failure, we can check worker.success)
    # But current logic just logs warnings and falls back, which is handled inside wrapper/settings
    
    # ------------------------------------------------------------------------
    
    # Create main window in background while splash is still visible
    print("[BUILD] Creating main window in background...")
    window = MainWindow(is_trial=is_trial)
    set_dark_title_bar(window)  # Apply dark title bar to main window
    QApplication.processEvents()  # Process events during window creation
    print("[OK] Main window created")
    
    # Ensure splash displays for minimum 2 seconds (non-blocking wait)
    if not skip_splash and splash:
        MIN_SPLASH_TIME = 2.0
        elapsed = time.time() - splash_start_time
        if elapsed < MIN_SPLASH_TIME:
            remaining_ms = int((MIN_SPLASH_TIME - elapsed) * 1000)
            print(f"[WAIT] Waiting {remaining_ms}ms more for splash (non-blocking)...")
            # Non-blocking wait - keeps UI responsive
            end_time = time.time() + (MIN_SPLASH_TIME - elapsed)
            while time.time() < end_time:
                QApplication.processEvents()
                time.sleep(0.016)  # ~60fps update rate
    
        # Close splash
        splash.close()
        print("[OK] Splash closed, returning main window")
    
    return window


def main():
    """Main application entry point with comprehensive error handling"""
    profile_startup = '--profile-startup' in sys.argv
    if profile_startup:
        # Remove the flag so Qt doesn't see it
        sys.argv = [arg for arg in sys.argv if arg != '--profile-startup']
    t0 = time.perf_counter()

    if CRASH_REPORTING_AVAILABLE:
        log_info("Starting ImgApp with crash protection", "startup")
    
    # Check for dev mode - skip login window
    # dev_mode: skips splash screen. False in production (env var never set in frozen build).
    dev_mode = os.getenv('DEV_MODE', '0') == '1'
    
    # Set AppUserModelID for Windows taskbar icon
    if os.name == 'nt':
        try:
            import ctypes
            myappid = 'imgapp.converter.v1'  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    try:
        app = QApplication(sys.argv)
        
        if profile_startup:
            t_app = time.perf_counter()
            print(f"[startup] QApplication created in {(t_app - t0)*1000:.1f} ms")
        
        # Initialize custom fonts after QApplication is created
        AppFonts.init_fonts()
        app.setFont(AppFonts.get_base_font())
        
        app.setApplicationName(APP_NAME)
        
        # Initialize MessageManager early in the application lifecycle
        if MESSAGE_MANAGER_AVAILABLE:
            try:
                msg_manager = get_message_manager(SERVER_BASE_URL)
                # Attempt to fetch messages from server (non-blocking, will use cache/fallback on failure)
                msg_manager.fetch_from_server(timeout=3)
                if CRASH_REPORTING_AVAILABLE:
                    log_info("MessageManager initialized successfully", "startup")
            except Exception as e:
                print(f"Warning: Failed to initialize MessageManager: {e}")
                if CRASH_REPORTING_AVAILABLE:
                    log_error(e, "message_manager_init")
        app.setApplicationVersion("1.1.2")
        
        # Set global application font - single point of control
        app.setFont(AppFonts.get_base_font())
        
        # Set application icon
        try:
            from PySide6.QtGui import QIcon
            from client.utils.resource_path import get_app_icon_path
            
            icon_path = get_app_icon_path()
            if os.path.exists(icon_path):
                app.setWindowIcon(QIcon(icon_path))
                if CRASH_REPORTING_AVAILABLE:
                    log_info(f"Application icon loaded: {icon_path}", "startup")
            else:
                if CRASH_REPORTING_AVAILABLE:
                    log_error(f"Icon file not found: {icon_path}", "icon_loading")
        except Exception as e:
            error_msg = f"Could not set application icon: {e}"
            print(error_msg)
            if CRASH_REPORTING_AVAILABLE:
                log_error(e, "icon_loading")
        
        # Show login window first (unless in dev mode)
        if CRASH_REPORTING_AVAILABLE:
            log_info("Initializing Store Authentication", "startup")
            
        # --------------------------------------------------------------------
        # Store Authentication (Replaces Login Window)
        # --------------------------------------------------------------------
        from client.core.auth import get_store_auth_provider, IStoreAuthProvider
        from client.core.energy_manager import EnergyManager
        from client.core.session_manager import SessionManager
        
        # Initialize Store Provider (MS Store on Windows, Apple on macOS)
        try:
            auth_provider = get_store_auth_provider()
            print(f"[AUTH] Using provider: {auth_provider.__class__.__name__}")
            
            # Attempt silent login
            auth_result = auth_provider.login()
            
            if auth_result and auth_result.success:
                print("[AUTH] Store login successful")
            else:
                print("[AUTH] Store login failed or unavailable")
            
            # Ensure SessionManager is initialized (may have been started inside provider.login())
            session = SessionManager.instance()
            
            # Apply developer override if configured (DEV MODE ONLY)
            from client.config.config import Config, PREMIUM_OVERRIDE
            if Config.DEVELOPMENT_MODE and PREMIUM_OVERRIDE is not None:
                session._set_premium_status(PREMIUM_OVERRIDE)
                if Config.DEVELOPMENT_MODE:
                    print(f"[AUTH] DEV Override: Premium = {PREMIUM_OVERRIDE}")
            
            # If session was never started (e.g. Store APIs unavailable), start a dev session
            if not session.is_authenticated:
                # In dev mode, apply override; in production, default to Free
                default_premium = PREMIUM_OVERRIDE if (Config.DEVELOPMENT_MODE and PREMIUM_OVERRIDE is not None) else False
                session.start_session(
                    store_user_id="dev-user",
                    jwt_token="",
                    is_premium=default_premium
                )
                if Config.DEVELOPMENT_MODE:
                    print("[AUTH] Started dev session (no Store APIs)")
            
            if Config.DEVELOPMENT_MODE:
                print(f"[AUTH] Session active. Premium: {session.is_premium}")
            
            # Configure Energy Manager sync
            if session.jwt_token:
                energy_mgr = EnergyManager.instance()
                energy_mgr.sync_with_server_jwt()
                
            if CRASH_REPORTING_AVAILABLE:
                log_info(f"Store auth successful. User: {session.store_user_id}", "startup")
                    
        except Exception as e:
            print(f"[AUTH] Error during store authentication: {e}")
            if CRASH_REPORTING_AVAILABLE:
                log_error(e, "store_auth")

        # --------------------------------------------------------------------

        # Launch main application
        if CRASH_REPORTING_AVAILABLE:
            log_info("Launching main application", "startup")

        # Use extracted initialization function
        # is_trial is now managed by EnergyManager state, so we pass False here
        window = initialize_main_window(is_trial=False, skip_splash=dev_mode)
        
        # --------------------------------------------------------------------
        # Version Gateway Pattern - Check for Updates
        # --------------------------------------------------------------------
        try:
            from client.utils.update_checker import check_for_updates, UpdateState
            
            logger.info("Checking for app updates...")
            update_result = check_for_updates(timeout=5)
            
            if update_result.state == UpdateState.MANDATORY_UPDATE:
                # Show blocking screen - app never reaches main window
                logger.warning(f"Mandatory update required: {update_result.latest_version}")
                from client.gui.dialogs.update_dialog import MandatoryUpdateScreen
                from client.gui.theme_manager import ThemeManager
                blocker = MandatoryUpdateScreen(update_result, theme_manager=ThemeManager.instance())
                blocker.show()
                sys.exit(app.exec())
                
            elif update_result.state == UpdateState.OPTIONAL_UPDATE:
                # Show dismissible dialog
                logger.info(f"Optional update available: {update_result.latest_version}")
                from client.gui.dialogs.update_dialog import OptionalUpdateDialog
                from client.gui.theme_manager import ThemeManager
                dialog = OptionalUpdateDialog(update_result, parent=window, theme_manager=ThemeManager.instance())
                dialog.exec()
                # Falls through to window.show() regardless of user choice
                
            else:
                # UP_TO_DATE - continue normally
                logger.info("App is up to date")
                
        except Exception as e:
            # Update check failed - fail silently and continue
            logger.warning(f"Update check failed: {e}")
            if CRASH_REPORTING_AVAILABLE:
                log_error(e, "update_check")
        # --------------------------------------------------------------------
        
        window.show()
        
        if CRASH_REPORTING_AVAILABLE:
            log_info("Main application window displayed", "startup")
            
        sys.exit(app.exec())
            
    except Exception as e:
        error_msg = f"Critical error in main application: {e}"
        print(error_msg)
        
        if CRASH_REPORTING_AVAILABLE:
            log_error(e, "main_application")
            # Create diagnostic report for troubleshooting
            get_error_reporter().create_diagnostic_report()
        
        # Re-raise to let emergency reporter handle it
        raise

def main_with_protection():
    """Main entry point with emergency crash protection"""
    if CRASH_REPORTING_AVAILABLE:
        return run_with_crash_protection(main)
    else:
        return main()

if __name__ == "__main__":
    # Support a headless runtime verification entry used by CI and smoke-tests.
    if '--verify-bundled-tools' in sys.argv:
        # Run the runtime verifier and return JSON+exit code. This keeps the same
        # runtime code path as the packaged executable and helps CI validate
        # extraction + checksum logic after packaging.
        import json as _json
        try:
            from client.core.tool_manager import verify_bundled_tools
            results = verify_bundled_tools(timeout=10)
            print(_json.dumps(results, indent=2))
            # Determine success: every tool that has a path and an expected_sha256 must match
            success = True
            for entry in results.values():
                p = entry.get('path')
                if p and os.path.exists(p):
                    # if an expected value was provided and mismatch, then fail
                    if entry.get('expected_sha256') is not None and not entry.get('checksum_match'):
                        success = False
                else:
                    # path missing is a failure
                    success = False

            sys.exit(0 if success else 2)
        except Exception as e:
            print(f"verify-bundled-tools failed: {e}")
            sys.exit(3)
    else:
        main_with_protection()
