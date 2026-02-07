"""
Presets Plugin - Preset Card Widget

A 3:4 ratio card widget displaying preset information.
Based on .agent/preset_card_spec.md design specification.
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QIcon, QColor, QPainter

from client.plugins.presets.logic.models import PresetDefinition
from client.utils.resource_path import get_resource_path
from client.gui.theme import Theme
from client.gui.components.info_tooltip import TooltipHoverFilter
from client.gui.components.tooltips.preset_info import PRESET_MESSAGES


class PresetCard(QFrame):
    """
    Preset card widget following the 3:4 "Monolith" design.
    
    Layout:
    +---------------------------+
    |   [ ZONE A: ICON ]        |  1:1 square
    |   Centered glyph          |
    +---------------------------+
    |   [ ZONE B: TEXT ]        |  Remaining
    |   Title (bold)            |
    |   Subtitle (mono)         |
    +---------------------------+
    
    Signals:
        clicked: Emitted when card is clicked, passes PresetDefinition
    """
    
    clicked = pyqtSignal(object)  # Emits PresetDefinition
    
    # Card dimensions (3:4 ratio)
    CARD_WIDTH = 120
    CARD_HEIGHT = 160
    ICON_SIZE = 65  # Increased by ~35% from 48
    
    def __init__(self, preset: PresetDefinition, parent=None):
        super().__init__(parent)
        self._preset = preset
        self._is_available = preset.is_available
        
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setObjectName("PresetCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._setup_ui()
        self._apply_styles()
        
        # Ghost effect and badge for unavailable presets
        if not self._is_available:
            self._apply_ghost_effect()
            self._add_unavailable_badge()
            self._attach_tooltip()
    
    def _setup_ui(self):
        """Setup the card layout with icon and text zones."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(0)
        
        # Zone A: Icon Chamber (stretch factor 3)
        self.icon_label = QLabel()
        self.icon_label.setObjectName("CardIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_icon()
        layout.addWidget(self.icon_label, 3)
        
        # Zone B: Text Base (stretch factor 1)
        self.title_label = QLabel(self._preset.name.upper())
        self.title_label.setObjectName("CardTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.title_label, 0)
    
    def _load_icon(self, color: QColor = None):
        """Load the preset icon with optional color override.
        
        Args:
            color: QColor to apply to the icon. If None, uses Theme.text()
        """
        if color is None:
            color = QColor(Theme.text())
        
        icon_name = self._preset.style.icon
        
        # Try to load from assets
        icon_path = get_resource_path(f"client/assets/icons/{icon_name}.svg")
        
        try:
            if icon_path:
                from PyQt6.QtSvg import QSvgRenderer
                from PyQt6.QtCore import QByteArray, QRectF
                
                # Read SVG file
                with open(icon_path, 'r', encoding='utf-8') as f:
                    svg_content = f.read()
                
                # Replace color values in SVG with theme color
                # Only replace actual color values (hex, rgb, named colors), NOT "none"
                import re
                
                # Replace fill with color values (but preserve fill="none")
                svg_content = re.sub(
                    r'fill="(?!none)[^"]*"', 
                    f'fill="{color.name()}"', 
                    svg_content
                )
                
                # Replace stroke with color values (but preserve stroke="none")
                svg_content = re.sub(
                    r'stroke="(?!none)[^"]*"', 
                    f'stroke="{color.name()}"', 
                    svg_content
                )
                
                # Replace style attribute colors
                svg_content = re.sub(
                    r'(fill|stroke):(?!none)[^;}"]+', 
                    fr'\1:{color.name()}', 
                    svg_content
                )
                
                # Render SVG to pixmap
                renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
                pixmap = QPixmap(self.ICON_SIZE, self.ICON_SIZE)
                pixmap.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                # Calculate aspect-ratio preserved rect
                default_size = renderer.defaultSize()
                if not default_size.isEmpty():
                    aspect = default_size.width() / default_size.height()
                    
                    if aspect > 1:
                        # Wider than tall
                        w = self.ICON_SIZE
                        h = self.ICON_SIZE / aspect
                    else:
                        # Taller than wide
                        h = self.ICON_SIZE
                        w = self.ICON_SIZE * aspect
                        
                    x = (self.ICON_SIZE - w) / 2
                    y = (self.ICON_SIZE - h) / 2
                    target_rect = QRectF(x, y, w, h)
                    renderer.render(painter, target_rect)
                else:
                    renderer.render(painter)
                    
                painter.end()
                
                self.icon_label.setPixmap(pixmap)
            else:
                # Fallback: use first letter as icon
                self.icon_label.setText(self._preset.name[0].upper())
                self.icon_label.setStyleSheet(f"""
                    font-size: 32px;
                    font-weight: bold;
                    color: {color.name()};
                """)
        except Exception as e:
            # Fallback on any error
            self.icon_label.setText(self._preset.name[0].upper())
            self.icon_label.setStyleSheet(f"""
                font-size: 32px;
                font-weight: bold;
                color: {color.name()};
            """)
    
    def _apply_styles(self):
        """Apply the card styling from design spec."""
        accent = self._preset.style.accent_color
        
        self.setStyleSheet(f"""
            QFrame#PresetCard {{
                background-color: {Theme.surface_element()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_LG}px;
            }}
            QFrame#PresetCard:hover {{
                background-color: {Theme.color('surface_hover')};
                border: 1px solid {Theme.border_focus()};
            }}
            QLabel#CardIcon {{
                background-color: transparent;
                padding: 10px;
            }}
            QLabel#CardTitle {{
                color: {Theme.text()};
                font-size: {Theme.FONT_SIZE_SM}px;
                font-weight: bold;
                background: transparent;
                margin-bottom: 2px;
            }}
        """)
    
    def _apply_ghost_effect(self):
        """Apply ghost effect for unavailable presets."""
        opacity = QGraphicsOpacityEffect(self)
        opacity.setOpacity(0.5)  # 50% opacity for disabled state
        self.setGraphicsEffect(opacity)
        self.setCursor(Qt.CursorShape.ForbiddenCursor)
    
    def _add_unavailable_badge(self):
        """Add badge overlay indicating why preset is unavailable."""
        # Determine badge text based on missing tools
        if self._preset.missing_tools:
            if "GPU (NVIDIA/AMD/Intel)" in self._preset.missing_tools:
                badge_text = "GPU REQUIRED"
                badge_color = Theme.warning()
            else:
                badge_text = "TOOL MISSING"
                badge_color = Theme.error()
        else:
            badge_text = "UNAVAILABLE"
            badge_color = Theme.text_muted()
        
        # Create badge label
        self.badge_label = QLabel(badge_text)
        self.badge_label.setParent(self)
        self.badge_label.setObjectName("UnavailableBadge")
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Position badge at bottom of card
        badge_height = 20
        self.badge_label.setGeometry(
            0, 
            self.CARD_HEIGHT - badge_height, 
            self.CARD_WIDTH, 
            badge_height
        )
        
        # Style badge
        self.badge_label.setStyleSheet(f"""
            QLabel#UnavailableBadge {{
                background-color: {badge_color};
                color: {Theme.surface()};
                font-size: {Theme.FONT_SIZE_XS}px;
                font-weight: bold;
                border-bottom-left-radius: {Theme.RADIUS_LG}px;
                border-bottom-right-radius: {Theme.RADIUS_LG}px;
                padding: 2px;
            }}
        """)
        
        self.badge_label.show()
    
    def _attach_tooltip(self):
        """Attach InfoTooltip explaining why preset is unavailable."""
        if self._preset.missing_tools and "GPU (NVIDIA/AMD/Intel)" in self._preset.missing_tools:
            # GPU required tooltip
            self.tooltip_filter = TooltipHoverFilter(
                self, 
                PRESET_MESSAGES["gpu_required"],
                simple_mode=True
            )
        elif self._preset.missing_tools:
            # Missing tool tooltip
            tool_names = ", ".join(self._preset.missing_tools)
            tooltip_data = {
                "title": "Tool Not Found",
                "message": f"Required tool(s) not available: {tool_names}",
                "icon": "error"
            }
            self.tooltip_filter = TooltipHoverFilter(
                self,
                tooltip_data,
                simple_mode=True
            )
    
    def set_drag_active(self, active: bool):
        """Set drag-active state for visual feedback."""
        if active:
            self.setStyleSheet(self.styleSheet() + f"""
                QFrame#PresetCard {{
                    background-color: rgba(0, 224, 255, 0.1);
                    border: 2px solid {Theme.accent_turbo()};
                }}
            """)
        else:
            self._apply_styles()
    
    def mousePressEvent(self, event):
        """Handle click - emit preset."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_available:
            self.clicked.emit(self._preset)
        super().mousePressEvent(event)
    
    @property
    def preset(self) -> PresetDefinition:
        """Get the preset definition."""
        return self._preset
    
    def update_theme(self, is_dark: bool):
        """Update card styling when theme changes."""
        Theme.set_dark_mode(is_dark)
        self._apply_styles()
        # Reload icon with new theme color
        self._load_icon()
