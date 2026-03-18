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
        
        # We no longer track manual resize edges here, as Windows natively handles it via WM_NCHITTEST
    
    def handle_mouse_press(self, event) -> bool:
        """Deprecated: Returns False so Qt routes events normally."""
        return False
        
    def handle_mouse_release(self, event):
        """Deprecated."""
        pass
        
    def handle_mouse_move(self, event) -> bool:
        """Deprecated: Returns False so Qt routes events normally."""
        return False
    
    def native_event(self, eventType, message) -> tuple[bool, int]:
        """
        Handle Windows native events for frameless window resizing edges.
        
        Args:
            eventType: Type of event
            message: Windows message pointer
            
        Returns:
            Tuple of (handled, result). result should be an int.
        """
        try:
            import ctypes.wintypes
            # Only intercept for Windows messages
            if eventType == b"windows_generic_MSG" or eventType == b"windows_dispatcher_MSG":
                msg = ctypes.wintypes.MSG.from_address(message.__int__())
                
                # WM_NCHITTEST = 0x0084
                if msg.message == 0x0084:
                    # Parse mouse coordinates using QCursor for precise logical DPI scaling
                    # msg.lParam contains physical coordinates which mismatch Qt's logical mapFromGlobal
                    from PySide6.QtGui import QCursor
                    global_pos = QCursor.pos()
                    
                    # Convert to window-local coordinates
                    local_pos = self.window.mapFromGlobal(global_pos)
                    
                    w = self.window.width()
                    h = self.window.height()
                    border = self.border_width
                    
                    left = local_pos.x() < border
                    right = local_pos.x() >= w - border
                    top = local_pos.y() < border
                    bottom = local_pos.y() >= h - border
                    
                    # Windows HT* constants
                    HTTOPLEFT = 13
                    HTTOP = 12
                    HTTOPRIGHT = 14
                    HTLEFT = 10
                    HTRIGHT = 11
                    HTBOTTOMLEFT = 16
                    HTBOTTOM = 15
                    HTBOTTOMRIGHT = 17
                    HTCLIENT = 1
                    
                    if top and left: return True, HTTOPLEFT
                    if top and right: return True, HTTOPRIGHT
                    if bottom and left: return True, HTBOTTOMLEFT
                    if bottom and right: return True, HTBOTTOMRIGHT
                    if left: return True, HTLEFT
                    if right: return True, HTRIGHT
                    if top: return True, HTTOP
                    if bottom: return True, HTBOTTOM
                    
                    # If not on border, return unhandled (let Qt decide)
                    # We MUST return True, HTCLIENT to tell windows it's the client area usually natively
                    # BUT doing so might block Qt's click events.
                    # Returning False, 0 is usually correct for Qt to handle widgets itself
        except Exception as e:
            print(f"Error in native event handling: {e}")
            
        return False, 0
    
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
