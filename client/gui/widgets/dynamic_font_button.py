"""
DynamicFontButton - Hardware-aware button with GPU acceleration visual effects.

Extracted from custom_widgets.py for better organization.
"""

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QPainter, QPen, QColor, QBrush


class DynamicFontButton(QPushButton):
    """
    Hardware-aware Start button with GPU acceleration visual effects.
    
    When GPU is available:
    - Circuit trace effect: 1px cyan line traces the border on hover
    - Scanline fill: subtle diagonal pattern moves across background
    - Bolt icon lights up in cyan
    
    When CPU only:
    - Standard button appearance, no animation
    """
    
    def __init__(self, text=""):
        super().__init__(text)
        from client.utils.font_manager import FONT_FAMILY_APP_NAME, FONT_SIZE_BUTTON
        
        self._font_family = FONT_FAMILY_APP_NAME
        self._font_size = FONT_SIZE_BUTTON
        
        # GPU state
        self._gpu_available = False
        self._is_hovered = False
        
        # Animation properties
        self._trace_offset = 0.0
        self._scanline_offset = 0.0
        
        # Animation timers
        self._trace_timer = QTimer(self)
        self._trace_timer.timeout.connect(self._update_trace_animation)
        self._trace_timer.setInterval(16)  # ~60 FPS
        
        self._scanline_timer = QTimer(self)
        self._scanline_timer.timeout.connect(self._update_scanline_animation)
        self._scanline_timer.setInterval(33)  # ~30 FPS
        
        # Base style
        self.base_style = {
            "normal": (
                "background-color: #2196f3; "
                "color: white; "
                "border: 2px solid #43a047; "
                "border-radius: 8px; "
                "padding: 12px 0px; "
                "font-weight: bold; "
            ),
            "hover": "background-color: #43a047; color: white; border-color: #43a047;",
            "pressed": "background-color: #388e3c; color: white; border-color: #2e7d32;",
            "disabled": "background-color: #2196f3; color: #eeeeee; border-color: #bdbdbd;",
            "stop_normal": (
                "background-color: transparent; "
                "color: #d32f2f; "
                "border: 2px solid #d32f2f; "
                "border-radius: 8px; "
                "padding: 12px 0px; "
                "font-weight: bold; "
            ),
            "stop_hover": "background-color: #d32f2f; color: white; border-color: #b71c1c;",
            "stop_pressed": "background-color: #b71c1c; color: white; border-color: #9c0d0d;",
        }
        
        self._cached_stylesheet = None
        self.update_stylesheet()
        
    def set_gpu_available(self, available: bool):
        """Set whether GPU acceleration is available for current format"""
        self._gpu_available = available
        self.update()
        
    def enterEvent(self, event):
        """Handle mouse enter - start animations if GPU available"""
        self._is_hovered = True
        if self._gpu_available and "STOP" not in self.text().upper():
            self._trace_timer.start()
            self._scanline_timer.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Handle mouse leave - stop animations"""
        self._is_hovered = False
        self._trace_timer.stop()
        self._scanline_timer.stop()
        self._trace_offset = 0.0
        self._scanline_offset = 0.0
        self.update()
        super().leaveEvent(event)
        
    def _update_trace_animation(self):
        """Update circuit trace animation offset"""
        self._trace_offset += 0.02
        if self._trace_offset > 1.0:
            self._trace_offset = 0.0
        self.update()
        
    def _update_scanline_animation(self):
        """Update scanline animation offset"""
        self._scanline_offset += 2.0
        if self._scanline_offset > 20.0:
            self._scanline_offset = 0.0
        self.update()
        
    def paintEvent(self, event):
        """Custom paint to add GPU effects"""
        super().paintEvent(event)
        
        if not self._gpu_available or not self._is_hovered or "STOP" in self.text().upper():
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self._draw_circuit_trace(painter)
        self._draw_scanline_overlay(painter)
        self._draw_bolt_icon(painter)
        
        painter.end()
        
    def _draw_circuit_trace(self, painter):
        """Draw the animated circuit trace around the border"""
        pen = QPen(QColor("#00F3FF"))
        pen.setWidth(2)
        painter.setPen(pen)
        
        w, h = self.width(), self.height()
        perimeter = 2 * (w + h) - 16
        
        trace_pos = self._trace_offset * perimeter
        trace_length = perimeter * 0.15
        
        margin = 4
        corner_radius = 8
        
        points = self._get_border_points(trace_pos, trace_length, margin, corner_radius)
        
        if len(points) >= 2:
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])
                
    def _get_border_points(self, start_pos, length, margin, radius):
        """Get points along the border for circuit trace"""
        w, h = self.width() - margin * 2, self.height() - margin * 2
        perimeter = 2 * (w + h)
        
        points = []
        pos = start_pos
        remaining = length
        
        while remaining > 0 and len(points) < 50:
            pos = pos % perimeter
            
            if pos < w:
                x = margin + pos
                y = margin
            elif pos < w + h:
                x = margin + w
                y = margin + (pos - w)
            elif pos < 2 * w + h:
                x = margin + w - (pos - w - h)
                y = margin + h
            else:
                x = margin
                y = margin + h - (pos - 2 * w - h)
                
            points.append(QPoint(int(x), int(y)))
            pos += 3
            remaining -= 3
            
        return points
        
    def _draw_scanline_overlay(self, painter):
        """Draw subtle diagonal scanline pattern"""
        painter.setOpacity(0.08)
        pen = QPen(QColor("#00F3FF"))
        pen.setWidth(1)
        painter.setPen(pen)
        
        spacing = 10
        offset = int(self._scanline_offset)
        
        for i in range(-self.height(), self.width() + self.height(), spacing):
            x1 = i + offset
            y1 = 0
            x2 = i + self.height() + offset
            y2 = self.height()
            painter.drawLine(x1, y1, x2, y2)
            
        painter.setOpacity(1.0)
        
    def _draw_bolt_icon(self, painter):
        """Draw small bolt icon that lights up when GPU is active"""
        icon_size = 10
        x = self.width() - icon_size - 8
        y = 6
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#00F3FF")))
        
        bolt = [
            QPoint(x + 6, y),
            QPoint(x + 2, y + 5),
            QPoint(x + 5, y + 5),
            QPoint(x + 4, y + 10),
            QPoint(x + 8, y + 4),
            QPoint(x + 5, y + 4),
        ]
        painter.drawPolygon(bolt)
        
    def update_stylesheet(self):
        """Build stylesheet with CURRENT font values from font_manager"""
        text_upper = self.text().upper()
        if "STOP" in text_upper:
            stylesheet = (
                f"QPushButton {{ "
                f"{self.base_style['stop_normal']} "
                f"font-family: '{self._font_family}'; "
                f"font-size: {self._font_size}px; "
                f"}} "
                f"QPushButton:hover {{ {self.base_style['stop_hover']} }} "
                f"QPushButton:pressed {{ {self.base_style['stop_pressed']} }} "
                f"QPushButton:disabled {{ background-color: #2196f3; color: #eeeeee; border-color: #bdbdbd; }}"
            )
        else:
            stylesheet = (
                f"QPushButton {{ "
                f"{self.base_style['normal']} "
                f"font-family: '{self._font_family}'; "
                f"font-size: {self._font_size}px; "
                f"}} "
                f"QPushButton:hover {{ {self.base_style['hover']} }} "
                f"QPushButton:pressed {{ {self.base_style['pressed']} }} "
                f"QPushButton:disabled {{ {self.base_style['disabled']} }}"
            )
        
        if stylesheet != self._cached_stylesheet:
            self._cached_stylesheet = stylesheet
            self.setStyleSheet(stylesheet)
