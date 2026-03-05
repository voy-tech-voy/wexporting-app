"""
Centralized Font Configuration for ImgApp
Single source of truth for all fonts used in the application
"""

from PySide6.QtGui import QFont, QFontDatabase
from client.utils.resource_path import get_resource_path

# Global font settings - CHANGE THESE TO UPDATE FONTS EVERYWHERE
# Global font settings - CHANGE THESE TO UPDATE FONTS EVERYWHERE
FONT_FAMILY = "Lexend"  # Custom font family
FONT_FAMILY_APP_NAME = "Montserrat Alternates" # Special font for App Name
FONT_FAMILY_MONO = "Roboto Mono"  # For paths, logs, code
FONT_SIZE_BASE = 14  # Base font size for the application
FONT_SIZE_TITLE = 12  # Title bar fonts
FONT_SIZE_BUTTON = 16  # Button fonts

class AppFonts:
    """Centralized font definitions"""
    
    @staticmethod
    def init_fonts():
        """Load custom fonts from assets"""
        fonts = [
            "Lexend-Regular.ttf",
            "MontserratAlternates-Bold.ttf"
        ]
        for font_file in fonts:
            path = get_resource_path(f"client/assets/fonts/{font_file}")
            QFontDatabase.addApplicationFont(path)
    
    @staticmethod
    def get_base_font(bold=False):
        """Base application font (size 11)"""
        font = QFont(FONT_FAMILY, FONT_SIZE_BASE)
        if bold:
            font.setBold(True)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font
    
    @staticmethod
    def get_title_font(bold=True):
        """Title bar font (size 12)"""
        font = QFont(FONT_FAMILY, FONT_SIZE_TITLE)
        if bold:
            font.setBold(True)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font
    
    @staticmethod
    def get_button_font(bold=False):
        """Button font (size 16)"""
        font = QFont(FONT_FAMILY, FONT_SIZE_BUTTON)
        if bold:
            font.setBold(True)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font
    
    @staticmethod
    def get_custom_font(size=10, bold=False):
        """Custom font with specified size"""
        font = QFont(FONT_FAMILY, size)
        if bold:
            font.setBold(True)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font

    @staticmethod
    def get_app_name_font(size=None):
        """App Name font (Montserrat Alternates Bold)"""
        # Default size is slightly larger than standard title if not specified
        final_size = size if size else (FONT_SIZE_TITLE + 1)
        font = QFont(FONT_FAMILY_APP_NAME, final_size)
        font.setBold(True)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font


