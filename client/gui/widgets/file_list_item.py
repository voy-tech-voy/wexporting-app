"""
FileListItemWidget - Custom widget for file list items with thumbnails.

Extracted from custom_widgets.py for better organization.
"""

import os
import subprocess
import tempfile
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QPixmap, QCursor, QPainter, QLinearGradient, QColor, QPainterPath, QBrush, QPen

from client.gui.theme import Theme
from client.gui.dev_panels.noise_params import NoiseParams
from typing import List


class FileListItemWidget(QWidget):
    """Custom widget for list items with hover-based remove button and progress indicator"""
    remove_clicked = pyqtSignal()
    status_clicked = pyqtSignal()
    
    _noise_texture = None # Static texture cache
    
    def __init__(self, text, file_path=None, parent=None):
        super().__init__(parent)
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QCursor
        
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)  # Enable stylesheet rendering
        self.installEventFilter(self)
        self._hovered = False
        self.file_path = file_path
        self._is_completed = False  # Track if conversion is complete
        self._status = None # None | 'success' | 'skipped' | 'failed' | 'stopped'
        self._QEvent = QEvent  # Store for eventFilter
        
        self._is_dark = True # Default
        
        # Set transparent background
        self.setStyleSheet("FileListItemWidget { background-color: transparent; }")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4) # Reduced margins to fit 48px thumb in 56px height
        layout.setSpacing(10)
        
        # Thumbnail label (48x48 square)
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(48, 48)
        self.thumbnail_label.setScaledContents(False)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet("background: #1a1a1a; border: 1px solid #444; border-radius: 4px;")
        
        # Load thumbnail if file_path provided
        if file_path:
            self.load_thumbnail(file_path)
        
        layout.addWidget(self.thumbnail_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # Text label
        self.text_label = QLabel(text)
        self.text_label.setStyleSheet("background: transparent; border: none;")
        self.text_label.setWordWrap(False)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.text_label, 1)
        
        # Remove button (X)
        self.remove_btn = QPushButton("✕")
        self.remove_btn.setMaximumSize(28, 28)
        self.remove_btn.setMinimumSize(24, 24)
        self.remove_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.remove_btn.setVisible(False)
        self.remove_btn.clicked.connect(self.remove_clicked.emit)
        layout.addWidget(self.remove_btn, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        
        self.update_button_style(self._is_dark)
    
    
    def set_status(self, status: str):
        """Set visual status (success/skipped/failed/stopped)"""
        self._status = status
        self.update() # Trigger repaint
        
    def clear_status(self):
        """Clear visual status"""
        self._status = None
        self.update()

    def clear_progress(self):
        """Reset sequence progress state"""
        if hasattr(self, 'completed_files'):
            self.completed_files.clear()
        self.clear_status()


    def set_completed(self):
        """Mark item as completed (Legacy compatibility)"""
        self.set_status('success')
        self._is_completed = True

    def mark_file_complete(self, file_path: str, status: str = 'success'):
        """Mark a single file in a sequence as complete with a specific status"""
        if not getattr(self, 'is_sequence', False):
            self.set_status(status)
            return

        if not hasattr(self, 'completed_files'):
            self.completed_files = set()
            
        self.completed_files.add(file_path)
        
        # Track per-status sets for aggregation
        if status == 'failed':
            if not hasattr(self, 'failed_files'):
                self.failed_files = set()
            self.failed_files.add(file_path)
        elif status == 'skipped':
            if not hasattr(self, 'skipped_files'):
                self.skipped_files = set()
            self.skipped_files.add(file_path)
        elif status == 'stopped':
            if not hasattr(self, 'stopped_files'):
                self.stopped_files = set()
            self.stopped_files.add(file_path)
        
        # Update aggregate status
        self._update_sequence_status()
        
        # Trigger repaint to show progress
        self.update()
        
        
    def mousePressEvent(self, event):
        """Clear status on click (notify parent)"""
        # Only clear status if persistence is NOT enabled
        print(f"[FileListItem] Click detected. Persistence enabled: {NoiseParams.persistence_enabled}")
        if not NoiseParams.persistence_enabled:
            # Always emit click to allow parent to clear ALL statuses
            self.status_clicked.emit()
            
        super().mousePressEvent(event)
    
    @staticmethod
    def _get_noise_texture():
        """
        Get or create static noise texture using void-and-cluster algorithm (Blue Noise).
        This provides high-quality dithering for smooth gradient fades.
        """
        if FileListItemWidget._noise_texture is None:
            # Generate 64x64 blue noise (simplified approximation)
            import random
            from PyQt6.QtGui import QImage
            
            # Generate blue noise (scaled up for lower frequency/larger grain)
            import random
            from PyQt6.QtGui import QImage
            
            size = NoiseParams.texture_size  # Dynamic size from dev panel
            random.seed(42) 
            
            # Start with random values
            pattern = [[random.random() for _ in range(size)] for _ in range(size)]
            
            # Void-and-cluster approximation (dynamic passes)
            for _ in range(NoiseParams.void_cluster_passes):
                new_pattern = [[0.0 for _ in range(size)] for _ in range(size)]
                for y in range(size):
                    for x in range(size):
                        total = 0.0
                        count = 0
                        for dy in [-1, 0, 1]:
                            for dx in [-1, 0, 1]:
                                if dx == 0 and dy == 0: continue
                                nx, ny = (x + dx) % size, (y + dy) % size
                                total += pattern[ny][nx]
                                count += 1
                        avg = total / count
                        if pattern[y][x] > avg:
                            new_pattern[y][x] = min(1.0, pattern[y][x] + 0.1)
                        else:
                            new_pattern[y][x] = max(0.0, pattern[y][x] - 0.1)
                pattern = new_pattern
            
            # Convert to QImage
            img = QImage(size, size, QImage.Format.Format_ARGB32)
            img.fill(QColor(0, 0, 0, 0))
            
            for y in range(size):
                for x in range(size):
                    val = pattern[y][x]
                    # Dynamic max alpha from dev panel
                    alpha = int(val * NoiseParams.max_alpha) 
                    img.setPixelColor(x, y, QColor(255, 255, 255, alpha))
            
            # Scale up to 64x64 for "lower frequency" look
            FileListItemWidget._noise_texture = QPixmap.fromImage(img).scaled(
                64, 64, 
                Qt.AspectRatioMode.IgnoreAspectRatio, 
                Qt.TransformationMode.FastTransformation # Pixelated look for noise is fine/better
            )
            
        return FileListItemWidget._noise_texture
    
    def set_sequence_mode(self, count: int, file_paths: List[str]):
        """Enable sequence mode with stacked thumbnails"""
        self.is_sequence = True
        self.sequence_count = count
        self.sequence_files = file_paths
        self.completed_files = set() # Track completed files for granular progress
        self.failed_files = set()    # Track failed files
        self.skipped_files = set()   # Track skipped files
        self.stopped_files = set()   # Track stopped files
        
        # Load thumbnails for first few items (max 4)
        self.sequence_pixmaps = []
        limit = min(4, len(file_paths))
        
        # Use existing load logic but return pixmap instead of setting label
        for i in range(limit):
            pix = self._load_single_thumbnail(file_paths[i])
            if pix:
                self.sequence_pixmaps.append(pix)
        
        # Keep thumbnail_label visible (it shows the first file normally)
        # The paintEvent will draw 3 empty squares behind it
        self.update()

    def _update_sequence_status(self):
        """Update the aggregate status for a sequence based on individual file statuses.
        
        Priority: failed > stopped > skipped > success/processing
        """
        # Priority 1: Any failures -> entire sequence is 'failed'
        if hasattr(self, 'failed_files') and len(self.failed_files) > 0:
            self.set_status('failed')
            return
        
        # Priority 2: Any stopped -> entire sequence is 'stopped'
        if hasattr(self, 'stopped_files') and len(self.stopped_files) > 0:
            self.set_status('stopped')
            return
        
        # Priority 3: Any skipped (but no failures) -> entire sequence is 'skipped'
        if hasattr(self, 'skipped_files') and len(self.skipped_files) > 0:
            self.set_status('skipped')
            return
        
        # Priority 4: All files completed successfully
        if len(self.completed_files) >= self.sequence_count:
            self.set_status('success')
        else:
            # Still processing
            if self._status is None:
                self._status = 'processing'
    
    def _load_single_thumbnail(self, path):
        """Load a single thumbnail pixmap"""
        try:
            from pathlib import Path
            file_ext = Path(path).suffix.lower()
            
            if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.gif']:
                pix = QPixmap(path)
                if not pix.isNull():
                    return pix
            elif file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v']:
                # Reuse existing extraction logic if possible, or simplified
                # For now, let's try to use the method if it exists, or skip
                if hasattr(self, 'extract_video_thumbnail'):
                    return self.extract_video_thumbnail(path)
            return None
        except:
            return None

    


    def paintEvent(self, event):
        """Paint sequence stack if enabled, otherwise just status overlay"""
        super().paintEvent(event)
        
        # 1. Paint Sequence Stack (3 Empty Squares Behind)
        if getattr(self, 'is_sequence', False):
            from client.gui.dev_panels.sequence_params import SequenceParams
            
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Base parameters (matching single item thumbnail)
            base_x = 4
            base_w = 48
            base_h = 48
            center_y = self.height() / 2
            
            # Draw empty rounded squares BEHIND the main thumbnail based on params
            # We iterate backwards so the largest index (furthest back) is drawn first
            for i in range(SequenceParams.stack_count, 0, -1):
                # Calculate offset and scale
                offset_x = i * SequenceParams.offset_x
                offset_y = i * SequenceParams.offset_y
                scale = 1.0 - (i * SequenceParams.scale_step)
                
                # Size
                w = base_w * scale
                h = base_h * scale
                
                # Position (shifted right/down based on offsets)
                x = base_x + offset_x
                y = (center_y - (h / 2)) + offset_y
                
                # Draw rounded rectangle (empty square)
                rect = QRectF(x, y, w, h)
                
                # Background color (matching thumbnail background)
                bg_color = QColor("#1a1a1a")  # Dark theme default
                border_color = QColor("#444")
                
                # Fill background
                painter.setBrush(QBrush(bg_color))
                painter.setPen(QPen(border_color, 1))
                
                # Draw rounded rect (4px radius to match thumbnail)
                painter.drawRoundedRect(rect, 4, 4)


        
        # 2. Paint Status Gradient (Existing Logic)
        if self._status:
            # Reuse painter if already created for sequence, otherwise create new one
            if not getattr(self, 'is_sequence', False):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Determine color based on status
            color_hex = Theme.success() # Default green
            if self._status == 'skipped':
                color_hex = Theme.warning()
            elif self._status == 'failed':
                color_hex = Theme.error()
            elif self._status == 'stopped':
                color_hex = Theme.warning()
                
            base_color = QColor(color_hex)
            
            # 1. Base Gradient: Color -> Transparent (dynamic from dev panel)
            gradient = QLinearGradient(0, 0, self.width(), 0)
            
            # Calculate progress width for sequences
            progress_ratio = 1.0
            if getattr(self, 'is_sequence', False) and hasattr(self, 'completed_files'):
                # If status is NOT 'success' (completed), show partial progress
                # If status IS 'success', show full (ratio 1.0)
                if self._status != 'success': 
                    progress_ratio = len(self.completed_files) / max(1, self.sequence_count)
            
            c1 = QColor(base_color)
            c1.setAlpha(NoiseParams.gradient_start_alpha)
            
            c_mid = QColor(base_color)
            c_mid.setAlpha(NoiseParams.gradient_mid_alpha)
            
            c2 = QColor(base_color)
            c2.setAlpha(0)
            
            # Adjust gradient stops??? No, gradient is the "style". 
            # We want to CLIP the gradient to the progress width.
            
            gradient.setColorAt(0.0, c1)
            gradient.setColorAt(NoiseParams.gradient_mid_position, c_mid)
            gradient.setColorAt(1.0, c2)
            
            path = QPainterPath()
            path.addRoundedRect(0, 0, self.width(), self.height(), Theme.RADIUS_MD, Theme.RADIUS_MD)
            
            # Clip to progress if sequence and not fully done
            if progress_ratio < 1.0:
                # Create a clip path that is the intersection of rounded rect AND progress rect
                progress_rect = QRectF(0, 0, self.width() * progress_ratio, self.height())
                progress_path = QPainterPath()
                progress_path.addRect(progress_rect)
                path = path.intersected(progress_path)
            
            # Fill base gradient
            painter.fillPath(path, QBrush(gradient))
            
            # 2. Apply Noise Dithering
            # Draw noise into a temporary pixmap, apply gradient mask, then overlay
            noise_tex = self._get_noise_texture()
            if noise_tex:
                # Create noise layer
                noise_pix = QPixmap(self.size())
                noise_pix.fill(Qt.GlobalColor.transparent)
                
                np = QPainter(noise_pix)
                np.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Tile the noise
                np.setClipPath(path)
                np.drawTiledPixmap(self.rect(), noise_tex)
                
                # Apply Gradient Mask to Noise (DestinationIn)
                # Keep noise only where the gradient fades to reduce banding
                np.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                
                mask_grad = QLinearGradient(0, 0, self.width(), 0)
                # Mask Alpha: dynamic from dev panel
                mask_grad.setColorAt(NoiseParams.mask_start_pos, QColor(0, 0, 0, 0))  # Clean start
                mask_grad.setColorAt(NoiseParams.mask_ramp_pos, QColor(0, 0, 0, NoiseParams.mask_ramp_alpha))  # Noise starts
                mask_grad.setColorAt(NoiseParams.mask_peak_pos, QColor(0, 0, 0, NoiseParams.mask_peak_alpha))  # Max noise
                mask_grad.setColorAt(NoiseParams.mask_end_pos, QColor(0, 0, 0, 0))  # Clean end
                
                np.fillRect(self.rect(), mask_grad)
                np.end()
                
                # Overlay masked noise
                painter.drawPixmap(0, 0, noise_pix)
        
        # 3. Paint Background (if hovered) - already handled by stylesheet in update_background_style?
        # No, stylesheet handles it.
        pass

    
    def update_theme(self, is_dark):
        """Update widget colors based on theme"""
        self._is_dark = is_dark
        Theme.set_dark_mode(is_dark)
        
        text_color = Theme.text()
        thumb_bg = Theme.color("input_bg") if is_dark else "#f5f5f5"
        thumb_border = Theme.border()
        
        # Update labels
        self.text_label.setStyleSheet(f"background: transparent; border: none; color: {text_color};")
        self.thumbnail_label.setStyleSheet(f"background: {thumb_bg}; border: 1px solid {thumb_border}; border-radius: {Theme.RADIUS_SM}px;")
        
        # Update remove button
        self.update_button_style(is_dark)
        
        # Update background if currently hovered
        self._update_background_style()
        
    def _update_background_style(self):
        """Update the main widget background based on hover state"""
        if self._hovered:
            # Highlight style
            Theme.set_dark_mode(self._is_dark)
            bg_color = Theme.color_with_alpha('surface_element', 0.5) if self._is_dark else "rgba(0, 0, 0, 0.05)"
            # radius = Theme.RADIUS_MD # Variable not always avail?
            # Hardcode 6px for now or use Theme constant
            radius = 6
            
            self.setStyleSheet(f"""
                FileListItemWidget {{
                    background-color: {bg_color};
                    border-radius: {radius}px;
                }}
            """)
        else:
            self.setStyleSheet("FileListItemWidget { background-color: transparent; }")
        
    def sizeHint(self):
        """Return the recommended size for the widget"""
        return QSize(0, 56)
    
    def minimumSizeHint(self):
        """Return the minimum recommended size"""
        return QSize(0, 56)
        
    def eventFilter(self, obj, event):
        if obj == self:
            if event.type() == self._QEvent.Type.Enter:
                self._hovered = True
                self.remove_btn.setVisible(True)
                self._update_background_style()
            elif event.type() == self._QEvent.Type.Leave:
                self._hovered = False
                self.remove_btn.setVisible(False)
                self._update_background_style()
        return super().eventFilter(obj, event)
    
    def load_thumbnail(self, file_path):
        """Load and display thumbnail for the file"""
        try:
            from pathlib import Path
            
            file_ext = Path(file_path).suffix.lower()
            pixmap = None
            
            # For images, load directly
            if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.gif']:
                pixmap = QPixmap(file_path)
            
            # For videos, extract first frame
            elif file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v']:
                pixmap = self.extract_video_thumbnail(file_path)
            
            # If thumbnail loaded successfully, scale and display
            if pixmap and not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    48, 48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
            else:
                self.set_fallback_icon(file_ext)
        except Exception as e:
            print(f"Failed to load thumbnail: {e}")
            from pathlib import Path
            self.set_fallback_icon(Path(file_path).suffix.lower())
    
    def extract_video_thumbnail(self, video_path):
        """Extract first frame from video as thumbnail"""
        try:
            ffmpeg_path = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
            
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                thumb_path = tmp.name
            
            try:
                cmd = [
                    str(ffmpeg_path),
                    '-ss', '0.5',
                    '-i', str(video_path),
                    '-vframes', '1',
                    '-vf', 'scale=128:-1',
                    '-q:v', '2',
                    '-y',
                    thumb_path
                ]
                
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                    pixmap = QPixmap(thumb_path)
                    try:
                        os.remove(thumb_path)
                    except:
                        pass
                    
                    if not pixmap.isNull():
                        return pixmap
                
            finally:
                if os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                    except:
                        pass
            
        except subprocess.TimeoutExpired:
            print(f"Video thumbnail extraction timed out for {video_path}")
        except Exception as e:
            print(f"Video thumbnail extraction failed: {e}")
        
        return None
    
    def set_fallback_icon(self, file_ext):
        """Set a fallback icon based on file type"""
        if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.gif']:
            icon_text = "[IMG]"
        elif file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v']:
            icon_text = "[VIDEO]"
        elif file_ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']:
            icon_text = "🎵"
        else:
            icon_text = "📄"
        
        self.thumbnail_label.setText(icon_text)
        self.thumbnail_label.setStyleSheet(
            "background: #1a1a1a; border: 1px solid #444; border-radius: 4px; "
            "font-size: 24px; color: #888;"
        )
    
    def update_button_style(self, is_dark_theme):
        """Update button styling based on theme"""
        if is_dark_theme:
            btn_style = """
                QPushButton {
                    background-color: transparent;
                    color: #888888;
                    border: none;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 0px;
                }
                QPushButton:hover {
                    color: #ff4444;
                    background-color: rgba(255, 68, 68, 0.1);
                    border-radius: 3px;
                }
                QPushButton:pressed {
                    color: #ff0000;
                    background-color: rgba(255, 0, 0, 0.2);
                }
            """
            text_style = "background: transparent; border: none; color: #ffffff; font-size: 13px;"
        else:
            btn_style = """
                QPushButton {
                    background-color: transparent;
                    color: #999999;
                    border: none;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 0px;
                }
                QPushButton:hover {
                    color: #ff4444;
                    background-color: rgba(255, 68, 68, 0.1);
                    border-radius: 3px;
                }
                QPushButton:pressed {
                    color: #ff0000;
                    background-color: rgba(255, 0, 0, 0.2);
                }
            """
            text_style = "background: transparent; border: none; color: #333333; font-size: 13px;"
        
        self.remove_btn.setStyleSheet(btn_style)
        self.text_label.setStyleSheet(text_style)
        
        current_thumb_style = self.thumbnail_label.styleSheet()
        if is_dark_theme:
            thumb_style = "background: #1a1a1a; border: 1px solid #444; border-radius: 4px;"
            if "font-size" in current_thumb_style:
                thumb_style += " font-size: 24px; color: #888;"
        else:
            thumb_style = "background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px;"
            if "font-size" in current_thumb_style:
                thumb_style += " font-size: 24px; color: #666;"
        
        self.thumbnail_label.setStyleSheet(thumb_style)
