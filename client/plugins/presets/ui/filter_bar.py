"""
Presets Plugin - Category Filter Bar

Dynamic filter bar with exclusive toggle buttons for filtering presets by category.
Single selection mode with "ALL" button to show all presets.
"""
from typing import List, Optional
from PyQt6.QtWidgets import (
    QHBoxLayout, QPushButton, QButtonGroup
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPixmap, QImage, QPainterPath

from client.plugins.presets.logic.models import PresetDefinition
from client.gui.theme import Theme
from client.gui.widgets.gradient_blur_bar import GradientBlurBar


class CategoryFilterBar(GradientBlurBar):
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
        # Initialize base class with top orientation and gallery_filter theme prefix
        super().__init__(parent, orientation='top', theme_prefix='gallery_filter')
        
        self._buttons: dict[str, QPushButton] = {}
        self._selected_category: Optional[str] = None  # None or category name
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        
        # Custom blur capture state (overrides base class behavior)
        self._is_capturing = False
        self._blurred_bg = None
        
        # DEBUG MODE - Set to False for production
        self._debug_mode = False
        
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
        
        # Rounded top corners only
        path = QPainterPath()
        radius = 12
        rect = self.rect().toRectF()
        
        # Start at top-left, after the radius
        path.moveTo(rect.left() + radius, rect.top())
        # Top edge to top-right corner
        path.lineTo(rect.right() - radius, rect.top())
        # Top-right arc
        path.arcTo(rect.right() - radius * 2, rect.top(), radius * 2, radius * 2, 90, -90)
        # Right edge
        path.lineTo(rect.right(), rect.bottom())
        # Bottom edge
        path.lineTo(rect.left(), rect.bottom())
        # Left edge
        path.lineTo(rect.left(), rect.top() + radius)
        # Top-left arc
        path.arcTo(rect.left(), rect.top(), radius * 2, radius * 2, 180, -90)
        path.closeSubpath()
        
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
        # Use multi-stop gradient for smoother transitions (eliminates banding)
        # Extra stops concentrated in bottom 60% where fade is most visible
        solid_gradient = QLinearGradient(0, 0, 0, self.height())
        
        # 13 color stops for ultra-smooth gradient (more stops in bottom half)
        solid_gradient.setColorAt(0.0, QColor(bg_r, bg_g, bg_b, mask_top))
        solid_gradient.setColorAt(0.15, QColor(bg_r, bg_g, bg_b, mask_top))
        solid_gradient.setColorAt(0.3, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.95 + mask_bottom * 0.05)))
        solid_gradient.setColorAt(0.45, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.85 + mask_bottom * 0.15)))
        solid_gradient.setColorAt(0.55, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.75 + mask_bottom * 0.25)))
        solid_gradient.setColorAt(0.65, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.60 + mask_bottom * 0.40)))
        solid_gradient.setColorAt(0.72, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.45 + mask_bottom * 0.55)))
        solid_gradient.setColorAt(0.78, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.30 + mask_bottom * 0.70)))
        solid_gradient.setColorAt(0.84, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.20 + mask_bottom * 0.80)))
        solid_gradient.setColorAt(0.89, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.12 + mask_bottom * 0.88)))
        solid_gradient.setColorAt(0.93, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.06 + mask_bottom * 0.94)))
        solid_gradient.setColorAt(0.97, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.02 + mask_bottom * 0.98)))
        solid_gradient.setColorAt(1.0, QColor(bg_r, bg_g, bg_b, mask_bottom))
        painter.fillRect(self.rect(), solid_gradient)
        
        # 1.5. Draw overlay tint on top of background
        overlay_gradient = QLinearGradient(0, 0, 0, self.height())
        overlay_gradient.setColorAt(0.0, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, mask_top)))
        overlay_gradient.setColorAt(0.15, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, mask_top)))
        overlay_gradient.setColorAt(0.3, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.95 + mask_bottom * 0.05))))
        overlay_gradient.setColorAt(0.45, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.85 + mask_bottom * 0.15))))
        overlay_gradient.setColorAt(0.55, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.75 + mask_bottom * 0.25))))
        overlay_gradient.setColorAt(0.65, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.60 + mask_bottom * 0.40))))
        overlay_gradient.setColorAt(0.72, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.45 + mask_bottom * 0.55))))
        overlay_gradient.setColorAt(0.78, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.30 + mask_bottom * 0.70))))
        overlay_gradient.setColorAt(0.84, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.20 + mask_bottom * 0.80))))
        overlay_gradient.setColorAt(0.89, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.12 + mask_bottom * 0.88))))
        overlay_gradient.setColorAt(0.93, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.06 + mask_bottom * 0.94))))
        overlay_gradient.setColorAt(0.97, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.02 + mask_bottom * 0.98))))
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
            
            # Multiply Alpha with Gradient (biased toward bottom for button legibility)
            mask_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            
            alpha_gradient = QLinearGradient(0, 0, 0, self.height())
            # Multi-stop gradient for ultra-smooth alpha transition
            alpha_gradient.setColorAt(0.0, QColor(0, 0, 0, mask_top))
            alpha_gradient.setColorAt(0.3, QColor(0, 0, 0, mask_top))  # Hold opacity longer
            alpha_gradient.setColorAt(0.6, QColor(0, 0, 0, int(mask_top * 0.7 + mask_bottom * 0.3)))
            alpha_gradient.setColorAt(0.8, QColor(0, 0, 0, int(mask_top * 0.3 + mask_bottom * 0.7)))
            alpha_gradient.setColorAt(1.0, QColor(0, 0, 0, mask_bottom))
            
            mask_painter.fillRect(blurred_masked.rect(), alpha_gradient)
            mask_painter.end()
            
            # Paint the masked blur
            painter.drawPixmap(0, 0, blurred_masked)
        
        # Draw smooth fade-out overlay at top edge
        fade_height = 30  # Larger fade zone for smoother transition
        top_fade = QLinearGradient(0, 0, 0, fade_height)
        # Start with fully opaque gallery background at very top
        top_fade.setColorAt(0.0, QColor(bg_r, bg_g, bg_b, 255))
        # Fade to transparent
        top_fade.setColorAt(1.0, QColor(bg_r, bg_g, bg_b, 0))
        painter.fillRect(0, 0, self.width(), fade_height, top_fade)
        
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
        
        # 3. Apply Noise Dithering (gradient-aware - only where needed)
        try:
            noise_opacity = int(get_color("gallery_filter_noise_opacity", is_dark))
        except (ValueError, TypeError):
            noise_opacity = 15  # Default subtle noise
            
        if noise_opacity > 0 and self._noise_pixmap:
            # Create a gradient mask for the noise itself
            # Apply noise ONLY in the gradient transition zone (middle area)
            # Keep top and bottom clean
            
            noise_pixmap = QPixmap(self.size())
            noise_pixmap.fill(Qt.GlobalColor.transparent)
            
            noise_painter = QPainter(noise_pixmap)
            noise_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw tiled noise
            noise_painter.drawTiledPixmap(self.rect(), self._noise_pixmap)
            
            # Apply gradient mask to noise - only show in transition zone
            noise_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            
            noise_mask = QLinearGradient(0, 0, 0, self.height())
            # Top 20% - no noise (clean)
            noise_mask.setColorAt(0.0, QColor(0, 0, 0, 0))
            noise_mask.setColorAt(0.2, QColor(0, 0, 0, 0))
            # Ramp up noise through middle
            noise_mask.setColorAt(0.35, QColor(0, 0, 0, noise_opacity // 2))
            noise_mask.setColorAt(0.5, QColor(0, 0, 0, noise_opacity))
            # Keep full noise through bottom fade zone (where banding is worst)
            noise_mask.setColorAt(0.85, QColor(0, 0, 0, noise_opacity))
            # Final fade at very bottom
            noise_mask.setColorAt(0.95, QColor(0, 0, 0, noise_opacity // 2))
            noise_mask.setColorAt(1.0, QColor(0, 0, 0, 0))
            
            noise_painter.fillRect(noise_pixmap.rect(), noise_mask)
            noise_painter.end()
            
            # Draw the masked noise
            painter.drawPixmap(0, 0, noise_pixmap)
            
        painter.end()


    def _generate_noise_texture(self) -> QPixmap:
        """Generate blue noise texture using void-and-cluster algorithm.
        
        Blue noise has optimal perceptual properties - it distributes energy
        into high frequencies where the human eye is least sensitive.
        This creates the most natural-looking dither with minimal visual artifacts.
        """
        import random
        from PyQt6.QtGui import QImage
        
        size = 64  # Smaller is more efficient, still tiles seamlessly
        
        # Simplified blue noise generation using void-and-cluster
        # This creates a distribution that avoids low-frequency clumping
        
        random.seed(42)  # Consistent pattern
        
        # Start with random values
        pattern = [[random.random() for _ in range(size)] for _ in range(size)]
        
        # Apply multiple passes of local averaging to push energy to high frequencies
        # This is a simplified approximation of blue noise
        for iteration in range(3):
            new_pattern = [[0.0 for _ in range(size)] for _ in range(size)]
            
            for y in range(size):
                for x in range(size):
                    # Sample neighborhood
                    total = 0.0
                    count = 0
                    
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            nx = (x + dx) % size
                            ny = (y + dy) % size
                            total += pattern[ny][nx]
                            count += 1
                    
                    avg = total / count
                    
                    # Push away from local average (creates high-frequency distribution)
                    if pattern[y][x] > avg:
                        new_pattern[y][x] = min(1.0, pattern[y][x] + 0.1)
                    else:
                        new_pattern[y][x] = max(0.0, pattern[y][x] - 0.1)
            
            pattern = new_pattern
        
        # Normalize to 0-255 range with good contrast
        min_val = min(min(row) for row in pattern)
        max_val = max(max(row) for row in pattern)
        range_val = max_val - min_val
        
        image = QImage(size, size, QImage.Format.Format_Grayscale8)
        
        for y in range(size):
            for x in range(size):
                # Normalize and convert to byte
                normalized = (pattern[y][x] - min_val) / range_val
                # Center around 128 with moderate range for subtle effect
                value = int(128 + (normalized - 0.5) * 60)
                value = max(0, min(255, value))
                image.setPixel(x, y, value)
        
        return QPixmap.fromImage(image)


    
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
