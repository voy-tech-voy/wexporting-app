import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QApplication, QWidget, QScrollArea,
    QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QIcon, QColor, QPainter, QBrush

from client.utils.font_manager import AppFonts
from client.gui.theme import Theme
from client.gui.utils.winrt_interop import WinRTInterop
from client.gui.utils.window_effects import WindowEffects
from client.core.auth import get_store_auth_provider
from PyQt6.QtCore import QEvent

import logging
logger = logging.getLogger("PurchaseDialog")


class PurchaseOptionCard(QWidget):
    """
    Card widget for a single purchase option with smooth hover animations.
    """
    purchase_requested = pyqtSignal(str)  # Emits product_id
    
    def __init__(self, option_data: dict, parent=None):
        super().__init__(parent)
        self.option_data = option_data
        self.product_id = option_data.get('product_id', '')
        
        # Animation state
        # Initial Border Color will be set in _setup_ui based on theme
        self._border_color = QColor("#707070") 
        self._bg_opacity = 0.95 # Opaque initially
        self._button_opacity = 0.3 # Ghost opacity (Static)
        self._text_color = QColor("#B0B0B0") # Light grey for ghost state
        
        # Color mapping using Theme variables
        # This allows purchase_options.json to specify 'blue', 'green', etc.
        # and we map them to the correct Theme colors.
        color_map = {
            'blue': Theme.accent(),
            'green': Theme.success(),
            'purple': Theme.color('accent_turbo'), # Using turbo for purple/electric look
            'orange': Theme.warning(),
            'red': Theme.error()
        }
        
        color_key = option_data.get('color', 'blue')
        # specific check if the json value is a direct hex code (starts with #)
        if color_key.startswith('#'):
             self.accent_color = QColor(color_key)
        else:
             self.accent_color = QColor(color_map.get(color_key, Theme.accent()))
             
        # Initial default border (will be updated in _setup_ui)
        self.default_border = QColor("#505050") 
        
        # Initialize bg_base early (needed by _apply_style_config)
        surface = QColor(Theme.surface())
        if not Theme.is_dark():
            surface = surface.darker(105)
            if surface.lightness() > 240:
                surface = QColor(245, 245, 245)
        self.bg_base = f"{surface.red()}, {surface.green()}, {surface.blue()}"
        
        # Ensure custom painting works
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("PurchaseOptionCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Load style config from option_data
        self._load_style_config()
        
        self._setup_ui()
        self._setup_animations()

    def _load_style_config(self):
        """Load dynamic style configuration from option data."""
        style = self.option_data.get('style', {})
        
        # Helper to parse color strings (handles both hex and rgba formats)
        def parse_color(color_str, fallback_color):
            """Parse color string, supporting hex and rgba() formats."""
            if not color_str:
                return fallback_color
                
            if color_str.startswith('rgba('):
                # Parse rgba(r, g, b, a) format
                import re
                match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color_str)
                if match:
                    r, g, b, a = match.groups()
                    col = QColor(int(r), int(g), int(b))
                    col.setAlphaF(float(a))
                    return col
                else:
                    # Invalid rgba format, use fallback
                    return fallback_color
            else:
                # Try as hex or named color
                col = QColor(color_str)
                if col.isValid():
                    return col
                else:
                    return fallback_color
        
        # Helper to resolve color
        def resolve_color(key, default_color_obj):
            val = style.get(key)
            return parse_color(val, default_color_obj)
            
        # Default colors (Ghost state)
        self._col_outline_ghost = QColor("#707070") # Will be updated in setup_ui based on theme
        
        # Button BG Ghost - read from JSON or fallback to grey
        ghost_default = QColor("#808080")  # Grey fallback
        ghost_default.setAlphaF(0.3)
        self._col_btn_bg_ghost = parse_color(style.get('btn_bg_ghost'), ghost_default)
        
        self._col_btn_text_ghost = resolve_color('btn_text_ghost', QColor("#B0B0B0"))
        
        # Default colors (Active state)
        self._col_outline_active = resolve_color('outline_active', self.accent_color)
        
        # Button BG Active - read from JSON or fallback to grey
        active_default = QColor("#808080")  # Grey fallback
        active_default.setAlphaF(0.5)
        self._col_btn_bg_active = parse_color(style.get('btn_bg_active'), active_default)
        
        self._col_btn_text_active = resolve_color('btn_text_active', QColor("#FFFFFF"))
        
        self._col_price = resolve_color('price_color', self.accent_color)
        
        
        # Initialize current state to ghost values
        self._button_bg_color = self._col_btn_bg_ghost
        self._text_color = self._col_btn_text_ghost
        
        # Note: _apply_style_config() will be called after _setup_ui() creates the widgets


    def _apply_style_config(self):
        """Apply the currently loaded style configuration to widgets."""
        # Initial Border and Outline Color
        # Use Dynamic Ghost Outline
        self._border_color = self._col_outline_ghost
        # Also need to update default border used in leaveEvent
        self.default_border = self._col_outline_ghost

        # Update stylesheet
        self.setStyleSheet(f"""
            #PurchaseOptionCard {{
                background-color: rgba({self.bg_base}, {self._bg_opacity});
                border: 3px solid {self._border_color.name()};
                border-radius: 12px;
            }}
        """)
        
        # Update button style
        self._update_button_style()
        
        # Trigger repaint
        self.update()

    def update_style_config(self, new_style: dict):
        """Public method to update style config dynamically."""
        if not new_style:
             return
             
        # Merge new style into existing option_data['style']
        current_style = self.option_data.get('style', {})
        current_style.update(new_style)
        self.option_data['style'] = current_style
        
        # Reload and Apply
        self._load_style_config()
    
    def _setup_ui(self):
        """Setup the card UI."""
        # Align with App Theme
        text_color = Theme.text()
        text_muted = Theme.text_muted()
        
        # Note: bg_base is now initialized in __init__
        bg_base = self.bg_base  # Use the already-initialized value
        
        
        # Initial border color (Theme border or slightly stronger)
        # Use a dynamic border color based on theme
        border_c = QColor(Theme.border())
        if Theme.is_dark():
            border_c = border_c.lighter(150)
        else:
            border_c = border_c.darker(110)
            
            border_c = border_c.darker(110)
            
            
        self._border_color = border_c
        self.default_border = border_c # Ensure hover exit uses this color
        self._col_outline_ghost = border_c # Update ghost outline to match theme
        
        # Semi-transparent background (User requested "opaque all the time")
        # Setting to 0.95 to keep slight depth but opaque mostly
        self._bg_opacity = 0.95
        
        # Initial stylesheet (border set in _apply_style_config)
        self.setStyleSheet(f"""
            #PurchaseOptionCard {{
                background-color: rgba({bg_base}, {self._bg_opacity});
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 24, 20, 24)
        
        # Cost label
        lbl_cost = QLabel(self.option_data.get('cost', '$0.00'))
        cost_font = QFont(AppFonts.get_base_font().family(), 24)
        cost_font.setBold(True)
        lbl_cost.setFont(cost_font)
        lbl_cost.setFont(cost_font)
        lbl_cost.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_cost.setStyleSheet(f"color: {self._col_price.name()}; background: transparent; border: none;")
        layout.addWidget(lbl_cost)
        
        # Name label
        lbl_name = QLabel(self.option_data.get('name', 'Unknown'))
        name_font = QFont(AppFonts.get_base_font().family(), 14)
        name_font.setBold(True)
        lbl_name.setFont(name_font)
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_name.setStyleSheet(f"color: {text_color}; background: transparent; border: none;")
        layout.addWidget(lbl_name)
        
        # Divider
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: rgba(128, 128, 128, 0.2);")
        layout.addWidget(line)
        
        # Description
        lbl_desc = QLabel(self.option_data.get('description', ''))
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        lbl_desc.setFont(QFont(AppFonts.get_base_font().family(), 10))
        lbl_desc.setStyleSheet(f"color: {text_muted}; background: transparent; border: none;")
        layout.addWidget(lbl_desc, 1)
        
        # Ghost-style buy button (starts semi-transparent)
        self.btn_buy = QPushButton(self.option_data.get('button_label', 'Buy'))
        self.btn_buy.setObjectName("GhostButton")
        self.btn_buy.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Card handles clicks
        self._update_button_style()
        layout.addWidget(self.btn_buy)
        
        # Now that all widgets are created, apply the style configuration
        self._apply_style_config()
    
    def _setup_animations(self):
        """Setup smooth animations for hover effects."""
        # Border color animation
        self.border_anim = QPropertyAnimation(self, b"borderColor")
        self.border_anim.setDuration(300)
        self.border_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Background opacity animation
        self.bg_anim = QPropertyAnimation(self, b"bgOpacity")
        self.bg_anim.setDuration(300)
        self.bg_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Button background color animation
        self.button_bg_anim = QPropertyAnimation(self, b"buttonBgColor")
        self.button_bg_anim.setDuration(300)
        self.button_bg_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Text color animation
        self.text_anim = QPropertyAnimation(self, b"textColor")
        self.text_anim.setDuration(300)
        self.text_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
    
    # Custom properties for animation
    @pyqtProperty(QColor)
    def borderColor(self):
        return self._border_color
    
    @borderColor.setter
    def borderColor(self, color):
        self._border_color = color
        self.setStyleSheet(f"""
            #PurchaseOptionCard {{
                background-color: rgba({self.bg_base}, {self._bg_opacity});
                border: 3px solid {color.name()};
                border-radius: 12px;
            }}
        """)
    
    @pyqtProperty(float)
    def bgOpacity(self):
        return self._bg_opacity
    
    @bgOpacity.setter
    def bgOpacity(self, opacity):
        self._bg_opacity = opacity
        self.setStyleSheet(f"""
            #PurchaseOptionCard {{
                background-color: rgba({self.bg_base}, {opacity});
                border: 3px solid {self._border_color.name()};
                border-radius: 12px;
            }}
        """)
    
    @pyqtProperty(QColor)
    def buttonBgColor(self):
        return self._button_bg_color
    
    @buttonBgColor.setter
    def buttonBgColor(self, color):
        self._button_bg_color = color
        self._update_button_style()
    
    @pyqtProperty(QColor)
    def textColor(self):
        return self._text_color

    @textColor.setter
    def textColor(self, color):
        self._text_color = color
        self._update_button_style()
    
    def _update_button_style(self):
        """Update button stylesheet with current opacity."""
        # Use simple rgba string for maximum compatibility
        c = self._button_bg_color
        bg_rgba = f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alphaF():.2f})"
        
        self.btn_buy.setStyleSheet(f"""
            #GhostButton {{
                background-color: {bg_rgba};
                color: {self._text_color.name()};
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-family: 'Segoe UI', sans-serif;
                font-weight: bold;
                font-size: 14px;
            }}
        """)
    
    def enterEvent(self, event):
        """Animate to hover state."""
        # Border
        self.border_anim.stop()
        self.border_anim.setStartValue(self._border_color)
        self.border_anim.setEndValue(self._col_outline_active)
        self.border_anim.start()
        
        # Button Background
        self.button_bg_anim.stop()
        self.button_bg_anim.setStartValue(self._button_bg_color)
        self.button_bg_anim.setEndValue(self._col_btn_bg_active)
        self.button_bg_anim.start()
        
        # Button Text
        self.text_anim.stop()
        self.text_anim.setStartValue(self._text_color)
        self.text_anim.setEndValue(self._col_btn_text_active)
        self.text_anim.start()
        
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Animate back to normal state."""
        # Border
        self.border_anim.stop()
        self.border_anim.setStartValue(self._border_color)
        self.border_anim.setEndValue(self._col_outline_ghost)
        self.border_anim.start()
        
        # Button Background
        self.button_bg_anim.stop()
        self.button_bg_anim.setStartValue(self._button_bg_color)
        self.button_bg_anim.setEndValue(self._col_btn_bg_ghost)
        self.button_bg_anim.start()
        
        # Button Text
        self.text_anim.stop()
        self.text_anim.setStartValue(self._text_color)
        self.text_anim.setEndValue(self._col_btn_text_ghost)
        self.text_anim.start()
        
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle card click to trigger purchase."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.purchase_requested.emit(self.product_id)
        super().mousePressEvent(event)
    
    def set_busy(self, busy: bool):
        """Set the card to busy state."""
        self.setEnabled(not busy)
        self.btn_buy.setText("Processing..." if busy else self.option_data.get('button_label', 'Buy'))


class PurchaseDialog(QDialog):
    """
    Dynamic purchase dialog that loads options from purchase_options.json.
    Handles Windows Store IAP with proper window association.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Load purchase options
        self.options = self._load_purchase_options()
        
        # Frameless, full-screen overlay dialog
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self._setup_ui()

    def _load_purchase_options(self) -> list:
        """Load purchase options from JSON config."""
        try:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'purchase_options.json'
            
            if not config_path.exists():
                logger.warning(f"Purchase options config not found: {config_path}")
                return self._get_default_options()
            
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('options', [])
        
        except Exception as e:
            logger.error(f"Failed to load purchase options: {e}")
            return self._get_default_options()
    
    def _get_default_options(self) -> list:
        """Return default options if config fails to load."""
        return [
            {
                "id": "credits_100",
                "name": "100 Credits",
                "description": "Additional 100 credits",
                "cost": "$0.99",
                "color": "blue",
                "button_label": "Buy 100 Credits",
                "product_id": "9NBLGGH42DRG",
                "type": "consumable"
            }
        ]
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        # Main layout - centers the content panel within the full-screen overlay
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 40, 60, 40)  # Margins around the content
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Content Container (The "Frosted Glass" Frame)
        self.content_panel = QFrame()
        self.content_panel.setObjectName("ContentPanel")
        self.content_panel.setMinimumSize(550, 400)
        self.content_panel.setMaximumSize(850, 500)
        
        # Get theme-appropriate tint for the glass
        # If dark mode, use a dark tint. If light mode, white tint.
        # User asked for alpha = 0.25
        glass_tint = "255, 255, 255" if not Theme.is_dark() else "30, 30, 30"
        
        self.content_panel.setStyleSheet(f"""
            #ContentPanel {{
                background-color: rgba({glass_tint}, 0.25);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
            QLabel {{ 
                color: {Theme.text()}; 
                background: transparent; 
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
        """)
        
        # Container layout
        layout = QVBoxLayout(self.content_panel)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        # Scroll area for options (Horizontal Scroll)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Container for option cards
        cards_container = QWidget()
        cards_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        cards_container.setStyleSheet("background: transparent;")
        
        # HORIZONTAL LAYOUT for cards
        container_layout = QHBoxLayout(cards_container)
        container_layout.setSpacing(24)
        container_layout.setContentsMargins(16, 10, 16, 20)
        
        # Create cards for each option
        self.option_cards = []
        for option in self.options:
            card = PurchaseOptionCard(option, self)
            card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            card.setMinimumWidth(200)
            card.purchase_requested.connect(self._on_purchase_requested)
            container_layout.addWidget(card)
            self.option_cards.append(card)
        
        scroll.setWidget(cards_container)
        layout.addWidget(scroll, 1)
        
        # Progress Indicator (Hidden by default)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: rgba(128, 128, 128, 0.3);
                height: 4px;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.accent()};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress)
        
        # Status label
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setFont(QFont(AppFonts.get_base_font().family(), 10))
        self.lbl_status.setStyleSheet(f"color: {Theme.text_muted()};")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)
        
        # Add content panel to main layout
        main_layout.addWidget(self.content_panel, 0, Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event):
        """Paint the dim overlay background."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        painter.end()

    def showEvent(self, event):
        """Size dialog to cover parent."""
        super().showEvent(event)
        
        # Apply Acrylic/Mica Blur (Windows 10/11)
        # This blurs the content BEHIND the dialog
        try:
            # Must cast winId to int for ctypes
            WindowEffects.apply_mica(int(self.winId()), dark_mode=True)
        except Exception as e:
            logger.error(f"Failed to apply acrylic: {e}")
        
        # Size dialog to cover entire parent window
        if self.parent():
            parent_geo = self.parent().frameGeometry()
            self.setGeometry(parent_geo)
            logger.debug(f"[PurchaseDialog] Dialog geometry set to: {self.geometry()}, parent: {parent_geo}")
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging or closing."""
        self._drag_start_pos = None
        self._is_dragging = False
        
        # 1. Handle Emulated Title Bar Interactions (Drag, Min, Close)
        # Title bar is at top 0, height 45 (TitleBarWindow.TITLE_BAR_HEIGHT)
        if event.pos().y() < 45:
            # Check for button areas (Right aligned)
            # Layout logic from TitleBarWindow:
            # [Theme] 10 [Min 45] 10 [Close 45] 10 (Margin)
            
            # Close Button: Right 10 to Right 55 (45px width)
            # Minimize Button: Right 65 to Right 110 (45px width)
            
            x_from_right = self.width() - event.pos().x()
            
            # Close Button
            if 10 <= x_from_right <= 55:
                if not self.progress.isVisible():
                    self.reject() # Close dialog
                return
            
            # Minimize Button
            elif 65 <= x_from_right <= 110:
                if self.parent():
                    self.parent().showMinimized()
                return

            # Otherwise: Drag Window
            else:
                 self._drag_start_pos = event.globalPosition().toPoint()
                 self._is_dragging = True
                 return

        # 2. Check if click is inside content panel
        content_rect = self.content_panel.geometry()
        if content_rect.contains(event.pos()):
            # If inside content, checking if it's in the "Header" area of content panel (top 60px)
            local_pos = self.content_panel.mapFrom(self, event.pos())
            if local_pos.y() < 60:
                self._drag_start_pos = event.globalPosition().toPoint()
                self._is_dragging = True
        else:
            # Clicked outside - prepare to close (but wait for release to confirm it wasn't a drag)
            pass
            
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle window dragging."""
        if self._is_dragging and self._drag_start_pos:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            
            # Move the PARENT window (Main Application)
            if self.parent():
                new_pos = self.parent().pos() + delta
                self.parent().move(new_pos)
                # Sync dialog position immediately
                self.move(self.pos() + delta)
            
            self._drag_start_pos = event.globalPosition().toPoint()
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release for closing or ending drag."""
        if self._is_dragging:
            self._is_dragging = False
            self._drag_start_pos = None
        else:
            # Only close if we weren't dragging, clicked outside content, AND NOT in title bar
            # Title bar clicks are handled in mousePressEvent's immediate actions or drag start
            # But if a user clicked title bar (non-button) and didn't drag much?
            # We don't want to close.
            
            if event.pos().y() < 45:
                return # Ignore title bar releases
                
            content_rect = self.content_panel.geometry()
            if not content_rect.contains(event.pos()):
                # Confirm it wasn't a drag release (simple check)
                # Don't close if busy with purchase
                if not self.progress.isVisible():
                    self.reject()
                
        super().mouseReleaseEvent(event)
    
    def _on_purchase_requested(self, product_id: str):
        """Handle purchase request from a card."""
        # Set all cards to busy
        for card in self.option_cards:
            card.set_busy(True)
        
        self.progress.setVisible(True)
        self.lbl_status.setText("Contacting Microsoft Store...")
        self.lbl_status.setVisible(True)
        
        # Force UI update
        QApplication.processEvents()
        
        try:
            from client.config.config import Config
            if Config.DEVELOPMENT_MODE:
                logger.info(f"DEV MODE: Simulating purchase for {product_id}")
                self.lbl_status.setText(f"DEV: Simulating purchase...")
                QApplication.processEvents()
                
                from client.core.energy_manager import EnergyManager
                from client.core.session_manager import SessionManager
                em = EnergyManager.instance()
                
                if product_id == "9NBLGGH42DRH": # 500 Credits
                    em.balance += 500
                    em.save()
                    em.energy_changed.emit(em.balance, em.max_daily_energy)
                elif product_id == "9NBLGGH42DRJ": # Daily focus pack +200
                    em.max_daily_energy += 200
                    em.balance += 100
                    em.save()
                    em.energy_changed.emit(em.balance, em.max_daily_energy)
                elif product_id == "9NBLGGH42DRI": # Premium Lifetime
                    SessionManager.instance()._set_premium_status(True)
                else: # Generic fallback for testing like credits 100
                    em.balance += 100
                    em.save()
                    em.energy_changed.emit(em.balance, em.max_daily_energy)
                
                self.lbl_status.setText("DEV: Simulated Successfully!")
                self.progress.setVisible(False)
                QTimer.singleShot(1000, self.accept)
                return

            # Get Provider
            provider = get_store_auth_provider()
            
            # Get Window Handle
            hwnd = int(self.winId())
            logger.info(f"PurchaseDialog: Initiating purchase for {product_id} with HWND {hwnd}")
            
            # Call Purchase via Provider
            success = provider.purchase_add_on(product_id, window_handle=hwnd)
            
            if success:
                self.lbl_status.setText("Purchase Successful!")
                self.progress.setVisible(False)
                # Auto-close after short delay
                QTimer.singleShot(1500, self.accept)
            else:
                # Failed or Cancelled
                self.lbl_status.setText("Purchase cancelled or failed.")
                self.progress.setVisible(False)
                self.lbl_status.setVisible(False)
                
                # Re-enable cards
                for card in self.option_cards:
                    card.set_busy(False)
                
        except Exception as e:
            logger.error(f"Purchase Error: {e}")
            self.lbl_status.setText(f"Error: {str(e)}")
            self.progress.setVisible(False)
            
            # Re-enable cards
            for card in self.option_cards:
                card.set_busy(False)

    def keyPressEvent(self, event):
        """Handle key events, specifically for Dev Panel access."""
        if event.key() == Qt.Key.Key_F9:
            # Forward F9 to parent's dev manager to toggle Purchase Panel
            if self.parent() and hasattr(self.parent(), 'dev_panel_manager'):
                self.parent().dev_panel_manager.toggle_panel('purchase')
                event.accept()
                return

        # Default behavior (e.g. Escape to close)
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """Prevent closing while busy."""
        if self.progress.isVisible():
            event.ignore()
        else:
            super().closeEvent(event)
    
    def resizeEvent(self, event):
        """Resize to parent on resize."""
        super().resizeEvent(event)
        # Keep dialog covering parent window
        if self.parent():
            self.setGeometry(self.parent().frameGeometry())

    def update_card_style(self, card_id: str, new_style: dict):
        """Update style for a specific card dynamically."""
        for card in self.option_cards:
            if card.option_data.get('id') == card_id:
                card.update_style_config(new_style)
                break
