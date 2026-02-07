"""
Title Bar Window - Separate OS window for blur effect
Visually docks above the main window, enables blur only on this small area.
"""

import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QLabel, QPushButton, QFrame, QMenu, QApplication
)
from PyQt6.QtGui import QIcon, QMouseEvent, QAction, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize

from client.utils.font_manager import AppFonts, FONT_FAMILY_APP_NAME, FONT_FAMILY
from client.utils.resource_path import get_app_icon_path, get_resource_path
from client.version import APP_NAME
from client.gui.theme import Theme
from client.gui.effects.blur_effects import NativeWindowsBlurEffect


class ClickableLabel(QLabel):
    """Custom label that emits a signal when clicked"""
    clicked = pyqtSignal()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Emit signal when label is clicked"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class TitleBarWindow(QMainWindow):
    """
    Separate OS window for the title bar with blur effect.
    Attaches to a main window and follows its position.
    """
    
    # Signals to communicate with main window
    minimize_requested = pyqtSignal()
    close_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()
    show_advanced_requested = pyqtSignal()
    show_about_requested = pyqtSignal()

    logout_requested = pyqtSignal()
    
    TITLE_BAR_HEIGHT = 45
    
    def __init__(self, parent=None, is_trial=False, is_dev_mode=False):
        # Pass parent to QMainWindow for proper z-order grouping
        super().__init__(parent)
        
        self.is_trial = is_trial
        self.is_dev_mode = is_dev_mode
        self._main_window = None
        self._drag_position = None
        self._is_dark_theme = True
        
        # Initialize native Windows blur effect (Mica on Win11, fallback on Win10)
        self._blur_effect = NativeWindowsBlurEffect(use_mica=True, enable_rounded_corners=True)
        
        # Window flags: Frameless, Tool (no taskbar), Translucent for blur
        # Setting parent ensures z-order follows main window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool  # Won't appear in taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setFixedHeight(self.TITLE_BAR_HEIGHT)
        self.setMouseTracking(True)
        
        self._setup_ui()
        self._apply_theme(is_dark=True)
    
    def attach_to(self, main_window: QMainWindow):
        """Attach this title bar to a main window for position syncing"""
        self._main_window = main_window
        self._sync_position()
        self._sync_width()
    
    def raise_with_main_window(self):
        """Raise both title bar and main window together to bring app to front."""
        if self._main_window:
            self._main_window.raise_()
            self._main_window.activateWindow()
        self.raise_()
    
    def _setup_ui(self):
        """Create the title bar UI"""
        central = QWidget()
        central.setMouseTracking(True)
        self.setCentralWidget(central)
        
        # Main container frame (for styling)
        self._frame = QFrame(central)
        self._frame.setObjectName("TitleBarFrame")
        self._frame.setMouseTracking(True)
        
        frame_layout = QHBoxLayout(central)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        frame_layout.addWidget(self._frame)
        
        # Title bar content layout
        layout = QHBoxLayout(self._frame)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # Logo
        try:
            icon_path = get_app_icon_path()
            if os.path.exists(icon_path):
                self._logo_label = ClickableLabel()
                icon = QIcon(icon_path)
                self._logo_label.setPixmap(icon.pixmap(32, 32))
                self._logo_label.setMaximumWidth(40)
                self._logo_label.setCursor(Qt.CursorShape.PointingHandCursor)
                self._logo_label.setStyleSheet("border: none; padding: 0px; margin: 0px; background: transparent;")
                self._logo_label.clicked.connect(self._show_menu)
                layout.addWidget(self._logo_label)
        except Exception as e:
            print(f"TitleBar: Could not load logo: {e}")
        
        # Title label
        from client.utils.font_manager import FONT_FAMILY
        title_text = f'<span style="font-family: \'{FONT_FAMILY_APP_NAME}\'; font-weight: bold;">{APP_NAME}</span>'
        
        if self.is_trial:
            title_text += f'&nbsp;&nbsp;<span style="font-family: \'{FONT_FAMILY}\'; font-weight: normal; font-size: 10pt;">[ TRIAL ]</span>'
        if self.is_dev_mode:
            title_text += f'&nbsp;&nbsp;<span style="font-family: \'{FONT_FAMILY}\'; font-weight: normal; font-size: 10pt;">[ DEV ]</span>'
        
        self._title_label = ClickableLabel(title_text)
        self._title_label.setTextFormat(Qt.TextFormat.RichText)
        self._title_label.setFont(AppFonts.get_app_name_font())
        self._title_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title_label.clicked.connect(self._show_menu)
        layout.addWidget(self._title_label)
        
        # Spacer
        layout.addStretch()
        
        # Theme toggle button
        self._theme_btn = QPushButton()
        self._theme_btn.setMinimumSize(40, 35)
        self._theme_btn.setMaximumSize(40, 35)
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.clicked.connect(self.theme_toggle_requested.emit)
        try:
            svg_path = get_resource_path('client/assets/icons/sun-moon.svg')
            if os.path.exists(svg_path):
                self._sun_moon_svg_path = svg_path
                self._theme_btn.setIcon(QIcon(svg_path))
                self._theme_btn.setIconSize(QSize(24, 21))
        except Exception as e:
            self._theme_btn.setText("◐")
        layout.addWidget(self._theme_btn)
        
        # Minimize button
        self._minimize_btn = QPushButton("—")
        self._minimize_btn.setMinimumSize(45, 35)
        self._minimize_btn.setMaximumSize(45, 35)
        self._minimize_btn.setFont(AppFonts.get_button_font())
        self._minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._minimize_btn.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self._minimize_btn)
        
        layout.addSpacing(10)
        
        # Close button
        self._close_btn = QPushButton("✕")
        self._close_btn.setMinimumSize(45, 35)
        self._close_btn.setMaximumSize(45, 35)
        self._close_btn.setFont(AppFonts.get_button_font())
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(self._close_btn)
        
        # Dropdown menu
        self._menu = QMenu(self)
        
        advanced_action = QAction("Advanced", self)
        advanced_action.triggered.connect(self.show_advanced_requested.emit)
        self._menu.addAction(advanced_action)
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_requested.emit)
        self._menu.addAction(about_action)
        

        
        self._menu.addSeparator()
        
        logout_action = QAction("Log Out", self)
        logout_action.triggered.connect(self.logout_requested.emit)
        self._menu.addAction(logout_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close_requested.emit)
        self._menu.addAction(exit_action)
    
    def _show_menu(self):
        """Show the dropdown menu"""
        menu_pos = self.mapToGlobal(QPoint(10, self.TITLE_BAR_HEIGHT))
        self._menu.popup(menu_pos)
    
    def _sync_position(self):
        """Sync position to be directly above the main window"""
        if self._main_window:
            main_pos = self._main_window.pos()
            # Position title bar above main window with 1px overlap to prevent gaps
            # The overlap ensures no visible gap due to rounding or DPI scaling
            self.move(main_pos.x(), main_pos.y() - self.TITLE_BAR_HEIGHT + 1)
    
    def _sync_width(self):
        """Sync width to match main window"""
        if self._main_window:
            self.setFixedWidth(self._main_window.width())
    
    def enable_blur(self):
        """Enable Windows Blur effect on this window using the blur effect system"""
        hwnd = int(self.winId())
        self._blur_effect.apply(hwnd)
    
    def showEvent(self, event):
        """Enable blur when shown"""
        super().showEvent(event)
        self.enable_blur()
        
    def _get_tinted_icon(self, icon_path, color):
        """Helper to tint SVG icon with specific color"""
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtGui import QPainter, QPixmap, QColor
        from PyQt6.QtCore import QSize
        
        renderer = QSvgRenderer(icon_path)
        pixmap = QPixmap(QSize(24, 24))
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), color)
        painter.end()
        
        return QIcon(pixmap)
        
    def _apply_theme(self, is_dark: bool):
        """Apply theme styling using centralized Theme class"""
        self._is_dark_theme = is_dark
        Theme.set_dark_mode(is_dark)
        
        # Use translucent_bg for title bar background (for blur effect)
        bg_color = Theme.translucent_bg()
        
        text_color = Theme.text()
        
        # Use dedicated title bar button colors
        from client.gui.theme_variables import get_color
        from client.gui.theme_manager import ThemeManager
        is_dark = ThemeManager.instance().is_dark_mode()
        
        btn_bg = get_color("titlebar_btn_bg", is_dark)
        btn_hover = get_color("titlebar_btn_hover", is_dark)
        border_color = Theme.border()
        
        # Frame style (rounded top corners, translucent bg for blur)
        self._frame.setStyleSheet(f"""
            QFrame#TitleBarFrame {{
                background-color: {bg_color};
                border-bottom: 1px solid {border_color};
                border-top-left-radius: {Theme.RADIUS_LG}px;
                border-top-right-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        
        # Title label
        self._title_label.setStyleSheet(f"color: {text_color}; border: none; padding: 0px; margin: 0px; background: transparent;")
        
        # Button styles
        button_style = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text_color};
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
        """
        
        self._minimize_btn.setStyleSheet(button_style)
        self._close_btn.setStyleSheet(button_style + f"""
            QPushButton:hover {{
                background-color: {Theme.error()};
                color: white;
            }}
        """)
        self._theme_btn.setStyleSheet(button_style)
        
        # Update theme button icon with tint
        if hasattr(self, '_sun_moon_svg_path'):
            from PyQt6.QtGui import QColor
            icon_color = QColor(Theme.text()) # Use theme text color for icon
            self._theme_btn.setIcon(self._get_tinted_icon(self._sun_moon_svg_path, icon_color))
    
    def apply_theme(self, is_dark: bool):
        """Public method to apply theme"""
        self._apply_theme(is_dark)
    
    # --- Mouse events for dragging the MAIN window ---
    
    def mousePressEvent(self, event: QMouseEvent):
        """Start dragging and raise the main window"""
        if event.button() == Qt.MouseButton.LeftButton and self._main_window:
            # Raise both windows to bring app to front
            self.raise_with_main_window()
            self._drag_position = event.globalPosition().toPoint() - self._main_window.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Move both windows when dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_position is not None and self._main_window:
            new_pos = event.globalPosition().toPoint() - self._drag_position
            self._main_window.move(new_pos)
            self._sync_position()
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """End dragging"""
        self._drag_position = None
        super().mouseReleaseEvent(event)
