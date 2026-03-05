"""
Custom Preset Gallery Widget

Self-contained, reusable component for displaying user-created lab presets
inside the Command Panel's "Lab Presets" mode.

Usage (one line per tab):
    gallery = CustomPresetGallery(['image'], tab_ref=self)
    gallery = CustomPresetGallery(['video'], tab_ref=self)
    gallery = CustomPresetGallery(['gif', 'loop'], tab_ref=self)

The component handles internally:
- Loading and filtering presets by type
- Applying settings to the owning tab via tab_ref.restore_settings()
- Syncing the CommandPanel mode button after apply
- Deleting preset files and refreshing the list

Signals exposed for optional external listeners:
    preset_applied(dict)   - emitted after lab settings are applied
    preset_deleted()       - emitted after a preset file is removed

NOTE: All imports from client.plugins.presets are intentionally lazy
to avoid circular import issues at module load time.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QFrame, QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QAction, QPixmap, QPainter, QColor

from client.gui.theme import Theme
from client.utils.resource_path import get_resource_path

if TYPE_CHECKING:
    from client.gui.tabs.base_tab import BaseTab


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Type → icon filename mapping (mirrors PresetCard._load_lab_mode_icon)
_TYPE_ICONS = {
    'image': 'client/assets/icons/pic_icon.svg',
    'video': 'client/assets/icons/vid_icon.svg',
    'gif':   'client/assets/icons/loop_icon3.svg',
    'loop':  'client/assets/icons/loop_icon3.svg',
}
_DEFAULT_ICON = 'client/assets/icons/settings_v2.svg'


def _detect_size_mode(lab_settings: dict) -> str:
    """Return 'max_size' or 'manual' using the type-specific size_mode key."""
    file_type = lab_settings.get('type', '')
    # Use type-specific key first (mirrors PresetCard._load_lab_mode_icon logic)
    if file_type in ('gif', 'loop'):
        val = lab_settings.get('gif_size_mode')
    elif file_type == 'video':
        val = lab_settings.get('video_size_mode')
    elif file_type == 'image':
        val = lab_settings.get('image_size_mode')
    else:
        val = None
    # Fall back to generic key
    if not val:
        val = lab_settings.get('size_mode', 'manual')
    return val or 'manual'


def _render_svg_to_pixmap(svg_path: str, color_hex: str, size: int) -> Optional[QPixmap]:
    """
    Read an SVG file, tint all fills/strokes to color_hex,
    and render to a QPixmap at the requested size.
    Returns None if the file cannot be loaded.
    """
    import re
    try:
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray, QRectF

        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_text = f.read()

        # Tint fill and stroke to the requested color
        svg_text = re.sub(r'fill="(?!none)[^"]*"', f'fill="{color_hex}"', svg_text)
        svg_text = re.sub(r'stroke="(?!none)[^"]*"', f'stroke="{color_hex}"', svg_text)

        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer = QSvgRenderer(QByteArray(svg_text.encode('utf-8')))
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return pix
    except Exception:
        return None


# ---------------------------------------------------------------------------
# MiniPresetCard
# ---------------------------------------------------------------------------

class MiniPresetCard(QFrame):
    """
    Compact adaptive card (2-per-row, fixed height ~72px) for a custom lab preset.

    Layout:
        [ icon ]  [ Title          ] [ submode badge ]
                  [ type subtitle  ]

    Selection border: Theme.success() (green).
    Right-click: "Remove preset" context menu.
    """

    clicked = Signal(object)          # emits preset definition
    delete_requested = Signal(str)    # emits file path

    CARD_HEIGHT = 72
    ICON_SIZE = 28
    BADGE_SIZE = 14

    def __init__(self, preset, parent=None):
        super().__init__(parent)
        self._preset = preset
        self._is_selected = False

        self.setObjectName("MiniPresetCard")
        self.setFixedHeight(self.CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._setup_ui()
        self._apply_styles()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def preset(self):
        return self._preset

    def set_selected(self, selected: bool):
        if self._is_selected != selected:
            self._is_selected = selected
            self._apply_styles()

    def update_theme(self, is_dark: bool):
        Theme.set_dark_mode(is_dark)
        self._apply_styles()
        self._refresh_icon()

    # ------------------------------------------------------------------
    # Private – layout
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # Submode icon (target=max_size, settings=manual)
        self._icon_label = QLabel()
        self._icon_label.setObjectName("MiniCardIcon")
        self._icon_label.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._refresh_icon()
        layout.addWidget(self._icon_label, 0)

        # Text column
        text_col = QWidget()
        text_col.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_col)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._title_label = QLabel(self._preset.name)
        self._title_label.setObjectName("MiniCardTitle")
        self._title_label.setWordWrap(False)
        text_layout.addWidget(self._title_label)

        lab_settings = self._preset.raw_yaml.get('lab_mode_settings', {})
        ptype = lab_settings.get('type', self._preset.raw_yaml.get('type', ''))
        if ptype:
            sub_text = self._get_codec_label(lab_settings, ptype)
            self._sub_label = QLabel(sub_text)
            self._sub_label.setObjectName("MiniCardSub")
            text_layout.addWidget(self._sub_label)

        text_layout.addStretch()
        layout.addWidget(text_col, 1)

    @staticmethod
    def _get_codec_label(lab_settings: dict, ptype: str) -> str:
        """Return a short human-readable codec/format label for the card subtitle."""
        file_type = (ptype or '').lower()
        if file_type == 'image':
            fmt = lab_settings.get('format', '')
            return fmt if fmt else 'Image'
        elif file_type == 'video':
            codec = lab_settings.get('codec', '')
            return codec if codec else 'Video'
        elif file_type in ('gif', 'loop'):
            codec = lab_settings.get('codec', '')
            fmt = lab_settings.get('format', '')
            label = codec or fmt
            return label if label else file_type.upper()
        return ptype.capitalize()

    def _refresh_icon(self):
        """Show the submode icon: target for max_size presets, settings for manual."""
        lab_settings = self._preset.raw_yaml.get('lab_mode_settings', {})
        size_mode = _detect_size_mode(lab_settings)
        is_max = (size_mode == 'max_size')

        icon_name = 'target_icon.svg' if is_max else 'settings_v2.svg'
        tooltip = 'Max Size mode' if is_max else 'Manual mode'
        self._icon_label.setToolTip(tooltip)

        abs_path = get_resource_path(f'client/assets/icons/{icon_name}')
        pix = _render_svg_to_pixmap(abs_path, Theme.text_muted(), self.ICON_SIZE)
        if pix:
            self._icon_label.setPixmap(pix)
            self._icon_label.setStyleSheet("background: transparent;")
        else:
            self._icon_label.clear()
            self._icon_label.setText('◎' if is_max else '⚙')
            self._icon_label.setStyleSheet(
                f"color: {Theme.text_muted()}; background: transparent;"
            )

    # ------------------------------------------------------------------
    # Private – styles
    # ------------------------------------------------------------------

    def _apply_styles(self):
        bg = Theme.surface_element()
        border = Theme.border()
        hover_bg = Theme.color('surface_hover')
        focus_border = Theme.border_focus()
        radius = Theme.RADIUS_MD
        text_color = Theme.text()
        muted_color = Theme.text_muted()
        font_sm = Theme.FONT_SIZE_SM
        font_xs = getattr(Theme, 'FONT_SIZE_XS', font_sm - 2)

        if self._is_selected:
            success = Theme.success()
            card_css = f"""
                QFrame#MiniPresetCard {{
                    background-color: {bg};
                    border: 2px solid {success};
                    border-radius: {radius}px;
                }}
                QFrame#MiniPresetCard:hover {{
                    background-color: {hover_bg};
                    border: 2px solid {success};
                }}
            """
        else:
            card_css = f"""
                QFrame#MiniPresetCard {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: {radius}px;
                }}
                QFrame#MiniPresetCard:hover {{
                    background-color: {hover_bg};
                    border: 1px solid {focus_border};
                }}
            """

        label_css = f"""
            QLabel#MiniCardTitle {{
                color: {text_color};
                font-size: {Theme.FONT_SIZE_LG}px;
                font-weight: 600;
                background: transparent;
            }}
            QLabel#MiniCardSub {{
                color: {muted_color};
                font-size: {font_sm}px;
                background: transparent;
            }}
            QLabel#MiniCardBadge {{
                background: transparent;
            }}
            QLabel#MiniCardIcon {{
                background: transparent;
            }}
        """
        self.setStyleSheet(card_css + label_css)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._preset)
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu()
        super().mousePressEvent(event)

    def _show_context_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Theme.surface_element()};
                color: {Theme.text()};
                border: 1px solid {Theme.border()};
                border-radius: {Theme.RADIUS_MD}px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QMenu::item:selected {{
                background-color: rgba(255, 80, 80, 0.15);
                color: {Theme.error()};
            }}
        """)
        remove_action = QAction("Remove preset", menu)
        # Build a flat SVG trash icon tinted in the error/red colour
        try:
            from PySide6.QtGui import QIcon
            from client.utils.resource_path import get_resource_path
            icon_path = get_resource_path('client/assets/icons/removefile.svg')
            pix = _render_svg_to_pixmap(icon_path, Theme.error(), 16)
            if pix:
                remove_action.setIcon(QIcon(pix))
        except Exception:
            pass
        remove_action.triggered.connect(self._on_remove)
        menu.addAction(remove_action)
        menu.exec(QCursor.pos())

    def _on_remove(self):
        source_path = self._preset.raw_yaml.get('_source_path', '')
        if source_path:
            self.delete_requested.emit(source_path)


# ---------------------------------------------------------------------------
# CustomPresetGallery
# ---------------------------------------------------------------------------

class CustomPresetGallery(QWidget):
    """
    Self-contained scrollable 2-per-row grid of MiniPresetCards.

    The component manages its own preset loading, filtering, apply,
    deletion and CommandPanel mode-button sync.

    Args:
        preset_types: list of preset type strings to show, e.g. ['image'],
                      ['video'], or ['gif', 'loop']
        tab_ref:      the owning BaseTab instance. Used to call
                      tab_ref.restore_settings() and to walk up to
                      CommandPanel for mode-button sync.

    Signals:
        preset_applied(dict)  - emitted after settings are applied
        preset_deleted()      - emitted after a file is deleted
    """

    preset_applied = Signal(dict)
    preset_deleted = Signal()

    CARDS_PER_ROW = 2
    CARD_SPACING = 8

    def __init__(self, preset_types: list, tab_ref=None, parent=None):
        super().__init__(parent)
        self._preset_types: list = preset_types
        self._tab_ref = tab_ref          # BaseTab instance
        self._cards: List[MiniPresetCard] = []
        self._selected_card: Optional[MiniPresetCard] = None
        self._presets: list = []

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self):
        """
        Load presets from disk, filter by self._preset_types,
        and rebuild the card grid.
        """
        try:
            from client.plugins.presets.logic.manager import PresetManager
            from client.core.tool_registry import get_registry
            manager = PresetManager(get_registry())
            all_presets = manager.load_all()
            filtered = [
                p for p in all_presets
                if p.is_user_preset
                and p.raw_yaml.get('lab_mode_settings', {}).get('type') in self._preset_types
            ]
            self._presets = filtered
            self._rebuild()
        except Exception as e:
            print(f"[CustomPresetGallery] Error loading presets: {e}")

    # kept for backward compat in case tabs call it
    def load_presets(self, presets: list):
        """Directly set a pre-filtered list of presets (bypass disk load)."""
        self._presets = presets
        self._rebuild()

    # ------------------------------------------------------------------
    # Private – UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        self._header = QLabel("Your Custom Presets")
        self._header.setObjectName("CustomGalleryHeader")
        self._header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._header)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent;")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 4, 0, 0)
        self._container_layout.setSpacing(self.CARD_SPACING)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, 1)

        # Empty state
        self._empty_label = QLabel(
            "No custom presets yet.\nCreate one using the 'Add Preset' button."
        )
        self._empty_label.setObjectName("CustomGalleryEmpty")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        self._apply_header_styles()

    def _apply_header_styles(self):
        self.setStyleSheet(f"""
            QLabel#CustomGalleryHeader {{
                color: {Theme.text_muted()};
                font-size: {Theme.FONT_SIZE_SM}px;
                font-weight: 600;
                letter-spacing: 1px;
                padding: 2px 0px;
                background: transparent;
            }}
            QLabel#CustomGalleryEmpty {{
                color: {Theme.text_muted()};
                font-size: {Theme.FONT_SIZE_SM}px;
                background: transparent;
                padding: 20px;
            }}
        """)

    # ------------------------------------------------------------------
    # Private – rebuild grid
    # ------------------------------------------------------------------

    def _rebuild(self):
        # Clean up old cards
        for card in self._cards:
            try:
                card.deleteLater()
            except RuntimeError:
                pass
        self._cards.clear()
        self._selected_card = None

        # Clear layout rows
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                try:
                    w.deleteLater()
                except RuntimeError:
                    pass

        has_presets = bool(self._presets)
        self._empty_label.setVisible(not has_presets)
        self._scroll.setVisible(has_presets)

        if not has_presets:
            return

        row_layout = None
        for i, preset in enumerate(self._presets):
            if i % self.CARDS_PER_ROW == 0:
                row_widget = QWidget()
                row_widget.setStyleSheet("background: transparent;")
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(self.CARD_SPACING)
                self._container_layout.addWidget(row_widget)

            card = MiniPresetCard(preset, parent=self._container)
            card.clicked.connect(self._on_card_clicked)
            card.delete_requested.connect(self._on_delete_requested)
            row_layout.addWidget(card, 1)
            self._cards.append(card)

        # Pad the last row so cards are equal width
        if row_layout is not None:
            remaining = len(self._presets) % self.CARDS_PER_ROW
            if remaining != 0:
                for _ in range(self.CARDS_PER_ROW - remaining):
                    ph = QWidget()
                    ph.setFixedHeight(MiniPresetCard.CARD_HEIGHT)
                    ph.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    ph.setStyleSheet("background: transparent;")
                    row_layout.addWidget(ph, 1)

    # ------------------------------------------------------------------
    # Private – event handlers
    # ------------------------------------------------------------------

    def _on_card_clicked(self, preset):
        """Select card visually, apply settings to owning tab, sync mode button."""
        # Update selection
        if self._selected_card is not None:
            try:
                self._selected_card.set_selected(False)
            except RuntimeError:
                pass
            self._selected_card = None

        for card in self._cards:
            try:
                if card.preset.id == preset.id:
                    card.set_selected(True)
                    self._selected_card = card
                    break
            except RuntimeError:
                pass

        # Apply to tab
        lab_settings = preset.raw_yaml.get('lab_mode_settings', {})
        if not lab_settings:
            print(f"[CustomPresetGallery] '{preset.name}' has no lab_mode_settings")
            return

        print(f"[CustomPresetGallery] Applying: {preset.name}")

        if self._tab_ref is not None:
            try:
                # switch_mode=False: keep gallery visible, don't switch to Max Size / Manual mode.
                # Tabs that support this param (ImageTab, VideoTab) will skip their internal
                # set_mode() call. LoopTab never calls set_mode() from restore_settings, so
                # calling without the kwarg is also safe.
                try:
                    self._tab_ref.restore_settings(lab_settings, switch_mode=False)
                except TypeError:
                    # LoopTab doesn't have switch_mode param — call without it
                    self._tab_ref.restore_settings(lab_settings)
            except Exception as e:
                print(f"[CustomPresetGallery] restore_settings error: {e}")


        # Sync mode button
        self._sync_mode_button()

        # Emit for any external listeners
        self.preset_applied.emit(lab_settings)

    def _sync_mode_button(self):
        """
        Walk up to CommandPanel and sync its mode button with the current mode.

        Calls tab.set_mode() (not just mode_buttons.set_mode()) so that tabs
        with internal format-visibility logic (e.g. LoopTab._update_format_visibility)
        re-evaluate with the correct mode string after a preset is applied.
        """
        if self._tab_ref is None:
            return
        try:
            panel = self._tab_ref.parent()   # CommandPanel
            if not (panel and hasattr(panel, 'mode_buttons') and hasattr(panel, 'tab_modes')):
                return

            # Detect the mode from which sections are now visible
            tab = self._tab_ref
            if hasattr(tab, 'target_size_section') and tab.target_size_section.isVisible():
                current_mode = "Max Size"
            elif self.isVisible():
                current_mode = "Presets"
            else:
                current_mode = "Manual"

            tab_index = panel.tabs.indexOf(tab)
            if tab_index >= 0:
                panel.tab_modes[tab_index] = current_mode

            # Sync the sidebar button (suppress re-emitting mode_changed to avoid loops)
            panel.mode_buttons.set_mode(current_mode)
        except Exception as e:
            print(f"[CustomPresetGallery] Mode sync error: {e}")

    def _on_delete_requested(self, file_path: str):
        """Delete preset file and refresh the gallery."""
        if not file_path:
            print("[CustomPresetGallery] Cannot delete: no file path")
            return

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"[CustomPresetGallery] Deleted: {file_path}")
            except Exception as e:
                print(f"[CustomPresetGallery] Delete error: {e}")
                return
        else:
            print(f"[CustomPresetGallery] File not found: {file_path}")

        self.refresh()
        self.preset_deleted.emit()
