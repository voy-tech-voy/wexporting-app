"""
Presets Plugin - Preset Gallery

Overlay widget displaying a responsive grid of preset cards.
Adapts to container width and groups presets by category when showing all.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, 
    QLabel, QGraphicsOpacityEffect, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPainterPath

from typing import List, Dict
from PyQt6 import sip
from client.plugins.presets.logic.models import PresetDefinition
from client.plugins.presets.ui.card import PresetCard
from client.plugins.presets.ui.filter_bar import CategoryFilterBar
from client.plugins.presets.ui.blur_mixin import BlurBackgroundMixin
from client.plugins.presets.ui.grid_layout import GridLayoutManager
from client.plugins.presets.ui.social_navigator import SocialNavigator
from client.gui.theme import Theme


class PresetGallery(BlurBackgroundMixin, QWidget):
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
    go_to_lab_requested = pyqtSignal(dict)  # lab_mode_settings
    
    # Animation configuration
    ANIMATION_DURATION = 250  # Fade-in duration in ms
    
    def __init__(self, parent=None):
        super().__init__()
        QWidget.__init__(self, parent)
        self.setObjectName("PresetGallery")
        
        self._cards: List[PresetCard] = []
        self._presets: List[PresetDefinition] = []
        self._meta = {}
        self._row_widgets: List[QWidget] = []  # Track row widgets for cleanup
        self._is_dark = True  # Default to dark mode
        self.content_padding = 16 # Tunable layout padding
        self._selected_card: PresetCard = None  # Track currently selected card
        
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
        
        # Initialize extracted components AFTER UI setup
        self._grid_layout = GridLayoutManager(self._scroll, self._on_card_clicked)
        self._social_nav = SocialNavigator(self)
        
        self._apply_styles()
        
        # Initially hidden
        self.hide()
    
    def eventFilter(self, obj, event):
        """Monitor parent resize events and catch double-clicks on scroll area."""
        from PyQt6.QtCore import QEvent
        
        # Handle parent resize
        if obj == self.parent() and event.type() == QEvent.Type.Resize:
            # Expand slightly to cover drop area dashed outline
            rect = obj.rect()
            rect.adjust(-2, -2, 2, 2)  # Expand by 2px on all sides
            self.setGeometry(rect)
            self._position_filter_bar()
            if self.isVisible():
                self.capture_blur_background()
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
        """Position the filter bar at the top of the gallery."""
        if hasattr(self, '_filter_bar'):
            # Position at top spanning full width, touching top edge
            # Extended height for more blur area below buttons
            self._filter_bar.setGeometry(0, 0, self.width(), 80)
    
    def set_meta(self, meta):
        """Store media metadata for parameter visibility rules."""
        self._meta = meta
    
    def _is_showing_ratio_platforms(self) -> bool:
        """Check if we are currently drilled down into a specific ratio."""
        return self._social_nav.is_in_ratio_view()
    
    def _setup_ui(self):
        """Setup the gallery layout."""
        main_layout = QVBoxLayout(self)
        # No top padding so filter bar overlays correctly at the very top
        main_layout.setContentsMargins(self.content_padding, 0, self.content_padding, self.content_padding)
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
        # Add top padding equal to filter bar height (80px) to prevent card overlap
        self._container_layout.setContentsMargins(0, 80, 0, 0)
        self._container_layout.setSpacing(GridLayoutManager.CARD_SPACING)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self._scroll.setWidget(self._card_container)
        main_layout.addWidget(self._scroll, 1)
        
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self._scroll.setWidget(self._card_container)
        main_layout.addWidget(self._scroll, 1)
        
        # Category filter bar - positioned as overlay on top of scroll area
        self._filter_bar = CategoryFilterBar(self)
        self._filter_bar.filterChanged.connect(self._apply_filter)
        self._filter_bar.raise_()  # Ensure filter bar is on top
        
        # Install event filters to catch background clicks
        self._scroll.viewport().installEventFilter(self)
        self._card_container.installEventFilter(self)
        
        # Parameter panel - use new dynamic component
        from client.plugins.presets.ui.parameter_form import ParameterForm
        from client.plugins.presets.ui.dynamic_parameter_panel import DynamicParameterPanel
        
        self._parameter_form = ParameterForm()
        self._param_panel = DynamicParameterPanel()
        self._param_panel.go_to_lab_clicked.connect(self._on_go_to_lab)
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
    

    
    def _apply_filter(self):
        """Apply current filter and rebuild visible layout."""
        # Reset drill-down state when filter changes
        self._social_nav._current_ratio_view = None
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
        cards_per_row = self._grid_layout.calculate_cards_per_row()
        
        if not active_categories:
            # Show ALL with category grouping
            self._layout_grouped_all(cards_per_row)
        else:
            # Show filtered category
            self._layout_filtered_category(active_categories[0], cards_per_row)
    
    def _layout_grouped_all(self, cards_per_row: int):
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
            ratio_groups = self._social_nav.group_social_presets(social_presets)
            label = self._grid_layout.create_category_label("SOCIAL")
            self._container_layout.addWidget(label)
            
            rows = self._grid_layout.create_rows_for_presets(ratio_groups, cards_per_row)
            for row in rows:
                self._container_layout.addWidget(row)
                self._row_widgets.append(row)

        # 3. Layout other categories
        other_widgets = self._grid_layout.layout_grouped(categories, cards_per_row)
        for widget in other_widgets:
            self._container_layout.addWidget(widget)
            if not isinstance(widget, QLabel):
                self._row_widgets.append(widget)
            
    def _layout_filtered_category(self, category: str, cards_per_row: int):
        """Layout only cards for a specific category."""
        target_cat = category.lower()
        
        if target_cat == 'social':
            presets = [p for p in self._presets if (p.category or "").lower() == 'social']
            aggregated = self._social_nav.group_social_presets(presets)
            rows = self._grid_layout.create_rows_for_presets(aggregated, cards_per_row)
        else:
            presets = [p for p in self._presets if (p.category or "").lower() == target_cat]
            rows = self._grid_layout.layout_filtered(presets, cards_per_row)
        
        for row in rows:
            self._container_layout.addWidget(row)
            self._row_widgets.append(row)


    
    def _on_card_clicked(self, preset: PresetDefinition):
        """Handle card click with smooth animations."""
        
        # 0. Handle Back Click
        if getattr(preset, '_is_back_card', False):
            self._social_nav.exit_ratio_view()
            return
            
        # 1. Handle Virtual Group Click (Drill Down)
        if getattr(preset, '_is_virtual_group', False):
            self._social_nav.enter_ratio_view(preset._group_ratio, preset._child_presets)
            return

        # 2. Standard Preset Click
        # Save scroll position before any changes
        scroll_pos = self._scroll.verticalScrollBar().value()
        
        # Update card selection states
        # Deselect previous card (if it still exists)
        if self._selected_card is not None:
            try:
                # Check if the card still exists and is valid
                if not sip.isdeleted(self._selected_card):
                    self._selected_card.set_selected(False)
            except RuntimeError:
                # Card was deleted, ignore
                pass
            self._selected_card = None
        
        # Find and select the clicked card
        for card in self._cards:
            if card.preset.id == preset.id:
                card.set_selected(True)
                self._selected_card = card
                break
        
        # Show parameter panel with description
        if preset.parameters:
            self._parameter_form.set_parameters(preset.parameters, self._meta)
            self._param_panel.set_content(
                title=f"{preset.name} Settings",
                parameter_form=self._parameter_form,
                description=preset.description,
                preset=preset  # Pass preset for Lab Mode detection
            )
            self._param_panel.show_animated()
        else:
            # No parameters - clear form and show panel with description only
            self._parameter_form.set_parameters([], self._meta)  # Clear any previous parameters
            self._param_panel.set_content(
                title=preset.name,
                parameter_form=None,
                description=preset.description,
                preset=preset  # Pass preset for Lab Mode detection
            )
            self._param_panel.show_animated()
        
        # Restore scroll position after layout changes
        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(scroll_pos))
        
        self.preset_selected.emit(preset)
    
    def _on_go_to_lab(self, lab_settings: dict):
        """Forward go to lab request to orchestrator."""
        print(f"[PresetGallery] Go to Lab requested with {len(lab_settings)} settings")
        self.go_to_lab_requested.emit(lab_settings)
    

    
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
            # Expand slightly to cover drop area dashed outline
            rect = self.parent().rect()
            rect.adjust(-2, -2, 2, 2)  # Expand by 2px on all sides
            self.setGeometry(rect)
        
        # Position filter bar overlay
        self._position_filter_bar()
        
        # Delay blur capture to allow file list to render (important when files are just dropped)
        QTimer.singleShot(50, lambda: self.capture_blur_background(force=True))
        
        # Capture blur for filter bar after a short delay (let cards render)
        QTimer.singleShot(100, self._update_filter_bar_blur)
        
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
        
        # Use mixin to paint blurred background with dark overlay
        self.paint_blur_background(painter, self.rect(), overlay_alpha=180)
        
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
            
            # --- Tune Gallery Layout ---
            def update_layout():
                # Apply padding to main layout
                self.layout().setContentsMargins(
                    self.content_padding, self.content_padding, 
                    self.content_padding, self.content_padding
                )
                self._position_filter_bar() # Re-position filter bar
                self.update()

            layout_params = {
                'content_padding': (0, 100, 2),
            }
            
            self._dev_panel.add_section(
                target=self,
                params=layout_params,
                title="Gallery Layout", 
                source_file=__file__,
                on_change=update_layout
            )
        
        if self._dev_panel.isVisible():
            self._dev_panel.hide()
        else:
            self._dev_panel.show()
            self._dev_panel.raise_()
    
    def toggle_gallery_color_panel(self):
        """Toggle gallery color panel for F12."""
        if not hasattr(self, '_gallery_color_panel') or self._gallery_color_panel is None:
            from client.gui.dev_gallery_color_panel import DevGalleryColorPanel
            self._gallery_color_panel = DevGalleryColorPanel(self)
        
        if self._gallery_color_panel.isVisible():
            self._gallery_color_panel.hide()
        else:
            self._gallery_color_panel.show()
            self._gallery_color_panel.raise_()
    
    def keyPressEvent(self, event):
        """Handle F12 key to open gallery color panel."""
        from PyQt6.QtCore import Qt
        if event.key() == Qt.Key.Key_F12:
            self.toggle_gallery_color_panel()
        super().keyPressEvent(event)
    
    def update_theme(self, is_dark: bool):
        """Update theme for gallery and all child components."""
        self._is_dark = is_dark
        Theme.set_dark_mode(is_dark)
        
        # Update gallery styles
        self._apply_styles()
        self._update_preset_label_style()
        
        # Update parameter panel
        if hasattr(self, '_param_panel') and hasattr(self._param_panel, 'update_theme'):
            self._param_panel.update_theme(is_dark)
        
        # Update parameter form
        self._parameter_form.update_theme(is_dark)
        
        # Update all visible cards
        for card in self._cards:
            if hasattr(card, 'update_theme'):
                card.update_theme(is_dark)
        


