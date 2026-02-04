"""
Presets Plugin - Preset Gallery

Overlay widget displaying a responsive grid of preset cards.
Adapts to container width and groups presets by category when showing all.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QGridLayout, QLabel, QGraphicsOpacityEffect, QFrame, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QPainter, QColor

from typing import List, Dict
from client.plugins.presets.logic.models import PresetDefinition
from client.plugins.presets.ui.card import PresetCard
from client.plugins.presets.ui.filter_bar import CategoryFilterBar
from client.gui.theme import Theme


class PresetGallery(QWidget):
    """
    Overlay widget displaying preset cards in a responsive grid.
    
    Features:
    - Responsive layout: adapts columns to available width
    - No horizontal scroll: cards wrap to new rows
    - Category grouping: when ALL selected, each category starts on new row
    - Centered cards within each row
    """
    
    preset_selected = pyqtSignal(object)  # PresetDefinition
    dismissed = pyqtSignal()
    
    # Layout configuration
    CARD_WIDTH = 120
    CARD_SPACING = 16
    PADDING = 24
    MIN_CARDS_PER_ROW = 2
    MAX_CARDS_PER_ROW = 6
    ANIMATION_DURATION = 250  # Fade-in duration in ms
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PresetGallery")
        self._cards: List[PresetCard] = []
        self._presets: List[PresetDefinition] = []
        self._meta = {}
        self._row_widgets: List[QWidget] = []  # Track row widgets for cleanup
        self._current_ratio_view = None  # Track drill-down state (None or ratio string)
        self._is_dark = True  # Default to dark mode
        
        # Animation state
        self._param_panel_animation = None
        self._param_fade_animation = None
        self._dev_panel = None
        
        # Enable proper background painting
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        
        # Install event filter on parent to follow its size
        if parent:
            parent.installEventFilter(self)
        
        self._setup_ui()
        self._apply_styles()
        
        # Initially hidden
        self.hide()
    
    def eventFilter(self, obj, event):
        """Monitor parent resize events and catch double-clicks on scroll area."""
        from PyQt6.QtCore import QEvent
        
        # Handle parent resize
        if obj == self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(obj.rect())
            self._position_filter_bar()
            if self.isVisible():
                self._capture_blur_background()
            return super().eventFilter(obj, event)
        
        # Handle double-click on scroll viewport or card container
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if obj == self._scroll.viewport() or obj == self._card_container:
                # Check if double-click is on empty space (not on a child widget like a card)
                child = obj.childAt(event.pos())
                # If child is None OR child is the card container layout (not a card itself)
                if child is None or child == self._card_container:
                    print("[PresetGallery] Double-click on background detected - dismissing")
                    self.dismissed.emit()
                    return True
        
        return super().eventFilter(obj, event)
    
    def _position_filter_bar(self):
        """Position the filter bar as an overlay at the top of the gallery."""
        if hasattr(self, '_filter_bar'):
            # Position at top with some padding from edges
            self._filter_bar.setGeometry(16, 16, self.width() - 32, 60)
    
    def set_meta(self, meta):
        """Store media metadata for parameter visibility rules."""
        self._meta = meta
    
    def _is_showing_ratio_platforms(self) -> bool:
        """Check if we are currently drilled down into a specific ratio."""
        return getattr(self, '_current_ratio_view', None) is not None
    
    def _setup_ui(self):
        """Setup the gallery layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(0)  # No spacing - filter will overlay
        
        # Scroll area for cards (full height)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent;")
        
        # Update filter bar blur when scrolling
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
        
        # Card container
        self._card_container = QWidget()
        self._card_container.setStyleSheet("background: transparent;")
        self._container_layout = QVBoxLayout(self._card_container)
        self._container_layout.setContentsMargins(0, 60, 0, 0)  # Top padding for filter bar overlay
        self._container_layout.setSpacing(self.CARD_SPACING)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self._scroll.setWidget(self._card_container)
        main_layout.addWidget(self._scroll, 1)
        
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self._scroll.setWidget(self._card_container)
        main_layout.addWidget(self._scroll, 1)
        
        # Category filter bar - positioned as overlay on top of scroll area
        self._filter_bar = CategoryFilterBar(self)
        self._filter_bar.filterChanged.connect(self._apply_filter)
        self._filter_bar.raise_()  # Ensure it's on top
        
        # Install event filters to catch background clicks
        self._scroll.viewport().installEventFilter(self)
        self._card_container.installEventFilter(self)
        
        # Parameter panel - use new dynamic component
        from client.plugins.presets.ui.parameter_form import ParameterForm
        from client.plugins.presets.ui.dynamic_parameter_panel import DynamicParameterPanel
        
        self._parameter_form = ParameterForm()
        self._param_panel = DynamicParameterPanel()
        main_layout.addWidget(self._param_panel)
    
    def _on_scroll(self, value):
        """Handle scroll - update filter bar blur."""
        self._update_filter_bar_blur()
    
    def _update_param_panel_style(self):
        """Update parameter panel background based on theme."""
        self._param_panel.setStyleSheet(f"""
            QFrame#ParamPanel {{
                background-color: {Theme.color_with_alpha('surface_element', 0.95)};
                border-radius: {Theme.RADIUS_LG}px;
                padding: 12px;
            }}
        """)
    
    def _update_preset_label_style(self):
        """Update preset label styling - no icon, just text."""
        if hasattr(self, '_selected_preset_label') and self._selected_preset_label:
            self._selected_preset_label.setStyleSheet(f"""
                QLabel {{
                    color: {Theme.text()};
                    font-size: {Theme.FONT_SIZE_LG}px;
                    font-weight: bold;
                    font-family: '{Theme.FONT_BODY}';
                    padding-bottom: 8px;
                }}
            """)
    
    def _apply_styles(self):
        """Apply gallery-specific styles."""
        # Use theme-aware preset gallery background
        bg_color = Theme.presets_bg()
        self.setStyleSheet(f"""
            QWidget#PresetGallery {{
                background-color: {bg_color};
                border-radius: {Theme.RADIUS_LG}px;
            }}
            QLabel#CategoryLabel {{
                color: {Theme.text_muted()};
                font-size: {Theme.FONT_SIZE_SM}px;
                font-weight: 600;
                letter-spacing: 1px;
                padding: 4px 0px;
                margin-top: 8px;
                background: transparent;
            }}
        """)
    
    def get_parameter_values(self) -> dict:
        """Get current parameter values from the form."""
        return self._parameter_form.get_values()
    
    def set_presets(self, presets: List[PresetDefinition]):
        """Populate the gallery with preset cards."""
        self._presets = presets
        self._filter_bar.set_categories(presets)
        self._rebuild_cards()
    
    def _rebuild_cards(self):
        """Recreate all cards and layout them."""
        # Clean up existing cards and rows
        self._cleanup_layout()
        
        # Create new cards
        for preset in self._presets:
            card = PresetCard(preset)
            card.clicked.connect(self._on_card_clicked)
            self._cards.append(card)
        
        # Layout based on filter
        self._apply_filter()
    
    def _cleanup_layout(self):
        """Remove all cards and row widgets."""
        # Delete row widgets (which contain cards) - safely
        for row in self._row_widgets:
            try:
                if row is not None:
                    row.deleteLater()
            except RuntimeError:
                pass  # Already deleted
        self._row_widgets.clear()
        
        # Delete cards - safely
        for card in self._cards:
            try:
                if card is not None:
                    card.deleteLater()
            except RuntimeError:
                pass  # Already deleted
        self._cards.clear()
        
        # Clear container layout - safely
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item and item.widget():
                try:
                    item.widget().deleteLater()
                except RuntimeError:
                    pass  # Already deleted
    
    def _calculate_cards_per_row(self) -> int:
        """Calculate how many cards fit per row based on available width."""
        available_width = self._scroll.viewport().width() - 2 * self.PADDING
        if available_width <= 0:
            return self.MIN_CARDS_PER_ROW
        
        card_with_spacing = self.CARD_WIDTH + self.CARD_SPACING
        cols = max(self.MIN_CARDS_PER_ROW, available_width // card_with_spacing)
        return min(cols, self.MAX_CARDS_PER_ROW)
    
    def _apply_filter(self):
        """Apply current filter and rebuild visible layout."""
        # If we are in Ratio Drill-down mode, ignore filter bar changes locally or handle?
        # Actually changing filter should probably reset drill-down.
        self._current_ratio_view = None
        self._filter_bar.show()

        # Remove rows from layout but don't delete cards yet - safely
        for row in self._row_widgets:
            try:
                if row is not None:
                    self._container_layout.removeWidget(row)
                    row.deleteLater()
            except RuntimeError:
                pass
        self._row_widgets.clear()
        
        # Clear any remaining items - safely
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item and item.widget():
                try:
                    item.widget().deleteLater()
                except RuntimeError:
                    pass
        
        active_categories = self._filter_bar.get_active_categories()
        cards_per_row = self._calculate_cards_per_row()
        
        if not active_categories:
            # Show ALL with category grouping
            self._layout_grouped(cards_per_row)
        else:
            # Show filtered category
            self._layout_filtered(active_categories[0], cards_per_row)
    
    def _layout_grouped(self, cards_per_row: int):
        """Layout cards grouped by category. Virtualizes social presets into Ratio Groups."""
        
        # 1. Aggregate presets
        categories: Dict[str, List[PresetDefinition]] = {}
        social_presets: List[PresetDefinition] = []
        
        for preset in self._presets:
            cat = (preset.category or "other").lower()
            if cat == 'social':
                social_presets.append(preset)
                continue
                
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(preset)
        
        # 2. Add Social Category (with Ratio Aggregation)
        if social_presets:
            # Group by ratio
            ratio_groups = self._group_social_presets(social_presets)
            
            # Label
            label = QLabel("SOCIAL")
            label.setObjectName("CategoryLabel")
            label.setStyleSheet("""
                color: #86868B;
                font-size: 13px;
                font-weight: 600;
                letter-spacing: 1px;
                padding: 8px 0px 4px 0px;
                background: transparent;
            """)
            self._container_layout.addWidget(label)
            self._add_preset_rows(ratio_groups, cards_per_row)

        # 3. Layout other categories
        for category in sorted(categories.keys()):
            presets = categories[category]
            
            # Category label
            label = QLabel(category.upper())
            label.setObjectName("CategoryLabel")
            label.setStyleSheet("""
                color: #86868B;
                font-size: 13px;
                font-weight: 600;
                letter-spacing: 1px;
                padding: 8px 0px 4px 0px;
                background: transparent;
            """)
            self._container_layout.addWidget(label)
            
            # Cards for this category
            self._add_preset_rows(presets, cards_per_row)
            
    def _layout_filtered(self, category: str, cards_per_row: int):
        """Layout only cards for a specific category."""
        target_cat = category.lower()
        
        if target_cat == 'social':
            # Ratio aggregation for social filter too
            presets = [p for p in self._presets if (p.category or "").lower() == 'social']
            aggregated = self._group_social_presets(presets)
            self._add_preset_rows(aggregated, cards_per_row)
        else:
            presets = [p for p in self._presets if (p.category or "").lower() == target_cat]
            self._add_preset_rows(presets, cards_per_row)

    def _group_social_presets(self, presets: List[PresetDefinition]) -> List[PresetDefinition]:
        """Aggregate list of social presets into Virtual Ratio Presets."""
        from client.plugins.presets.logic.models import PresetStyle
        
        # 1. Bucket by ratio
        ratio_buckets = {}
        for p in presets:
            ratio = getattr(p, 'ratio', None) or 'other'
            if ratio not in ratio_buckets:
                ratio_buckets[ratio] = []
            ratio_buckets[ratio].append(p)
            
        aggregated_cards = []
        
        # 2. Create Virtual Preset for each ratio
        # Map ratio codes to nice names/icons
        RATIO_META = {
            "9x16": {"name": "Vertical 9:16", "icon": "916", "desc": "Reels / Shorts / TikTok"},
            "1x1": {"name": "Square 1:1", "icon": "11", "desc": "Feeds / Carousel Posts"},
            "3x4": {"name": "Portrait 3:4", "icon": "34", "desc": "Instagram / FB Feed"},
            "16x9": {"name": "Landscape 16:9", "icon": "169", "desc": "YouTube / LinkedIn"},
            "4x5": {"name": "Portrait 4:5", "icon": "mobile", "desc": "Optimized Feed Portrait"}, # Fallback icon
            "other": {"name": "Other Social", "icon": "settings", "desc": "Miscellaneous social presets"}
        }
        
        # Sort keys to ensure consistent order (e.g. 9x16 first)
        # Custom sort order: 9x16, 3x4, 4x5, 1x1, 16x9, other
        sort_order = ["9x16", "3x4", "4x5", "1x1", "16x9", "other"]
        sorted_ratios = sorted(ratio_buckets.keys(), key=lambda x: sort_order.index(x) if x in sort_order else 99)
        
        for ratio in sorted_ratios:
            count = len(ratio_buckets[ratio])
            meta = RATIO_META.get(ratio, RATIO_META['other'])
            
            # Create a virtual preset definition that acts as a folder
            # We tag it with a special attribute '_is_virtual_group' and '_child_presets'
            virtual_preset = PresetDefinition(
                id=f"group_ratio_{ratio}",
                name=meta['name'],
                category="social",
                pipeline=[], # Empty pipeline
                description=meta['desc'],
                style=PresetStyle(
                    accent_color="#86868B", # Neutral color for groups
                    icon=meta['icon']
                )
            )
            # Attach magic attributes for our gallery logic
            virtual_preset._is_virtual_group = True
            virtual_preset._group_ratio = ratio
            virtual_preset._child_presets = ratio_buckets[ratio]
            
            aggregated_cards.append(virtual_preset)
            
        return aggregated_cards
    
    def _add_preset_rows(self, presets: List[PresetDefinition], cards_per_row: int):
        """Add rows of cards for the given presets."""
        for i in range(0, len(presets), cards_per_row):
            row_presets = presets[i:i + cards_per_row]
            row_widget = self._create_row(row_presets)
            self._row_widgets.append(row_widget)
            self._container_layout.addWidget(row_widget)
    
    def _create_row(self, presets: List[PresetDefinition]) -> QWidget:
        """Create a centered row of new cards."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.CARD_SPACING)
        
        # Center with stretch
        layout.addStretch()
        for preset in presets:
            card = PresetCard(preset)
            card.clicked.connect(self._on_card_clicked)
            layout.addWidget(card)
        layout.addStretch()
        
        return row
    
    def _on_card_clicked(self, preset: PresetDefinition):
        """Handle card click with smooth animations."""
        
        # 0. Handle Back Click
        if getattr(preset, '_is_back_card', False):
            self._exit_ratio_view()
            return
            
        # 1. Handle Virtual Group Click (Drill Down)
        if getattr(preset, '_is_virtual_group', False):
            self._enter_ratio_view(preset._group_ratio, preset._child_presets)
            return

        # 2. Standard Preset Click
        # Save scroll position before any changes
        scroll_pos = self._scroll.verticalScrollBar().value()
        
        if preset.parameters:
            self._parameter_form.set_parameters(preset.parameters, self._meta)
            self._param_panel.set_content(
                title=f"{preset.name} Settings",
                parameter_form=self._parameter_form
            )
            self._param_panel.show_animated()
        else:
            self._param_panel.hide_animated()
        
        # Restore scroll position after layout changes
        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(scroll_pos))
        
        self.preset_selected.emit(preset)

    def _enter_ratio_view(self, ratio_id: str, presets: List[PresetDefinition]):
        """Enter step 2: Show platform presets for a specific ratio using fade transition."""
        self._current_ratio_view = ratio_id
        
        # Save scroll position
        scroll_pos = self._scroll.verticalScrollBar().value()
        
        # 1. Find the social category widgets to replace
        social_widgets = []
        social_start_index = -1
        
        for i in range(self._container_layout.count()):
            item = self._container_layout.itemAt(i)
            if not item or not item.widget():
                continue
            
            widget = item.widget()
            
            # Check if this is the SOCIAL label
            if isinstance(widget, QLabel) and widget.objectName() == "CategoryLabel":
                text = widget.text()
                if "SOCIAL" in text:
                    social_start_index = i
                    social_widgets.append(widget)
                    continue
            
            # If we've found the social section, collect widgets until next category
            if social_start_index >= 0:
                # Check if we've hit the next category label
                if isinstance(widget, QLabel) and widget.objectName() == "CategoryLabel":
                    break  # Stop collecting
                social_widgets.append(widget)
        
        # 2. Create new platform content
        items_to_add = []
        
        # Helper label for context
        label = QLabel(f"SOCIAL: {ratio_id.replace('x', ':').upper()}")
        label.setObjectName("CategoryLabel")
        label.setStyleSheet("""
            color: #86868B;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 1px;
            padding: 8px 0px 4px 0px;
            background: transparent;
        """)
        items_to_add.append(label)
        
        # Create Back Card
        from client.plugins.presets.logic.models import PresetStyle
        back_preset = PresetDefinition(
            id="back_card",
            name="Back", 
            category="social",
            pipeline=[],
            description="Return to ratios",
            style=PresetStyle(accent_color="#666666", icon="chevron-left")
        )
        back_preset._is_back_card = True
        
        # Prepend back card to presets list
        display_presets = [back_preset] + presets
        
        # Create rows
        cards_per_row = self._calculate_cards_per_row()
        rows = self._create_rows_for_presets(display_presets, cards_per_row)
        items_to_add.extend(rows)
        
        # 3. Perform in-place crossfade for social section only
        self._crossfade_social_section(social_widgets, items_to_add, social_start_index)
        
        # 4. Hide filter bar
        self._filter_bar.hide()
        
        # 5. Restore scroll position
        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(scroll_pos))

        
    def _exit_ratio_view(self):
        """Exit ratio view and return to main gallery using selective crossfade."""
        self._current_ratio_view = None
        self._filter_bar.show()
        
        # Save scroll position
        scroll_pos = self._scroll.verticalScrollBar().value()
        
        # 1. Find platform widgets to replace
        platform_widgets = []
        platform_start_index = -1
        
        for i in range(self._container_layout.count()):
            item = self._container_layout.itemAt(i)
            if not item or not item.widget():
                continue
            
            widget = item.widget()
            
            # Check if this is the SOCIAL: X:X label (platform view)
            if isinstance(widget, QLabel) and widget.objectName() == "CategoryLabel":
                text = widget.text()
                if "SOCIAL:" in text and ":" in text:
                    platform_start_index = i
                    platform_widgets.append(widget)
                    continue
            
            # If we've found the platform section, collect widgets until next category
            if platform_start_index >= 0:
                # Check if we've hit the next category label
                if isinstance(widget, QLabel) and widget.objectName() == "CategoryLabel":
                    break  # Stop collecting
                platform_widgets.append(widget)
        
        # 2. Recreate ratio cards for social category
        social_presets = [p for p in self._presets if (p.category or "").lower() == 'social']
        ratio_groups = self._group_social_presets(social_presets)
        
        items_to_add = []
        
        # Label
        label = QLabel("SOCIAL")
        label.setObjectName("CategoryLabel")
        label.setStyleSheet("""
            color: #86868B;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 1px;
            padding: 8px 0px 4px 0px;
            background: transparent;
        """)
        items_to_add.append(label)
        
        # Create ratio card rows
        cards_per_row = self._calculate_cards_per_row()
        rows = self._create_rows_for_presets(ratio_groups, cards_per_row)
        items_to_add.extend(rows)
        
        # 3. Crossfade back to ratio cards
        if platform_start_index >= 0:
            self._crossfade_social_section(platform_widgets, items_to_add, platform_start_index)
        
        # 4. Restore scroll position
        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(scroll_pos)) 
        
    def _crossfade_social_section(self, old_widgets: List[QWidget], new_widgets: List[QWidget], insert_index: int):
        """
        Simple, stable swap of social section widgets.
        No opacity effects - just hide old, show new, cleanup after delay.
        """
        # 1. Hide old widgets immediately
        for widget in old_widgets:
            try:
                widget.hide()
            except RuntimeError:
                pass
        
        # 2. Add and show new widgets at the same position
        for i, widget in enumerate(new_widgets):
            self._container_layout.insertWidget(insert_index + i, widget)
            widget.show()
        
        # 3. Schedule cleanup of old widgets after a short delay
        def cleanup():
            for widget in old_widgets:
                try:
                    if widget is not None:
                        self._container_layout.removeWidget(widget)
                        widget.setParent(None)
                        widget.deleteLater()
                except RuntimeError:
                    pass
        
        QTimer.singleShot(50, cleanup)


    
    def _create_rows_for_presets(self, presets: List[PresetDefinition], cards_per_row: int) -> List[QWidget]:
        """Helper to create row widgets without adding them to layout immediately."""
        rows = []
        for i in range(0, len(presets), cards_per_row):
            row_presets = presets[i:i + cards_per_row]
            row_widget = self._create_row(row_presets)
            rows.append(row_widget)
        return rows

    def _fade_switch_content(self, new_widgets: List[QWidget]):
        """
        Simple, stable content swap.
        No opacity effects - just hide old, show new, cleanup after delay.
        """
        # Save scroll position
        scroll_pos = self._scroll.verticalScrollBar().value()
        
        # 1. Collect and hide old widgets
        old_widgets = []
        for i in range(self._container_layout.count()):
            item = self._container_layout.itemAt(i)
            if item and item.widget():
                old_widgets.append(item.widget())
                try:
                    item.widget().hide()
                except RuntimeError:
                    pass
        
        # 2. Add and show new widgets
        for widget in new_widgets:
            self._container_layout.addWidget(widget)
            widget.show()
        
        # 3. Handle filter bar visibility
        if self._current_ratio_view:
            self._filter_bar.hide()
        else:
            self._filter_bar.show()
        
        # 4. Restore scroll position
        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(scroll_pos))
        
        # 5. Schedule cleanup of old widgets after a short delay
        def cleanup():
            for widget in old_widgets:
                try:
                    if widget is not None:
                        self._container_layout.removeWidget(widget)
                        widget.setParent(None)
                        widget.deleteLater()
                except RuntimeError:
                    pass
        
        QTimer.singleShot(50, cleanup)


    
    def _cleanup_old_widgets(self, old_widgets: List[QWidget]):
        """Clean up old widgets after fade-out animation completes."""
        for widget in old_widgets:
            try:
                if widget is not None:
                    self._container_layout.removeWidget(widget)
                    widget.setParent(None)
                    widget.deleteLater()
            except RuntimeError:
                pass  # Widget already deleted
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click on gallery background - dismiss gallery."""
        child = self.childAt(event.pos())
        # If clicked on empty space or on self (not a child widget)
        if child is None or child == self:
            print("[PresetGallery] Double-click on gallery background - dismissing")
            self.dismissed.emit()
        super().mouseDoubleClickEvent(event)
    
    
    def show_animated(self):
        """Show the gallery with fade-in animation and blur background."""
        if self.parent():
            self.setGeometry(self.parent().rect())
            self._capture_blur_background()
        
        # Position filter bar overlay
        self._position_filter_bar()
        
        # Capture blur for filter bar after a short delay (let cards render)
        QTimer.singleShot(50, self._update_filter_bar_blur)
        
        # Setup opacity animation
        if not hasattr(self, '_opacity_effect'):
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._opacity_effect)
        
        self._opacity_effect.setOpacity(0.0)
        self.show()
        self.raise_()
        
        self._show_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._show_anim.setDuration(self.ANIMATION_DURATION)
        self._show_anim.setStartValue(0.0)
        self._show_anim.setEndValue(1.0)
        self._show_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._show_anim.start()
    
    def _update_filter_bar_blur(self):
        """Update the filter bar's blur background."""
        if hasattr(self, '_filter_bar'):
            self._filter_bar.capture_blur()
    
    def _capture_blur_background(self):
        """
        Capture parent window content and apply optimized blur effect.
        """
        if not self.parent() or getattr(self, '_is_capturing_blur', False):
            return
            
        self._is_capturing_blur = True
        try:
            # Hide self temporarily to capture what's behind
            was_visible = self.isVisible()
            if was_visible:
                self.setVisible(False)
                
            # Grab parent pixmap
            # Use minimal grab to avoid heavy painting
            parent_rect = self.parent().rect()
            
            try:
                parent_pixmap = self.parent().grab(parent_rect)
            except Exception:
                # Fallback if grab fails
                parent_pixmap = None
            
            if was_visible:
                self.setVisible(True)
            
            if not parent_pixmap:
                self._is_capturing_blur = False
                return
            
            # OPTIMIZATION: Downscale to ~10% size
            target_width = max(1, parent_rect.width() // 4) # Even smaller for speed
            small_pixmap = parent_pixmap.scaledToWidth(target_width, Qt.TransformationMode.SmoothTransformation)
            
            # Apply blur to the small pixmap
            from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
            from PyQt6.QtGui import QPainter, QPixmap
            
            # Effective blur radius
            blur_radius = 12
            
            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(small_pixmap)
            blur = QGraphicsBlurEffect()
            blur.setBlurRadius(blur_radius)
            blur.setBlurHints(QGraphicsBlurEffect.BlurHint.PerformanceHint)
            item.setGraphicsEffect(blur)
            scene.addItem(item)
            
            # Render scene to new small pixmap
            output_pixmap = QPixmap(small_pixmap.size())
            output_pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter()
            try:
                if painter.begin(output_pixmap):
                    scene.render(painter)
            finally:
                painter.end()
            
            self._blurred_background = output_pixmap
            
        except Exception as e:
            print(f"[PresetGallery] Blur capture error: {e}")
        finally:
            self._is_capturing_blur = False
    
    def hide_animated(self):
        """Hide the gallery with fade-out animation."""
        if not hasattr(self, '_opacity_effect'):
            self.hide()
            return
        
        self._hide_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._hide_anim.setDuration(150)
        self._hide_anim.setStartValue(1.0)
        self._hide_anim.setEndValue(0.0)
        self._hide_anim.setEasingCurve(QEasingCurve.Type.InQuad)
        self._hide_anim.finished.connect(self.hide)
        self._hide_anim.start()
    
    # resizeEvent removed: Handled by eventFilter watching parent resize
    
    def paintEvent(self, event):
        """Paint the blurred background and dark overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Clip to rounded corners to match parent drop area bevel
        from PyQt6.QtGui import QPainterPath
        from PyQt6.QtCore import QRectF
        path = QPainterPath()
        # Use Theme.RADIUS_LG for the bevel as used in Drop Area
        radius = Theme.RADIUS_LG
        path.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter.setClipPath(path)
        
        # 1. Draw blurred background if available (Upscale smoothly)
        if hasattr(self, '_blurred_background') and self._blurred_background:
            # Scale the small blurry pixmap to fill the rect
            painter.drawPixmap(self.rect(), self._blurred_background)
        
        # 2. Draw dark tint overlay
        # Dark grey with 70% opacity (alpha = 180 out of 255)
        painter.fillRect(self.rect(), QColor(20, 20, 20, 180))
        
        super().paintEvent(event)
    
    
    def toggle_dev_panel(self):
        """Toggle dev panel for tuning animations (F12 in dev mode)."""
        if self._dev_panel is None:
            from client.gui.effects.dev_panel import DevPanel
            from client.gui.animators.animation_driver import AnimationDriver
            import os
            
            self._dev_panel = DevPanel(title="Preset Gallery Animation Tuning")
            
            # Get list of easing curve names for dropdown
            easing_options = list(AnimationDriver.EASING_MAP.keys())
            
            params = {
                'ANIM_DURATION': (50, 600, 10),
                'EASING_CURVE': (easing_options,),  # Dropdown for open animation
                'CLOSE_EASING': (easing_options,),  # Dropdown for close animation
                'LAYOUT_SETTLE_DELAY': (10, 150, 10),  # Layout delay tuning
            }
            
            # Point to the actual file that contains the constants
            dynamic_panel_file = os.path.join(
                os.path.dirname(__file__), 
                'dynamic_parameter_panel.py'
            )
            
            self._dev_panel.add_section(
                target=self._param_panel,
                params=params,
                title="Parameter Panel Animations",
                source_file=dynamic_panel_file,
                on_change=None
            )
        
        if self._dev_panel.isVisible():
            self._dev_panel.hide()
        else:
            self._dev_panel.show()
            self._dev_panel.raise_()
    
    def keyPressEvent(self, event):
        """Handle F12 key for dev panel in dev mode."""
        from PyQt6.QtCore import Qt
        if event.key() == Qt.Key.Key_F12:
            self.toggle_dev_panel()
        super().keyPressEvent(event)
    
    def update_theme(self, is_dark: bool):
        """Update theme for gallery and all child components."""
        self._is_dark = is_dark
        Theme.set_dark_mode(is_dark)
        
        # Update gallery styles
        self._apply_styles()
        self._update_param_panel_style()
        self._update_preset_label_style()
        
        # Update parameter form
        self._parameter_form.update_theme(is_dark)
        
        # Update all visible cards
        for card in self._cards:
            if hasattr(card, 'update_theme'):
                card.update_theme(is_dark)
        


