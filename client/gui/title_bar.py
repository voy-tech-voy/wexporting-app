"""
Title Bar Window - Separate OS window for blur effect
Visually docks above the main window, enables blur only on this small area.
"""

import os

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QLabel, QPushButton, QFrame, QMenu, QApplication
)
from PySide6.QtGui import QIcon, QMouseEvent, QAction, QFont, QPainter, QPen, QColor
from PySide6.QtCore import Qt, Signal, QPoint, QSize, QRect

from client.utils.font_manager import AppFonts, FONT_FAMILY_APP_NAME, FONT_FAMILY
from client.utils.resource_path import get_app_icon_path, get_resource_path
from client.version import APP_NAME
from client.gui.theme import Theme
from client.gui.effects.blur_effects import NativeWindowsBlurEffect


class ClickableLabel(QLabel):
    """Custom label that emits a signal when clicked"""
    clicked = Signal()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Emit signal when label is clicked"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)



class MaxRestoreButton(QPushButton):
    """Custom-painted maximize / restore button with controlled stroke width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_expanded = False
        self._icon_color = QColor("#cccccc")
        self._icon_hover_color = QColor("#ffffff")
        # Same fixed size as the other title-bar buttons
        self.setFixedSize(45, 35)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_expanded(self, expanded: bool):
        self._is_expanded = expanded
        self.update()  # trigger repaint

    def set_icon_color(self, color: QColor, hover_color: QColor = None):
        self._icon_color = color
        if hover_color:
            self._icon_hover_color = hover_color
        self.update()

    def paintEvent(self, event):
        """Draw a filled rect (background/hover) then the icon on top."""
        super().paintEvent(event)  # draws the button bg / hover state from stylesheet

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # crisp pixel lines

        active_color = self._icon_hover_color if self.underMouse() else self._icon_color
        pen = QPen(active_color)
        pen.setWidth(1)  # line thickness – change freely
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        w, h = self.width(), self.height()
        icon_w, icon_h = 16, 12  # 4:3 ratio
        cx, cy = w // 2, h // 2

        if not self._is_expanded:
            # Maximise: single outlined rect, centred
            x = cx - icon_w // 2
            y = cy - icon_h // 2
            painter.drawRect(x, y, icon_w, icon_h)
        else:
            # Restore: two smaller overlapping rects
            sm_w, sm_h = 12, 9
            # The bounding box of the pair is 15x12
            # Offset by 3 pixels to overlap
            offset = 3
            
            # Front rect (bottom-left area of bounding box)
            fx = cx - 7
            fy = cy - 3
            
            # Back rect (top-right area of bounding box)
            bx = cx - 4
            by = cy - 6
            
            # Draw back rect using lines to avoid erasing operations (clean transparency)
            painter.drawLine(bx, by, bx + sm_w, by)  # Top line
            painter.drawLine(bx + sm_w, by, bx + sm_w, by + sm_h)  # Right line
            painter.drawLine(fx + sm_w, by + sm_h, bx + sm_w, by + sm_h)  # Bottom line (partial)
            painter.drawLine(bx, by, bx, fy)  # Left line (partial)
            
            # Draw front rect normally
            painter.drawRect(fx, fy, sm_w, sm_h)

        painter.end()


class TitleBarWindow(QMainWindow):
    """
    Separate OS window for the title bar with blur effect.
    Attaches to a main window and follows its position.
    """
    
    # Signals to communicate with main window
    minimize_requested = Signal()
    close_requested = Signal()
    theme_toggle_requested = Signal()
    show_advanced_requested = Signal()
    show_about_requested = Signal()
    check_updates_requested = Signal()
    buy_credits_requested = Signal()
    expand_requested = Signal()
    restore_to_init_requested = Signal()

    logout_requested = Signal()
    
    TITLE_BAR_HEIGHT = 45
    
    def __init__(self, parent=None, is_dev_mode=False):
        # Pass parent to QMainWindow for proper z-order grouping
        super().__init__(parent)

        self.is_dev_mode = is_dev_mode
        self._main_window = None
        self._drag_position = None
        self._last_drag_pos = None
        self._is_dark_theme = True
        self._is_expanded = False
        self._last_screen_available_geom = None
        
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
        self._theme_btn.setMinimumSize(45, 35)
        self._theme_btn.setMaximumSize(45, 35)
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

        # Maximize/Restore button (custom-painted)
        self._maxrestore_btn = MaxRestoreButton()
        self._maxrestore_btn.clicked.connect(self._on_maxrestore_clicked)
        layout.addWidget(self._maxrestore_btn)

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
        
        check_updates_action = QAction("Check for Updates", self)
        check_updates_action.triggered.connect(self.check_updates_requested.emit)
        self._menu.addAction(check_updates_action)
        
        buy_action = QAction("Buy...", self)
        buy_action.triggered.connect(self.buy_credits_requested.emit)
        self._menu.addAction(buy_action)
        
        self._menu.addSeparator()
        
        
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
        if self.windowHandle():
            try:
                self.windowHandle().screenChanged.disconnect(self._on_screen_changed)
            except Exception:
                pass
            self.windowHandle().screenChanged.connect(self._on_screen_changed)
            
            screen = self.windowHandle().screen()
            if screen:
                self._last_screen_available_geom = screen.availableGeometry()

    def _on_screen_changed(self, screen):
        """Re-apply blur and re-sync when title bar moves to a new screen"""
        if not screen:
            return
            
        from PySide6.QtGui import QCursor
        new_avail_geom = screen.availableGeometry()
        
        if self._main_window and getattr(self, '_last_screen_available_geom', None):
            old_geom = self._last_screen_available_geom
            
            # Compute ratio against the previous screen
            if old_geom.width() > 0 and old_geom.height() > 0:
                old_w = self._main_window.width()
                old_h = self._main_window.height()
                
                w_ratio = old_w / float(old_geom.width())
                h_ratio = old_h / float(old_geom.height())
                
                # Apply ratio to new screen geometry
                new_w = int(new_avail_geom.width() * w_ratio)
                new_h = int(new_avail_geom.height() * h_ratio)
                
                # Apply min/max constraints
                new_w = max(self._main_window.minimumWidth(), min(new_w, new_avail_geom.width() - 40))
                # Allow height to be up to 95% of the screen height
                new_h = max(self._main_window.minimumHeight(), min(new_h, int(new_avail_geom.height() * 0.95)))
                
                actual_w_ratio = new_w / float(old_w) if old_w > 0 else 1.0
                actual_h_ratio = new_h / float(old_h) if old_h > 0 else 1.0
                
                self._main_window.resize(new_w, new_h)
                
                # Re-align mouse drag anchor to prevent jumping
                if self._drag_position is not None:
                    # Update local drag offset relative to the new window size
                    self._drag_position.setX(int(self._drag_position.x() * actual_w_ratio))
                    self._drag_position.setY(int(self._drag_position.y() * actual_h_ratio))
                    
                    cursor_pos = QCursor.pos()
                    
                    # Ensure the window is placed exactly under the mouse pointer
                    expected_x = cursor_pos.x() - self._drag_position.x()
                    expected_y = cursor_pos.y() - self._drag_position.y()
                    
                    # Hard constraints: don't let it go completely outside the new screen
                    min_x = new_avail_geom.left() - new_w + 100
                    max_x = new_avail_geom.right() - 100
                    min_y = new_avail_geom.top()
                    max_y = new_avail_geom.bottom() - 50
                    
                    expected_x = max(min_x, min(expected_x, max_x))
                    expected_y = max(min_y, min(expected_y, max_y))
                    
                    self._main_window.move(expected_x, expected_y)
                    self._last_drag_pos = cursor_pos
                
        self._last_screen_available_geom = new_avail_geom

        self.enable_blur()
        self._sync_position()
        self._sync_width()
        
    def _get_tinted_icon(self, icon_path, color):
        """Helper to tint SVG icon with specific color"""
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtGui import QPainter, QPixmap, QColor
        from PySide6.QtCore import QSize
        
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
        
        icon_normal = "#aaaaaa" if is_dark else "#666666"
        icon_hover = "#ffffff" if is_dark else "#000000"

        # Button styles
        button_style = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {icon_normal};
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
                color: {icon_hover};
            }}
        """
        
        self._minimize_btn.setStyleSheet(button_style)
        self._maxrestore_btn.setStyleSheet(button_style)
        self._maxrestore_btn.set_icon_color(QColor(icon_normal), hover_color=QColor(icon_hover))
        
        self._close_btn.setStyleSheet(button_style + f"""
            QPushButton:hover {{
                background-color: {Theme.error()};
                color: white;
            }}
        """)
        
        self._theme_btn.setStyleSheet(button_style)
        
        # Update theme button icon with tint (needs normal and hover states for SVG)
        if hasattr(self, '_sun_moon_svg_path'):
            normal_pix = self._get_tinted_icon(self._sun_moon_svg_path, QColor(icon_normal))
            hover_pix = self._get_tinted_icon(self._sun_moon_svg_path, QColor(icon_hover))
            
            # The user requested .75 size of 24x21, which is 18x16
            icon = QIcon()
            icon.addPixmap(normal_pix.pixmap(18, 16), QIcon.Mode.Normal, QIcon.State.Off)
            
            self._theme_normal_pix = normal_pix
            self._theme_hover_pix = hover_pix
            self._theme_btn.setIcon(normal_pix)
            self._theme_btn.setIconSize(QSize(18, 16))
            
            # Add dynamic hover swapping
            if not hasattr(self._theme_btn, '_original_enterEvent'):
                self._theme_btn._original_enterEvent = self._theme_btn.enterEvent
                self._theme_btn._original_leaveEvent = self._theme_btn.leaveEvent
                
                def on_enter(e):
                    self._theme_btn.setIcon(self._theme_hover_pix)
                    self._theme_btn._original_enterEvent(e)
                def on_leave(e):
                    self._theme_btn.setIcon(self._theme_normal_pix)
                    self._theme_btn._original_leaveEvent(e)
                    
                self._theme_btn.enterEvent = on_enter
                self._theme_btn.leaveEvent = on_leave
    
    def apply_theme(self, is_dark: bool):
        """Public method to apply theme"""
        self._apply_theme(is_dark)
    
    # --- Mouse events for dragging the MAIN window ---
    
    def _on_maxrestore_clicked(self):
        if self._is_expanded:
            self.restore_to_init_requested.emit()
        else:
            self.expand_requested.emit()

    def set_expanded_state(self, expanded: bool):
        self._is_expanded = expanded
        self._maxrestore_btn.set_expanded(expanded)

    def mousePressEvent(self, event: QMouseEvent):
        """Start dragging and raise the main window"""
        if event.button() == Qt.MouseButton.LeftButton and self._main_window:
            # Raise both windows to bring app to front
            self.raise_with_main_window()
            self._drag_position = event.globalPosition().toPoint() - self._main_window.frameGeometry().topLeft()
            self._last_drag_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Move both windows when dragging and emulate Windows Snap when hitting edges"""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_position is not None and self._main_window:
            # --- Custom Emulated Windows Snap Logic ---
            screen = QApplication.screenAt(event.globalPosition().toPoint())
            if screen:
                screen_geom = screen.availableGeometry()
                mouse_pos = event.globalPosition().toPoint()

                # Check for screen edges (5px threshold)
                snap_threshold = 5

                is_top_edge = mouse_pos.y() <= screen_geom.top() + snap_threshold
                is_left_edge = mouse_pos.x() <= screen_geom.left() + snap_threshold
                is_right_edge = mouse_pos.x() >= screen_geom.right() - snap_threshold

                # We need to account for the title bar height so it doesn't get pushed off screen
                tb_h = self.TITLE_BAR_HEIGHT

                # A snapped window needs to start LOWER by tb_h, and be SHORTER by tb_h
                snap_top = screen_geom.top() + tb_h
                snap_height = screen_geom.height() - tb_h

                snapped = False

                if is_top_edge:
                    # Snap Maximize
                    self._main_window.setGeometry(screen_geom.left(), snap_top, screen_geom.width(), snap_height)
                    snapped = True
                elif is_left_edge:
                    # Snap Left Half
                    half_width = screen_geom.width() // 2
                    self._main_window.setGeometry(screen_geom.left(), snap_top, half_width, snap_height)
                    snapped = True
                elif is_right_edge:
                    # Snap Right Half
                    half_width = screen_geom.width() // 2
                    self._main_window.setGeometry(screen_geom.left() + half_width, snap_top, half_width, snap_height)
                    snapped = True

                if snapped:
                    self._sync_position()
                    self._sync_width()
                    self.set_expanded_state(True)

                    # Fix: User reported persistent resize pointer
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                    if self._main_window:
                        self._main_window.setCursor(Qt.CursorShape.ArrowCursor)

                    return

            # Delta-based move — immune to DPI coordinate shifts across monitors
            current_pos = event.globalPosition().toPoint()
            delta = current_pos - self._last_drag_pos
            self._last_drag_pos = current_pos
            
            new_pos = self._main_window.pos() + delta
            
            # Constrain window to prevent losing it completely out of bounds
            if screen:
                geom = screen.availableGeometry()
                w = self._main_window.width()
                min_x = geom.left() - w + 100
                max_x = geom.right() - 100
                min_y = geom.top() - 20
                max_y = geom.bottom() - 50
                
                new_x = max(min_x, min(new_pos.x(), max_x))
                new_y = max(min_y, min(new_pos.y(), max_y))
                new_pos.setX(new_x)
                new_pos.setY(new_y)
                
            self._main_window.move(new_pos)
            self._sync_position()
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """End dragging"""
        self._drag_position = None
        
        # Ensure cursor resets completely on release
        self.unsetCursor()
        if self._main_window:
            self._main_window.unsetCursor()
            
        super().mouseReleaseEvent(event)
