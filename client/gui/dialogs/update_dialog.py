"""
Update Dialog
Shows available updates to the user.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTextBrowser
from PyQt6.QtCore import Qt
from client.gui.theme_manager import ThemeManager

class UpdateDialog(QDialog):
    """
    Dialog showing available updates and asking for confirmation.
    """
    def __init__(self, manifest, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Updates Available")
        self.setFixedWidth(450)
        self.setFixedHeight(400)
        
        # Get theme manager
        self.theme_manager = ThemeManager.instance()
        colors = self.theme_manager.get_colors()
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("New Content Available")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; margin-bottom: 10px; color: {colors['text']};")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Description
        desc = QLabel("The following components have updates available:")
        desc.setStyleSheet(f"color: {colors['text_secondary']}; margin-bottom: 5px;")
        layout.addWidget(desc)
        
        # Details Area
        self.details = QTextBrowser()
        self.details.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 10px;
                font-family: Consolas, monospace;
                color: {colors['text']};
            }}
        """)
        
        # Build update list
        html = ""
        
        if manifest.presets:
            html += f"<h3 style='color: {colors['accent']};'>Presets</h3><ul>"
            for p in manifest.presets:
                name = p.get('name', p['id'])
                version = p.get('version', 'new')
                html += f"<li><b>{name}</b> <span style='color: {colors['text_secondary']};'>v{version}</span></li>"
            html += "</ul>"
            
        if manifest.estimators:
            html += f"<h3 style='color: {colors['primary']};'>Intelligence</h3><ul>"
            for e in manifest.estimators:
                name = e.get('name', e['id'])
                version = e.get('version', 'new')
                html += f"<li><b>{name}</b> <span style='color: {colors['text_secondary']};'>v{version}</span></li>"
            html += "</ul>"
            
        self.details.setHtml(html)
        layout.addWidget(self.details)
        
        # Summary
        total_count = len(manifest.presets) + len(manifest.estimators)
        summary = QLabel(f"{total_count} items will be updated.")
        summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        summary.setStyleSheet(f"color: {colors['text_secondary']}; margin-top: 5px;")
        layout.addWidget(summary)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 10, 0, 0)
        
        self.btn_later = QPushButton("Later")
        self.btn_later.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_later.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {colors['border']};
                color: {colors['text']};
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {colors['surface']};
                border-color: {colors['border_hover']};
            }}
        """)
        self.btn_later.clicked.connect(self.reject)
        
        self.btn_update = QPushButton("Update Now")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['accent']};
                color: {colors['text_on_accent']};
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors['accent_hover']};
            }}
            QPushButton:pressed {{
                background-color: {colors['accent_pressed']};
            }}
        """)
        self.btn_update.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_later)
        btn_layout.addWidget(self.btn_update)
        
        layout.addLayout(btn_layout)
