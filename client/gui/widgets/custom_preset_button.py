"""
Custom Preset Button - Simple button for creating custom presets from Lab Mode.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont
from client.gui.effects.glow_effect import GlowEffectManager, GlowState
from client.utils.font_manager import FONT_FAMILY


class CustomPresetButton(QWidget):
    """
    Simple circular button with "+" icon for creating custom presets.
    Features Siri-style glow effect on hover.
    """
    clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 44)
        self.setToolTip("Create Custom Preset\nSaves current Lab Mode settings")
        
        # State
        self._is_hovered = False
        
        # Track theme
        from client.utils.theme_utils import is_dark_mode
        self._is_dark = is_dark_mode()
        
        # Glow Effect Manager
        self._glow_manager = None
    
    def _setup_glow(self):
        """Create the glow effect manager"""
        if self._glow_manager is not None:
            return
            
        # Get the top-level window (MainWindow)
        top_window = self.window()
        if top_window is None or top_window == self:
            # Retry later if window not ready
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._setup_glow)
            return
            
        # Initialize the manager
        self._glow_manager = GlowEffectManager(self, top_window)
        # Force initial position update
        self._update_glow_position()
    
    def _update_glow_position(self):
        """Update glow position"""
        if self._glow_manager:
            self._glow_manager.update_position()
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            if self._glow_manager:
                self._glow_manager.set_state(GlowState.CLICKED)
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def moveEvent(self, event):
        """Update glow position when button moves"""
        super().moveEvent(event)
        self._update_glow_position()
    
    def resizeEvent(self, event):
        """Update glow position when button resizes"""
        super().resizeEvent(event)
        self._update_glow_position()
        
    def hideEvent(self, event):
        """Hide glow when button is hidden"""
        super().hideEvent(event)
        if self._glow_manager:
            self._glow_manager.hide()
            
    def showEvent(self, event):
        """Show/create glow when button is shown"""
        super().showEvent(event)
        if self._glow_manager is None:
            self._setup_glow()
        else:
            self._glow_manager.show()
            # Force position update after show
            from PySide6.QtCore import QTimer
            QTimer.singleShot(10, self._update_glow_position)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        radius = w / 2
        
        # Background
        if self._is_dark:
            bg_color = QColor(255, 255, 255, 12)  # Ghost white
            border_color = QColor(255, 255, 255, 50)
            icon_color = QColor(255, 255, 255, 150)
            
            if self._is_hovered:
                bg_color = QColor(255, 255, 255, 25)
                border_color = QColor(255, 255, 255, 100)
                icon_color = QColor(255, 255, 255, 255)
        else:
            bg_color = QColor(0, 0, 0, 8)  # Ghost black
            border_color = QColor(0, 0, 0, 30)
            icon_color = QColor(0, 0, 0, 150)
            
            if self._is_hovered:
                bg_color = QColor(0, 0, 0, 15)
                border_color = QColor(0, 0, 0, 80)
                icon_color = QColor(0, 0, 0, 255)
        
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))
        painter.drawEllipse(1, 1, w-2, h-2)
        
        # Draw "+" icon
        painter.setPen(QPen(icon_color, 2))
        center_x = w / 2
        center_y = h / 2
        icon_size = 12
        
        # Horizontal line
        painter.drawLine(
            int(center_x - icon_size/2), int(center_y),
            int(center_x + icon_size/2), int(center_y)
        )
        
        # Vertical line
        painter.drawLine(
            int(center_x), int(center_y - icon_size/2),
            int(center_x), int(center_y + icon_size/2)
        )
    
    def enterEvent(self, event):
        self._is_hovered = True
        if self._glow_manager:
            self._glow_manager.set_state(GlowState.HOVER)
        self.update()
    
    def leaveEvent(self, event):
        self._is_hovered = False
        if self._glow_manager:
            self._glow_manager.set_state(GlowState.IDLE)
        self.update()
    
    def deleteLater(self):
        """Clean up glow manager"""
        if self._glow_manager:
            self._glow_manager.cleanup()
        super().deleteLater()
    
    def update_theme(self, is_dark):
        """Update theme state"""
        self._is_dark = is_dark
        self.update()
