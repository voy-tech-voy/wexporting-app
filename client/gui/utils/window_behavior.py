"""
Frameless Window Behavior - Mediator-Shell Architecture Utility

Encapsulates frameless window dragging, resizing, and OS blur effects.
Extracted from MainWindow to follow the Mediator-Shell pattern.
"""

import ctypes
from ctypes import POINTER, Structure, c_int, byref, windll, sizeof
from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QMainWindow


class FramelessWindowBehavior:
    """
    Encapsulates frameless window dragging, resizing, and OS blur effects.
    
    This class provides:
    - Manual edge/corner resize detection and handling
    - Cursor shape updates on edge hover
    - Windows 11 Acrylic/Mica blur effect support
    
    Usage:
        behavior = FramelessWindowBehavior(main_window, border_width=8)
        
        # In MainWindow:
        def mousePressEvent(self, event):
            if behavior.handle_mouse_press(event):
                return
            super().mousePressEvent(event)
    """
    
    def __init__(self, window: QMainWindow, border_width: int = 8):
        """
        Initialize the frameless window behavior.
        
        Args:
            window: The QMainWindow to manage
            border_width: Width of the resize border in pixels
        """
        self.window = window
        self.border_width = border_width
        
        # Resize state
        self.resize_edge = ""
        self.resize_start_pos = None
        self.resize_start_geo = None
    
    def handle_mouse_press(self, event) -> bool:
        """
        Handle mouse press event for resize detection.
        
        Args:
            event: QMouseEvent
            
        Returns:
            True if event was handled (resize started), False otherwise
        """
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        
        pos = event.pos()
        border = self.border_width
        w = self.window.width()
        h = self.window.height()
        
        left = pos.x() < border
        right = pos.x() > w - border
        top = pos.y() < border
        bottom = pos.y() > h - border
        
        self.resize_edge = ""
        if top: self.resize_edge += "top"
        if bottom: self.resize_edge += "bottom"
        if left: self.resize_edge += "left"
        if right: self.resize_edge += "right"
        
        if self.resize_edge:
            self.resize_start_pos = event.globalPosition().toPoint()
            self.resize_start_geo = self.window.geometry()
            event.accept()
            return True
        
        return False
    
    def handle_mouse_release(self, event):
        """Reset resize state on mouse release."""
        self.resize_edge = ""
    
    def handle_mouse_move(self, event) -> bool:
        """
        Handle mouse move event for resize and cursor updates.
        
        Args:
            event: QMouseEvent
            
        Returns:
            True if resize was handled, False if only cursor update
        """
        # Handle resizing if active
        if self.resize_edge:
            bg = self.resize_start_geo
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            
            new_geo = QRect(bg)
            
            if "top" in self.resize_edge:
                new_geo.setTop(bg.top() + delta.y())
            if "bottom" in self.resize_edge:
                new_geo.setBottom(bg.bottom() + delta.y())
            if "left" in self.resize_edge:
                new_geo.setLeft(bg.left() + delta.x())
            if "right" in self.resize_edge:
                new_geo.setRight(bg.right() + delta.x())
            
            # Respect minimum size
            if new_geo.width() >= self.window.minimumWidth() and \
               new_geo.height() >= self.window.minimumHeight():
                self.window.setGeometry(new_geo)
            
            event.accept()
            return True
        
        # Update cursor based on position
        self._update_cursor(event.pos())
        return False
    
    def _update_cursor(self, pos):
        """Update cursor shape based on position near edges."""
        border = self.border_width
        w = self.window.width()
        h = self.window.height()
        
        left = pos.x() < border
        right = pos.x() > w - border
        top = pos.y() < border
        bottom = pos.y() > h - border
        
        # Set appropriate cursor
        if (top and left) or (bottom and right):
            self.window.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif (top and right) or (bottom and left):
            self.window.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif left or right:
            self.window.setCursor(Qt.CursorShape.SizeHorCursor)
        elif top or bottom:
            self.window.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.window.unsetCursor()
    
    def enable_blur(self):
        """
        Enable Windows Blur/Acrylic effect on the window.
        
        This uses the Windows SetWindowCompositionAttribute API
        to enable blur-behind effect.
        """
        try:
            class ACCENT_POLICY(Structure):
                _fields_ = [
                    ("AccentState", c_int),
                    ("AccentFlags", c_int),
                    ("GradientColor", c_int),
                    ("AnimationId", c_int)
                ]

            class WINDOWCOMPOSITIONATTRIBDATA(Structure):
                _fields_ = [
                    ("Attribute", c_int),
                    ("Data", ctypes.c_void_p),
                    ("SizeOfData", c_int)
                ]
            
            # Accent states
            ACCENT_ENABLE_BLURBEHIND = 3
            
            hwnd = int(self.window.winId())
            
            accent = ACCENT_POLICY()
            accent.AccentState = ACCENT_ENABLE_BLURBEHIND
            accent.GradientColor = 0 
            
            data = WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = 19
            data.Data = ctypes.cast(byref(accent), ctypes.c_void_p)
            data.SizeOfData = sizeof(accent)
            
            windll.user32.SetWindowCompositionAttribute(hwnd, byref(data))
            
        except Exception as e:
            print(f"Failed to enable blur: {e}")
