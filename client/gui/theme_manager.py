"""
Theme Manager - Singleton Controller for Application Theming
Handles dark/light mode detection and theme switching.

This is the central orchestrator that:
1. Maintains theme state (dark/light)
2. Emits signals when theme changes
3. Delegates QSS generation to StyleFactory
"""

from threading import Lock
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from client.gui.theme import Theme
from client.gui.styles.style_factory import StyleFactory


class ThemeManager(QObject):
    """
    Thread-safe Singleton Theme Manager.
    
    Responsibilities:
    - Detect system theme preferences
    - Maintain current theme state
    - Emit theme_changed signal with boolean payload (is_dark)
    - Delegate all QSS generation to StyleFactory
    
    Usage:
        manager = ThemeManager.instance()
        manager.theme_changed.connect(my_widget.update_theme)
        manager.set_theme('dark')
    """
    
    # Singleton instance
    _instance = None
    _lock = Lock()
    
    # Signal emits boolean: True for dark mode, False for light mode
    theme_changed = Signal(bool)
    
    def __new__(cls):
        """Thread-safe singleton implementation."""
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking pattern
                if cls._instance is None:
                    cls._instance = super(ThemeManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the theme manager (only runs once due to singleton)."""
        # Check if already initialized (must check before super().__init__)
        # Use __dict__ to avoid triggering QObject machinery
        if '_initialized' in self.__dict__:
            return
        
        # Initialize QObject base class
        super().__init__()
        
        # Mark as initialized
        self._initialized = True
        self.current_theme = 'dark'  # Default to dark mode
        Theme.set_dark_mode(True)
    
    @classmethod
    def instance(cls) -> 'ThemeManager':
        """
        Get the singleton instance of ThemeManager.
        
        Returns:
            ThemeManager: The singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def detect_system_theme(self) -> str:
        """
        Detect if system is using dark mode.
        
        Returns:
            str: 'dark' or 'light'
        """
        palette = QApplication.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        
        # Calculate luminance to determine if background is dark
        window_luminance = (0.299 * window_color.red() + 
                           0.587 * window_color.green() + 
                           0.114 * window_color.blue()) / 255
        
        return 'dark' if window_luminance < 0.5 else 'light'
    
    def get_current_theme(self) -> str:
        """
        Get the current theme.
        
        Returns:
            str: 'dark' or 'light'
        """
        return self.current_theme
    
    def is_dark_mode(self) -> bool:
        """
        Check if dark mode is active.
        
        Returns:
            bool: True if dark mode, False if light mode
        """
        return self.current_theme == 'dark'
    
    def set_theme(self, theme: str):
        """
        Set theme manually and emit signal.
        
        Args:
            theme: 'dark' or 'light'
        """
        if theme in ['dark', 'light'] and theme != self.current_theme:
            self.current_theme = theme
            is_dark = (theme == 'dark')
            Theme.set_dark_mode(is_dark)
            # Emit boolean payload for robust signal propagation
            self.theme_changed.emit(is_dark)
    
    def toggle_theme(self):
        """Toggle between dark and light mode."""
        new_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.set_theme(new_theme)
    
    # ============================================
    # DELEGATION METHODS (to StyleFactory)
    # ============================================
    
    def get_drag_drop_styles(self) -> dict:
        """
        Get drag and drop area styles for current theme.
        Delegates to StyleFactory.
        
        Returns:
            dict: Dictionary with 'normal' and 'drag_over' QSS strings
        """
        Theme.set_dark_mode(self.is_dark_mode())
        return StyleFactory.get_drag_drop_styles()
    
    def get_main_window_style(self) -> str:
        """
        Get main window stylesheet for current theme.
        Delegates to StyleFactory.
        
        Returns:
            str: Complete QSS stylesheet for main window
        """
        Theme.set_dark_mode(self.is_dark_mode())
        return StyleFactory.get_main_window_style()
    
    def get_dialog_styles(self) -> str:
        """
        Generate dialog-specific styling based on current theme.
        Delegates to StyleFactory.
        
        Returns:
            str: Complete QSS stylesheet for dialogs
        """
        Theme.set_dark_mode(self.is_dark_mode())
        return StyleFactory.get_dialog_styles()
