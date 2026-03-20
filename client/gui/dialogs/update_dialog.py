"""
Update Dialog
Shows available updates to the user.
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTextBrowser
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
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


class OptionalUpdateDialog(QDialog):
    """
    Dismissible dialog shown when an optional app update is available.
    User can choose 'Later' to skip or 'Update Now' to open the download URL.
    """
    def __init__(self, update_result, parent=None, theme_manager=None):
        super().__init__(parent)
        self.update_result = update_result
        self.setWindowTitle("Update Available")
        self.setFixedWidth(420)
        self.setFixedHeight(220)

        tm = theme_manager or ThemeManager.instance()
        colors = tm.get_colors()

        layout = QVBoxLayout(self)

        header = QLabel("A new version is available")
        header.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {colors['text']};")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        version_label = QLabel(f"Version {update_result.latest_version} is ready to install.")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(f"color: {colors['text_secondary']}; margin: 6px 0;")
        layout.addWidget(version_label)

        if update_result.release_notes:
            notes = QLabel(update_result.release_notes[:160])
            notes.setWordWrap(True)
            notes.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 11px;")
            layout.addWidget(notes)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 0)

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
            QPushButton:hover {{ background-color: {colors['accent_hover']}; }}
            QPushButton:pressed {{ background-color: {colors['accent_pressed']}; }}
        """)
        self.btn_update.clicked.connect(self._open_update)

        btn_layout.addWidget(self.btn_later)
        btn_layout.addWidget(self.btn_update)
        layout.addLayout(btn_layout)

    def _open_update(self):
        if self.update_result.update_url:
            QDesktopServices.openUrl(QUrl(self.update_result.update_url))
        self.accept()


class MandatoryUpdateScreen(QDialog):
    """
    Blocking full-screen dialog shown when the current version is below the
    minimum required. The user cannot dismiss this — 'Update Now' is the only
    exit (opens the download URL and quits the app via sys.exit in main).
    """
    def __init__(self, update_result, theme_manager=None, parent=None):
        super().__init__(parent)
        self.update_result = update_result
        self.setWindowTitle("Update Required")
        self.setFixedWidth(460)
        self.setFixedHeight(240)
        # Remove the close (X) button so the user cannot dismiss the dialog
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowCloseButtonHint
        )

        tm = theme_manager or ThemeManager.instance()
        colors = tm.get_colors()

        layout = QVBoxLayout(self)

        header = QLabel("Update Required")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {colors['text']};")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        msg = QLabel(
            "This version of the app is no longer supported.\n"
            "Please update to continue using the application."
        )
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet(f"color: {colors['text_secondary']}; margin: 10px 0;")
        layout.addWidget(msg)

        if update_result.latest_version:
            ver = QLabel(f"Latest version: {update_result.latest_version}")
            ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ver.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 11px;")
            layout.addWidget(ver)

        layout.addStretch()

        self.btn_update = QPushButton("Update Now")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['accent']};
                color: {colors['text_on_accent']};
                border: none;
                padding: 10px 24px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{ background-color: {colors['accent_hover']}; }}
            QPushButton:pressed {{ background-color: {colors['accent_pressed']}; }}
        """)
        self.btn_update.clicked.connect(self._open_update)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.btn_update)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _open_update(self):
        if self.update_result.update_url:
            QDesktopServices.openUrl(QUrl(self.update_result.update_url))
        self.accept()

    def closeEvent(self, event):
        # Block the close event — user must click Update Now
        event.ignore()
