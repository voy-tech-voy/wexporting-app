"""
Window Event Mixin for MainWindow

Extracts boilerplate window event handlers (resize, move, show, close, mouse events)
into a reusable mixin to reduce MainWindow complexity.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt


class WindowEventMixin:
    """
    Mixin providing standard window event handlers for frameless windows.
    
    Requires the following attributes on the class using this mixin:
    - title_bar_window: Separate title bar window instance
    - window_behavior: FramelessWindowBehavior instance
    """
    
    def resizeEvent(self, event):
        """Handle resize event - sync title bar width"""
        super().resizeEvent(event)
        # Sync title bar width
        if hasattr(self, 'title_bar_window'):
            self.title_bar_window._sync_width()

    def moveEvent(self, event):
        """Handle move event - sync title bar position"""
        super().moveEvent(event)
        # Sync title bar position
        if hasattr(self, 'title_bar_window'):
            self.title_bar_window._sync_position()

    def showEvent(self, event):
        """Override showEvent - show title bar window"""
        super().showEvent(event)
        # Show and position the separate title bar window
        if hasattr(self, 'title_bar_window'):
            self.title_bar_window.attach_to(self)
            self.title_bar_window.show()
        # NOTE: Blur is now ONLY on the title bar window, not main window
        self.enable_mouse_tracking_all()
        
    def closeEvent(self, event):
        """Close title bar window when main window closes"""
        if hasattr(self, 'title_bar_window'):
            self.title_bar_window.close()
        super().closeEvent(event)
        
    def enable_mouse_tracking_all(self):
        """Recursively enable mouse tracking for all widgets to ensure resize events propagate"""
        self.setMouseTracking(True)
        for widget in self.findChildren(QWidget):
            widget.setMouseTracking(True)
    
    def mousePressEvent(self, event):
        """Delegate window resize to FramelessWindowBehavior."""
        if hasattr(self, 'window_behavior') and self.window_behavior.handle_mouse_press(event):
            return
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        """Delegate to FramelessWindowBehavior."""
        if hasattr(self, 'window_behavior'):
            self.window_behavior.handle_mouse_release(event)
        super().mouseReleaseEvent(event)
        
    def mouseMoveEvent(self, event):
        """Delegate resize and cursor updates to FramelessWindowBehavior."""
        if hasattr(self, 'window_behavior'):
            self.window_behavior.handle_mouse_move(event)
        super().mouseMoveEvent(event)
        
    def changeEvent(self, event):
        """Handle window state changes - sync title bar visibility on minimize/restore"""
        super().changeEvent(event)
        
        # Hide title bar when minimized, show when restored
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized() and hasattr(self, 'title_bar_window'):
                self.title_bar_window.hide()
            elif not self.isMinimized() and hasattr(self, 'title_bar_window'):
                self.title_bar_window.show()
        
        # When main window is activated, also raise the title bar
        elif event.type() == event.Type.ActivationChange:
            if self.isActiveWindow() and hasattr(self, 'title_bar_window'):
                self.title_bar_window.raise_()
