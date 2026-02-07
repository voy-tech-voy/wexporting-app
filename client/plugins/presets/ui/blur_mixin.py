"""
Blur Background Mixin

Provides blur background capture and rendering functionality for overlay widgets.
"""
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
from PyQt6.QtGui import QPainter, QPixmap, QColor
from PyQt6.QtCore import Qt, QRect


class BlurBackgroundMixin:
    """
    Mixin for widgets that need blurred background capture.
    
    Usage:
        class MyWidget(BlurBackgroundMixin, QWidget):
            def paintEvent(self, event):
                painter = QPainter(self)
                self.paint_blur_background(painter, self.rect())
                super().paintEvent(event)
    """
    
    def __init__(self):
        super().__init__()
        self._blurred_background = None
        self._is_capturing_blur = False
    
    def capture_blur_background(self, force: bool = False):
        """
        Capture parent window content and apply optimized blur effect.
        
        Args:
            force: If True, force re-capture even if background exists.
        """
        if not self.parent() or getattr(self, '_is_capturing_blur', False):
            return
            
        # Optimization: Return if we already have a background and not forced
        if not force and self._blurred_background is not None:
            return
            
        self._is_capturing_blur = True
        try:
            # Check if we should use clean background (when drop area is empty)
            # Gallery's parent is file_list_widget, so we need to check grandparent (DragDropArea)
            parent = self.parent()
            drag_drop_area = None
            
            # Traverse up to find DragDropArea
            current = parent
            while current is not None:
                if hasattr(current, 'file_list'):
                    drag_drop_area = current
                    break
                current = current.parent()
            
            if drag_drop_area and hasattr(drag_drop_area, 'file_list') and len(drag_drop_area.file_list) == 0:
                print("[BlurBackgroundMixin] File list is empty - using clean transparent background")
                # Create a clean transparent background instead of capturing drop icon
                parent_rect = parent.rect()
                
                # Create clean transparent pixmap
                clean_pixmap = QPixmap(parent_rect.size())
                clean_pixmap.fill(Qt.GlobalColor.transparent)
                
                # Downscale for consistency with normal blur path
                target_width = max(1, parent_rect.width() // 4)
                small_pixmap = clean_pixmap.scaledToWidth(
                    target_width,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                self._blurred_background = small_pixmap
                self._is_capturing_blur = False
                return
            
            file_count = len(drag_drop_area.file_list) if drag_drop_area and hasattr(drag_drop_area, 'file_list') else 'N/A'
            print(f"[BlurBackgroundMixin] File list has {file_count} files - capturing blur normally")
            # Normal path: capture and blur parent content
            # Hide self temporarily to capture what's behind
            was_visible = self.isVisible()
            if was_visible:
                self.setVisible(False)
                
            # Grab parent pixmap
            parent_rect = parent.rect()
            
            try:
                parent_pixmap = parent.grab(parent_rect)
            except Exception:
                # Fallback if grab fails
                parent_pixmap = None
            
            if was_visible:
                self.setVisible(True)
            
            if not parent_pixmap:
                self._is_capturing_blur = False
                return
            
            # OPTIMIZATION: Downscale to ~25% size for faster blur
            target_width = max(1, parent_rect.width() // 4)
            small_pixmap = parent_pixmap.scaledToWidth(
                target_width, 
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Apply blur to the small pixmap
            blur_radius = 12
            
            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(small_pixmap)
            blur = QGraphicsBlurEffect()
            blur.setBlurRadius(blur_radius)
            blur.setBlurHints(QGraphicsBlurEffect.BlurHint.PerformanceHint)
            item.setGraphicsEffect(blur)
            scene.addItem(item)
            
            # Render scene to new small pixmap
            output_pixmap = QPixmap(small_pixmap.size())
            output_pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter()
            try:
                if painter.begin(output_pixmap):
                    scene.render(painter)
            finally:
                painter.end()
            
            self._blurred_background = output_pixmap
            
        except Exception as e:
            print(f"[BlurBackgroundMixin] Blur capture error: {e}")
        finally:
            self._is_capturing_blur = False
    
    def paint_blur_background(self, painter: QPainter, rect: QRect, overlay_alpha: int = None):
        """
        Paint the blurred background with dark overlay.
        
        Args:
            painter: QPainter instance
            rect: Rectangle to paint
            overlay_alpha: Alpha value for dark overlay (0-255), uses theme default if None
        """
        # Draw blurred background if available (upscale smoothly)
        if hasattr(self, '_blurred_background') and self._blurred_background:
            painter.drawPixmap(rect, self._blurred_background)
        
        # Use theme variables for overlay
        from client.gui.theme_variables import get_color
        from client.gui.theme_manager import ThemeManager
        
        is_dark = ThemeManager.instance().is_dark_mode()
        overlay_color_hex = get_color("gallery_overlay_color", is_dark)
        
        if overlay_alpha is None:
            overlay_alpha = int(get_color("gallery_overlay_alpha", is_dark))
        
        # Parse hex color and apply alpha
        overlay_color = QColor(overlay_color_hex)
        overlay_color.setAlpha(overlay_alpha)
        painter.fillRect(rect, overlay_color)

    def clear_blur_cache(self):
        """Clear the cached blurred background, forcing re-capture on next show."""
        self._blurred_background = None

