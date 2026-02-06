"""
Theme Variables for the Application
Based on Design Spec v4.0 - Premium Industrial (Tesla Dark Mode / Apple Ceramic)
"""

# ============================================
# DARK MODE (Default) - Deepest Void
# ============================================
DARK_THEME = {
    # Backgrounds
    "app_bg": "#1B1B1B",           # Deepest Void (Window Background)
    "surface_main": "#232323",     # Drop Zone / Panels (brighter for better visibility)
    "surface_element": "#2D2D2D",  # Buttons / Inputs (lighter for clear interactivity)
    "surface_drop_area": "#212121", # Drop area file item background
    "surface_hover": "#333333",    # Hover state for surfaces
    "surface_pressed": "#282828",  # Pressed state
    "input_bg": "#1a1a1a",         # Text input background
    "translucent_bg": "rgba(28, 28, 28, 0.7)",  # Translucent background for title bar with blur
    "presets_bg": "rgba(11, 11, 11, 0.9)",  # Preset gallery overlay background
    
    # Borders
    "border_dim": "#333333",       # Subtle Separation
    "border_focus": "#555555",     # Hover/Focus State
    
    # Text
    "text_primary": "#F5F5F7",     # Main Readability
    "text_secondary": "#86868B",   # Labels / Meta Data
    
    # Accents
    "accent_primary": "#FFFFFF",   # Standard Action
    "accent_turbo": "#00E0FF",     # GPU Active (Electric Cyan)
    "accent_success": "#30D158",   # Success State
    
    # Status Colors
    "error": "#FF3B30",            # Error/Danger (iOS Red)
    "warning": "#FF9500",          # Warning (iOS Orange)
    "info": "#007AFF",             # Info (iOS Blue)
    
    # Scrollbar
    "scrollbar_bg": "#1a1a1a",     # Scrollbar track
    "scrollbar_thumb": "#404040",  # Scrollbar handle
    
    # Other
    "tooltip_bg": "#333333",       # Tooltip Background
    
    # Header Button Colors
    "btn_preset_active": "#00AA00",      # Preset button active (green)
    "btn_preset_ghost": "#1B1B1B",  # Preset button inactive
    "btn_lab_solid": "#2196F3",          # Lab button solid state (blue)
    "btn_lab_ghost": "#1B1B1B",  # Lab button inactive
    "btn_file_normal": "#A1A1A1",        # File button normal (grey)
    "btn_file_hover": "#FFFFFF",         # File button hover (white)
    
    # Preset Gallery Colors
    "gallery_overlay_color": "#141414",      # Gallery blur overlay base color
    "gallery_overlay_alpha": "180",          # Gallery overlay transparency (0-255)
    "gallery_filter_bg": "#232323",          # Filter bar background
    "gallery_filter_overlay": "#000000",     # Filter bar overlay tint
    "gallery_filter_overlay_alpha": "180",   # Filter bar overlay alpha
    "gallery_param_bg": "#1F1F1F",            # Parameter form input background
    "gallery_param_panel_bg": "#232323",      # Parameter panel window background
    "gallery_filter_blur_radius": "7",        # Filter bar blur radius (0-20)
    "gallery_filter_blur_scale": "2",         # Filter bar downscale factor (1-8)
    # Filter Gradient Mask
    "gallery_filter_mask_top_alpha": "255",   # Filter mask top alpha (Opaque)
    "gallery_filter_mask_bottom_alpha": "0",  # Filter mask bottom alpha (Transparent)
    "gallery_filter_debug_mask": "0",         # Show mask for debugging (0=Off, 1=On)
    # Filter Button Colors
    "gallery_filter_btn_active_bg": "#30D158",     # Active button background (green)
    "gallery_filter_btn_active_text": "#FFFFFF",   # Active button text
    "gallery_filter_btn_inactive_bg": "#2D2D2D",   # Inactive button background
    "gallery_filter_btn_inactive_text": "#86868B", # Inactive button text
    "gallery_filter_btn_border": "#333333",        # Button border color
    
    # Title Bar Button Colors
    "titlebar_btn_bg": "#2D2D2D",             # Title bar button background
    "titlebar_btn_hover": "#3D3D3D",          # Title bar button hover
}

# ============================================
# LIGHT MODE - Apple Ceramic
# ============================================
LIGHT_THEME = {
    # Backgrounds
    "app_bg": "#D2D2D4",           # Light background
    "surface_main": "#DEDEE2",     # Drop Zone / Panels
    "surface_element": "#EEEEF3",  # Buttons / Inputs
    "surface_drop_area": "#D2D2D4", # Drop area file item background
    "surface_hover": "#E0E0E5",    # Hover state for surfaces
    "surface_pressed": "#D8D8DD",  # Pressed state
    "input_bg": "#FFFFFF",         # Text input background
    "translucent_bg": "rgba(232, 232, 232, 0.6)",  # Translucent background for title bar with blur
    "presets_bg": "rgba(245, 245, 247, 0.9)",  # Preset gallery overlay background
    
    # Borders
    "border_dim": "#C4C4C6",       # Subtle Separation
    "border_focus": "#8E8E93",     # Hover/Focus State
    
    # Text
    "text_primary": "#000000",     # Main Readability
    "text_secondary": "#6C6C70",   # Labels / Meta Data
    
    # Accents
    "accent_primary": "#000000",   # Standard Action
    "accent_turbo": "#007AFF",     # GPU Active (Blue for light mode)
    "accent_success": "#30D158",   # Success State
    
    # Status Colors
    "error": "#FF3B30",            # Error/Danger (iOS Red)
    "warning": "#FF9500",          # Warning (iOS Orange)
    "info": "#007AFF",             # Info (iOS Blue)
    
    # Scrollbar
    "scrollbar_bg": "#E8E8ED",     # Scrollbar track
    "scrollbar_thumb": "#C0C0C5",  # Scrollbar handle
    
    # Other
    "tooltip_bg": "#E8E8ED",       # Tooltip Background
    
    # Header Button Colors
    "btn_preset_active": "#00AA00",      # Preset button active (green)
    "btn_preset_ghost": "#D8D8DA",  # Preset button inactive (darker for light mode)
    "btn_lab_solid": "#2196F3",          # Lab button solid state (blue)
    "btn_lab_ghost": "#D7D7D9",  # Lab button inactive
    "btn_file_normal": "#59595A",        # File button normal (dark grey)
    "btn_file_hover": "#000000",         # File button hover (black)
    
    # Preset Gallery Colors
    "gallery_overlay_color": "#D2D2D4",      # Gallery blur overlay base color (light)
    "gallery_overlay_alpha": "255",          # Gallery overlay transparency (0-255)
    "gallery_filter_bg": "#9E9EA0",          # Filter bar background (light)
    "gallery_filter_overlay": "#D2D2D4",     # Filter bar overlay tint (light)
    "gallery_filter_overlay_alpha": "255",   # Filter bar overlay alpha
    "gallery_param_bg": "#F8F8FA",            # Parameter form input background (light)
    "gallery_param_panel_bg": "#DEDEE2",      # Parameter panel window background (light)
    "gallery_filter_blur_radius": "10",        # Filter bar blur radius (0-20)
    "gallery_filter_blur_scale": "1",         # Filter bar downscale factor (1-8)
    # Filter Gradient Mask
    "gallery_filter_mask_top_alpha": "255",   # Filter mask top alpha (Opaque)
    "gallery_filter_mask_bottom_alpha": "0",  # Filter mask bottom alpha (Transparent)
    "gallery_filter_debug_mask": "0",         # Show mask for debugging (0=Off, 1=On)
    # Filter Button Colors
    "gallery_filter_btn_active_bg": "#30D158",     # Active button background (green)
    "gallery_filter_btn_active_text": "#FFFFFF",   # Active button text
    "gallery_filter_btn_inactive_bg": "#DEDEE2",   # Inactive button background (light)
    "gallery_filter_btn_inactive_text": "#6C6C70", # Inactive button text
    "gallery_filter_btn_border": "#C4C4C6",        # Button border color (light)
    
    # Title Bar Button Colors
    "titlebar_btn_bg": "#BEBEBE",             # Title bar button background (light)
    "titlebar_btn_hover": "#D8D8DD",          # Title bar button hover (light)
}


def get_theme(is_dark: bool = True) -> dict:
    """Get theme dictionary based on mode"""
    return DARK_THEME if is_dark else LIGHT_THEME


def get_color(key: str, is_dark: bool = True) -> str:
    """Get a specific color from the theme"""
    theme = get_theme(is_dark)
    return theme.get(key, "#FF00FF")  # Magenta fallback for missing keys

class ThemeVariables:
    """Wrapper class for theme access"""
    @staticmethod
    def get_theme(is_dark: bool = True) -> dict:
        return get_theme(is_dark)
        
    @staticmethod
    def get_color(key: str, is_dark: bool = True) -> str:
        return get_color(key, is_dark)
