import ctypes
from ctypes import POINTER, Structure, c_int, byref, windll, sizeof, c_void_p
from ctypes.wintypes import DWORD, HWND
import sys

# DWM Constants
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38

# DWM_SYSTEMBACKDROP_TYPE Values
DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2      # Mica
DWMSBT_TRANSIENTWINDOW = 3 # Acrylic
DWMSBT_TABBEDWINDOW = 4    # Mica Alt

# DWM_WINDOW_CORNER_PREFERENCE Values
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3

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
        ("Data", c_void_p),
        ("SizeOfData", c_int)
    ]

class WindowEffects:
    """
    Apply Windows 11/10 Fluent Design effects (Mica, Acrylic, Rounded Corners).
    """

    @staticmethod
    def get_build_number():
        try:
            return sys.getwindowsversion().build
        except:
            return 0

    @staticmethod
    def apply_mica(hwnd: int, dark_mode: bool = True):
        """
        Apply Mica effect (Windows 11 only).
        Falls back to Acrylic on Windows 10.
        """
        build = WindowEffects.get_build_number()
        
        # Set Dark Mode preference first
        WindowEffects.set_dark_mode(hwnd, dark_mode)
        
        # Windows 11 (Build 22000+)
        if build >= 22000:
            try:
                # 38 = DWMWA_SYSTEMBACKDROP_TYPE
                value = c_int(DWMSBT_MAINWINDOW) # Mica
                windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 
                    DWMWA_SYSTEMBACKDROP_TYPE, 
                    byref(value), 
                    sizeof(value)
                )
            except Exception as e:
                print(f"Failed to set Mica: {e}")
        else:
            # Fallback to Acrylic for Windows 10
            WindowEffects.apply_acrylic(hwnd)

    @staticmethod
    def apply_acrylic(hwnd: int):
        """
        Apply Acrylic effect (Windows 10 style).
        """
        try:
            # Undocumented SetWindowCompositionAttribute
            ACCENT_ENABLE_BLURBEHIND = 3
            ACCENT_ENABLE_ACRYLICBLURBEHIND = 4 # Or 3?
            
            # Use basic blur for safety on older builds
            accent = ACCENT_POLICY()
            accent.AccentState = 3 # ENABLE_BLURBEHIND matches standard Win10 transparency
            accent.GradientColor = 0 # 0xAB000000 for acrylic tint?
            
            data = WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = 19 # WCA_ACCENT_POLICY
            data.Data = ctypes.cast(byref(accent), ctypes.c_void_p)
            data.SizeOfData = sizeof(accent)
            
            windll.user32.SetWindowCompositionAttribute(hwnd, byref(data))
        except Exception as e:
            print(f"Failed to set Acrylic: {e}")

    @staticmethod
    def set_rounded_corners(hwnd: int):
        """
        Enforce rounded corners (Windows 11).
        """
        build = WindowEffects.get_build_number()
        if build >= 22000:
            try:
                value = c_int(DWMWCP_ROUND)
                windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 
                    DWMWA_WINDOW_CORNER_PREFERENCE, 
                    byref(value), 
                    sizeof(value)
                )
            except Exception:
                pass

    @staticmethod
    def set_dark_mode(hwnd: int, is_dark: bool):
        """
        Inform DWM about dark mode preference for window frame/controls.
        """
        try:
            value = c_int(1 if is_dark else 0)
            windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 
                DWMWA_USE_IMMERSIVE_DARK_MODE, 
                byref(value), 
                sizeof(value)
            )
        except Exception:
            pass
    
    @staticmethod
    def remove_background(hwnd: int):
        """Clear background effect"""
        try:
            build = WindowEffects.get_build_number()
            if build >= 22000:
                 value = c_int(DWMSBT_NONE)
                 windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_SYSTEMBACKDROP_TYPE, byref(value), sizeof(value)
                )
            else:
                # Clear acrylic
                accent = ACCENT_POLICY()
                accent.AccentState = 0
                data = WINDOWCOMPOSITIONATTRIBDATA()
                data.Attribute = 19
                data.Data = ctypes.cast(byref(accent), ctypes.c_void_p)
                data.SizeOfData = sizeof(accent)
                windll.user32.SetWindowCompositionAttribute(hwnd, byref(data))
        except:
            pass
