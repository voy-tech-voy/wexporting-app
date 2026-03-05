"""
Tests for Presets Plugin - Category Filter Bar

Tests the CategoryFilterBar widget:
- Dynamic category extraction from presets
- Single-select exclusive toggle behavior
- ALL button functionality
- Signal emission on filter change
"""
import pytest
from unittest.mock import MagicMock
from typing import List

from PySide6.QtWidgets import QApplication

from client.plugins.presets.ui.filter_bar import CategoryFilterBar
from client.plugins.presets.logic.models import PresetDefinition, PresetStatus, PipelineStep


# Fixture for QApplication (required for Qt widgets)
@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def create_mock_preset(category: str, name: str = "Test") -> PresetDefinition:
    """Create a mock preset with a specific category."""
    return PresetDefinition(
        id=f"test_{name.lower()}",
        name=name,
        category=category,
        pipeline=[PipelineStep(tool="ffmpeg", command_template="test")],
        status=PresetStatus.READY
    )


@pytest.mark.usefixtures("qapp")
class TestCategoryExtraction:
    """Tests for extracting unique categories from presets."""
    
    def test_extract_unique_categories(self):
        """Test that set_categories extracts unique categories."""
        presets = [
            create_mock_preset("web", "Hero Image"),
            create_mock_preset("social", "Instagram Reel"),
            create_mock_preset("web", "WebM Export"),  # Duplicate category
            create_mock_preset("utility", "Audio Extract"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Should have 4 buttons: ALL + 3 unique categories
        assert len(bar._buttons) == 4
        assert CategoryFilterBar.ALL_KEY in bar._buttons
        assert "web" in bar._buttons
        assert "social" in bar._buttons
        assert "utility" in bar._buttons
    
    def test_empty_presets_list(self):
        """Test handling of empty preset list."""
        bar = CategoryFilterBar()
        bar.set_categories([])
        
        # Should have only ALL button
        assert len(bar._buttons) == 1
        assert CategoryFilterBar.ALL_KEY in bar._buttons
    
    def test_categories_sorted_alphabetically(self):
        """Test that categories are sorted alphabetically."""
        presets = [
            create_mock_preset("web"),
            create_mock_preset("audio"),
            create_mock_preset("social"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Get category buttons (excluding ALL)
        category_keys = [k for k in bar._buttons.keys() if k != CategoryFilterBar.ALL_KEY]
        assert category_keys == sorted(category_keys)
    
    def test_empty_category_ignored(self):
        """Test that presets with empty category are ignored."""
        presets = [
            create_mock_preset("web"),
            create_mock_preset(""),  # Empty category
            create_mock_preset("social"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Should have 3 buttons: ALL + 2 categories
        assert len(bar._buttons) == 3
        assert "" not in bar._buttons


@pytest.mark.usefixtures("qapp")
class TestSingleSelection:
    """Tests for single-selection exclusive behavior."""
    
    def test_default_all_selected(self):
        """Test that ALL is selected by default."""
        presets = [
            create_mock_preset("web"),
            create_mock_preset("social"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Default should be "ALL" (empty list)
        assert bar.get_active_categories() == []
        assert bar._selected_category is None
    
    def test_single_category_selection(self):
        """Test selecting a single category."""
        presets = [
            create_mock_preset("web"),
            create_mock_preset("social"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Click "web" button
        bar._buttons["web"].click()
        
        active = bar.get_active_categories()
        assert active == ["web"]
        assert bar._selected_category == "web"
    
    def test_exclusive_selection(self):
        """Test that selecting one category deselects others."""
        presets = [
            create_mock_preset("web"),
            create_mock_preset("social"),
            create_mock_preset("utility"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Click "web", then "social"
        bar._buttons["web"].click()
        bar._buttons["social"].click()
        
        # Only "social" should be active
        active = bar.get_active_categories()
        assert active == ["social"]
        assert bar._selected_category == "social"
    
    def test_all_button_clears_selection(self):
        """Test that clicking ALL clears category selection."""
        presets = [
            create_mock_preset("web"),
            create_mock_preset("social"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Select a category, then click ALL
        bar._buttons["web"].click()
        bar._buttons[CategoryFilterBar.ALL_KEY].click()
        
        assert bar.get_active_categories() == []
        assert bar._selected_category is None


@pytest.mark.usefixtures("qapp")
class TestSignalEmission:
    """Tests for filterChanged signal emission."""
    
    def test_signal_emitted_on_selection(self):
        """Test signal is emitted when category is selected."""
        presets = [
            create_mock_preset("web"),
            create_mock_preset("social"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Track signal emission
        signal_received = []
        bar.filterChanged.connect(lambda: signal_received.append(True))
        
        # Click a button
        bar._buttons["web"].click()
        
        assert len(signal_received) == 1
    
    def test_signal_emitted_on_each_selection(self):
        """Test signal is emitted for each selection change."""
        presets = [
            create_mock_preset("web"),
            create_mock_preset("social"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        signal_count = []
        bar.filterChanged.connect(lambda: signal_count.append(1))
        
        # Multiple selections
        bar._buttons["web"].click()
        bar._buttons["social"].click()
        bar._buttons[CategoryFilterBar.ALL_KEY].click()
        
        assert len(signal_count) == 3


@pytest.mark.usefixtures("qapp")
class TestResetFilters:
    """Tests for reset_filters method."""
    
    def test_reset_selects_all(self):
        """Test that reset_filters returns to ALL state."""
        presets = [
            create_mock_preset("web"),
            create_mock_preset("social"),
        ]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Select a category
        bar._buttons["web"].click()
        
        # Reset
        bar.reset_filters()
        
        assert bar.get_active_categories() == []
        assert bar._selected_category is None


@pytest.mark.usefixtures("qapp")
class TestButtonStyling:
    """Tests for button styling."""
    
    def test_button_text_uppercase(self):
        """Test that button text is UPPERCASE."""
        presets = [create_mock_preset("web")]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        # Button text should be uppercase
        assert bar._buttons["web"].text() == "WEB"
    
    def test_all_button_text(self):
        """Test that ALL button has correct text."""
        presets = [create_mock_preset("web")]
        
        bar = CategoryFilterBar()
        bar.set_categories(presets)
        
        assert bar._buttons[CategoryFilterBar.ALL_KEY].text() == "ALL"
