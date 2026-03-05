"""
Grid Layout Manager

Manages responsive card grid layout for preset gallery.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QScrollArea, QLabel
from PySide6.QtCore import Qt
from typing import List, Dict
from client.plugins.presets.logic.models import PresetDefinition
from client.plugins.presets.ui.card import PresetCard


class GridLayoutManager:
    """
    Manages responsive card grid layout.
    
    Handles:
    - Calculating cards per row based on available width
    - Creating centered rows of cards
    - Laying out cards grouped by category
    - Laying out filtered cards for a specific category
    """
    
    # Layout configuration
    CARD_WIDTH = 120
    CARD_SPACING = 16
    PADDING = 24
    MIN_CARDS_PER_ROW = 2
    MAX_CARDS_PER_ROW = 6
    
    def __init__(self, scroll_area: QScrollArea, on_card_clicked_callback):
        """
        Initialize grid layout manager.
        
        Args:
            scroll_area: QScrollArea containing the card container
            on_card_clicked_callback: Callback function for card clicks
        """
        self._scroll = scroll_area
        self._on_card_clicked = on_card_clicked_callback
    
    def calculate_cards_per_row(self) -> int:
        """Calculate how many cards fit per row based on available width."""
        available_width = self._scroll.viewport().width() - 2 * self.PADDING
        if available_width <= 0:
            return self.MIN_CARDS_PER_ROW
        
        card_with_spacing = self.CARD_WIDTH + self.CARD_SPACING
        cols = max(self.MIN_CARDS_PER_ROW, available_width // card_with_spacing)
        return min(cols, self.MAX_CARDS_PER_ROW)
    
    def create_row(self, presets: List[PresetDefinition]) -> QWidget:
        """
        Create a centered row of preset cards.
        
        Args:
            presets: List of preset definitions to create cards for
            
        Returns:
            QWidget containing the row of cards
        """
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
    
    def create_rows_for_presets(
        self, 
        presets: List[PresetDefinition], 
        cards_per_row: int
    ) -> List[QWidget]:
        """
        Helper to create row widgets without adding them to layout immediately.
        
        Args:
            presets: List of preset definitions
            cards_per_row: Number of cards per row
            
        Returns:
            List of row widgets
        """
        rows = []
        for i in range(0, len(presets), cards_per_row):
            row_presets = presets[i:i + cards_per_row]
            row_widget = self.create_row(row_presets)
            rows.append(row_widget)
        return rows
    
    def create_category_label(self, category_text: str) -> QLabel:
        """
        Create a styled category label.
        
        Args:
            category_text: Text to display (will be uppercased)
            
        Returns:
            Styled QLabel
        """
        label = QLabel(category_text.upper())
        label.setObjectName("CategoryLabel")
        label.setStyleSheet("""
            color: #86868B;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 1px;
            padding: 8px 0px 4px 0px;
            background: transparent;
        """)
        return label
    
    def layout_grouped(
        self, 
        categories: Dict[str, List[PresetDefinition]], 
        cards_per_row: int
    ) -> List[QWidget]:
        """
        Layout cards grouped by category.
        
        Args:
            categories: Dictionary mapping category names to preset lists
            cards_per_row: Number of cards per row
            
        Returns:
            List of widgets (labels + rows) to add to layout
        """
        widgets = []
        
        for category in sorted(categories.keys()):
            presets = categories[category]
            
            # Category label
            label = self.create_category_label(category)
            widgets.append(label)
            
            # Cards for this category
            rows = self.create_rows_for_presets(presets, cards_per_row)
            widgets.extend(rows)
        
        return widgets
    
    def layout_filtered(
        self, 
        presets: List[PresetDefinition], 
        cards_per_row: int
    ) -> List[QWidget]:
        """
        Layout cards for a specific category (no labels).
        
        Args:
            presets: List of preset definitions to layout
            cards_per_row: Number of cards per row
            
        Returns:
            List of row widgets to add to layout
        """
        return self.create_rows_for_presets(presets, cards_per_row)
