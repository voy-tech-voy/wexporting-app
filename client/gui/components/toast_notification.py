"""
Toast Notification Component

A reusable, non-blocking notification widget that appears in the upper left corner.
Styled to match the app's design language with auto-dismiss functionality.
"""
from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout, QGraphicsOpacityEffect, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QEvent
from PyQt6.QtGui import QPixmap
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
