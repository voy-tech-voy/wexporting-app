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
        
        # DEBUG MODE - Set to False for production
        self._debug_mode = False
        
        # Prevent Qt from painting any background - we handle it in paintEvent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        
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
            filter_pos_in_gallery = self.pos()
            scroll_pos_in_gallery = scroll_area.pos()
            
            # Calculate offset
            offset_x = filter_pos_in_gallery.x() - scroll_pos_in_gallery.x()
            offset_y = filter_pos_in_gallery.y() - scroll_pos_in_gallery.y()
            
            from PyQt6.QtCore import QRect
            capture_rect = QRect(offset_x, offset_y, self.width(), self.height())
            
            # Grab from scroll viewport
            pixmap = scroll_area.viewport().grab(capture_rect)
            
            self.show()
            
            if pixmap.isNull():
                return
            
            # Simple blur via downscale + upscale
            from client.gui.theme_variables import get_color
            from client.gui.theme_manager import ThemeManager
            is_dark = ThemeManager.instance().is_dark_mode()
            
            scale = int(get_color("gallery_filter_blur_scale", is_dark))
            blur_passes = int(get_color("gallery_filter_blur_radius", is_dark))
            
            # Downscale for blur effect
            small = pixmap.scaled(
                pixmap.width() // scale, 
                pixmap.height() // scale,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Apply multiple downscale passes for stronger blur
            current = small
            for _ in range(blur_passes):
                if current.width() > 4 and current.height() > 4:
                    current = current.scaled(
                        current.width() // 2,
                        current.height() // 2,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
            
            # Scale back up - creates blur effect
            self._blurred_bg = current.scaled(
                pixmap.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.update()
            
        finally:
            self._is_capturing = False
    
    def paintEvent(self, event):
        """Paint blurred background with tunable gradient mask that fades cards underneath."""
        from client.gui.theme_variables import get_color
        from client.gui.theme_manager import ThemeManager
        
        is_dark = ThemeManager.instance().is_dark_mode()
        
        # Get tunable mask parameters - Default to Opaque Top / Transparent Bottom
        try:
            mask_top = int(get_color("gallery_filter_mask_top_alpha", is_dark))
            mask_bottom = int(get_color("gallery_filter_mask_bottom_alpha", is_dark))
            debug_mask = int(get_color("gallery_filter_debug_mask", is_dark)) == 1
        except (ValueError, TypeError):
            mask_top = 255
            mask_bottom = 0
            debug_mask = False

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Rounded corners clipping
        path = QPainterPath()
        radius = 8
        path.addRoundedRect(self.rect().toRectF(), radius, radius)
        painter.setClipPath(path)
        
        # Get filter bar background color for solid overlay
        filter_bg = get_color("gallery_filter_bg", is_dark)
        filter_overlay = get_color("gallery_filter_overlay", is_dark)
        try:
            filter_overlay_alpha = int(get_color("gallery_filter_overlay_alpha", is_dark))
        except (ValueError, TypeError):
            filter_overlay_alpha = 180
        
        # Parse hex color
        bg_color = QColor(filter_bg)
        bg_r, bg_g, bg_b = bg_color.red(), bg_color.green(), bg_color.blue()
        
        # Parse overlay color  
        overlay_color = QColor(filter_overlay)
        ov_r, ov_g, ov_b = overlay_color.red(), overlay_color.green(), overlay_color.blue()
        
        # 1. Draw solid background with gradient alpha - this fades/multiplies the cards underneath
        solid_gradient = QLinearGradient(0, 0, 0, self.height())
        solid_gradient.setColorAt(0.0, QColor(bg_r, bg_g, bg_b, mask_top))
        solid_gradient.setColorAt(1.0, QColor(bg_r, bg_g, bg_b, mask_bottom))
        painter.fillRect(self.rect(), solid_gradient)
        
        # 1.5. Draw overlay tint on top of background
        overlay_gradient = QLinearGradient(0, 0, 0, self.height())
        overlay_gradient.setColorAt(0.0, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, mask_top)))
        overlay_gradient.setColorAt(1.0, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, mask_bottom)))
        painter.fillRect(self.rect(), overlay_gradient)
        
        # 2. Draw blur with gradient mask on top
        if self._blurred_bg and not self._blurred_bg.isNull():
            # Create temporary pixmap for masking
            blurred_masked = QPixmap(self._blurred_bg.size())
            blurred_masked.fill(Qt.GlobalColor.transparent)
            
            # Draw the full blur
            mask_painter = QPainter(blurred_masked)
            mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            mask_painter.drawPixmap(0, 0, self._blurred_bg)
            
            # Multiply Alpha with Gradient
            mask_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            
            alpha_gradient = QLinearGradient(0, 0, 0, self.height())
            alpha_gradient.setColorAt(0.0, QColor(0, 0, 0, mask_top))
            alpha_gradient.setColorAt(1.0, QColor(0, 0, 0, mask_bottom))
            
            mask_painter.fillRect(blurred_masked.rect(), alpha_gradient)
            mask_painter.end()
            
            # Paint the masked blur
            painter.drawPixmap(0, 0, blurred_masked)
        
        # DEBUG MODE: Show the gradient rectangle ON TOP of everything
        if debug_mask:
            # Create semi-transparent gradient overlay with colors
            debug_gradient = QLinearGradient(0, 0, 0, self.height())
            top_color = QColor(255, 0, 0, min(mask_top, 200))  # Red
            bottom_color = QColor(0, 255, 0, min(mask_bottom, 200))  # Green
            
            debug_gradient.setColorAt(0.0, top_color)
            debug_gradient.setColorAt(1.0, bottom_color)
            
            painter.fillRect(self.rect(), debug_gradient)
            
            # Draw debug text
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(10, 20, f"GRADIENT: Top={mask_top} → Bottom={mask_bottom}")
        
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
        from client.gui.theme_variables import get_color
        from client.gui.theme_manager import ThemeManager
        
        is_dark = ThemeManager.instance().is_dark_mode()
        
        # Get button colors from theme
        active_bg = get_color("gallery_filter_btn_active_bg", is_dark)
        active_text = get_color("gallery_filter_btn_active_text", is_dark)
        inactive_bg = get_color("gallery_filter_btn_inactive_bg", is_dark)
        inactive_text = get_color("gallery_filter_btn_inactive_text", is_dark)
        border_color = get_color("gallery_filter_btn_border", is_dark)
        
        if checked:
            # Opaque active button (green)
            return f"""
                QPushButton {{
                    background-color: {active_bg};
                    color: {active_text};
                    border: none;
                    font-weight: bold;
                    font-size: {Theme.FONT_SIZE_SM}px;
                    border-radius: {self.BUTTON_HEIGHT // 2}px;
                    padding: {self.BUTTON_PADDING_V}px {self.BUTTON_PADDING_H}px;
                }}
                QPushButton:hover {{
                    background-color: {active_bg};
                    opacity: 0.9;
                }}
            """
        else:
            # Opaque inactive button
            return f"""
                QPushButton {{
                    background-color: {inactive_bg};
                    color: {inactive_text};
                    border: 1px solid {border_color};
                    font-size: {Theme.FONT_SIZE_SM}px;
                    border-radius: {self.BUTTON_HEIGHT // 2}px;
                    padding: {self.BUTTON_PADDING_V}px {self.BUTTON_PADDING_H}px;
                }}
                QPushButton:hover {{
                    background-color: {border_color};
                    color: {active_text};
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
