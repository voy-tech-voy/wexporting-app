"""
Blur Effects for Windows Title Bar

Provides different blur effect implementations for Windows 10/11:
- CustomBlurEffect: Legacy implementation using SetWindowCompositionAttribute
- NativeWindowsBlurEffect: Modern implementation using DwmSetWindowAttribute (Win11 Mica/Acrylic)
"""

import os
import sys
import ctypes
from ctypes import Structure, c_int, byref, sizeof
from abc import ABC, abstractmethod


class BaseBlurEffect(ABC):
    """Abstract base class for blur effects"""
    
    @abstractmethod
    def apply(self, hwnd: int) -> bool:
        """
        Apply the blur effect to a window.
        
        Args:
            hwnd: Window handle (HWND)
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def is_supported(self) -> bool:
        """Check if this blur effect is supported on the current system"""
        pass


class CustomBlurEffect(BaseBlurEffect):
    """
    Legacy blur effect using SetWindowCompositionAttribute.
    Works on Windows 10 and 11, but uses older undocumented API.
    """
    
    def is_supported(self) -> bool:
        """Supported on Windows only"""
        return os.name == 'nt'
    
    def apply(self, hwnd: int) -> bool:
        """Apply blur using SetWindowCompositionAttribute"""
        if not self.is_supported():
            print("[CustomBlurEffect] Not supported on this OS")
            return False
        
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
            
            ACCENT_ENABLE_BLURBEHIND = 3
            
            accent = ACCENT_POLICY()
            accent.AccentState = ACCENT_ENABLE_BLURBEHIND
            accent.GradientColor = 0
            
            data = WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = 19
            data.Data = ctypes.cast(byref(accent), ctypes.c_void_p)
            data.SizeOfData = sizeof(accent)
            
            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, byref(data))
            print("[CustomBlurEffect] Blur enabled")
            return True
            
        except Exception as e:
            print(f"[CustomBlurEffect] Failed to enable blur: {e}")
            return False


class NativeWindowsBlurEffect(BaseBlurEffect):
    """
    Native Windows blur effect using DwmSetWindowAttribute.
    
    - Windows 11 (Build 22000+): Uses Mica or Acrylic backdrop
    - Windows 10: Falls back to CustomBlurEffect
    
    Also enables rounded corners on Windows 11.
    """
    
    # DwmSetWindowAttribute attributes
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    
    # Backdrop types
    DWMSBT_AUTO = 0
    DWMSBT_NONE = 1
    DWMSBT_MAINWINDOW = 2  # Mica
    DWMSBT_TRANSIENTWINDOW = 3  # Acrylic
    DWMSBT_TABBEDWINDOW = 4  # Mica Alt
    
    # Corner preferences
    DWMWCP_DEFAULT = 0
    DWMWCP_DONOTROUND = 1
    DWMWCP_ROUND = 2
    DWMWCP_ROUNDSMALL = 3
    
    def __init__(self, use_mica: bool = True, enable_rounded_corners: bool = True):
        """
        Initialize native Windows blur effect.
        
        Args:
            use_mica: If True, use Mica effect (Win11). If False, use Acrylic.
            enable_rounded_corners: If True, enable rounded corners on Win11.
        """
        self.use_mica = use_mica
        self.enable_rounded_corners = enable_rounded_corners
        self._fallback = CustomBlurEffect()
        self._is_win11 = self._check_windows_11()
    
    def _check_windows_11(self) -> bool:
        """Check if running on Windows 11 (Build 22000+)"""
        if os.name != 'nt':
            return False
        
        try:
            version = sys.getwindowsversion()
            # Windows 11 is version 10.0 with build >= 22000
            if version.major == 10 and version.build >= 22000:
                return True
        except Exception as e:
            print(f"[NativeWindowsBlurEffect] Could not detect Windows version: {e}")
        
        return False
    
    def is_supported(self) -> bool:
        """Supported on Windows (uses fallback on Win10)"""
        return os.name == 'nt'
    
    def apply(self, hwnd: int) -> bool:
        """Apply native blur effect"""
        if not self.is_supported():
            print("[NativeWindowsBlurEffect] Not supported on this OS")
            return False
        
        # Use fallback on Windows 10
        if not self._is_win11:
            print("[NativeWindowsBlurEffect] Windows 10 detected, using fallback")
            return self._fallback.apply(hwnd)
        
        # Apply Windows 11 native effects
        success = True
        
        # Apply backdrop (Mica or Acrylic)
        backdrop_type = self.DWMSBT_MAINWINDOW if self.use_mica else self.DWMSBT_TRANSIENTWINDOW
        if not self._set_backdrop(hwnd, backdrop_type):
            success = False
        
        # Apply rounded corners
        if self.enable_rounded_corners:
            if not self._set_rounded_corners(hwnd):
                success = False
        
        return success
    
    def _set_backdrop(self, hwnd: int, backdrop_type: int) -> bool:
        """Set the system backdrop type (Mica/Acrylic)"""
        try:
            dwmapi = ctypes.windll.dwmapi
            backdrop_value = c_int(backdrop_type)
            
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                self.DWMWA_SYSTEMBACKDROP_TYPE,
                byref(backdrop_value),
                sizeof(backdrop_value)
            )
            
            if result == 0:  # S_OK
                effect_name = "Mica" if backdrop_type == self.DWMSBT_MAINWINDOW else "Acrylic"
                print(f"[NativeWindowsBlurEffect] {effect_name} backdrop enabled")
                return True
            else:
                print(f"[NativeWindowsBlurEffect] Failed to set backdrop, HRESULT: {result}")
                return False
                
        except Exception as e:
            print(f"[NativeWindowsBlurEffect] Failed to set backdrop: {e}")
            return False
    
    def _set_rounded_corners(self, hwnd: int) -> bool:
        """Enable rounded corners on Windows 11"""
        try:
            dwmapi = ctypes.windll.dwmapi
            corner_preference = c_int(self.DWMWCP_ROUND)
            
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                self.DWMWA_WINDOW_CORNER_PREFERENCE,
                byref(corner_preference),
                sizeof(corner_preference)
            )
            
            if result == 0:  # S_OK
                print("[NativeWindowsBlurEffect] Rounded corners enabled")
                return True
            else:
                print(f"[NativeWindowsBlurEffect] Failed to set rounded corners, HRESULT: {result}")
                return False
                
        except Exception as e:
            print(f"[NativeWindowsBlurEffect] Failed to set rounded corners: {e}")
            return False
