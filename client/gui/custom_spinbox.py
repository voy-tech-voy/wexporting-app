"""
Custom SpinBox Widget with Chevron Arrows and Drag-to-Change
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSpinBox, QSizePolicy
from PySide6.QtCore import Signal, Qt, QEvent, QTimer
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QCursor


class IntegerDragOverlay(QWidget):
    """Transparent overlay that captures mouse events for drag-to-change behavior (integer version)"""
    
    def __init__(self, parent_spinbox_widget):
        super().__init__(parent_spinbox_widget)
        self.parent_widget = parent_spinbox_widget
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        
        # Drag state
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_value = 0
    
    def mousePressEvent(self, event):
        """Start drag tracking on mouse press"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.drag_start_x = event.globalPosition().x()
            self.drag_start_value = self.parent_widget.spinbox.value()
            self.grabMouse()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Update value based on horizontal drag distance"""
        if self.is_dragging:
            delta_x = event.globalPosition().x() - self.drag_start_x
            
            # Only update if drag exceeds threshold
            if abs(delta_x) >= 3:
                value_change = int(delta_x * self.parent_widget.drag_sensitivity)
                new_value = self.drag_start_value + value_change
                
                # Clamp to range
                spinbox = self.parent_widget.spinbox
                new_value = max(spinbox.minimum(), min(new_value, spinbox.maximum()))
                spinbox.setValue(new_value)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """End drag - enter edit mode if it was a click (minimal movement)"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            delta = abs(event.globalPosition().x() - self.drag_start_x)
            self.is_dragging = False
            self.releaseMouse()
            
            # If minimal movement, this was a click - enter text edit mode
            if delta < 3:
                self.hide()
                line_edit = self.parent_widget.spinbox.lineEdit()
                line_edit.setFocus(Qt.FocusReason.MouseFocusReason)
                line_edit.selectAll()
                line_edit.setCursor(Qt.CursorShape.IBeamCursor)
            event.accept()


class CustomSpinBox(QWidget):
    """
    Custom integer spinbox with chevron arrows matching CustomTargetSizeSpinBox style.
    Supports drag-to-change: click and drag horizontally to adjust value.
    """
    
    valueChanged = Signal(int)
    
    def __init__(self, parent=None, default_value=100, on_enter_callback=None):
        super().__init__(parent)
        self.is_dark = True
        self.on_enter_callback = on_enter_callback
        
        # Connect to ThemeManager for automatic theme updates
        from client.gui.theme_manager import ThemeManager
        theme_manager = ThemeManager.instance()
        theme_manager.theme_changed.connect(self.update_theme)
        self.is_dark = theme_manager.is_dark_mode()
        
        # Drag sensitivity: value change per pixel dragged
        self.drag_sensitivity = 1.0  # 1 pixel = 1 unit change
        
        # Create custom cursor
        self.custom_drag_cursor = self._create_custom_cursor(is_dark=self.is_dark)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        from PySide6.QtWidgets import QAbstractSpinBox
        
        self.spinbox = QSpinBox()
        self.spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spinbox.setValue(default_value)
        self.spinbox.setMinimumWidth(120)
        self.spinbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Set focus policy
        self.spinbox.lineEdit().setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        # Install event filter
        self.spinbox.installEventFilter(self)
        self.spinbox.lineEdit().installEventFilter(self)
        
        # Set custom cursor
        self.spinbox.lineEdit().setCursor(self.custom_drag_cursor)
        
        # Create arrow buttons
        arrow_container = QWidget()
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(0)
        
        arrow_font = QFont()
        arrow_font.setPointSize(11)
        arrow_font.setStretch(200)
        arrow_font.setWeight(QFont.Weight.DemiBold)
        
        self.up_arrow = QLabel("˄")
        self.up_arrow.setFont(arrow_font)
        self.up_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.up_arrow.setFixedSize(24, 21)
        self.up_arrow.mousePressEvent = lambda e: self.spinbox.stepUp()
        
        self.down_arrow = QLabel("˅")
        self.down_arrow.setFont(arrow_font)
        self.down_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.down_arrow.setFixedSize(24, 21)
        self.down_arrow.mousePressEvent = lambda e: self.spinbox.stepDown()
        
        arrow_layout.addWidget(self.up_arrow)
        arrow_layout.addWidget(self.down_arrow)
        arrow_container.setFixedHeight(42)
        arrow_container.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        
        self.spinbox.valueChanged.connect(self.valueChanged.emit)
        
        layout.addWidget(self.spinbox)
        layout.addWidget(arrow_container)
        
        # Create drag overlay
        self.drag_overlay = IntegerDragOverlay(self)
        self.drag_overlay.setCursor(self.custom_drag_cursor)
        self.drag_overlay.hide()
        
        self._apply_custom_style(self.is_dark)
    
    def _create_custom_cursor(self, is_dark=True):
        """Create custom cursor with horizontal arrows and I-beam in center"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if is_dark:
            main_color = QColor(255, 255, 255)
            outline_color = QColor(0, 0, 0)
        else:
            main_color = QColor(0, 0, 0)
            outline_color = QColor(255, 255, 255)
        
        # Draw outline
        pen = QPen(outline_color)
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(10, 16, 6, 13)
        painter.drawLine(10, 16, 6, 19)
        painter.drawLine(16, 8, 16, 24)
        painter.drawLine(14, 8, 18, 8)
        painter.drawLine(14, 24, 18, 24)
        painter.drawLine(22, 16, 26, 13)
        painter.drawLine(22, 16, 26, 19)
        
        # Draw main cursor
        pen.setColor(main_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(10, 16, 6, 13)
        painter.drawLine(10, 16, 6, 19)
        painter.drawLine(16, 8, 16, 24)
        painter.drawLine(14, 8, 18, 8)
        painter.drawLine(14, 24, 18, 24)
        painter.drawLine(22, 16, 26, 13)
        painter.drawLine(22, 16, 26, 19)
        
        painter.end()
        return QCursor(pixmap, 16, 16)
    
    def resizeEvent(self, event):
        """Position the drag overlay to cover the spinbox"""
        super().resizeEvent(event)
        spinbox_geo = self.spinbox.geometry()
        self.drag_overlay.setGeometry(spinbox_geo)
        self.drag_overlay.raise_()
    
    def showEvent(self, event):
        """Ensure overlay is positioned correctly when shown"""
        super().showEvent(event)
        QTimer.singleShot(0, self._update_overlay_geometry)
    
    def _update_overlay_geometry(self):
        """Update overlay geometry to match spinbox"""
        if self.isVisible():
            spinbox_geo = self.spinbox.geometry()
            self.drag_overlay.setGeometry(spinbox_geo)
            self.drag_overlay.show()
            self.drag_overlay.raise_()
    
    def eventFilter(self, obj, event):
        """Handle Enter/Escape key presses and focus changes"""
        if event.type() == QEvent.Type.KeyPress:
            if obj in (self.spinbox, self.spinbox.lineEdit()):
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                    self.spinbox.lineEdit().blockSignals(True)
                    self.spinbox.lineEdit().deselect()
                    
                    main_window = self.window()
                    if main_window:
                        main_window.setFocus(Qt.FocusReason.OtherFocusReason)
                    
                    self.spinbox.lineEdit().clearFocus()
                    self.spinbox.clearFocus()
                    self._restore_drag_mode()
                    self.spinbox.lineEdit().blockSignals(False)
                    
                    if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.on_enter_callback:
                        QTimer.singleShot(0, self.on_enter_callback)
                    
                    return True
        
        if obj in (self.spinbox, self.spinbox.lineEdit()):
            if event.type() == QEvent.Type.FocusOut:
                QTimer.singleShot(50, self._restore_drag_mode)
                return False
            elif event.type() == QEvent.Type.FocusIn:
                self.drag_overlay.hide()
                self.spinbox.lineEdit().setCursor(Qt.CursorShape.IBeamCursor)
        
        return super().eventFilter(obj, event)
    
    def _restore_drag_mode(self):
        """Restore drag mode by showing overlay and resetting cursor"""
        if self.spinbox.lineEdit().hasFocus():
            return
        
        self.drag_overlay.is_dragging = False
        self.drag_overlay.drag_start_x = 0
        self.drag_overlay.drag_start_value = 0
        
        self.spinbox.lineEdit().deselect()
        self.spinbox.lineEdit().setCursor(self.custom_drag_cursor)
        
        self.drag_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        spinbox_geo = self.spinbox.geometry()
        self.drag_overlay.setGeometry(spinbox_geo)
        self.drag_overlay.show()
        self.drag_overlay.setVisible(True)
        self.drag_overlay.setEnabled(True)
        self.drag_overlay.raise_()
    
    def value(self):
        return self.spinbox.value()
    
    def setValue(self, value):
        self.spinbox.setValue(value)
    
    def setRange(self, min_val, max_val):
        self.spinbox.setRange(min_val, max_val)
        # Adjust drag sensitivity based on range
        range_size = max_val - min_val
        if range_size <= 200:
            self.drag_sensitivity = 0.5  # Fine control for small ranges
        elif range_size <= 1000:
            self.drag_sensitivity = 1.0
        else:
            self.drag_sensitivity = 2.0  # Faster for large ranges like 10000
    
    def setSuffix(self, suffix):
        self.spinbox.setSuffix(suffix)
    
    def setVisible(self, visible):
        super().setVisible(visible)
        self.spinbox.setVisible(visible)
        if visible:
            QTimer.singleShot(0, self._update_overlay_geometry)
        else:
            self.drag_overlay.hide()
    
    def update_theme(self, is_dark):
        self.is_dark = is_dark
        self.custom_drag_cursor = self._create_custom_cursor(is_dark)
        self.spinbox.lineEdit().setCursor(self.custom_drag_cursor)
        self.drag_overlay.setCursor(self.custom_drag_cursor)
        self._apply_custom_style(is_dark)
    
    def _apply_custom_style(self, is_dark):
        from client.gui.theme import Theme
        
        # Ensure Theme is in correct mode before querying colors
        Theme.set_dark_mode(is_dark)
        
        # Use centralized theme tokens for logic
        bg_color = Theme.param_bg()
        text_color = Theme.text()
        border_color = Theme.color("border_dim")
        arrow_color = Theme.text_muted()
        hover_color = Theme.color("border_focus")
        
        spinbox_style = f"""
            QSpinBox {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-right: none;
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
                padding: 6px 8px;
                min-height: 28px;
            }}
            QSpinBox:hover {{
                border-color: {hover_color};
            }}
            QSpinBox:focus {{
                border-color: {hover_color};
            }}
        """
        self.spinbox.setStyleSheet(spinbox_style)
        
        # Arrows share the same background, but handle their own border logic
        arrow_style = f"""
            QLabel {{
                background-color: {bg_color};
                color: {arrow_color};
                border: 1px solid {border_color};
                border-left: none;
                padding: 0px;
                margin: 0px;
                min-height: 20px;
            }}
            QLabel:hover {{
                background-color: {Theme.color('surface_hover')};
            }}
        """
        
        self.up_arrow.setStyleSheet(arrow_style + f"""
            border-top-right-radius: 4px;
            border-bottom: none;
        """)
        
        self.down_arrow.setStyleSheet(arrow_style + f"""
            border-bottom-right-radius: 4px;
            border-top: none;
        """)
