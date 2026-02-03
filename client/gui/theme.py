"""
Master Design System - Single Source of Truth
All visual constants defined here.

Design Spec v4.0 - Premium Industrial (Tesla Dark Mode / Apple Ceramic)

Usage:
    from client.gui.theme import Theme
    
    # Colors
    bg = Theme.color("app_bg")
    text = Theme.text()
    
    # Fonts
    font = Theme.FONT_BODY
    
    # Metrics
    radius = Theme.RADIUS_MD
    spacing = Theme.SPACING_LG
"""

from client.utils.font_manager import (
    FONT_FAMILY, FONT_FAMILY_APP_NAME, FONT_FAMILY_MONO,
    FONT_SIZE_BASE, FONT_SIZE_TITLE, FONT_SIZE_BUTTON
)
from client.gui.theme_variables import DARK_THEME, LIGHT_THEME
from PyQt6.QtGui import QColor


class Theme:
    """
    Centralized design tokens for the application.
    
    This class provides a single source of truth for all visual constants
    including colors, fonts, spacing, and border radii.
    """
    
    # ============================================
    # COLOR PRIMITIVES & HELPERS
    # ============================================
    @classmethod
    def to_qcolor(cls, key: str) -> QColor:
        """
        Get a QColor object for the given theme key.
        Useful for custom painting in paintEvent().
        """
        hex_color = cls.color(key)
        return QColor(hex_color)

    @classmethod
    def color_with_alpha(cls, key: str, alpha: float) -> str:
        """
        Get an RGBA string for the given theme key with specified alpha (0.0 - 1.0).
        Useful for QSS stylesheets (e.g., 'rgba(255, 0, 0, 0.5)').
        """
        color = cls.to_qcolor(key)
        color.setAlphaF(max(0.0, min(1.0, alpha)))
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alphaF()})"
    
    # ============================================
    # FONTS (Single Source)
    # ============================================
    FONT_BODY = FONT_FAMILY              # "Lexend" - All UI text (buttons, labels, inputs)
    FONT_DISPLAY = FONT_FAMILY_APP_NAME  # "Montserrat Alternates" - App title only
    FONT_MONO = FONT_FAMILY_MONO         # "Roboto Mono" - Paths, logs, code
    
    # Font Sizes
    FONT_SIZE_XS = 10
    FONT_SIZE_SM = 11
    FONT_SIZE_BASE = FONT_SIZE_BASE      # 14
    FONT_SIZE_LG = FONT_SIZE_BUTTON      # 16
    FONT_SIZE_XL = 20
    FONT_SIZE_TITLE = FONT_SIZE_TITLE    # 12
    
    # ============================================
    # SPACING / METRICS (4px grid)
    # ============================================
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 12
    SPACING_LG = 16
    SPACING_XL = 24
    SPACING_XXL = 32
    
    # ============================================
    # BORDER RADII
    # ============================================
    RADIUS_XS = 2      # Tiny elements
    RADIUS_SM = 4      # Small elements (checkboxes, pills)
    RADIUS_MD = 8      # Standard (buttons, inputs)
    RADIUS_LG = 12     # Large containers (cards, panels)
    RADIUS_XL = 16     # Modals, overlays
    RADIUS_ROUND = 50  # Fully rounded (circular)
    
    # ============================================
    # ANIMATION DURATIONS (ms)
    # ============================================
    DURATION_FAST = 100
    DURATION_NORMAL = 200
    DURATION_SLOW = 300
    
    # ============================================
    # SHADOWS (for elevation)
    # ============================================
    SHADOW_SM = "0px 2px 4px rgba(0, 0, 0, 0.2)"
    SHADOW_MD = "0px 4px 8px rgba(0, 0, 0, 0.25)"
    SHADOW_LG = "0px 8px 16px rgba(0, 0, 0, 0.3)"
    
    # ============================================
    # STATE (Dark/Light mode)
    # ============================================
    _is_dark: bool = True
    
    @classmethod
    def set_dark_mode(cls, is_dark: bool):
        """Set the current theme mode."""
        cls._is_dark = is_dark
    
    @classmethod
    def is_dark(cls) -> bool:
        """Check if dark mode is active."""
        return cls._is_dark
    
    @classmethod
    def palette(cls) -> dict:
        """Get the full color palette for current mode."""
        return DARK_THEME if cls._is_dark else LIGHT_THEME
    
    @classmethod
    def color(cls, key: str) -> str:
        """
        Get color by key from current theme.
        
        Keys: app_bg, surface_main, surface_element, border_dim, border_focus,
              text_primary, text_secondary, accent_primary, accent_turbo, 
              accent_success, tooltip_bg, error, warning, info
        """
        return cls.palette().get(key, "#FF00FF")  # Magenta fallback
    
    # ============================================
    # CONVENIENCE COLOR ACCESSORS
    # ============================================
    @classmethod
    def bg(cls) -> str:
        """App background color (deepest)."""
        return cls.color("app_bg")
    
    @classmethod
    def surface(cls) -> str:
        """Main surface color (panels, drop zones)."""
        return cls.color("surface_main")
    
    @classmethod
    def surface_element(cls) -> str:
        """Element surface color (buttons, inputs)."""
        return cls.color("surface_element")

    @classmethod
    def param_bg(cls) -> str:
        """Background for parameter inputs (text, dropdowns, pills).
        Uses surface_element for clear contrast against panel backgrounds."""
        return cls.color("surface_element")
    
    @classmethod
    def translucent_bg(cls) -> str:
        """Translucent background for title bar with blur effect."""
        return cls.color("translucent_bg")
    
    @classmethod
    def surface_drop_area(cls) -> str:
        """Background for file items in drop area."""
        return cls.color("surface_drop_area")
    
    @classmethod
    def presets_bg(cls) -> str:
        """Background for preset gallery overlay."""
        return cls.color("presets_bg")
    
    @classmethod
    def text(cls) -> str:
        """Primary text color."""
        return cls.color("text_primary")
    
    @classmethod
    def text_muted(cls) -> str:
        """Secondary/muted text color."""
        return cls.color("text_secondary")
    
    @classmethod
    def accent(cls) -> str:
        """Primary accent color (white in dark, black in light)."""
        return cls.color("accent_primary")
    
    @classmethod
    def accent_turbo(cls) -> str:
        """GPU/Turbo accent color (cyan)."""
        return cls.color("accent_turbo")
    
    @classmethod
    def success(cls) -> str:
        """Success state color (green)."""
        return cls.color("accent_success")
    
    @classmethod
    def error(cls) -> str:
        """Error/danger color (red)."""
        return cls.color("error")
    
    @classmethod
    def warning(cls) -> str:
        """Warning color (orange)."""
        return cls.color("warning")
    
    @classmethod
    def border(cls) -> str:
        """Subtle border color."""
        return cls.color("border_dim")
    
    @classmethod
    def border_focus(cls) -> str:
        """Focus/hover border color."""
        return cls.color("border_focus")
    
    # ============================================
    # QSS HELPER METHODS
    # ============================================
    @classmethod
    def font_style(cls, font_type: str = "body", size: int = None, bold: bool = False) -> str:
        """
        Generate font QSS properties.
        
        Args:
            font_type: "body", "display", or "mono"
            size: Font size in pixels (uses default if None)
            bold: Whether text should be bold
        """
        fonts = {
            "body": cls.FONT_BODY,
            "display": cls.FONT_DISPLAY,
            "mono": cls.FONT_MONO
        }
        font_family = fonts.get(font_type, cls.FONT_BODY)
        font_size = size or cls.FONT_SIZE_BASE
        weight = "bold" if bold else "normal"
        
        return f"font-family: '{font_family}'; font-size: {font_size}px; font-weight: {weight};"
    
    @classmethod
    def button_style(cls, variant: str = "primary") -> str:
        """
        Generate button QSS for common variants.
        
        Args:
            variant: "primary", "secondary", "danger", "ghost"
        """
        if variant == "primary":
            return f"""
                background-color: {cls.accent()};
                color: {cls.bg()};
                border: none;
                border-radius: {cls.RADIUS_MD}px;
                font-family: '{cls.FONT_BODY}';
                font-size: {cls.FONT_SIZE_LG}px;
                font-weight: 700;
                padding: 8px 24px;
            """
        elif variant == "secondary":
            return f"""
                background-color: {cls.surface_element()};
                color: {cls.text()};
                border: 1px solid {cls.border()};
                border-radius: {cls.RADIUS_MD}px;
                font-family: '{cls.FONT_BODY}';
                font-size: {cls.FONT_SIZE_BASE}px;
                padding: 8px 16px;
            """
        elif variant == "danger":
            return f"""
                background-color: transparent;
                color: {cls.error()};
                border: 2px solid {cls.error()};
                border-radius: {cls.RADIUS_MD}px;
                font-family: '{cls.FONT_BODY}';
                font-size: {cls.FONT_SIZE_LG}px;
                font-weight: 700;
                padding: 8px 24px;
            """
        elif variant == "ghost":
            return f"""
                background-color: transparent;
                color: {cls.text_muted()};
                border: none;
                border-radius: {cls.RADIUS_SM}px;
                font-family: '{cls.FONT_BODY}';
                font-size: {cls.FONT_SIZE_BASE}px;
                padding: 4px 8px;
            """
        return ""
    
    @classmethod
    def input_style(cls) -> str:
        """Generate standard input field QSS."""
        return f"""
            background-color: {cls.param_bg()};
            color: {cls.text()};
            border: 1px solid {cls.border()};
            border-radius: {cls.RADIUS_SM}px;
            font-family: '{cls.FONT_BODY}';
            font-size: {cls.FONT_SIZE_BASE}px;
            padding: 6px 10px;
        """
    
    @classmethod
    def card_style(cls) -> str:
        """Generate card/panel container QSS."""
        return f"""
            background-color: {cls.surface()};
            border: 1px solid {cls.border()};
            border-radius: {cls.RADIUS_LG}px;
        """


# ============================================
# STANDALONE STYLE FUNCTIONS
# ============================================

def get_combobox_style(is_dark: bool) -> str:
    """Get QComboBox style that respects dark/light mode with chevron arrow.
    
    Args:
        is_dark: Whether dark mode is active
        
    Returns:
        QSS stylesheet string for QComboBox
    """
    Theme.set_dark_mode(is_dark) # Ensure theme state is correct
    
    bg_color = Theme.param_bg()
    text_color = Theme.text()
    border_color = Theme.border()
    dropdown_bg = bg_color  # Match main background
    arrow_color = Theme.text_muted()
    
    return (
        f"QComboBox {{ "
        f"background-color: {bg_color}; "
        f"color: {text_color}; "
        f"border: 1px solid {border_color}; "
        f"border-radius: 4px; "
        f"padding: 4px 25px 4px 8px; "
        f"}} "
        f"QComboBox:hover {{ border-color: #4CAF50; }} "
        f"QComboBox::drop-down {{ "
        f"subcontrol-origin: padding; "
        f"subcontrol-position: top right; "
        f"width: 20px; "
        f"border: none; "
        f"background-color: {dropdown_bg}; "
        f"}} "
        f"QComboBox::down-arrow {{ "
        f"image: none; "
        f"width: 0; "
        f"height: 0; "
        f"border-left: 5px solid transparent; "
        f"border-right: 5px solid transparent; "
        f"border-top: 6px solid {arrow_color}; "
        f"margin-right: 5px; "
        f"}} "
        f"QComboBox QAbstractItemView {{ "
        f"background-color: {bg_color}; "
        f"color: {text_color}; "
        f"selection-background-color: #4CAF50; "
        f"selection-color: white; "
        f"border: 1px solid {border_color}; "
        f"}}"
    )
