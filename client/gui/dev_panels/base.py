"""
Base class for all Developer Panels.
Enforces consistent styling (Dark Mode) and common functionality.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent

from client.gui.theme import Theme

class BaseDevPanel(QWidget):
    """
    Base class for Dev Panels.
    Provides standard layout, dark styling, and common signals.
    """
    
    # Signal emitted when changes should be applied/saved
    apply_changes = Signal()
    
    def __init__(self, title="Dev Panel", parent=None, width=500, height=600):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(title)
        self.setMinimumSize(width, height)
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)
        
        # Standard Header
        self._setup_header(title)
        
        # Content Area (Scrollable by default)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        
        self.scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll, 1) # Expand to fill
        
        # Footer Action Area
        self._setup_footer()
        
        # Apply Base Styling
        self._apply_base_theme()

    def _setup_header(self, title_text):
        """Standard header with title."""
        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #F5F5F7;") 
        
        header_layout.addWidget(title)
        self.main_layout.addWidget(header_container)

    def _setup_footer(self):
        """Standard footer with Apply/Save and Close buttons."""
        footer_container = QWidget()
        self.footer_layout = QHBoxLayout(footer_container)
        self.footer_layout.setContentsMargins(0, 10, 0, 0)
        self.footer_layout.setSpacing(12)
        
        # Subclasses can add more buttons here via add_footer_button
        
        self.footer_layout.addStretch()
        
        # Close Button
        self.close_btn = QPushButton("Close")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        self.style_button(self.close_btn, bg_color="#3A3A3C", hover_color="#48484A")
        self.footer_layout.addWidget(self.close_btn)
        
        self.main_layout.addWidget(footer_container)

    def add_footer_button(self, text, callback, primary=False, color=None):
        """Helper to add buttons to the footer."""
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(callback)
        
        if color:
             self.style_button(btn, bg_color=color)
        elif primary:
            # Green/Accent style
            self.style_button(btn, bg_color="#30D158", hover_color="#28B04A", text_color="white")
        else:
            # Secondary style
            self.style_button(btn, bg_color="#3A3A3C", hover_color="#48484A")
            
        # Insert before the Close button (which is last)
        count = self.footer_layout.count()
        if count > 1:
            self.footer_layout.insertWidget(count - 2, btn) # Before stretch and close
        else:
            self.footer_layout.insertWidget(0, btn)
            
        return btn

    def style_button(self, btn, bg_color="#3A3A3C", hover_color=None, text_color="#FFFFFF"):
        """Apply consistent button styling."""
        if hover_color is None:
            # Simple lighten for hover if not specified
            hover_color = bg_color 
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                border: 1px solid rgba(255,255,255,0.3);
            }}
            QPushButton:pressed {{
                background-color: {bg_color};
                color: rgba(255,255,255,0.7);
            }}
        """)

    def _apply_base_theme(self):
        """Enforce Dark Mode styling for the panel itself."""
        # We manually set specific dark colors to ensure it's always dark 
        # regardless of the app's current theme.
        self.setStyleSheet("""
            BaseDevPanel, QWidget {
                background-color: #1C1C1E; /* iOS System Gray 6 (Dark) */
                color: #F5F5F7;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QLabel {
                color: #F5F5F7;
            }
            QGroupBox {
                border: 1px solid #38383A;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #8E8E93; /* System Gray */
            }
            QSlider::groove:horizontal {
                border: 1px solid #38383A;
                height: 6px;
                background: #2C2C2E;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0A84FF; /* iOS Blue */
                border: 1px solid #0A84FF;
                width: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #409CFF;
            }
        """)

    def keyPressEvent(self, event: QKeyEvent):
        """Close on Escape."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
