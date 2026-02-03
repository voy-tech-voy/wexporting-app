"""
CustomTargetSizeSpinBox - Spinbox with drag-to-change functionality.

Extracted from custom_widgets.py for better organization.
"""

from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QEvent, QByteArray, QDataStream, QMimeData, QRect
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, 
    QDoubleSpinBox, QAbstractSpinBox, QSizePolicy
)
from PyQt6.QtGui import (
    QCursor, QIcon, QPainter, QColor, QFont, QPen, QBrush, 
    QMouseEvent, QPixmap, QRegularExpressionValidator
)
from PyQt6.QtCore import QRegularExpression

from client.gui.theme import Theme


class SpinBoxLineEdit(QLineEdit):
    """Custom LineEdit that handles focus and keyboard events better for spinboxes"""
    
    enterPressed = pyqtSignal()
    escapePressed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.suffix_text = ""
        self.suffix_color = QColor("#aaaaaa")  # Default gray
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.enterPressed.emit()
            self.clearFocus()  # Lose focus on Enter
            # Don't call super() to avoid default behavior if needed
            super().keyPressEvent(event)
        elif event.key() == Qt.Key.Key_Escape:
            self.escapePressed.emit()
            self.clearFocus()
            event.ignore()  # Let parent handle reset if needed
        else:
            super().keyPressEvent(event)
            
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # Optional: emit signal or handle validation
        
    def paintEvent(self, event):
        """Custom paint to draw suffix text inside the box"""
        super().paintEvent(event)
        
        if self.suffix_text and self.text():
            painter = QPainter(self)
            
            # Calculate position for suffix
            # Get the rect of the text
            fm = self.fontMetrics()
            text_width = fm.horizontalAdvance(self.text())
            
            # Add padding
            left_padding = 4  # Standard lineEdit padding
            
            # Draw suffix
            # Ensure it fits within the widget
            if text_width < self.width() - 30:
                painter.setPen(self.suffix_color)
                # Draw at baseline
                # Check for alignment, simpler to just offset from text
                # Ideally would use QStyle but this is sufficient for custom widget
                
                # Get content rect with margins
                rect = self.rect()
                # Center vertically
                y = (rect.height() + fm.ascent() - fm.descent()) // 2
                
                x = left_padding + text_width + 2
                
                painter.drawText(x, y, self.suffix_text)


class DragOverlay(QWidget):
    """
    Transparent overlay that handles mouse dragging for value adjustment.
    Placed on top of the spinbox to intercept mouse events when outside the entry field.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.dragging = False
        self.last_x = 0
        self.start_value = 0
        self.parent_spinbox = parent  # Reference to CustomTargetSizeSpinBox
        
        # Cursor caching
        self._blank_cursor = None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.last_x = event.globalPosition().x()
            self.start_value = self.parent_spinbox.value()
            
            # Hide cursor while dragging for infinite feel
            self.setCursor(Qt.CursorShape.BlankCursor)
            
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            # Restore custom cursor
            self.setCursor(self.parent_spinbox.custom_drag_cursor)
            
        super().mouseReleaseEvent(event)
        
    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPosition().x() - self.last_x
            
            if delta != 0:
                # Calculate new value
                # Sensitivity: 1px = x MB (configurable)
                sensitivity = self.parent_spinbox.drag_sensitivity 
                change = delta * sensitivity
                
                current = self.parent_spinbox.value()
                new_value = current + change
                
                # Apply constraints
                self.parent_spinbox.setValue(new_value)
                
                # Reset mouse position to avoid hitting screen edge (infinite scroll)
                # Note: This requires moving the cursor, which might be jarring
                # For now, simplistic implementation without warping
                self.last_x = event.globalPosition().x()
                
        super().mouseMoveEvent(event)


class CustomTargetSizeSpinBox(QWidget):
    """
    Custom target size spinbox with MB suffix and theme support.
    Features delicate chevron arrows matching the CustomComboBox style.
    Supports drag-to-change: click and drag horizontally to adjust value.
    """
    
    valueChanged = pyqtSignal(float)  # Emit when value changes
    
    def __init__(self, parent=None, default_value=1.0, on_enter_callback=None, decimals=2):
        super().__init__(parent)
        self.is_dark = True
        self.on_enter_callback = on_enter_callback  # Callback when Enter is pressed
        
        # Connect to ThemeManager for automatic theme updates
        from client.gui.theme_manager import ThemeManager
        theme_manager = ThemeManager.instance()
        theme_manager.theme_changed.connect(self.update_theme)
        self.is_dark = theme_manager.is_dark_mode()
        
        # Drag state tracking
        self.drag_sensitivity = 0.01  # Value change per pixel dragged (10px = 0.1 value change)
        self._drag_start_pos = 0.0
        self._drag_start_value = 0.0
        self._is_dragging = False
        self._is_possible_drag = False
        
        # Create custom cursor (horizontal arrows with I-beam)
        self.custom_drag_cursor = self._create_custom_cursor(is_dark=self.is_dark)
        
        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.spinbox = QDoubleSpinBox()
        
        # Use custom lineEdit that intercepts Enter/Escape
        self.custom_line_edit = SpinBoxLineEdit()
        self.custom_line_edit.suffix_text = " MB" # Set the visual suffix
        self.spinbox.setLineEdit(self.custom_line_edit)
        
        # Connect signals from custom lineEdit
        self.custom_line_edit.enterPressed.connect(self._on_enter_pressed)
        self.custom_line_edit.escapePressed.connect(self._on_escape_pressed)
        
        self.spinbox.setRange(0.001, 10000.0)
        self.spinbox.setValue(default_value)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setSingleStep(0.1)
        self.spinbox.setSuffix("")
        self.spinbox.setMinimumWidth(120)
        self.spinbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        
        # Set validator to only allow numeric input
        validator = QRegularExpressionValidator(QRegularExpression(r"^\d*\.?\d*$"))
        self.spinbox.lineEdit().setValidator(validator)
        
        # Set focus policy to click focus - loses focus when clicking elsewhere
        self.spinbox.lineEdit().setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        # Install event filter on BOTH spinbox and lineEdit to catch Enter/Escape
        self.spinbox.installEventFilter(self)
        self.spinbox.lineEdit().installEventFilter(self)
        
        # Set custom cursor on lineEdit
        self.spinbox.lineEdit().setCursor(self.custom_drag_cursor)
        
        # Create custom arrow buttons
        arrow_container = QWidget()
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(0)
        
        # Create font with horizontal stretch for wider chevrons
        arrow_font = QFont()
        arrow_font.setPointSize(11)
        arrow_font.setStretch(200)  # 200% width stretch
        arrow_font.setWeight(QFont.Weight.DemiBold)  # Semi-bold weight
        
        self.up_arrow = QLabel("˄")
        self.up_arrow.setFont(arrow_font)
        self.up_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.up_arrow.setFixedSize(24, 21)  # Fixed height to match half of spinbox total height
        self.up_arrow.mousePressEvent = lambda e: self.spinbox.stepUp()
        
        self.down_arrow = QLabel("˅")
        self.down_arrow.setFont(arrow_font)
        self.down_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.down_arrow.setFixedSize(24, 21)  # Fixed height to match half of spinbox total height
        self.down_arrow.mousePressEvent = lambda e: self.spinbox.stepDown()
        
        arrow_layout.addWidget(self.up_arrow)
        arrow_layout.addWidget(self.down_arrow)
        arrow_container.setFixedHeight(42)  # Match spinbox total height
        arrow_container.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        
        # Connect signal
        self.spinbox.valueChanged.connect(self.valueChanged.emit)
        
        layout.addWidget(self.spinbox)
        layout.addWidget(arrow_container)
        
        # Create overlay for drag handling (sits on top of spinbox)
        self.drag_overlay = DragOverlay(self)
        self.drag_overlay.setCursor(self.custom_drag_cursor)
        self.drag_overlay.hide()  # Start hidden, will show in showEvent
        
        self._apply_custom_style(self.is_dark)
        
    def _create_custom_cursor(self, is_dark=True):
        """Create a custom cursor icon with horizontal arrows and I-beam"""
        # Create pixmap
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Colors
        color = QColor("#ffffff" if is_dark else "#000000")
        painter.setPen(QPen(color, 2))
        
        # Draw Left Arrow (<)
        painter.drawLine(8, 16, 12, 12)
        painter.drawLine(8, 16, 12, 20)
        
        # Draw Right Arrow (>)
        painter.drawLine(24, 16, 20, 12)
        painter.drawLine(24, 16, 20, 20)
        
        # Draw I-beam in middle
        painter.setPen(QPen(color, 1))
        # Top bar
        painter.drawLine(14, 10, 18, 10)
        # Vertical line
        painter.drawLine(16, 10, 16, 22)
        # Bottom bar
        painter.drawLine(14, 22, 18, 22)
        
        painter.end()
        
        return QCursor(pixmap, 16, 16)
        
    def showEvent(self, event):
        super().showEvent(event)
        # Position overlay over lineEdit part (excluding arrows)
        # We need to wait for layout? No, resizeEvent handles updates
        # But initially ensure size
        self._update_overlay_geometry()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay_geometry()
        
    def _update_overlay_geometry(self):
        """Position the drag overlay over the spinbox area"""
        # Only cover the value part, not the arrow buttons? 
        # Actually covering the whole text area makes sense for drag
        rect = self.spinbox.rect()
        # Adjust width to exclude our custom arrow container if possible
        # Since arrow_container is separate widget in layout, spinbox rect is just the spinbox
        self.drag_overlay.setGeometry(self.spinbox.geometry())
        
        # Crucial: Stack overlay UNDER the actual lineEdit for typing,
        # OR implement logic to pass clicks through if not dragging.
        # Actually typically drag-spinboxes work by: 
        # - Click+Drag = Change value
        # - Click+Release (short) = Focus edits
        
        # For now, let's just create an "invisible" overlay that passes clicks
        # Wait, if it's under lineEdit, lineEdit catches mouse.
        # If over, lineEdit doesn't get focus.
        
        # Strategy: Overlay is HIDDEN by default.
        # We install eventFilter on lineEdit to detect mouse press/move?
        # Yes, that's better than a separate overlay widget for this specific case.
        # But we already created DragOverlay class.
        pass
        
    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                self._on_enter_pressed()
                return True
            elif event.key() == Qt.Key.Key_Escape:
                self._on_escape_pressed()
                return True
                
        # Handle mouse events for dragging functionality directly on the lineEdit
        if source == self.spinbox.lineEdit():
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_start_pos = event.globalPosition().x()
                    self._drag_start_value = self.spinbox.value()
                    self._is_dragging = False
                    self._is_possible_drag = True
                    # Don't consume yet, let lineEdit handle focus if it's just a click
                    # But if we don't consume, selection might start.
                    # Standard behavior: Press -> Focus. 
                    # If we subsequently move, we treat it as drag.
                    
            elif event.type() == QEvent.Type.MouseMove:
                if getattr(self, '_is_possible_drag', False):
                    delta = event.globalPosition().x() - self._drag_start_pos
                    if abs(delta) > 2: # Threshold to detect drag
                        self._is_dragging = True
                        self._is_possible_drag = False # Confirmed drag
                        # Hide cursor? or Change it
                        self.spinbox.lineEdit().setCursor(Qt.CursorShape.BlankCursor)
                        
                if getattr(self, '_is_dragging', False):
                    delta = event.globalPosition().x() - self._drag_start_pos
                    
                    # Sensitivity: 1px = x value
                    change = delta * self.drag_sensitivity
                    new_value = self._drag_start_value + change
                    self.spinbox.setValue(new_value)
                    return True # Consume move event
                    
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if getattr(self, '_is_dragging', False):
                    self._is_dragging = False
                    self.spinbox.lineEdit().setCursor(self.custom_drag_cursor)
                    return True # Consume release event so we don't move cursor/selection
                
                if getattr(self, '_is_possible_drag', False):
                    self._is_possible_drag = False
                    # It was a click. Let default handler proceed (focus, cursor placement)
             
        return super().eventFilter(source, event)
        
    def _on_enter_pressed(self):
        """Handle Enter key - clear focus and execute callback"""
        self.spinbox.clearFocus()
        if self.on_enter_callback:
            self.on_enter_callback()
            
    def _on_escape_pressed(self):
        """Handle Escape key - revert value (not tracked here yet) and clear focus"""
        self.spinbox.clearFocus()
        # Could restore previous value if we tracked it
        
    def value(self):
        return self.spinbox.value()
    
    def setValue(self, value):
        """Set value"""
        self.spinbox.setValue(value)
    
    def setRange(self, minimum, maximum):
        """Set the range of allowed values"""
        self.spinbox.setRange(minimum, maximum)
    
    def setDecimals(self, decimals):
        """Set number of decimal places"""
        self.spinbox.setDecimals(decimals)
    
    def setSensitivity(self, sensitivity):
        """Set drag sensitivity (value change per pixel)"""
        self.drag_sensitivity = sensitivity
    
    def setVisible(self, visible):
        """Override setVisible to apply to spinbox"""
        super().setVisible(visible)
        self.spinbox.setVisible(visible)
    
    def update_theme(self, is_dark):
        """Update styling based on theme"""
        self.is_dark = is_dark
        # Recreate cursor with new theme
        self.custom_drag_cursor = self._create_custom_cursor(is_dark=is_dark)
        self.spinbox.lineEdit().setCursor(self.custom_drag_cursor)
        self.drag_overlay.setCursor(self.custom_drag_cursor)
        
        # Update suffix color
        from PyQt6.QtGui import QColor
        suffix_color = QColor("#aaaaaa") if is_dark else QColor("#888888")
        self.custom_line_edit.suffix_color = suffix_color
        
        self._apply_custom_style(is_dark)
    
    def _apply_custom_style(self, is_dark):
        """Apply custom styling with chevron arrows"""
        from client.gui.theme import Theme
        
        # Ensure Theme is in correct mode
        Theme.set_dark_mode(is_dark)
        
        # Use centralized theme tokens
        bg_color = Theme.param_bg()
        text_color = Theme.text()
        border_color = Theme.border()
        arrow_color = Theme.text_muted()
        hover_color = Theme.border_focus()
        
        # Style the spinbox
        spinbox_style = f"""
            QDoubleSpinBox {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                padding: 6px 8px;
                min-height: 28px;
            }}
            QDoubleSpinBox:hover {{
                border-color: {hover_color};
            }}
            QDoubleSpinBox:focus {{
                border-color: {hover_color};
            }}
        """
        self.spinbox.setStyleSheet(spinbox_style)
        
        # Style the arrow labels with minimalistic appearance
        arrow_style = f"""
            QLabel {{
                background-color: {bg_color};
                color: {arrow_color};
                border: 1px solid {border_color};
                padding: 0px;
                margin: 0px;
                min-height: 20px;
            }}
            QLabel:hover {{
                color: {hover_color};
                border-color: {hover_color};
            }}
        """
        
        # Apply rounded corners to arrows
        self.up_arrow.setStyleSheet(arrow_style + f"""
            border-top-right-radius: 4px;
            border-bottom: none;
            border-left: none;
        """)
        
        self.down_arrow.setStyleSheet(arrow_style + f"""
            border-bottom-right-radius: 4px;
            border-top: none;
            border-left: none;
        """)
