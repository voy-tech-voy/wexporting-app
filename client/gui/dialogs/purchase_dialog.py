import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon

from client.utils.font_manager import AppFonts
from client.gui.theme import Theme
from client.gui.utils.winrt_interop import WinRTInterop
from client.gui.utils.window_effects import WindowEffects
from client.core.auth import get_store_auth_provider
from PyQt6.QtCore import QEvent

import logging
logger = logging.getLogger("PurchaseDialog")

class PurchaseDialog(QDialog):
    """
    Native-feeling purchase dialog for MS Store IAP.
    Handles loading state, window association, and result masking.
    """
    
    def __init__(self, product_id: str, title: str = "Confirm Purchase", 
                 description: str = "Fetching details...", price: str = "TBD", parent=None):
        super().__init__(parent)
        self.product_id = product_id
        
        # UI Setup
        self.setWindowTitle("Store Purchase")
        self.setFixedSize(400, 250)
        # Use Tool type for clean window without maximize/minimize
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        
        # Styles
        # Use Theme methods safely
        text_color = Theme.text()
        accent_color = Theme.accent()
        text_muted = Theme.text_muted()
        
        # Initial Transparent Background for Mica
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: transparent;
                color: {text_color};
            }}
            QLabel {{ color: {text_color}; }}
            QPushButton {{
                background-color: {accent_color};
                color: #000000;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-family: 'Segoe UI', sans-serif;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
            QPushButton:disabled {{ background-color: #555555; color: #888888; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        self.lbl_title = QLabel(title)
        title_font = QFont(AppFonts.get_base_font().family(), 14)
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)
        layout.addWidget(self.lbl_title)
        
        # Description
        self.lbl_desc = QLabel(description)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setFont(QFont(AppFonts.get_base_font().family(), 10))
        layout.addWidget(self.lbl_desc)
        
        # Product ID (Debug/Info)
        lbl_id = QLabel(f"Item ID: {product_id}")
        lbl_id.setStyleSheet(f"color: {text_muted}; font-size: 10px;")
        layout.addWidget(lbl_id)
        
        # Spacer
        layout.addStretch()
        
        # Progress Indicator (Hidden by default)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0) # Indeterminate
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setVisible(False)
        # Style the progress bar chunks
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: #333;
                height: 4px;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {accent_color};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress)
        
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(f"""
            background-color: transparent; 
            border: 1px solid #555; 
            color: {text_muted};
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        self.btn_buy = QPushButton("Buy Now")
        self.btn_buy.clicked.connect(self._on_buy_clicked)
        btn_layout.addWidget(self.btn_buy)
        
        layout.addLayout(btn_layout)
        
        # Apply initial effects
        self._apply_effects()

    def _apply_effects(self):
        """Apply Windows 11/10 effects"""
        hwnd = int(self.winId())
        WindowEffects.apply_mica(hwnd, Theme.is_dark())
        WindowEffects.set_rounded_corners(hwnd)

    def changeEvent(self, event):
        """Handle window activation for resource saving"""
        if event.type() == QEvent.Type.ActivationChange:
            hwnd = int(self.winId())
            if self.isActiveWindow():
                # Active: Transparent bg + Mica
                self.setStyleSheet(self.styleSheet().replace(f"background-color: {Theme.bg()};", "background-color: transparent;"))
                WindowEffects.apply_mica(hwnd, Theme.is_dark())
            else:
                # Inactive: Solid bg + No Mica (Save User resources)
                # Note: We must set solid color because WA_TranslucentBackground makes it see-through otherwise
                bg = Theme.bg()
                self.setStyleSheet(self.styleSheet().replace("background-color: transparent;", f"background-color: {bg};"))
                WindowEffects.remove_background(hwnd)
        
        super().changeEvent(event)
        
    def _on_buy_clicked(self):
        """Handle Buy button click."""
        # 1. UI Busy State
        self.btn_buy.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress.setVisible(True)
        self.lbl_desc.setText("Contacting Microsoft Store...")
        
        # Force UI update
        QApplication.processEvents()
        
        # 2. Get Provider
        try:
            provider = get_store_auth_provider()
            
            # 3. Get Window Handle
            # Use 'effectiveWinId' or convert valid winId
            hwnd = int(self.winId())
            logger.info(f"PurchaseDialog: Initiating purchase for {self.product_id} with HWND {hwnd}")
            
            # 4. Call Async Purchase via Provider
            # Note: request_purchase/purchase_add_on is synchronous wrapper around async
            success = provider.purchase_add_on(self.product_id, window_handle=hwnd)
            
            if success:
                self.lbl_desc.setText("Purchase Successful!")
                self.progress.setVisible(False)
                # Auto-close after short delay
                QTimer.singleShot(1500, self.accept)
            else:
                # Failed or Cancelled
                self.lbl_desc.setText("Purchase cancelled or failed.")
                self.progress.setVisible(False)
                self.btn_buy.setEnabled(True)
                self.btn_cancel.setEnabled(True)
                
        except Exception as e:
            logger.error(f"Purchase Error: {e}")
            self.lbl_desc.setText(f"Error: {str(e)}")
            self.progress.setVisible(False)
            self.btn_buy.setEnabled(True)
            self.btn_cancel.setEnabled(True)

    def closeEvent(self, event):
        if self.progress.isVisible():
            event.ignore() # Prevent closing while busy
        else:
            super().closeEvent(event)
