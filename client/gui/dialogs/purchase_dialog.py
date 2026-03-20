import json
import re
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QApplication, QWidget,
    QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QRect, QEvent
from PySide6.QtGui import QFont, QFontMetrics, QColor, QPainter, QPen, QBrush, QCursor

from client.utils.font_manager import AppFonts
from client.gui.theme import Theme
from client.gui.utils.winrt_interop import WinRTInterop
from client.gui.utils.window_effects import WindowEffects
from client.core.auth import get_store_auth_provider

import logging
logger = logging.getLogger("PurchaseDialog")

# Duration of the hover in/out animation in milliseconds
HOVER_DURATION_MS = 250


class _PurchaseWorker(QThread):
    """
    Background thread for the MS Store purchase flow.

    Keeps the Qt event loop alive so the dialog spinner animates and the window
    stays responsive while asyncio.run() blocks inside purchase_add_on().
    Emits finished(bool) on the main thread when done.
    """
    finished = Signal(bool)

    def __init__(self, product_id: str, hwnd: int, parent=None):
        super().__init__(parent)
        self._product_id = product_id
        self._hwnd = hwnd

    def run(self):
        try:
            provider = get_store_auth_provider()
            success = provider.purchase_add_on(self._product_id, window_handle=self._hwnd)
        except Exception as e:
            logger.error(f"[PurchaseWorker] Unhandled exception: {e}")
            success = False
        self.finished.emit(bool(success))


class PurchaseOptionCard(QWidget):
    """
    Card widget for a single purchase option.

    Hover effects are driven by a per-card QTimer that advances _hover_t
    toward _hover_target, then calls self.update(). paintEvent reads _hover_t
    and interpolates all visual state directly via QPainter — no QPropertyAnimation,
    no setStyleSheet updates — so repaints always fire regardless of whether the
    dialog was opened by user input or programmatically.
    """
    purchase_requested = Signal(str)  # Emits product_id

    def __init__(self, option_data: dict, parent=None):
        super().__init__(parent)
        self.option_data = option_data
        self.product_id = option_data.get('product_id', '')

        # Hover animation state
        self._hover_t: float = 0.0       # current interpolation position (0 = ghost, 1 = active)
        self._hover_target: float = 0.0  # target driven by _set_hover()
        self._btn_label: str = option_data.get('button_label', 'Buy')

        # Accent color from JSON config
        color_map = {
            'blue':   Theme.accent(),
            'green':  Theme.success(),
            'purple': Theme.color('accent_turbo'),
            'orange': Theme.warning(),
            'red':    Theme.error(),
        }
        color_key = option_data.get('color', 'blue')
        if color_key.startswith('#'):
            self.accent_color = QColor(color_key)
        else:
            self.accent_color = QColor(color_map.get(color_key, Theme.accent()))

        # Card background base color (from theme surface)
        surface = QColor(Theme.surface())
        if not Theme.is_dark():
            surface = surface.darker(105)
            if surface.lightness() > 240:
                surface = QColor(245, 245, 245)
        self.bg_base_color = surface

        # Load style colors from option_data['style']
        self._load_style_config()

        # Per-card hover animation timer (~60 fps)
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(16)
        self._hover_timer.timeout.connect(self._on_hover_tick)

        self.setObjectName("PurchaseOptionCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()

    # ── Style config ─────────────────────────────────────────────────────────

    def _load_style_config(self):
        """Load color configuration from option_data['style'], with optional
        light/dark overrides via 'style_light' / 'style_dark' keys."""
        style = dict(self.option_data.get('style', {}))
        if Theme.is_dark():
            style.update(self.option_data.get('style_dark', {}))
        else:
            style.update(self.option_data.get('style_light', {}))

        def parse_color(color_str, fallback: QColor) -> QColor:
            if not color_str:
                return fallback
            if color_str.startswith('rgba('):
                m = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color_str)
                if m:
                    r, g, b, a = m.groups()
                    c = QColor(int(r), int(g), int(b))
                    c.setAlphaF(float(a))
                    return c
                return fallback
            c = QColor(color_str)
            return c if c.isValid() else fallback

        def resolve(key, default: QColor) -> QColor:
            return parse_color(style.get(key), default)

        # Ghost (unhovered) defaults
        ghost_bg = QColor("#808080")
        ghost_bg.setAlphaF(0.3)
        self._col_outline_ghost  = QColor("#707070")   # overwritten in _setup_ui from theme
        self._col_btn_bg_ghost   = parse_color(style.get('btn_bg_ghost'), ghost_bg)
        self._col_btn_text_ghost = resolve('btn_text_ghost', QColor("#B0B0B0"))

        # Active (hovered) defaults
        active_bg = QColor("#808080")
        active_bg.setAlphaF(0.5)
        self._col_outline_active  = resolve('outline_active', self.accent_color)
        self._col_btn_bg_active   = parse_color(style.get('btn_bg_active'), active_bg)
        self._col_btn_text_active = resolve('btn_text_active', QColor("#FFFFFF"))
        self._col_price           = resolve('price_color', self.accent_color)

    def update_style_config(self, new_style: dict):
        """Update style config dynamically and repaint."""
        if not new_style:
            return
        current_style = self.option_data.get('style', {})
        current_style.update(new_style)
        self.option_data['style'] = current_style
        self._load_style_config()
        self.update()

    # ── UI setup ─────────────────────────────────────────────────────────────

    def _setup_ui(self):
        text_color = Theme.text()
        text_muted = Theme.text_muted()

        # Ghost outline from theme border
        border_c = QColor(Theme.border())
        if Theme.is_dark():
            border_c = border_c.lighter(150)
        else:
            border_c = border_c.darker(110)
        self._col_outline_ghost = border_c

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 24, 20, 24)

        # Price
        lbl_cost = QLabel(self.option_data.get('cost', '$0.00'))
        cost_font = QFont(AppFonts.get_base_font().family(), 24)
        cost_font.setBold(True)
        lbl_cost.setFont(cost_font)
        lbl_cost.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_cost.setStyleSheet(f"color: {self._col_price.name()}; background: transparent; border: none;")
        layout.addWidget(lbl_cost)

        # Name
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
        line.setStyleSheet("background-color: rgba(128, 128, 128, 0.2);")
        layout.addWidget(line)

        # Description
        lbl_desc = QLabel(self.option_data.get('description', ''))
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        lbl_desc.setFont(QFont(AppFonts.get_base_font().family(), 10))
        lbl_desc.setStyleSheet(f"color: {text_muted}; background: transparent; border: none;")
        layout.addWidget(lbl_desc, 1)

        # Invisible placeholder — paintEvent draws the button in this geometry
        self.lbl_btn = QLabel()
        self.lbl_btn.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_btn.setFixedHeight(44)
        self.lbl_btn.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.lbl_btn)

        # Ensure the card is never narrower than its button label requires
        btn_font = QFont(AppFonts.get_base_font().family(), 11)
        btn_font.setBold(True)
        text_w = QFontMetrics(btn_font).horizontalAdvance(self._btn_label)
        # layout margins (20 each side) + 32px breathing room
        self.setMinimumWidth(text_w + 72)

    # ── Hover animation ───────────────────────────────────────────────────────

    def _set_hover(self, hovered: bool):
        """
        Set the hover target and start the animation timer.
        Safe to call from any context (poll timer, enterEvent, leaveEvent).
        """
        self._hover_target = 1.0 if hovered else 0.0
        if not self._hover_timer.isActive():
            self._hover_timer.start()

    def _on_hover_tick(self):
        step = 1.0 / max(1, HOVER_DURATION_MS // 16)
        if self._hover_t < self._hover_target:
            self._hover_t = min(self._hover_target, self._hover_t + step)
        else:
            self._hover_t = max(self._hover_target, self._hover_t - step)
        if self._hover_t == self._hover_target:
            self._hover_timer.stop()
        self.update()   # always processed by Qt's own scheduler, no WM_MOUSEMOVE needed

    @staticmethod
    def _lerp_color(c0: QColor, c1: QColor, t: float) -> QColor:
        r = int(c0.red()   + (c1.red()   - c0.red())   * t)
        g = int(c0.green() + (c1.green() - c0.green()) * t)
        b = int(c0.blue()  + (c1.blue()  - c0.blue())  * t)
        a = int(c0.alpha() + (c1.alpha() - c0.alpha()) * t)
        return QColor(r, g, b, a)

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        t = self._hover_t
        r = self.rect()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Card background
        bg = QColor(self.bg_base_color)
        bg.setAlpha(242)   # ~0.95 opacity
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(r, 12, 12)

        # 2. Border (interpolated ghost → active)
        border_color = self._lerp_color(self._col_outline_ghost, self._col_outline_active, t)
        painter.setPen(QPen(border_color, 6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(r.adjusted(3, 3, -3, -3), 10, 10)

        # 3. Button background (drawn in the space reserved by lbl_btn)
        btn_rect = self.lbl_btn.geometry()
        btn_bg = self._lerp_color(self._col_btn_bg_ghost, self._col_btn_bg_active, t)
        painter.setBrush(QBrush(btn_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(btn_rect, 8, 8)

        # 4. Button text
        btn_text_color = self._lerp_color(self._col_btn_text_ghost, self._col_btn_text_active, t)
        painter.setPen(btn_text_color)
        btn_font = QFont(AppFonts.get_base_font().family(), 11)
        btn_font.setBold(True)
        painter.setFont(btn_font)
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, self._btn_label)

        painter.end()

    # ── Qt events ─────────────────────────────────────────────────────────────

    def enterEvent(self, event):
        logger.debug(f"[PurchaseOptionCard] enterEvent for {self.product_id}")
        self._set_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        logger.debug(f"[PurchaseOptionCard] leaveEvent for {self.product_id}")
        self._set_hover(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.purchase_requested.emit(self.product_id)
        super().mousePressEvent(event)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_busy(self, busy: bool):
        self.setEnabled(not busy)
        self._btn_label = "Processing..." if busy else self.option_data.get('button_label', 'Buy')
        self.update()


class PurchaseDialog(QDialog):
    """
    Full-screen overlay dialog for purchasing credit add-ons.
    Handles Windows Store IAP with proper window association.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.options = self._load_purchase_options()
        self._drag_start_pos = None
        self._is_dragging = False

        # Frameless, full-screen overlay
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self._setup_ui()

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_purchase_options(self) -> list:
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
        return [
            {
                "id": "credits_100",
                "name": "100 Credits",
                "description": "Additional 100 credits",
                "cost": "$0.99",
                "color": "blue",
                "button_label": "Buy 100 Credits",
                "product_id": "9NBLGGH42DRG",
                "type": "consumable",
            }
        ]

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 40, 60, 40)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Frosted-glass content panel
        self.content_panel = QFrame()
        self.content_panel.setObjectName("ContentPanel")
        self.content_panel.setMouseTracking(True)
        self.content_panel.setMinimumHeight(350)
        self.content_panel.setMaximumSize(850, 500)

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

        layout = QVBoxLayout(self.content_panel)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Cards container — no scroll, fills available width adaptively
        cards_container = QWidget()
        # NOTE: Do NOT use WA_TranslucentBackground here — on Windows it causes
        # the widget to fail hit-testing on transparent pixels.
        cards_container.setStyleSheet("background: transparent;")
        cards_container.setMouseTracking(True)
        cards_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        container_layout = QHBoxLayout(cards_container)
        container_layout.setSpacing(24)
        container_layout.setContentsMargins(16, 10, 16, 20)

        self.option_cards = []
        for option in self.options:
            card = PurchaseOptionCard(option, self)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            card.purchase_requested.connect(self._on_purchase_requested)
            container_layout.addWidget(card)
            self.option_cards.append(card)

        layout.addWidget(cards_container, 1)

        # Progress bar (hidden by default)
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

        main_layout.addWidget(self.content_panel, 0, Qt.AlignmentFlag.AlignCenter)

    # ── Painting & window events ──────────────────────────────────────────────

    def paintEvent(self, event):
        """Dim overlay behind the content panel."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        painter.end()

    def showEvent(self, event):
        super().showEvent(event)

        # Apply Mica/Acrylic blur behind the window
        try:
            WindowEffects.apply_mica(int(self.winId()), dark_mode=True)
        except Exception as e:
            logger.error(f"Failed to apply window effect: {e}")

        # Size to cover the parent window and track its moves
        if self.parent():
            self.setGeometry(self.parent().frameGeometry())
            logger.debug(f"[PurchaseDialog] geometry set to {self.geometry()}")
            self.parent().installEventFilter(self)

        QTimer.singleShot(0, self.activateWindow)
        QTimer.singleShot(0, self.raise_)

        # Poll cursor position to drive card hover state.
        # This bypasses Qt's Enter/Leave delivery — which can be unreliable when
        # the dialog is shown programmatically without a user input context.
        # _set_hover() → _hover_timer → update() always fires regardless of OS state.
        self._polled_hovered_card = None
        self._hover_poll_timer = QTimer(self)
        self._hover_poll_timer.setInterval(30)
        self._hover_poll_timer.timeout.connect(self._poll_hover_state)
        self._hover_poll_timer.start()

    def _poll_hover_state(self):
        global_pos = QCursor.pos()
        new_card = None
        for card in self.option_cards:
            card_rect = QRect(card.mapToGlobal(card.rect().topLeft()), card.size())
            if card_rect.contains(global_pos):
                new_card = card
                break

        if new_card is not self._polled_hovered_card:
            if self._polled_hovered_card is not None:
                self._polled_hovered_card._set_hover(False)
            if new_card is not None:
                new_card._set_hover(True)
            self._polled_hovered_card = new_card

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Type.Move:
            self.setGeometry(self.parent().frameGeometry())
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().frameGeometry())

    # ── Mouse events (drag / close) ───────────────────────────────────────────

    def mousePressEvent(self, event):
        self._drag_start_pos = None
        self._is_dragging = False

        # Emulated title bar (top 45px)
        if event.pos().y() < 45:
            x_from_right = self.width() - event.pos().x()
            if 10 <= x_from_right <= 55:           # Close button
                if not self.progress.isVisible():
                    self.reject()
                return
            elif 65 <= x_from_right <= 110:        # Minimize button
                if self.parent():
                    self.parent().showMinimized()
                return
            else:                                   # Drag
                self._drag_start_pos = event.globalPosition().toPoint()
                self._is_dragging = True
                return

        # Drag from top of content panel
        content_rect = self.content_panel.geometry()
        if content_rect.contains(event.pos()):
            local_pos = self.content_panel.mapFrom(self, event.pos())
            if local_pos.y() < 60:
                self._drag_start_pos = event.globalPosition().toPoint()
                self._is_dragging = True

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging and self._drag_start_pos:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            if self.parent():
                self.parent().move(self.parent().pos() + delta)
                self.move(self.pos() + delta)
            self._drag_start_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging:
            self._is_dragging = False
            self._drag_start_pos = None
        else:
            if event.pos().y() < 45:
                return
            content_rect = self.content_panel.geometry()
            if not content_rect.contains(event.pos()):
                if not self.progress.isVisible():
                    self.reject()
        super().mouseReleaseEvent(event)

    # ── Purchase flow ─────────────────────────────────────────────────────────

    def _on_purchase_requested(self, product_id: str):
        for card in self.option_cards:
            card.set_busy(True)
        self.progress.setVisible(True)
        self.lbl_status.setText("Contacting Microsoft Store...")
        self.lbl_status.setVisible(True)

        hwnd = int(self.winId())
        logger.info(f"PurchaseDialog: Initiating purchase for {product_id} with HWND {hwnd}")

        self._worker = _PurchaseWorker(product_id, hwnd)
        self._worker.finished.connect(self._on_purchase_finished)
        self._worker.start()

    def _on_purchase_finished(self, success: bool):
        self.progress.setVisible(False)
        if success:
            self.lbl_status.setText("Purchase Successful!")
            try:
                from client.core.energy_manager import EnergyManager
                EnergyManager.instance().sync_with_server_jwt()
                logger.info("PurchaseDialog: Energy sync triggered after purchase")
            except Exception as sync_err:
                logger.warning(f"PurchaseDialog: Post-purchase sync failed (non-critical): {sync_err}")
            QTimer.singleShot(1500, self.accept)
        else:
            self.lbl_status.setText("Purchase cancelled or failed.")
            self.lbl_status.setVisible(False)
            for card in self.option_cards:
                card.set_busy(False)

    # ── Key events ────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F9:
            if self.parent() and hasattr(self.parent(), 'dev_panel_manager'):
                self.parent().dev_panel_manager.toggle_panel('purchase')
                event.accept()
                return
        super().keyPressEvent(event)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Guard busy state and clean up hover poll timer."""
        if self.progress.isVisible():
            event.ignore()
            return
        if hasattr(self, '_hover_poll_timer') and self._hover_poll_timer.isActive():
            self._hover_poll_timer.stop()
        if self.parent():
            self.parent().removeEventFilter(self)
        super().closeEvent(event)

    # ── Dev / dynamic API ─────────────────────────────────────────────────────

    def update_card_style(self, card_id: str, new_style: dict):
        for card in self.option_cards:
            if card.option_data.get('id') == card_id:
                card.update_style_config(new_style)
                break
