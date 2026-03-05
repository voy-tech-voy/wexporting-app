"""
Social Navigator

Manages social preset drill-down navigation (ratio grouping and platform views).
"""
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import QTimer
from typing import List
from client.plugins.presets.logic.models import PresetDefinition, PresetStyle


class SocialNavigator:
    """
    Manages social preset drill-down navigation.
    
    Handles:
    - Grouping social presets by ratio into virtual ratio cards
    - Entering ratio view (showing platform presets for a specific ratio)
    - Exiting ratio view (returning to ratio cards)
    - Managing drill-down state
    """
    
    def __init__(self, gallery: 'PresetGallery'):
        """
        Initialize social navigator.
        
        Args:
            gallery: Parent PresetGallery instance
        """
        self._gallery = gallery
        self._current_ratio_view = None
    
    def is_in_ratio_view(self) -> bool:
        """Check if we are currently drilled down into a specific ratio."""
        return self._current_ratio_view is not None
    
    def group_social_presets(self, presets: List[PresetDefinition]) -> List[PresetDefinition]:
        """
        Aggregate list of social presets into Virtual Ratio Presets.
        
        Args:
            presets: List of social presets to group
            
        Returns:
            List of virtual preset definitions representing ratio groups
        """
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
            "9x16": {"name": "REEL", "icon": "916", "desc": ""},
            "1x1": {"name": "SQUARE", "icon": "11", "desc": ""},
            "3x4": {"name": "PORTRAIT", "icon": "34", "desc": ""},
            "16x9": {"name": "LANDSCAPE", "icon": "169", "desc": ""},
            "4x5": {"name": "PORTRAIT 4:5", "icon": "mobile", "desc": ""},
            "other": {"name": "OTHER", "icon": "settings", "desc": ""}
        }
        
        # Custom sort order: 9x16, 3x4, 4x5, 1x1, 16x9, other
        sort_order = ["9x16", "3x4", "4x5", "1x1", "16x9", "other"]
        sorted_ratios = sorted(
            ratio_buckets.keys(), 
            key=lambda x: sort_order.index(x) if x in sort_order else 99
        )
        
        for ratio in sorted_ratios:
            count = len(ratio_buckets[ratio])
            meta = RATIO_META.get(ratio, RATIO_META['other'])
            
            # Create a virtual preset definition that acts as a folder
            virtual_preset = PresetDefinition(
                id=f"group_ratio_{ratio}",
                name=meta['name'],
                category="social",
                pipeline=[],
                description=meta['desc'],
                style=PresetStyle(
                    accent_color="#86868B",
                    icon=meta['icon']
                )
            )
            # Attach magic attributes for gallery logic
            virtual_preset._is_virtual_group = True
            virtual_preset._group_ratio = ratio
            virtual_preset._child_presets = ratio_buckets[ratio]
            
            aggregated_cards.append(virtual_preset)
            
        return aggregated_cards
    
    def enter_ratio_view(self, ratio_id: str, presets: List[PresetDefinition]):
        """
        Enter step 2: Show platform presets for a specific ratio.
        
        Args:
            ratio_id: Ratio identifier (e.g., "9x16")
            presets: List of platform presets for this ratio
        """
        self._current_ratio_view = ratio_id
        
        # Save scroll position
        scroll_pos = self._gallery._scroll.verticalScrollBar().value()
        
        # 1. Find the social category widgets to replace
        social_widgets = []
        social_start_index = -1
        
        for i in range(self._gallery._container_layout.count()):
            item = self._gallery._container_layout.itemAt(i)
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
        cards_per_row = self._gallery._grid_layout.calculate_cards_per_row()
        rows = self._gallery._grid_layout.create_rows_for_presets(display_presets, cards_per_row)
        items_to_add.extend(rows)
        
        # 3. Perform in-place swap for social section
        self._crossfade_social_section(social_widgets, items_to_add, social_start_index)
        
        # 4. Hide filter bar
        self._gallery._filter_bar.hide()
        
        # 5. Restore scroll position
        QTimer.singleShot(0, lambda: self._gallery._scroll.verticalScrollBar().setValue(scroll_pos))

    def exit_ratio_view(self):
        """Exit ratio view and return to main gallery."""
        self._current_ratio_view = None
        self._gallery._filter_bar.show()
        
        # Save scroll position
        scroll_pos = self._gallery._scroll.verticalScrollBar().value()
        
        # 1. Find platform widgets to replace
        platform_widgets = []
        platform_start_index = -1
        
        for i in range(self._gallery._container_layout.count()):
            item = self._gallery._container_layout.itemAt(i)
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
        social_presets = [p for p in self._gallery._presets if (p.category or "").lower() == 'social']
        ratio_groups = self.group_social_presets(social_presets)
        
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
        cards_per_row = self._gallery._grid_layout.calculate_cards_per_row()
        rows = self._gallery._grid_layout.create_rows_for_presets(ratio_groups, cards_per_row)
        items_to_add.extend(rows)
        
        # 3. Crossfade back to ratio cards
        if platform_start_index >= 0:
            self._crossfade_social_section(platform_widgets, items_to_add, platform_start_index)
        
        # 4. Restore scroll position
        QTimer.singleShot(0, lambda: self._gallery._scroll.verticalScrollBar().setValue(scroll_pos))
    
    def _crossfade_social_section(
        self, 
        old_widgets: List[QWidget], 
        new_widgets: List[QWidget], 
        insert_index: int
    ):
        """
        Simple, stable swap of social section widgets.
        No opacity effects - just hide old, show new, cleanup after delay.
        
        Args:
            old_widgets: Widgets to remove
            new_widgets: Widgets to add
            insert_index: Index to insert new widgets at
        """
        # 1. Hide old widgets immediately
        for widget in old_widgets:
            try:
                widget.hide()
            except RuntimeError:
                pass
        
        # 2. Add and show new widgets at the same position
        for i, widget in enumerate(new_widgets):
            self._gallery._container_layout.insertWidget(insert_index + i, widget)
            widget.show()
        
        # 3. Schedule cleanup of old widgets after a short delay
        def cleanup():
            for widget in old_widgets:
                try:
                    if widget is not None:
                        self._gallery._container_layout.removeWidget(widget)
                        widget.setParent(None)
                        widget.deleteLater()
                except RuntimeError:
                    pass
        
        QTimer.singleShot(50, cleanup)
