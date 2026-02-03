"""
Presets Plugin - Category Filter Bar

Dynamic filter bar with exclusive toggle buttons for filtering presets by category.
Single selection mode with "ALL" button to show all presets.
"""
from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QButtonGroup,
    QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QPixmap

from client.plugins.presets.logic.models import PresetDefinition
from client.gui.theme import Theme


class CategoryFilterBar(QWidget):
    """
    Horizontal bar with category toggle buttons.
    
    Behavior:
    - Dynamically generates buttons from preset categories
    - Single selection (exclusive) - only one category active at a time
    - "ALL" button shows all presets (default state)
    - Blurs the preset cards behind it
    
    Signals:
        filterChanged: Emitted when selection changes
    """
    
    filterChanged = pyqtSignal()
    
    # Special key for "ALL" button
    ALL_KEY = "__all__"
    
    # Styling constants
    BUTTON_PADDING_H = 16  # Horizontal padding inside button
    BUTTON_PADDING_V = 8   # Vertical padding inside button
    BUTTON_SPACING = 8     # Gap between buttons
    BUTTON_HEIGHT = 32
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._selected_category: Optional[str] = None  # None or category name
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._blurred_bg = None
        self._is_capturing = False
        
        # Enable custom painting
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 12, 0, 16)
        self._layout.setSpacing(self.BUTTON_SPACING)
        
        # Center buttons with stretch on both sides
        self._layout.addStretch()
        self._layout.addStretch()
    
    def capture_blur(self):
        """
        Capture and blur the content behind this filter bar.
        Call this when the gallery shows or scrolls.
        """
        if self._is_capturing:
            return
        
        gallery = self.parent()
        if not gallery or not hasattr(gallery, '_scroll'):
            return
        
        self._is_capturing = True
        try:
            scroll_area = gallery._scroll
            
            # Hide self to capture what's behind
            self.hide()
            
            # Get the rect in scroll area coordinates
            # Filter bar is at (16, 16) relative to gallery
            # Scroll area also starts at (16, 16) due to margins
            # So capture from top of scroll viewport
            capture_rect = self.geometry()
            capture_rect.moveTopLeft(scroll_area.viewport().mapFromParent(
                gallery.mapFromParent(self.mapToParent(self.rect().topLeft()))
            ))
            
            # Grab from scroll viewport
            pixmap = scroll_area.viewport().grab(capture_rect)
            
            self.show()
            
            if pixmap.isNull():
                return
            
            # Downscale for performance
            scale = 4
            small = pixmap.scaled(
                pixmap.width() // scale, 
                pixmap.height() // scale,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Apply blur using QGraphicsBlurEffect
            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(small)
            blur = QGraphicsBlurEffect()
            blur.setBlurRadius(3)
            blur.setBlurHints(QGraphicsBlurEffect.BlurHint.PerformanceHint)
            item.setGraphicsEffect(blur)
            scene.addItem(item)
            
            # Render blurred result
            result = QPixmap(small.size())
            result.fill(Qt.GlobalColor.transparent)
            painter = QPainter(result)
            scene.render(painter)
            painter.end()
            
            self._blurred_bg = result
            self.update()
            
        finally:
            self._is_capturing = False
    
    def paintEvent(self, event):
        """Paint blurred background with transparency fade at bottom."""
        # Create a temporary pixmap to render content, then apply alpha mask
        content = QPixmap(self.size())
        content.fill(Qt.GlobalColor.transparent)
        
        content_painter = QPainter(content)
        content_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Rounded corners
        path = QPainterPath()
        radius = 8
        path.addRoundedRect(self.rect().toRectF(), radius, radius)
        content_painter.setClipPath(path)
        
        # Fill with dark grey matching gallery visual appearance
        # Gallery uses rgba(11,11,11,0.9) over blurred content
        content_painter.fillRect(self.rect(), QColor(35, 35, 35, 255))
        
        # Draw blurred background on top
        if self._blurred_bg and not self._blurred_bg.isNull():
            content_painter.drawPixmap(self.rect(), self._blurred_bg)
        
        # Light tint to match gallery overlay
        content_painter.fillRect(self.rect(), QColor(20, 20, 20, 180))
        
        content_painter.end()
        
        # Apply vertical alpha gradient mask (fade to transparent at bottom)
        mask = QPixmap(self.size())
        mask.fill(Qt.GlobalColor.transparent)
        mask_painter = QPainter(mask)
        
        # Gradient from opaque at top to transparent at bottom
        alpha_gradient = QLinearGradient(0, 0, 0, self.height())
        alpha_gradient.setColorAt(0.0, QColor(255, 255, 255, 255))  # Fully opaque
        alpha_gradient.setColorAt(0.6, QColor(255, 255, 255, 200))  # Still mostly opaque
        alpha_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))    # Fully transparent
        mask_painter.fillRect(self.rect(), alpha_gradient)
        mask_painter.end()
        
        # Apply mask to content using DestinationIn composition
        result_painter = QPainter(content)
        result_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        result_painter.drawPixmap(0, 0, mask)
        result_painter.end()
        
        # Draw final result to widget
        painter = QPainter(self)
        painter.drawPixmap(0, 0, content)
        painter.end()

    
    def set_categories(self, presets: List[PresetDefinition]) -> None:
        """
        Extract unique categories from presets and create buttons.
        
        Args:
            presets: List of preset definitions to extract categories from
        """
        # Clear existing buttons (but keep stretches)
        self._clear_buttons()
        
        # Extract unique categories
        categories = sorted(set(p.category for p in presets if p.category))
        
        # Insert buttons between the two stretches
        # Layout: [Stretch] [Buttons...] [Stretch]
        insert_index = 1  # After first stretch
        
        # Create "ALL" button first
        all_btn = self._create_button(self.ALL_KEY, "ALL")
        all_btn.setChecked(True)  # Default selection
        self._buttons[self.ALL_KEY] = all_btn
        self._button_group.addButton(all_btn)
        self._layout.insertWidget(insert_index, all_btn)
        insert_index += 1
        
        # Create buttons for each category
        for category in categories:
            display_name = category.upper()  # UPPERCASE labels
            btn = self._create_button(category, display_name)
            self._buttons[category] = btn
            self._button_group.addButton(btn)
            self._layout.insertWidget(insert_index, btn)
            insert_index += 1
        
        # Set initial state
        self._selected_category = None  # None = ALL
        self._update_button_styles()
    
    def _create_button(self, key: str, display_name: str) -> QPushButton:
        """Create a pill-shaped toggle button."""
        btn = QPushButton(display_name)
        btn.setCheckable(True)
        btn.setChecked(False)
        
        # Adaptive width: let Qt calculate based on text + padding
        btn.setFixedHeight(self.BUTTON_HEIGHT)
        btn.setStyleSheet(self._get_button_style(checked=False))
        
        # Connect click signal
        btn.clicked.connect(lambda checked, k=key: self._on_button_clicked(k))
        
        return btn
    
    def _on_button_clicked(self, key: str) -> None:
        """Handle button click - exclusive selection."""
        if key == self.ALL_KEY:
            self._selected_category = None
        else:
            self._selected_category = key
        
        # Update button styles
        self._update_button_styles()
        
        # Emit filter changed signal
        self.filterChanged.emit()
    
    def _update_button_styles(self) -> None:
        """Update all button styles based on selection."""
        for key, btn in self._buttons.items():
            is_selected = (key == self.ALL_KEY and self._selected_category is None) or \
                          (key == self._selected_category)
            btn.setStyleSheet(self._get_button_style(is_selected))
            btn.setChecked(is_selected)
    
    def _get_button_style(self, checked: bool) -> str:
        """Get CSS stylesheet for button based on state."""
        if checked:
            return f"""
                QPushButton {{
                    background-color: {Theme.success()};
                    color: {Theme.bg()};
                    border: none;
                    font-weight: bold;
                    font-size: {Theme.FONT_SIZE_SM}px;
                    border-radius: {self.BUTTON_HEIGHT // 2}px;
                    padding: {self.BUTTON_PADDING_V}px {self.BUTTON_PADDING_H}px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.success()};
                    opacity: 0.9;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background-color: {Theme.surface_element()};
                    color: {Theme.text_muted()};
                    border: 1px solid {Theme.border()};
                    font-size: {Theme.FONT_SIZE_SM}px;
                    border-radius: {self.BUTTON_HEIGHT // 2}px;
                    padding: {self.BUTTON_PADDING_V}px {self.BUTTON_PADDING_H}px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.color('surface_hover')};
                    color: {Theme.text()};
                }}
            """
    
    def get_active_categories(self) -> List[str]:
        """
        Get list of currently selected categories.
        
        Returns:
            List with single category name, or empty list for "ALL".
        """
        if self._selected_category is None:
            return []  # Empty = show all
        return [self._selected_category]
    
    def _clear_buttons(self) -> None:
        """Remove all existing buttons (preserve stretches)."""
        # Remove from button group first
        for btn in self._buttons.values():
            self._button_group.removeButton(btn)
            btn.deleteLater()
        self._buttons.clear()
        self._selected_category = None
        
        # Clear only button widgets, preserve the two stretch items
        # Layout structure: [Stretch] [Buttons...] [Stretch]
        # Remove items from index 1 to count-2 (preserve stretches at 0 and last)
        while self._layout.count() > 2:
            item = self._layout.takeAt(1)  # Always remove at index 1
            if item.widget():
                item.widget().deleteLater()
    
    def reset_filters(self) -> None:
        """Reset to 'ALL' state."""
        self._selected_category = None
        self._update_button_styles()
        self.filterChanged.emit()
