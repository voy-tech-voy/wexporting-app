from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget, QApplication
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, Property
from PySide6.QtGui import QIcon, QPixmap
from client.utils.resource_path import get_resource_path
from client.gui.theme_variables import ThemeVariables

class PresetCard(QFrame):
    """
    A 3:4 aspect ratio card representing an export preset.
    Displays an icon (Zone A) and text (Zone B).
    """
    def __init__(self, preset_obj, parent=None):
        super().__init__(parent)
        self.preset = preset_obj
        self.setFixedSize(120, 160)
        self.setProperty("class", "PresetCard")
        self.setProperty("dragActive", False)
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(0)
        
        # Zone A: Icon Chamber
        self.icon_lbl = QLabel()
        self.icon_lbl.setObjectName("CardIcon")
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load Icon
        icon_path = get_resource_path(f"client/assets/icons/{preset_obj.icon_name}")
        if icon_path:
             # Use a smaller pixmap for the icon inside
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                 # Scale to appropriate size (e.g. 48x48)
                self.icon_lbl.setPixmap(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        
        layout.addWidget(self.icon_lbl, 3) # Stretch 3
        
        # Zone B: Text Base
        self.title_lbl = QLabel(preset_obj.title)
        self.title_lbl.setObjectName("CardTitle")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.sub_lbl = QLabel(preset_obj.subtitle)
        self.sub_lbl.setObjectName("CardSubtitle")
        self.sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.title_lbl, 0)
        layout.addWidget(self.sub_lbl, 0)
        
        self.setup_styles()
        
    def setup_styles(self):
        """Define strictly component-scoped QSS"""
        # Note: Colors should match theme variables where possible, but here we hardcode from spec for now
        # or inject from ThemeVariables if we want dynamic theming.
        # Spec defines dark mode colors.
        
        self.setStyleSheet("""
            QFrame[class="PresetCard"] {
                background-color: #1C1C1C;
                border: 1px solid #333333;
                border-radius: 12px;
            }
            QFrame[class="PresetCard"]:hover {
                background-color: #252525;
                border: 1px solid #666666;
            }
            QFrame[class="PresetCard"][dragActive="true"] {
                background-color: rgba(0, 224, 255, 0.1);
                border: 2px solid #00E0FF;
            }
            
            QLabel#CardIcon {
                background-color: transparent;
                padding: 10px;
            }
            
            QLabel#CardTitle {
                color: #F5F5F7;
                font-family: "Segoe UI", sans-serif;
                font-size: 13px;
                font-weight: 700;
                margin-bottom: 2px;
            }
            
            QLabel#CardSubtitle {
                color: #86868B;
                font-family: "Consolas", monospace;
                font-size: 10px;
                font-weight: 400;
            }
            /* Active Subtitle Color */
            QFrame[class="PresetCard"][dragActive="true"] QLabel#CardSubtitle {
                color: #00E0FF;
            }
        """)

    def set_active_state(self, is_active: bool):
        """Toggle the active drag state visual"""
        if self.property("dragActive") != is_active:
            self.setProperty("dragActive", is_active)
            self.style().unpolish(self)
            self.style().polish(self)

    def trigger_success_animation(self):
        """Flash Green to confirm drop"""
        # Quick inline style for success, then reset
        original_style = self.styleSheet()
        self.setStyleSheet(original_style + """
            QFrame[class="PresetCard"] {
                background-color: #00CC44 !important;
                border: 2px solid #00FF55 !important;
            }
        """)
        QApplication.processEvents()
        
        # Use a timer to revert? 
        # Actually simplest is just to set a flag or let the overlay handle the reset.
        # But for self-contained:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(150, lambda: self.setup_styles())
