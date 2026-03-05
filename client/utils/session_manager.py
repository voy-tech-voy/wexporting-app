"""
Session Manager - Handles application session lifecycle.

Extracted from MainWindow to follow the Mediator-Shell pattern.
Handles logout, login window display, and app restart logic.
"""

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QTimer


class SessionManager:
    """
    Manages application session lifecycle including logout and re-login.
    
    This class handles:
    - Graceful shutdown of running conversions
    - Displaying login window after logout
    - Creating new main window on successful login
    - Complete app exit on login cancel
    
    Usage:
        session_mgr = SessionManager(main_window, conversion_engine)
        session_mgr.logout()  # Handles entire logout flow
    """
    
    def __init__(self, main_window, get_conversion_engine):
        """
        Initialize session manager.
        
        Args:
            main_window: The MainWindow instance
            get_conversion_engine: Callable that returns current conversion engine
        """
        self.main_window = main_window
        self._get_engine = get_conversion_engine
    
    def logout(self):
        """
        Restart the application.
        
        Note: In the Store-Native architecture, we don't 'logout' in the traditional sense 
        (users manage accounts via OS settings). This method now acts as a 'Restart' 
        to refresh store credentials or clear local state.
        """
        # Stop any running conversions
        engine = self._get_engine()
        if engine and engine.isRunning():
            engine.stop_conversion()
            engine.wait(1000)  # Wait up to 1 second
        
        # Get the QApplication instance
        app = QApplication.instance()
        
        # Prevent app from quitting when main window closes
        app.setQuitOnLastWindowClosed(False)
        
        # Close main window
        self.main_window.close()
        
        # Restart application
        import sys
        import subprocess
        
        print("[SESSION] Restarting application...")
        subprocess.Popen([sys.executable] + sys.argv)
        app.quit()
    
    def _show_login_window(self, app):
        """Deprecated - Login window removed in Phase 4"""
        pass
