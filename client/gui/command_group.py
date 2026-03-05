from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QFormLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor
import os

from client.gui.custom_widgets import ModeButtonsWidget
from client.utils.resource_path import get_resource_path

class CommandGroup(QGroupBox):
    """
    A standardized group box for command panel sections.
    Features:
    - Consistent header with icon and title
    - Optional mode buttons section
    - Consistent content layout (QFormLayout)
    - Standardized margins and spacing
    """
    def __init__(self, title, icon_path=None, parent=None, size_policy=None):
        super().__init__(parent)
        self.setTitle("") # We use a custom header
        
        # Set size policy - horizontal should always expand, vertical is configurable
        if size_policy:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, size_policy)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Main layout for the group
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Header Section (Icon + Title) - STICKS TO TOP EDGE
        self.header_widget = QWidget()
        
        self.header_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header_layout = QHBoxLayout(self.header_widget)
        # Match the requested padding: 12px top/bottom, 12px left/right
        self.header_layout.setContentsMargins(12, 12, 12, 12) 
        self.header_layout.setSpacing(8)
        
        # Icon - 24x24 centered on placeholder position
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if icon_path:
            # Resolve absolute path for the bundle
            abs_icon_path = get_resource_path(icon_path)
            # Load SVG icon from assets (SVG preferred for crisp rendering)
            svg_path = abs_icon_path.replace('.png', '.svg')
            
            if os.path.exists(svg_path):
                # Use QIcon for high-quality SVG rendering
                icon = QIcon(svg_path)
                pixmap = icon.pixmap(24, 24, mode=QIcon.Mode.Normal, state=QIcon.State.On)
                # Apply grey tint with smooth rendering
                grey_pixmap = QPixmap(24, 24)
                grey_pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(grey_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.drawPixmap(0, 0, pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(grey_pixmap.rect(), QColor(136, 136, 136))  # #888888
                painter.end()
                self.icon_label.setPixmap(grey_pixmap)
            elif os.path.exists(abs_icon_path):
                pixmap = QPixmap(abs_icon_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.icon_label.setPixmap(scaled_pixmap)
                else:
                    self.icon_label.setStyleSheet("background-color: red;")
            else:
                self.icon_label.setStyleSheet("background-color: red;")
            self.icon_label.setVisible(True)
        else:
            self.icon_label.setVisible(False)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; background-color: transparent;")
        
        self.header_layout.addWidget(self.icon_label)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()

        self.main_layout.addWidget(self.header_widget)
        
        # Hide header if no title and no icon provided (to save space)
        if not title and not icon_path:
            self.header_widget.setVisible(False)

        # 2. Mode Buttons Section (Container)
        self.mode_buttons_container = QWidget()
        self.mode_buttons_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mode_buttons_layout = QVBoxLayout(self.mode_buttons_container)
        self.mode_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_buttons_layout.setSpacing(0)
        self.main_layout.addWidget(self.mode_buttons_container)
        self.mode_buttons_container.setVisible(False) # Hidden by default
        self.mode_buttons_widget = None

        # 3. Content Section (QFormLayout)
        self.content_widget = QWidget()
        self.content_layout = QFormLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 5, 12, 12)
        self.content_layout.setVerticalSpacing(14)
        self.main_layout.addWidget(self.content_widget)

    def add_mode_buttons(self, default_mode="Max Size"):
        """Adds mode buttons to the group."""
        self.mode_buttons_widget = ModeButtonsWidget(default_mode=default_mode)
        self.mode_buttons_layout.addWidget(self.mode_buttons_widget)
        self.mode_buttons_container.setVisible(True)
        return self.mode_buttons_widget

    def get_content_layout(self):
        """Returns the form layout to add rows to."""
        return self.content_layout
        
    def add_row(self, label, field=None, with_icon=False, icon_path=None):
        """Helper to add a row to the content layout."""
        # Check if label is a string, if so, create a standardized label with icon placeholder
        if isinstance(label, str):
            if with_icon:
                # Determine icon based on label text if not provided
                if icon_path is None:
                    if "Resize" in label:
                        icon_path = "client/assets/icons/scale.png"
                    elif "Rotation" in label:
                        icon_path = "client/assets/icons/rotate.png"
                label_widget = self._create_label_with_icon_placeholder(label, icon_path)
            else:
                label_widget = QLabel(label)
                
            if field:
                self.content_layout.addRow(label_widget, field)
            else:
                self.content_layout.addRow(label_widget)
        else:
            if field:
                self.content_layout.addRow(label, field)
            else:
                self.content_layout.addRow(label)

    def _create_label_with_icon_placeholder(self, text, icon_path=None):
        container = QWidget()
        container.setMinimumHeight(24)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Create icon label - 24x24
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if icon_path:
            # Resolve absolute path for the bundle
            abs_icon_path = get_resource_path(icon_path)
            # Prefer SVG over PNG for crisp rendering
            svg_path = abs_icon_path.replace('.png', '.svg')
            
            if os.path.exists(svg_path):
                # Use QIcon for high-quality SVG rendering
                icon = QIcon(svg_path)
                pixmap = icon.pixmap(24, 24, mode=QIcon.Mode.Normal, state=QIcon.State.On)
                # Apply grey tint with smooth rendering
                grey_pixmap = QPixmap(24, 24)
                grey_pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(grey_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.drawPixmap(0, 0, pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(grey_pixmap.rect(), QColor(136, 136, 136))  # #888888
                painter.end()
                icon_label.setPixmap(grey_pixmap)
            elif os.path.exists(abs_icon_path):
                pixmap = QPixmap(abs_icon_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    icon_label.setPixmap(scaled_pixmap)
                else:
                    icon_label.setStyleSheet("background-color: red;")
            else:
                icon_label.setStyleSheet("background-color: red;")
        else:
            icon_label.setStyleSheet("background-color: red;")
        
        # Create text label
        text_label = QLabel(text)
        
        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addStretch() # Ensure left alignment
        
        return container
