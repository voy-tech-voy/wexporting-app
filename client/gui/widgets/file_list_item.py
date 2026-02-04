"""
FileListItemWidget - Custom widget for file list items with thumbnails.

Extracted from custom_widgets.py for better organization.
"""

import os
import subprocess
import tempfile
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QPixmap, QCursor

from client.gui.theme import Theme


class FileListItemWidget(QWidget):
    """Custom widget for list items with hover-based remove button and progress indicator"""
    remove_clicked = pyqtSignal()
    
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
        self._QEvent = QEvent  # Store for eventFilter
        
        self._is_dark = True # Default
        
        # Set transparent background
        self.setStyleSheet("FileListItemWidget { background-color: transparent; }")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
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
        
        layout.addWidget(self.thumbnail_label)
        
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
    
    def set_completed(self):
        """Mark item as completed"""
        self._is_completed = True
    
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
            radius = Theme.RADIUS_MD
            
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
        return QSize(0, 50)
        
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
