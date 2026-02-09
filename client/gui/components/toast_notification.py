"""
Toast Notification Component

A reusable, non-blocking notification widget that appears in the upper left corner.
Styled to match the app's design language with auto-dismiss functionality.
"""
from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout, QGraphicsOpacityEffect, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QEvent, QPoint
from PyQt6.QtGui import QPixmap, QColor
from client.gui.theme import Theme
from pathlib import Path


class ToastNotification(QFrame):
    """
    Toast notification widget that appears in the upper left corner.
    
    Features:
    - Auto-dismiss after specified duration
    - Slide-in and fade-out animations
    - Theme-aware styling
    - Icon support (warning, error, info)
    """
    
    dismissed = pyqtSignal()
    
    def __init__(self, message: str, icon_type: str = "warning", duration: int = 4000, parent=None, position: str = "top-left"):
        """
        Initialize toast notification.
        
        Args:
            message: Text to display
            icon_type: Type of icon ("warning", "error", "info")
            duration: Time in milliseconds before auto-dismiss (default 4000ms = 4s)
            parent: Parent widget
            position: Toast position ("top-left", "top-right", "bottom-left", "bottom-right", "top-center", "bottom-center")
        """
        super().__init__(parent)
        self._message = message
        self._icon_type = icon_type
        self._duration = duration
        self._position = position
        
        self.setObjectName("ToastNotification")
        # Ensure stylesheet background styling works correctly
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        self._setup_ui()
        self._apply_styles()
        
        # Auto-dismiss timer
        self._dismiss_timer = QTimer()
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._start_fade_out)
        
    def _setup_ui(self):
        """Setup the toast UI layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Icon label
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24) # Increased icon size slightly
        self._load_icon()
        layout.addWidget(self.icon_label)
        
        # Message label
        self.message_label = QLabel(self._message)
        self.message_label.setObjectName("ToastMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setTextFormat(Qt.TextFormat.RichText)  # Enable HTML formatting
        self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction) # Disable selection to ensure clicks pass through
        layout.addWidget(self.message_label, 1)
        
        # Set fixed width but allow height to adjust
        self.setFixedWidth(340) # Slightly wider
        self.adjustSize()
        
    def _load_icon(self):
        """Load the appropriate icon based on type."""
        # For now, use text-based icons
        # You can replace this with actual SVG icons later
        icon_map = {
            "warning": "⚠️",
            "error": "❌",
            "info": "ℹ️"
        }
        
        icon_text = icon_map.get(self._icon_type, "ℹ️")
        self.icon_label.setText(icon_text)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(f"""
            font-size: 18px;
            background: transparent;
            border: none;
        """)
        
    def _apply_styles(self):
        """Apply theme-aware styling."""
        # Color based on icon type
        border_color = {
            "warning": Theme.warning(),
            "error": Theme.error(),
            "info": Theme.accent_turbo()
        }.get(self._icon_type, Theme.border_focus())
        
        # Build stylesheet with explicit values
        bg_color = Theme.surface_element()
        text_color = Theme.text()
        font_family = Theme.FONT_BODY
        # Use Large font size (16px) as requested
        font_size = Theme.FONT_SIZE_LG
        radius = Theme.RADIUS_LG
        
        self.setStyleSheet(f"""
            QFrame#ToastNotification {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: {radius}px;
            }}
            QLabel#ToastMessage {{
                color: {text_color};
                font-family: '{font_family}';
                font-size: {font_size}px;
                font-weight: 500;
                background-color: transparent;
                border: none;
            }}
        """)
        
    def show_toast(self):
        """Show the toast with slide-in animation."""
        # Calculate position based on parent
        if self.parent():
            parent_rect = self.parent().rect()
            # Ensure size is calculated before positioning
            self.adjustSize()
            
            padding = 16
            # Default to top-left
            x, y = padding, padding
            
            if self._position == "top-left":
                x = padding
                y = padding
            elif self._position == "top-right":
                x = parent_rect.width() - self.width() - padding
                y = padding
            elif self._position == "bottom-left":
                x = padding
                y = parent_rect.height() - self.height() - padding
            elif self._position == "bottom-right":
                x = parent_rect.width() - self.width() - padding
                y = parent_rect.height() - self.height() - padding
            elif self._position == "top-center":
                x = (parent_rect.width() - self.width()) // 2
                y = padding
            elif self._position == "bottom-center":
                x = (parent_rect.width() - self.width()) // 2
                y = parent_rect.height() - self.height() - padding
            
            self.move(x, y)
            self.raise_()  # Bring to front
        
        self.show()
        
        # Install event filter on application to catch global clicks
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)
        
        # Start auto-dismiss timer
        self._dismiss_timer.start(self._duration)
        
    def eventFilter(self, obj, event):
        """Monitor global events for dismissal."""
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            # Dismiss on any mouse click
            self._start_fade_out()
            # Don't consume the event - let it propagate
            return False
        return super().eventFilter(obj, event)
        
    def mousePressEvent(self, event):
        """Allow manual dismissal on click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_fade_out()
        super().mousePressEvent(event)

    def _start_fade_out(self):
        """Start fade-out animation before dismissing."""
        # Remove event filter to stop monitoring
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().removeEventFilter(self)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_animation.finished.connect(self._dismiss)
        self.fade_animation.start()
        
    def _dismiss(self):
        """Dismiss the toast and emit signal."""
        self.dismissed.emit()
        self.deleteLater()
        
    def update_theme(self, is_dark: bool):
        """Update styling when theme changes."""
        Theme.set_dark_mode(is_dark)
        self._apply_styles()


class InputToast(QFrame):
    """
    Toast notification with an input field.
    Stays visible until accepted or dismissed.
    """
    
    accepted = pyqtSignal(str)
    cancelled = pyqtSignal()
    
    def __init__(self, message: str, placeholder: str = "", button_text: str = "Add", parent=None, position: str = "top-right"):
        super().__init__(parent)
        self._message = message
        self._placeholder = placeholder
        self._button_text = button_text
        self._position = position
        
        self.setObjectName("InputToast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Shadow effect
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        self._setup_ui()
        self._apply_styles()
        
    def _setup_ui(self):
        """Setup UI components"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # Input (no label, just the input field)
        from PyQt6.QtWidgets import QLineEdit
        self.input = QLineEdit()
        self.input.setPlaceholderText(self._placeholder)
        self.input.setMinimumWidth(200)
        self.input.returnPressed.connect(self._on_accept)
        layout.addWidget(self.input)
        
        # Checkmark Button (replacing "Create" button)
        from PyQt6.QtWidgets import QPushButton
        self.btn = QPushButton("✓")
        self.btn.setObjectName("ToastCheckButton")
        self.btn.setFixedSize(28, 28)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self._on_accept)
        layout.addWidget(self.btn)
        
        # Close Button (red frame, no text)
        self.close_btn = QPushButton("")
        self.close_btn.setObjectName("ToastCloseButton")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.cancel)
        layout.addWidget(self.close_btn)
        
    def _apply_styles(self):
        """Apply theme styles"""
        bg_color = Theme.surface_element()
        text_color = Theme.text()
        border_color = Theme.border()
        accent_color = Theme.accent()
        success_color = Theme.success()
        
        self.setStyleSheet(f"""
            QFrame#InputToast {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {Theme.RADIUS_LG}px;
            }}
            QLineEdit {{
                background-color: {Theme.param_bg()};
                color: {text_color};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 6px 10px;
                font-family: '{Theme.FONT_BODY}';
                font-size: {Theme.FONT_SIZE_BASE}px;
            }}
            QLineEdit:focus {{
                border: 1px solid {accent_color};
            }}
            QPushButton#ToastCheckButton {{
                background-color: transparent;
                color: {success_color};
                border: 2px solid {success_color};
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton#ToastCheckButton:hover {{
                background-color: {success_color};
                color: {bg_color};
            }}
            QPushButton#ToastCheckButton:pressed {{
                background-color: transparent;
                border: 2px solid {accent_color};
                color: {accent_color};
            }}
            QPushButton#ToastCloseButton {{
                background-color: transparent;
                border: 2px solid {Theme.error()};
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QPushButton#ToastCloseButton:hover {{
                border-color: {Theme.error()};
            }}
            QPushButton#ToastCloseButton:pressed {{
                background-color: {Theme.error()};
            }}
        """)
        
    def show_toast(self):
        """Show the toast with slide-in animation."""
        if self.parent():
            parent_rect = self.parent().rect()
            self.adjustSize()
            
            padding = 16
            
            # Position at top-right by default
            if self._position == "top-right":
                x = parent_rect.width() - self.width() - padding
                y = padding
            else:
                x = padding
                y = padding
                
            self.move(x, y - 20) # Start slightly higher
            self.show()
            self.raise_()
            
            # Animate
            self.anim = QPropertyAnimation(self, b"pos")
            self.anim.setDuration(300)
            self.anim.setStartValue(QPoint(x, y - 20))
            self.anim.setEndValue(QPoint(x, y))
            self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim.start()
            
            # Opacity
            self.opacity_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self.opacity_effect)
            self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
            self.fade_anim.setDuration(200)
            self.fade_anim.setStartValue(0.0)
            self.fade_anim.setEndValue(1.0)
            self.fade_anim.start()
            
            self.input.setFocus()
            
    def hide_toast(self):
        """Hide with animation"""
        if hasattr(self, 'anim'):
            current = self.pos()
            self.anim.setStartValue(current)
            self.anim.setEndValue(QPoint(current.x(), current.y() - 20))
            self.anim.start()
            
        if hasattr(self, 'fade_anim'):
            self.fade_anim.setDirection(QPropertyAnimation.Direction.Backward)
            self.fade_anim.finished.connect(self.close)
            self.fade_anim.start()
        else:
            self.close()

    def _on_accept(self):
        text = self.input.text().strip()
        if text:
            self.accepted.emit(text)
            self.hide_toast()
            
    def cancel(self):
        self.cancelled.emit()
        self.hide_toast()
        
    def update_theme(self, is_dark: bool):
        Theme.set_dark_mode(is_dark)
        self._apply_styles()
