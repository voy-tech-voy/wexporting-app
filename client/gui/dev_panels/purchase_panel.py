import logging
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QComboBox, QFormLayout, QPushButton, 
    QColorDialog, QHBoxLayout, QLabel, QApplication, QMessageBox, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from client.gui.dev_panels.base import BaseDevPanel
from client.gui.theme import Theme

logger = logging.getLogger("PurchaseDevPanel")

class PurchaseDevPanel(BaseDevPanel):
    """
    Dev Panel for interactively editing Purchase Window styles.
    Reads/Writes to client/config/purchase_options.json.
    """
    
    def __init__(self, parent=None):
        super().__init__("Purchase Window Style", parent, width=500, height=700)
        
        self.options_data = []
        self.current_option_idx = 0
        self.color_buttons = {} # key -> QPushButton
        self.style_cache = {} # id -> style dict
        
        self._setup_ui()
        self._load_options()
        
        # Add Save Button to footer
        self.add_footer_button("Save to JSON", self._save_options, primary=True)

    def _setup_ui(self):
        """Setup the panel UI components."""
        layout = QVBoxLayout(self.content_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Card Selector
        selector_container = QWidget()
        selector_layout = QHBoxLayout(selector_container)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_select = QLabel("Select Card:")
        lbl_select.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.combo_cards = QComboBox()
        self.combo_cards.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 1px solid #38383A;
                border-radius: 6px;
                background: #2C2C2E;
                color: white;
            }
            QComboBox::drop-down { border: none; }
        """)
        self.combo_cards.currentIndexChanged.connect(self._on_card_changed)
        
        selector_layout.addWidget(lbl_select)
        selector_layout.addWidget(self.combo_cards, 1)
        layout.addWidget(selector_container)
        
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #38383A;")
        layout.addWidget(line)
        
        # Colors Form
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(15)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Define style keys to edit
        self.style_keys = [
            ("Outline Active", "outline_active"),
            ("Button BG Ghost", "btn_bg_ghost"),
            ("Button BG Active", "btn_bg_active"),
            ("Button Text Ghost", "btn_text_ghost"),
            ("Button Text Active", "btn_text_active"),
            ("Price Color", "price_color")
        ]
        
        for label, key in self.style_keys:
            btn_color = QPushButton()
            btn_color.setFixedSize(100, 30)
            btn_color.setCursor(Qt.CursorShape.PointingHandCursor)
            # Store key on button for callback
            btn_color.clicked.connect(lambda checked, k=key: self._pick_color(k))
            
            self.color_buttons[key] = btn_color
            
            # Label Styling
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 13px; color: #D1D1D6;")
            
            self.form_layout.addRow(lbl, btn_color)
            
        layout.addLayout(self.form_layout)
        layout.addStretch()

    def _load_options(self):
        """Load purchase options from JSON."""
        try:
            # Path relative to this file: ../../../config/purchase_options.json
            config_path = Path(__file__).parent.parent.parent / 'config' / 'purchase_options.json'
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.full_json_data = data # Keep full structure for saving
                    self.options_data = data.get('options', [])
                
                # Populate Combo
                self.combo_cards.clear()
                for opt in self.options_data:
                    self.combo_cards.addItem(f"{opt.get('name')} ({opt.get('id')})", opt.get('id'))
                
                # Load first option
                if self.options_data:
                    self._load_card_style(0)
            else:
                QMessageBox.warning(self, "Error", "Config file not found.")
                
        except Exception as e:
            logger.error(f"Failed to load options: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load options: {e}")

    def _on_card_changed(self, index):
        """Handle card selection change."""
        if index >= 0:
            self.current_option_idx = index
            self._load_card_style(index)

    def _load_card_style(self, index):
        """Load style into UI controls for specific card."""
        if index < 0 or index >= len(self.options_data):
            logger.warning(f"Invalid index {index}, options_data length: {len(self.options_data)}")
            return
            
        opt = self.options_data[index]
        style = opt.get('style', {})
        self.current_style = style # Reference to dict in options_data
        
        logger.info(f"Loading card style for index {index}: {opt.get('name')}")
        logger.info(f"Style data: {style}")
        logger.info(f"Color buttons available: {list(self.color_buttons.keys())}")
        
        # Update buttons
        for label, key in self.style_keys:
            val = style.get(key)
            logger.info(f"Setting {key} = {val}")
            self._update_color_button(key, val)

    def _update_color_button(self, key, color_str):
        """Update button appearance based on color string."""
        btn = self.color_buttons.get(key)
        if not btn: 
            return
            
        if color_str:
            # Parse color - handle both hex (#RRGGBB) and rgba(r, g, b, a) formats
            col = None
            
            if color_str.startswith('rgba('):
                # Parse rgba(r, g, b, a) format
                import re
                match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color_str)
                if match:
                    r, g, b, a = match.groups()
                    col = QColor(int(r), int(g), int(b))
                    col.setAlphaF(float(a))
            else:
                # Try as hex or named color
                col = QColor(color_str)
            
            # Check if valid
            if col and col.isValid():
                # Set background
                # Use rgba for stylesheet
                rgba = f"rgba({col.red()},{col.green()},{col.blue()},{col.alphaF():.2f})"
                
                # Text color logic for readability
                text_col = "black" if (col.lightness() > 128 or col.alpha() < 100) else "white"
                
                btn.setStyleSheet(f"""
                    background-color: {rgba};
                    color: {text_col};
                    border: 1px solid #555;
                    border-radius: 4px;
                """)
                btn.setText(color_str if col.alpha() == 255 else f"RGBA({col.alpha()})")
            else:
                btn.setStyleSheet("background: none; border: 1px dashed #555; color: #777;")
                btn.setText("Invalid")
        else:
            btn.setStyleSheet("background: none; border: 1px dashed #555; color: #777;")
            btn.setText("None (Default)")

    def _pick_color(self, key):
        """Open Color Dialog for a key."""
        # Get current color
        current_val = self.current_style.get(key)
        initial = QColor(current_val) if current_val else QColor(Theme.accent())
        
        # Open Dialog with Alpha
        col = QColorDialog.getColor(
            initial, 
            self, 
            f"Select Color for {key}", 
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        
        if col.isValid():
            # Format as string
            if col.alpha() < 255:
                # Use rgba string: rgba(r, g, b, a_float) match typical web usage
                col_str = f"rgba({col.red()}, {col.green()}, {col.blue()}, {col.alphaF():.2f})"
            else:
                col_str = col.name().upper() # #RRGGBB
            
            # Update Data
            self.current_style[key] = col_str
            
            # Update UI
            self._update_color_button(key, col_str)
            
            # Push Update to Live Window
            self._push_update_to_window()

    def _push_update_to_window(self):
        """Push current style to active PurchaseDialog."""
        app = QApplication.instance()
        
        # Find PurchaseDialog in topLevelWidgets
        # We look for window title or class name
        for w in app.topLevelWidgets():
            # It's a QDialog subclass
            if w.metaObject().className() == "PurchaseDialog" and w.isVisible():
                # Found it
                card_id = self.options_data[self.current_option_idx].get('id')
                if hasattr(w, 'update_card_style'):
                    w.update_card_style(card_id, self.current_style)
                break

    def _save_options(self):
        """Save changes back to JSON."""
        try:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'purchase_options.json'
            
            # We modified self.options_data in place (ref), which is inside self.full_json_data
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.full_json_data, f, indent=4)
                
            QMessageBox.information(self, "Saved", "Purchase options saved successfully.")
            
        except Exception as e:
            logger.error(f"Failed to save options: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save options: {e}")
