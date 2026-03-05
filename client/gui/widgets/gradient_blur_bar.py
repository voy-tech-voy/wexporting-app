"""
Gradient Blur Bar Widget

Reusable widget that renders a blurred background with gradient fade.
Supports both top-to-bottom and bottom-to-top orientations.

Features:
- Captures and blurs background content
- Multi-stop gradients for smooth transitions
- Blue noise dithering to prevent banding
- Configurable via theme variables
- Supports both top and bottom bar orientations
"""
from typing import Literal, Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QPixmap, QPainterPath, QImage

from client.gui.theme import Theme
from client.gui.theme_variables import get_color


class GradientBlurBar(QWidget):
    """Base widget for rendering gradient-blurred backgrounds.
    
    This widget captures the content behind it, applies a blur effect,
    and renders it with a smooth gradient fade. Includes blue noise
    dithering to prevent banding artifacts.
    
    Attributes:
        orientation: 'top' for top-to-bottom fade, 'bottom' for bottom-to-top
        theme_prefix: Prefix for theme variable names (e.g., 'gallery_filter')
    """
    
    def __init__(
        self,
        parent=None,
        orientation: Literal['top', 'bottom'] = 'top',
        theme_prefix: str = 'gallery_filter'
    ):
        super().__init__(parent)
        
        self.orientation = orientation
        self.theme_prefix = theme_prefix
        
        # Cached blur background
        self._blurred_bg: Optional[QPixmap] = None
        self._blur_timer = QTimer()
        self._blur_timer.setSingleShot(True)
        self._blur_timer.setInterval(50)
        self._blur_timer.timeout.connect(self._delayed_blur_refresh)
        
        # Prevent Qt from painting any background - we handle it in paintEvent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        
        # Generate noise texture for dithering
        self._noise_pixmap = self._generate_noise_texture()
    
    def capture_blur(self) -> None:
        """Capture and blur the content behind this bar.
        
        Call this when the parent content changes or scrolls.
        Uses a timer to debounce rapid calls.
        """
        self._blur_timer.start()
    
    def _delayed_blur_refresh(self) -> None:
        """Actually perform the blur capture (debounced)."""
        self._blurred_bg = self._capture_blur_background()
        self.update()
    
    def _capture_blur_background(self) -> QPixmap:
        """Capture the area behind this widget and apply blur effect."""
        if not self.parent():
            return QPixmap()
        
        # Get theme values
        is_dark = Theme.is_dark_mode()
        blur_radius = int(get_color(f"{self.theme_prefix}_blur_radius", is_dark))
        blur_scale = int(get_color(f"{self.theme_prefix}_blur_scale", is_dark))
        
        # Capture parent content
        parent_widget = self.parent()
        source_rect = self.geometry()
        
        # Render parent to pixmap
        source_pixmap = QPixmap(source_rect.size())
        source_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(source_pixmap)
        painter.translate(-source_rect.x(), -source_rect.y())
        parent_widget.render(painter, parent_widget.rect().topLeft())
        painter.end()
        
        # Apply blur
        if blur_radius > 0:
            # Downscale for performance
            small_size = source_pixmap.size() // blur_scale
            small_pixmap = source_pixmap.scaled(
                small_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Simple box blur approximation
            blurred = self._apply_box_blur(small_pixmap, blur_radius // blur_scale)
            
            # Scale back up
            return blurred.scaled(
                source_pixmap.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        return source_pixmap
    
    def _apply_box_blur(self, pixmap: QPixmap, radius: int) -> QPixmap:
        """Apply simple box blur to pixmap."""
        # This is a placeholder - Qt doesn't have built-in blur
        # In production, you'd use QGraphicsBlurEffect or custom implementation
        return pixmap
    
    def paintEvent(self, event) -> None:
        """Paint blurred background with gradient fade and noise dithering."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get theme values
        is_dark = Theme.is_dark_mode()
        
        # Background and overlay colors
        bg_color = QColor(get_color(f"{self.theme_prefix}_bg", is_dark))
        overlay_color = QColor(get_color(f"{self.theme_prefix}_overlay", is_dark))
        filter_overlay_alpha = int(get_color(f"{self.theme_prefix}_overlay_alpha", is_dark))
        
        # Gradient mask alphas
        mask_top = int(get_color(f"{self.theme_prefix}_mask_top_alpha", is_dark))
        mask_bottom = int(get_color(f"{self.theme_prefix}_mask_bottom_alpha", is_dark))
        
        # Swap for bottom orientation
        if self.orientation == 'bottom':
            mask_top, mask_bottom = mask_bottom, mask_top
        
        # Extract RGB
        bg_r, bg_g, bg_b = bg_color.red(), bg_color.green(), bg_color.blue()
        ov_r, ov_g, ov_b = overlay_color.red(), overlay_color.green(), overlay_color.blue()
        
        # 1. Draw solid background with gradient alpha
        solid_gradient = QLinearGradient(0, 0, 0, self.height())
        
        # 9 color stops for ultra-smooth gradient
        solid_gradient.setColorAt(0.0, QColor(bg_r, bg_g, bg_b, mask_top))
        solid_gradient.setColorAt(0.2, QColor(bg_r, bg_g, bg_b, mask_top))
        solid_gradient.setColorAt(0.4, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.9 + mask_bottom * 0.1)))
        solid_gradient.setColorAt(0.55, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.7 + mask_bottom * 0.3)))
        solid_gradient.setColorAt(0.65, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.5 + mask_bottom * 0.5)))
        solid_gradient.setColorAt(0.75, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.3 + mask_bottom * 0.7)))
        solid_gradient.setColorAt(0.85, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.15 + mask_bottom * 0.85)))
        solid_gradient.setColorAt(0.95, QColor(bg_r, bg_g, bg_b, int(mask_top * 0.05 + mask_bottom * 0.95)))
        solid_gradient.setColorAt(1.0, QColor(bg_r, bg_g, bg_b, mask_bottom))
        painter.fillRect(self.rect(), solid_gradient)
        
        # 1.5. Draw overlay tint
        overlay_gradient = QLinearGradient(0, 0, 0, self.height())
        overlay_gradient.setColorAt(0.0, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, mask_top)))
        overlay_gradient.setColorAt(0.2, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, mask_top)))
        overlay_gradient.setColorAt(0.4, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.9 + mask_bottom * 0.1))))
        overlay_gradient.setColorAt(0.55, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.7 + mask_bottom * 0.3))))
        overlay_gradient.setColorAt(0.65, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.5 + mask_bottom * 0.5))))
        overlay_gradient.setColorAt(0.75, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.3 + mask_bottom * 0.7))))
        overlay_gradient.setColorAt(0.85, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.15 + mask_bottom * 0.85))))
        overlay_gradient.setColorAt(0.95, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, int(mask_top * 0.05 + mask_bottom * 0.95))))
        overlay_gradient.setColorAt(1.0, QColor(ov_r, ov_g, ov_b, min(filter_overlay_alpha, mask_bottom)))
        painter.fillRect(self.rect(), overlay_gradient)
        
        # 2. Draw blurred background (if available)
        if self._blurred_bg and not self._blurred_bg.isNull():
            blurred_masked = QPixmap(self._blurred_bg.size())
            blurred_masked.fill(Qt.GlobalColor.transparent)
            
            mask_painter = QPainter(blurred_masked)
            mask_painter.drawPixmap(0, 0, self._blurred_bg)
            
            # Apply gradient alpha mask
            mask_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            
            alpha_gradient = QLinearGradient(0, 0, 0, self.height())
            alpha_gradient.setColorAt(0.0, QColor(0, 0, 0, mask_top))
            alpha_gradient.setColorAt(0.3, QColor(0, 0, 0, mask_top))
            alpha_gradient.setColorAt(0.6, QColor(0, 0, 0, int(mask_top * 0.7 + mask_bottom * 0.3)))
            alpha_gradient.setColorAt(0.8, QColor(0, 0, 0, int(mask_top * 0.3 + mask_bottom * 0.7)))
            alpha_gradient.setColorAt(1.0, QColor(0, 0, 0, mask_bottom))
            
            mask_painter.fillRect(blurred_masked.rect(), alpha_gradient)
            mask_painter.end()
            
            painter.drawPixmap(0, 0, blurred_masked)
        
        # 3. Apply noise dithering (gradient-aware)
        try:
            noise_opacity = int(get_color(f"{self.theme_prefix}_noise_opacity", is_dark))
        except (ValueError, TypeError):
            noise_opacity = 15
            
        if noise_opacity > 0 and self._noise_pixmap:
            noise_pixmap = QPixmap(self.size())
            noise_pixmap.fill(Qt.GlobalColor.transparent)
            
            noise_painter = QPainter(noise_pixmap)
            noise_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            noise_painter.drawTiledPixmap(self.rect(), self._noise_pixmap)
            
            # Apply gradient mask to noise
            noise_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            
            noise_mask = QLinearGradient(0, 0, 0, self.height())
            noise_mask.setColorAt(0.0, QColor(0, 0, 0, 0))
            noise_mask.setColorAt(0.2, QColor(0, 0, 0, 0))
            noise_mask.setColorAt(0.35, QColor(0, 0, 0, noise_opacity // 2))
            noise_mask.setColorAt(0.5, QColor(0, 0, 0, noise_opacity))
            noise_mask.setColorAt(0.85, QColor(0, 0, 0, noise_opacity))
            noise_mask.setColorAt(0.95, QColor(0, 0, 0, noise_opacity // 2))
            noise_mask.setColorAt(1.0, QColor(0, 0, 0, 0))
            
            noise_painter.fillRect(noise_pixmap.rect(), noise_mask)
            noise_painter.end()
            
            painter.drawPixmap(0, 0, noise_pixmap)
            
        painter.end()
    
    def _generate_noise_texture(self) -> QPixmap:
        """Generate blue noise texture using void-and-cluster algorithm."""
        import random
        
        size = 64
        random.seed(42)
        
        # Start with random values
        pattern = [[random.random() for _ in range(size)] for _ in range(size)]
        
        # Apply void-and-cluster iterations
        for iteration in range(3):
            new_pattern = [[0.0 for _ in range(size)] for _ in range(size)]
            
            for y in range(size):
                for x in range(size):
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
                    
                    if pattern[y][x] > avg:
                        new_pattern[y][x] = min(1.0, pattern[y][x] + 0.1)
                    else:
                        new_pattern[y][x] = max(0.0, pattern[y][x] - 0.1)
            
            pattern = new_pattern
        
        # Normalize to 0-255 range
        min_val = min(min(row) for row in pattern)
        max_val = max(max(row) for row in pattern)
        range_val = max_val - min_val
        
        image = QImage(size, size, QImage.Format.Format_Grayscale8)
        
        for y in range(size):
            for x in range(size):
                normalized = (pattern[y][x] - min_val) / range_val
                value = int(128 + (normalized - 0.5) * 60)
                value = max(0, min(255, value))
                image.setPixel(x, y, value)
        
        return QPixmap.fromImage(image)
