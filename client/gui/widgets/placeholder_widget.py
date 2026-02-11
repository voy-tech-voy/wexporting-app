"""
Drop Placeholder Widget

A centered SVG icon + text label widget shown when the file list is empty.
"""

from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QGraphicsColorizeEffect
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor


class DropPlaceholderWidget(QWidget):
    """
    Placeholder widget shown in the drop area when no files are present.
    
    Displays a centered SVG icon with "drag and drop media files here" text.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Build the placeholder UI."""
        # Transparent wrapper
        self.setStyleSheet("background-color: transparent; border: none;")
        wrapper_layout = QVBoxLayout(self)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Centered container
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        container.setStyleSheet("background-color: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load SVG icon with grey color
        svg_label = QLabel()
        svg_label.setStyleSheet("background-color: transparent;")
        svg_path = Path(__file__).parent.parent.parent / "assets" / "icons" / "drag_drop.svg"
        
        if svg_path.exists():
            pixmap = QPixmap(str(svg_path))
            pixmap = pixmap.scaledToWidth(150, Qt.TransformationMode.SmoothTransformation)
            svg_label.setPixmap(pixmap)
            
            # Apply grey colorize effect
            colorize_effect = QGraphicsColorizeEffect()
            colorize_effect.setColor(QColor(128, 128, 128))
            colorize_effect.setStrength(1.0)
            svg_label.setGraphicsEffect(colorize_effect)
        
        svg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(svg_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Text label below icon
        text_label = QLabel("drag and drop media files here")
        text_label.setStyleSheet("""
            background-color: transparent;
            color: #888888;
            font-size: 14px;
            padding-top: 10px;
        """)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        wrapper_layout.addWidget(container)
