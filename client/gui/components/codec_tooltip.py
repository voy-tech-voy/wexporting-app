"""
Codec Efficiency Tooltip Component

A rich tooltip widget that displays codec efficiency comparisons
when hovering over format/codec selectors.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QObject, QEvent, QPoint
from PyQt6.QtGui import QColor

from client.gui.theme import Theme


class CodecEfficiencyTooltip(QWidget):
    """
    A rich popup widget showing a comparative bar chart of codec efficiency.
    Designed to explain 'Quality per MB' to the user.
    """
    
    # Configuration data for different modes
    PRESETS = {
        "video": {
            "title": "Video Codec Efficiency",
            "desc": "Higher efficiency = better quality at same file size",
            "items": [
                ("H.264", 40, "warning", "Standard"),
                ("H.265", 70, "info", "Better"),
                ("AV1", 100, "success", "Best")
            ]
        },
        "loop": {
            "title": "Loop Format Efficiency",
            "desc": "WebM provides HD quality for same size as low-res GIF",
            "items": [
                ("GIF", 15, "error", "Poor"),
                ("WebM", 100, "success", "Excellent")
            ]
        },
        "image": {
            "title": "Image Format Efficiency",
            "desc": "WebP offers best quality-to-size ratio",
            "items": [
                ("PNG", 30, "warning", "Lossless"),
                ("JPEG", 60, "info", "Standard"),
                ("WebP", 100, "success", "Best")
            ]
        }
    }
    
    # Color mapping from semantic names to Theme colors
    COLOR_MAP = {
        "success": lambda: Theme.success(),
        "info": lambda: Theme.color("info") if Theme.color("info") != "#FF00FF" else "#3498db",
        "warning": lambda: Theme.warning(),
        "error": lambda: Theme.error()
    }
    
    def __init__(self, parent=None):
        super().__init__(
            parent, 
            Qt.WindowType.ToolTip | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI components."""
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Container Frame
        self.container = QFrame()
        self._update_styles()
        
        # Drop Shadow for depth (adjust opacity based on theme)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 5)
        # Lighter shadow in light mode
        shadow_opacity = 150 if Theme.is_dark() else 80
        shadow.setColor(QColor(0, 0, 0, shadow_opacity))
        self.container.setGraphicsEffect(shadow)
        
        self.inner_layout = QVBoxLayout(self.container)
        self.inner_layout.setSpacing(Theme.SPACING_SM)
        self.inner_layout.setContentsMargins(
            Theme.SPACING_LG, 
            Theme.SPACING_LG, 
            Theme.SPACING_LG, 
            Theme.SPACING_LG
        )
        
        # Title
        self.lbl_title = QLabel("Codec Efficiency")
        self.lbl_title.setStyleSheet(f"""
            font-weight: bold; 
            font-size: {Theme.FONT_SIZE_BASE}px; 
            color: {Theme.text()};
        """)
        self.inner_layout.addWidget(self.lbl_title)
        
        # Bars Container (Dynamic)
        self.bars_layout = QVBoxLayout()
        self.bars_layout.setSpacing(6)
        self.inner_layout.addLayout(self.bars_layout)
        
        # Description Text
        self.lbl_desc = QLabel("Description")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet(f"""
            color: {Theme.text_muted()}; 
            font-size: {Theme.FONT_SIZE_SM}px; 
            margin-top: 5px;
        """)
        self.inner_layout.addWidget(self.lbl_desc)
        
        self.layout.addWidget(self.container)
    
    def _update_styles(self):
        """Update styles based on current theme."""
        # Use brighter background in dark mode (#2b2b2b instead of surface)
        # Use tooltip_bg in light mode
        if Theme.is_dark():
            bg_color = "#2b2b2b"  # Brighter than default surface (#161616)
        else:
            bg_color = Theme.color("tooltip_bg")
        
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_LG}px;
            }}
            QLabel {{
                color: {Theme.text()};
                font-family: '{Theme.FONT_BODY}';
                border: none;
                background: transparent;
            }}
        """)
    
    def set_mode(self, mode: str):
        """
        Build the bars based on the selected mode.
        
        Args:
            mode: One of "video", "loop", or "image"
        """
        if mode not in self.PRESETS:
            return
        
        data = self.PRESETS[mode]
        self.lbl_title.setText(data["title"])
        self.lbl_desc.setText(data["desc"])
        
        # Clear previous bars
        while self.bars_layout.count():
            item = self.bars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add Comparison Bars
        for name, val, color_key, note in data["items"]:
            row = QFrame()
            row.setStyleSheet("background: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            
            # Codec Name
            lbl_name = QLabel(name)
            lbl_name.setFixedWidth(50)
            lbl_name.setStyleSheet(f"""
                font-weight: bold; 
                font-size: {Theme.FONT_SIZE_SM}px;
                color: {Theme.text()};
            """)
            
            # Get color from theme
            color = self.COLOR_MAP.get(color_key, lambda: Theme.text())()
            
            # Progress Bar
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(val)
            pbar.setFixedHeight(6)
            pbar.setTextVisible(False)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {Theme.surface_element()};
                    border-radius: {Theme.RADIUS_SM}px;
                    border: none;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: {Theme.RADIUS_SM}px;
                }}
            """)
            
            # Context Note
            lbl_note = QLabel(note)
            lbl_note.setStyleSheet(f"""
                font-size: {Theme.FONT_SIZE_XS}px; 
                color: {Theme.text_muted()};
            """)
            
            row_layout.addWidget(lbl_name)
            row_layout.addWidget(pbar, 1)  # Expand bar
            row_layout.addWidget(lbl_note)
            
            self.bars_layout.addWidget(row)


class TooltipHoverFilter(QObject):
    """
    Event filter to attach the CodecEfficiencyTooltip to any widget.
    Shows tooltip on hover, hides on leave.
    """
    
    def __init__(self, target_widget, mode="video"):
        """
        Initialize the hover filter.
        
        Args:
            target_widget: Widget to attach tooltip to
            mode: Tooltip mode ("video", "loop", or "image")
        """
        super().__init__(target_widget)
        self.target = target_widget
        self.tooltip = CodecEfficiencyTooltip(None)
        self.tooltip.set_mode(mode)
        self.target.installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Handle hover events to show/hide tooltip."""
        if obj == self.target:
            if event.type() == QEvent.Type.Enter:
                # Calculate Position
                pos = self.target.mapToGlobal(QPoint(0, self.target.height()))
                # Add slight offset so it doesn't overlap the mouse immediately
                self.tooltip.move(pos.x(), pos.y() + 5)
                self.tooltip.show()
                return True
            elif event.type() == QEvent.Type.Leave:
                self.tooltip.hide()
                return True
        return super().eventFilter(obj, event)
