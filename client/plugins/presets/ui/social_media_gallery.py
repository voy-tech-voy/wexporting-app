"""
Social Media Gallery - 2-Step Selection Flow

Step 1: Select aspect ratio (4 cards: 9:16, 3:4, 1:1, 16:9)
Step 2: Select platform (5 cards: Instagram, TikTok, X, YouTube, LinkedIn)
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QSize
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray

from typing import Optional, Dict, List
from pathlib import Path
from client.gui.theme import Theme
from client.utils.resource_path import get_resource_path


class SocialRatioCard(QFrame):
    """Card for aspect ratio selection (Step 1)."""
    
    clicked = pyqtSignal(str)  # Emits ratio_id like "9x16"
    
    CARD_WIDTH = 120
    CARD_HEIGHT = 140
    ICON_SIZE = 48
    
    def __init__(self, ratio_id: str, label: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._ratio_id = ratio_id
        self._label = label
        self._icon_name = icon_name
        
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setObjectName("SocialRatioCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)
        
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_icon()
        layout.addWidget(self.icon_label, 1)
        
        # Label
        self.title_label = QLabel(self._label)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("CardTitle")
        layout.addWidget(self.title_label)
    
    def _load_icon(self):
        """Load SVG icon with theme color."""
        icon_path = get_resource_path(f"client/assets/icons/{self._icon_name}.svg")
        color = QColor(Theme.text())
        
        try:
            if icon_path and Path(icon_path).exists():
                import re
                with open(icon_path, 'r', encoding='utf-8') as f:
                    svg_content = f.read()
                
                # Replace colors
                svg_content = re.sub(r'fill="(?!none)[^"]*"', f'fill="{color.name()}"', svg_content)
                svg_content = re.sub(r'stroke="(?!none)[^"]*"', f'stroke="{color.name()}"', svg_content)
                
                renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
                pixmap = QPixmap(self.ICON_SIZE, self.ICON_SIZE)
                pixmap.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer.render(painter)
                painter.end()
                
                self.icon_label.setPixmap(pixmap)
            else:
                self.icon_label.setText(self._ratio_id)
        except Exception:
            self.icon_label.setText(self._ratio_id)
    
    def _apply_styles(self):
        self.setStyleSheet(f"""
            QFrame#SocialRatioCard {{
                background-color: {Theme.surface_element()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_LG}px;
            }}
            QFrame#SocialRatioCard:hover {{
                background-color: {Theme.color('surface_hover')};
                border: 1px solid {Theme.border_focus()};
            }}
            QLabel#CardTitle {{
                color: {Theme.text()};
                font-size: {Theme.FONT_SIZE_SM}px;
                font-weight: bold;
                background: transparent;
            }}
        """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._ratio_id)
        super().mousePressEvent(event)
    
    def update_theme(self, is_dark: bool):
        Theme.set_dark_mode(is_dark)
        self._apply_styles()
        self._load_icon()


class SocialPlatformCard(QFrame):
    """Card for platform selection (Step 2)."""
    
    clicked = pyqtSignal(str, str)  # Emits (platform_id, ratio_id)
    
    CARD_WIDTH = 100
    CARD_HEIGHT = 120
    ICON_SIZE = 40
    
    def __init__(self, platform_id: str, label: str, icon_name: str, accent_color: str, parent=None):
        super().__init__(parent)
        self._platform_id = platform_id
        self._label = label
        self._icon_name = icon_name
        self._accent_color = accent_color
        self._ratio_id = ""  # Set when step 2 is shown
        
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setObjectName("SocialPlatformCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._setup_ui()
        self._apply_styles()
    
    def set_ratio(self, ratio_id: str):
        """Set the ratio context for this platform card."""
        self._ratio_id = ratio_id
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(6)
        
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_icon()
        layout.addWidget(self.icon_label, 1)
        
        # Label
        self.title_label = QLabel(self._label)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("PlatformTitle")
        layout.addWidget(self.title_label)
    
    def _load_icon(self):
        """Load SVG icon with platform accent color."""
        icon_path = get_resource_path(f"client/assets/icons/{self._icon_name}.svg")
        color = QColor(self._accent_color)
        
        try:
            if icon_path and Path(icon_path).exists():
                import re
                with open(icon_path, 'r', encoding='utf-8') as f:
                    svg_content = f.read()
                
                svg_content = re.sub(r'fill="(?!none)[^"]*"', f'fill="{color.name()}"', svg_content)
                svg_content = re.sub(r'stroke="(?!none)[^"]*"', f'stroke="{color.name()}"', svg_content)
                
                renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
                pixmap = QPixmap(self.ICON_SIZE, self.ICON_SIZE)
                pixmap.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer.render(painter)
                painter.end()
                
                self.icon_label.setPixmap(pixmap)
            else:
                self.icon_label.setText(self._platform_id[0].upper())
        except Exception:
            self.icon_label.setText(self._platform_id[0].upper())
    
    def _apply_styles(self):
        self.setStyleSheet(f"""
            QFrame#SocialPlatformCard {{
                background-color: {Theme.surface_element()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_LG}px;
            }}
            QFrame#SocialPlatformCard:hover {{
                background-color: {Theme.color('surface_hover')};
                border: 2px solid {self._accent_color};
            }}
            QLabel#PlatformTitle {{
                color: {Theme.text()};
                font-size: {Theme.FONT_SIZE_XS}px;
                font-weight: 600;
                background: transparent;
            }}
        """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._platform_id, self._ratio_id)
        super().mousePressEvent(event)
    
    def update_theme(self, is_dark: bool):
        Theme.set_dark_mode(is_dark)
        self._apply_styles()
        self._load_icon()


class SocialMediaGallery(QWidget):
    """
    2-step social media preset selection widget.
    
    Step 1: Select aspect ratio (9:16, 3:4, 1:1, 16:9)
    Step 2: Select platform (Instagram, TikTok, X, YouTube, LinkedIn)
    
    Signals:
        preset_selected: Emits (platform_id, ratio_id) when a preset is chosen
        back_requested: Emitted when user wants to go back from step 2 to step 1
    """
    
    preset_selected = pyqtSignal(str, str)  # (platform_id, ratio_id)
    back_requested = pyqtSignal()
    
    ANIMATION_DURATION = 150
    
    # Ratio definitions
    RATIOS = [
        {"id": "9x16", "label": "Reel 9:16", "icon": "916"},
        {"id": "3x4", "label": "Story 3:4", "icon": "34"},
        {"id": "1x1", "label": "Square 1:1", "icon": "11"},
        {"id": "16x9", "label": "Wide 16:9", "icon": "169"},
    ]
    
    # Platform definitions
    PLATFORMS = [
        {"id": "instagram", "label": "Instagram", "icon": "insta", "color": "#E1306C"},
        {"id": "tiktok", "label": "TikTok", "icon": "tik", "color": "#00F2EA"},
        {"id": "x", "label": "X", "icon": "X_icon", "color": "#FFFFFF"},
        {"id": "youtube", "label": "YouTube", "icon": "yt", "color": "#FF0000"},
        {"id": "linkedin", "label": "LinkedIn", "icon": "in", "color": "#0A66C2"},
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_step = 1
        self._selected_ratio: Optional[str] = None
        self._ratio_cards: List[SocialRatioCard] = []
        self._platform_cards: List[SocialPlatformCard] = []
        
        self._setup_ui()
        self._create_ratio_cards()
        self._create_platform_cards()
        self._show_step(1)
    
    def _setup_ui(self):
        self.setObjectName("SocialMediaGallery")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Container for cards (ratio or platform)
        self._cards_container = QWidget()
        self._cards_layout = QHBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(self._cards_container, 1)
        
        self._apply_styles()
    
    def _apply_styles(self):
        self.setStyleSheet(f"""
            QWidget#SocialMediaGallery {{
                background: transparent;
            }}
        """)
    
    def _create_ratio_cards(self):
        """Create the 4 ratio selection cards."""
        for ratio in self.RATIOS:
            card = SocialRatioCard(
                ratio_id=ratio["id"],
                label=ratio["label"],
                icon_name=ratio["icon"]
            )
            card.clicked.connect(self._on_ratio_selected)
            self._ratio_cards.append(card)
    
    def _create_platform_cards(self):
        """Create the 5 platform selection cards."""
        for platform in self.PLATFORMS:
            card = SocialPlatformCard(
                platform_id=platform["id"],
                label=platform["label"],
                icon_name=platform["icon"],
                accent_color=platform["color"]
            )
            card.clicked.connect(self._on_platform_selected)
            self._platform_cards.append(card)
    
    def _show_step(self, step: int):
        """Show the specified step with animation."""
        self._current_step = step
        
        # Safely clear current cards from layout
        if self._cards_layout is not None:
            try:
                while self._cards_layout.count():
                    item = self._cards_layout.takeAt(0)
                    if item and item.widget():
                        item.widget().setParent(None)
            except RuntimeError:
                # Layout was deleted, ignore
                pass
        
        if step == 1:
            # Add ratio cards
            for card in self._ratio_cards:
                self._cards_layout.addWidget(card)
                card.show()
        else:
            # Add platform cards with ratio context
            for card in self._platform_cards:
                card.set_ratio(self._selected_ratio)
                self._cards_layout.addWidget(card)
                card.show()
    
    def _on_ratio_selected(self, ratio_id: str):
        """Handle ratio card click - transition to step 2."""
        self._selected_ratio = ratio_id
        self._animate_transition(to_step=2)
    
    def _on_platform_selected(self, platform_id: str, ratio_id: str):
        """Handle platform card click - emit preset selection."""
        self.preset_selected.emit(platform_id, ratio_id)
    

    def _animate_transition(self, to_step: int):
        """Animate fade transition between steps."""
        # Create opacity effect
        effect = QGraphicsOpacityEffect(self._cards_container)
        self._cards_container.setGraphicsEffect(effect)
        
        # Fade out
        fade_out = QPropertyAnimation(effect, b"opacity")
        fade_out.setDuration(self.ANIMATION_DURATION)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        def on_fade_out_finished():
            self._show_step(to_step)
            
            # Fade in
            fade_in = QPropertyAnimation(effect, b"opacity")
            fade_in.setDuration(self.ANIMATION_DURATION)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.InQuad)
            fade_in.finished.connect(lambda: self._cards_container.setGraphicsEffect(None))
            fade_in.start()
            self._fade_in_anim = fade_in  # Keep reference
        
        fade_out.finished.connect(on_fade_out_finished)
        fade_out.start()
        self._fade_out_anim = fade_out  # Keep reference
    
    def reset(self):
        """Reset to step 1."""
        self._selected_ratio = None
        self._show_step(1)
    
    def update_theme(self, is_dark: bool):
        """Update theme for all components."""
        Theme.set_dark_mode(is_dark)
        self._apply_styles()
        
        for card in self._ratio_cards:
            card.update_theme(is_dark)
        for card in self._platform_cards:
            card.update_theme(is_dark)
