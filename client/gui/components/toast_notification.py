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
    
    def __init__(self, message: str, icon_type: str = "warning", duration: int = 4000, parent=None, position: str = "top-left", size: str = "standard"):
        """
        Initialize toast notification.
        
        Args:
            message: Text to display
            icon_type: Type of icon ("warning", "error", "info")
            duration: Time in milliseconds before auto-dismiss (default 4000ms = 4s)
            parent: Parent widget
            position: Toast position ("top-left", "top-right", "bottom-left", "bottom-right", "top-center", "bottom-center", "center")
            size: Size variant ("standard", "large")
        """
        super().__init__(parent)
        self._message = message
        self._icon_type = icon_type
        self._duration = duration
        self._position = position
        self._size_variant = size
        
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
        # Adaptive width: Min 300, Max will be set in show_toast based on parent
        self.setMinimumWidth(300)
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
        
        # Determine sizing based on variant
        if self._size_variant == "large":
            font_size = Theme.FONT_SIZE_XL  # Larger font
            radius = Theme.RADIUS_LG + 4
            padding = "24px 32px"
            icon_size = "32px"
        else:
            font_size = Theme.FONT_SIZE_LG
            radius = Theme.RADIUS_LG
            padding = "12px 16px"
            icon_size = "18px"
            
        self.icon_label.setStyleSheet(f"""
            font-size: {icon_size};
            background: transparent;
            border: none;
        """)
        
        self.icon_label.setStyleSheet(f"""
            font-size: {icon_size};
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
        
        # Determine sizing based on variant
        if self._size_variant == "large":
            font_size = Theme.FONT_SIZE_XL
            radius = Theme.RADIUS_LG + 4
        else:
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
                padding: 0px;
            }}
        """)
        
    def show_toast(self):
        """Show the toast with slide-in animation."""
        # Calculate position based on parent
        if self.parent():
            parent_rect = self.parent().rect()
            # Ensure size is calculated before positioning
            
            # Adaptive Width: Cap at 80% of parent width, but allow hugging content
            max_w = int(parent_rect.width() * 0.8)
            self.setMaximumWidth(max_w)
            self.adjustSize() # Recalculate size with new constraints
            
            padding = 16
            
            # Handle large variant padding
            if self._size_variant == "large":
                padding = 32
                
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
            elif self._position == "center":
                x = (parent_rect.width() - self.width()) // 2
                y = (parent_rect.height() - self.height()) // 2
            
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
        # Ensure it doesn't block mouse events immediately by hiding first
        self.hide()
        
        # Emit signal synchronously - this may block if connected to a modal dialog
        # but since we are hidden, it won't block input to the dialog
        self.dismissed.emit()
        
        # Schedule deletion after emit standard
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
    
    def __init__(self, message: str, placeholder: str = "", button_text: str = "Add", parent=None, position: str = "top-right", description: str = ""):
        super().__init__(parent)
        self._message = message
        self._placeholder = placeholder
        self._button_text = button_text
        self._position = position
        self._description = description
        self._is_confirmation_mode = False
        self._confirmation_timer = None
        self._align_widget = None  # Store widget reference, not position
        
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
        from PyQt6.QtWidgets import QLineEdit, QPushButton, QVBoxLayout
        
        # Use VBoxLayout if description is provided
        if self._description:
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(12, 10, 12, 10)
            main_layout.setSpacing(8)
            
            # Description label
            self.description_label = QLabel(self._description)
            self.description_label.setObjectName("ToastDescription")
            self.description_label.setWordWrap(True)
            main_layout.addWidget(self.description_label)
            
            # Input row
            input_layout = QHBoxLayout()
            input_layout.setSpacing(8)
            input_layout.setContentsMargins(0, 0, 0, 0)
        else:
            input_layout = QHBoxLayout(self)
            input_layout.setContentsMargins(12, 8, 12, 8)
            input_layout.setSpacing(8)
        
        # Input field
        self.input = QLineEdit()
        self.input.setPlaceholderText(self._placeholder)
        self.input.setMinimumWidth(200)
        self.input.returnPressed.connect(self._on_accept)
        input_layout.addWidget(self.input)
        
        # Checkmark Button
        self.btn = QPushButton("✓")
        self.btn.setObjectName("ToastCheckButton")
        self.btn.setFixedSize(28, 28)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self._on_accept)
        input_layout.addWidget(self.btn)
        
        # Close Button (X symbol)
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("ToastCloseButton")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.cancel)
        input_layout.addWidget(self.close_btn)
        
        # Add input layout to main layout if using VBoxLayout
        if self._description:
            main_layout.addLayout(input_layout)
        
    def _apply_styles(self):
        """Apply theme styles"""
        bg_color = Theme.surface_element()
        text_color = Theme.text()
        border_color = Theme.border()
        info_color = Theme.color("info")  # Blue for toast outline
        success_color = Theme.success()  # Green for accept button
        error_color = Theme.error()  # Red for cancel button
        input_bg = Theme.param_bg()  # Unified input background
        
        self.setStyleSheet(f"""
            QFrame#InputToast {{
                background-color: {bg_color};
                border: 2px solid {info_color};
                border-radius: {Theme.RADIUS_LG}px;
            }}
            QLabel#ToastDescription {{
                color: {text_color};
                font-family: '{Theme.FONT_BODY}';
                font-size: {Theme.FONT_SIZE_LG}px;
                background-color: transparent;
                border: none;
            }}
            QLineEdit {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 8px 12px;
                font-family: '{Theme.FONT_BODY}';
                font-size: {Theme.FONT_SIZE_LG}px;
            }}
            QLineEdit:focus {{
                border: 1px solid {info_color};
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
                background-color: {Theme.color_with_alpha("accent_success", 0.8)};
                border: 2px solid {success_color};
                color: {bg_color};
            }}
            QPushButton#ToastCloseButton {{
                background-color: transparent;
                color: {error_color};
                border: 2px solid {error_color};
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton#ToastCloseButton:hover {{
                background-color: {error_color};
                color: {bg_color};
            }}
            QPushButton#ToastCloseButton:pressed {{
                background-color: {Theme.color_with_alpha("error", 0.8)};
                border: 2px solid {error_color};
                color: {bg_color};
            }}
        """)
        
    def show_toast(self):
        """Show the toast with slide-in animation."""
        # Reset state - restore input mode
        if self._is_confirmation_mode:
            self._is_confirmation_mode = False
            # Remove event filter if it was added
            try:
                QApplication.instance().removeEventFilter(self)
            except:
                pass
            # Stop confirmation timer if running
            if self._confirmation_timer:
                self._confirmation_timer.stop()
                self._confirmation_timer = None
            # Show input controls
            self.input.show()
            self.btn.show()
            self.close_btn.show()
            # Reset description label if it exists
            if hasattr(self, 'description_label') and self._description:
                self.description_label.setText(self._description)
                self.description_label.setStyleSheet(f"""
                    QLabel {{
                        color: {Theme.text()};
                        font-family: '{Theme.FONT_BODY}';
                        font-size: {Theme.FONT_SIZE_LG}px;
                        background-color: transparent;
                        border: none;
                    }}
                """)
            # Clear input field
            self.input.clear()
            # Reset styles (blue border for input mode)
            self._apply_styles()
            self.layout().update()
            self.layout().activate()
            self.updateGeometry()
            self.adjustSize()
        
        if self.parent():
            # Calculate position (adjustSize must be called first)
            self.adjustSize()
            pos = self._calculate_position()
            x, y = pos.x(), pos.y()
                
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
            
            # Install event filter to detect clicks outside
            QApplication.instance().installEventFilter(self)
            
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
            
        # Ensure event filter is removed
        try:
            QApplication.instance().removeEventFilter(self)
        except:
            pass

    def _on_accept(self):
        text = self.input.text().strip()
        if text:
            self.accepted.emit(text)
            # Don't hide immediately - let the callback handle showing confirmation or hiding
            
    def cancel(self):
        self.cancelled.emit()
        self.hide_toast()
    
    def set_align_widget(self, widget):
        """Set the widget to align with. Position will be calculated on each show."""
        self._align_widget = widget
    
    def _calculate_position(self):
        """Calculate toast position. Always call adjustSize() before this."""
        if not self.parent():
            return QPoint(0, 0)
        
        parent_rect = self.parent().rect()
        padding = 16
        
        # X: always right-aligned to parent edge
        x = parent_rect.width() - self.width() - padding
        
        # Y: from aligned widget or default to top
        if self._align_widget:
            try:
                # Get widget's global position
                widget_global_pos = self._align_widget.mapToGlobal(self._align_widget.rect().topLeft())
                # Convert to parent's coordinate system
                parent_local_pos = self.parent().mapFromGlobal(widget_global_pos)
                y = parent_local_pos.y()
            except:
                # Widget might be deleted, fall back to top
                y = padding
        else:
            y = padding
        
        # Clamp to parent bounds
        if y + self.height() > parent_rect.height():
            y = parent_rect.height() - self.height() - padding
        if y < padding:
            y = padding
        
        return QPoint(x, y)
    
    def set_confirmation_mode(self, message: str, duration: int = 4000):
        """Switch toast to confirmation mode with auto-dismiss."""
        self._is_confirmation_mode = True
        
        # Update border to success color (green)
        self.setStyleSheet(f"""
            QFrame#InputToast {{
                background-color: {Theme.surface_element()};
                border: 2px solid {Theme.success()};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        
        # Hide input and buttons
        self.input.hide()
        self.btn.hide()
        self.close_btn.hide()
        
        # Update or create description label to show confirmation
        if hasattr(self, 'description_label'):
            self.description_label.setText(message)
            self.description_label.setStyleSheet(f"""
                QLabel {{
                    color: {Theme.success()};
                    font-family: '{Theme.FONT_BODY}';
                    font-size: {Theme.FONT_SIZE_LG}px;
                    font-weight: bold;
                    background-color: transparent;
                    border: none;
                }}
            """)
        else:
            # Create confirmation label
            from PyQt6.QtWidgets import QVBoxLayout
            self.description_label = QLabel(message)
            self.description_label.setObjectName("ToastConfirmation")
            self.description_label.setWordWrap(True)
            self.description_label.setStyleSheet(f"""
                QLabel {{
                    color: {Theme.success()};
                    font-family: '{Theme.FONT_BODY}';
                    font-size: {Theme.FONT_SIZE_LG}px;
                    font-weight: bold;
                    background-color: transparent;
                    border: none;
                }}
            """)
            self.layout().addWidget(self.description_label)
        
        # Recalculate size and reposition
        self.adjustSize()
        if self.parent():
            pos = self._calculate_position()
            self.move(pos)
        
        # Setup auto-dismiss timer
        if self._confirmation_timer:
            self._confirmation_timer.stop()
        
        self._confirmation_timer = QTimer()
        self._confirmation_timer.setSingleShot(True)
        self._confirmation_timer.timeout.connect(self.hide_toast)
        self._confirmation_timer.start(duration)
        
        # Install event filter for click-to-dismiss
        QApplication.instance().installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Handle global events for click-to-dismiss behavior."""
        if event.type() == QEvent.Type.MouseButtonPress:
            # Get the widget that was clicked
            global_pos = event.globalPosition().toPoint()
            widget_at_pos = QApplication.widgetAt(global_pos)
            
            # Check if the click is inside this toast or any of its children
            is_inside_toast = False
            if widget_at_pos:
                # Walk up the parent chain to see if this toast is an ancestor
                current = widget_at_pos
                while current:
                    if current == self:
                        is_inside_toast = True
                        break
                    current = current.parentWidget()
            
            # Only dismiss if click is outside the toast
            if not is_inside_toast:
                # If in confirmation mode, click anywhere outside dismisses
                if self._is_confirmation_mode:
                    self.hide_toast()
                    return True # Consume event
                
                # If in input mode, dismiss on outside click
                if self.isVisible():
                    self.cancel()
                    return True # Consume event to prevent accidental clicks behind
                    
        return super().eventFilter(obj, event)
        
    def update_theme(self, is_dark: bool):
        Theme.set_dark_mode(is_dark)
        self._apply_styles()
