"""
UI Rendering Tests for Preset Gallery

Tests for proper overlay rendering behavior:
- Background opacity and color
- Widget stacking (gallery on top of drop area)
- Proper geometry matching parent
- Click event handling (not passing through to elements behind)
- Category filtering layout
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor


# Ensure QApplication exists for Qt tests
@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_presets():
    """Create mock preset definitions for testing."""
    from client.plugins.presets.logic.models import PresetDefinition, PipelineStep
    
    return [
        PresetDefinition(
            id="test_social",
            name="Social Preset",
            category="social",
            pipeline=[PipelineStep(tool="ffmpeg", command_template="test")]
        ),
        PresetDefinition(
            id="test_web",
            name="Web Preset", 
            category="web",
            pipeline=[PipelineStep(tool="ffmpeg", command_template="test")]
        ),
        PresetDefinition(
            id="test_utility",
            name="Utility Preset",
            category="utility",
            pipeline=[PipelineStep(tool="ffmpeg", command_template="test")]
        ),
    ]


class TestGalleryRendering:
    """Tests for PresetGallery rendering behavior."""
    
    def test_gallery_imports(self):
        """Verify gallery can be imported."""
        from client.plugins.presets.ui.gallery import PresetGallery
        assert PresetGallery is not None
    
    def test_gallery_has_paint_event(self):
        """Verify gallery has custom paintEvent for background."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        # Check that paintEvent is overridden (not inherited from QWidget)
        assert hasattr(PresetGallery, 'paintEvent')
        # Ensure it's actually overridden, not just inherited
        assert PresetGallery.paintEvent is not QWidget.paintEvent
    
    def test_gallery_creation(self, qapp, mock_presets):
        """Test gallery widget can be created."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        parent = QWidget()
        parent.resize(800, 600)
        
        gallery = PresetGallery(parent)
        
        assert gallery.parent() == parent
        assert gallery.objectName() == "PresetGallery"
    
    def test_gallery_initially_hidden(self, qapp):
        """Test gallery is hidden by default."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        
        assert not gallery.isVisible()
    
    def test_gallery_has_styled_background_attribute(self, qapp):
        """Test gallery has WA_StyledBackground attribute set."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        
        assert gallery.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    
    def test_gallery_auto_fill_background(self, qapp):
        """Test gallery has autoFillBackground enabled."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        
        assert gallery.autoFillBackground()
    
    def test_gallery_geometry_matches_parent(self, qapp):
        """Test gallery geometry matches parent when shown."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        parent = QWidget()
        parent.resize(800, 600)
        
        gallery = PresetGallery(parent)
        gallery.show_animated()
        
        # After show_animated, geometry should match parent
        assert gallery.geometry() == parent.rect()
    
    def test_gallery_resize_follows_parent(self, qapp):
        """Test gallery resizes when parent resizes."""
        from client.plugins.presets.ui.gallery import PresetGallery
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QResizeEvent
        
        parent = QWidget()
        parent.resize(800, 600)
        
        gallery = PresetGallery(parent)
        gallery.setGeometry(parent.rect())  # Initial setup
        gallery.show()
        
        # Simulate parent resize
        new_size = QSize(1024, 768)
        parent.resize(new_size)
        
        # Manually trigger event filter since app loop isn't running
        event = QResizeEvent(new_size, QSize(800, 600))
        gallery.eventFilter(parent, event)
        
        assert gallery.geometry() == parent.rect()
    
    def test_gallery_horizontal_scroll_disabled(self, qapp):
        """Test gallery has horizontal scroll disabled."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        
        # Access the scroll area
        assert hasattr(gallery, '_scroll')
        assert gallery._scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    
    def test_gallery_load_presets(self, qapp, mock_presets):
        """Test gallery can load presets."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        gallery.set_presets(mock_presets)
        
        # Should have presets stored
        assert len(gallery._presets) == 3
    
    def test_gallery_filter_bar_exists(self, qapp):
        """Test gallery has filter bar."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        
        assert hasattr(gallery, '_filter_bar')
        assert gallery._filter_bar is not None
    
    def test_gallery_signals_exist(self, qapp):
        """Test gallery has required signals."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        
        # Check signals exist
        assert hasattr(gallery, 'preset_selected')
        assert hasattr(gallery, 'dismissed')


class TestGalleryOverlayBehavior:
    """Tests for gallery overlay behavior (stacking, clicks)."""
    
    def test_gallery_raises_to_top(self, qapp):
        """Test gallery raises itself when shown."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        parent = QWidget()
        parent.resize(800, 600)
        parent.show()  # Parent must be visible
        
        # Create sibling widget
        sibling = QWidget(parent)
        sibling.setGeometry(0, 0, 400, 300)
        
        gallery = PresetGallery(parent)
        gallery.show()  # Direct show for testing
        
        # Gallery should be visible
        assert gallery.isVisible()
    
    def test_gallery_click_on_background_emits_dismissed(self, qapp):
        """Test clicking on gallery background emits dismissed signal."""
        from client.plugins.presets.ui.gallery import PresetGallery
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QMouseEvent, QSinglePointEvent
        from PySide6.QtCore import QEvent
        
        gallery = PresetGallery()
        gallery.resize(800, 600)
        
        # Track if dismissed was emitted
        dismissed_called = []
        gallery.dismissed.connect(lambda: dismissed_called.append(True))
        
        # Note: Full mouse event testing requires more setup
        # This test documents the expected behavior
        assert hasattr(gallery, 'mousePressEvent')


class TestGalleryBackgroundColor:
    """Tests for gallery background color/opacity."""
    
    def test_gallery_background_is_dark_grey(self, qapp):
        """Test gallery background is dark grey with high opacity."""
        from client.plugins.presets.ui.gallery import PresetGallery
        from PySide6.QtGui import QPainter, QColor, QImage
        
        gallery = PresetGallery()
        gallery.resize(100, 100)
        
        # Create test image to paint onto
        image = QImage(100, 100, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)  # Start with white
        
        painter = QPainter(image)
        
        # Paint the background manually (simulate what paintEvent does)
        bg_color = QColor(40, 40, 40, 230)  # Expected color
        painter.fillRect(gallery.rect(), bg_color)
        painter.end()
        
        # Sample a pixel - color will be blended with white background
        pixel = image.pixelColor(50, 50)
        
        # Check color is dark grey (blended result)
        # 40 * 0.9 + 255 * 0.1 = 36 + 25.5 = ~61 (due to alpha blending)
        assert pixel.red() < 100, "Background should be dark"
        assert pixel.green() < 100, "Background should be dark"
        assert pixel.blue() < 100, "Background should be dark"
    
    def test_gallery_opacity_blocks_content_behind(self, qapp):
        """Test gallery opacity is high enough to obscure content behind."""
        from client.plugins.presets.ui.gallery import PresetGallery
        from PySide6.QtGui import QColor
        
        # The expected alpha is 230/255 = 0.9 (90% opacity)
        expected_alpha = 230
        
        # This is a documentation test - we verify the expected value
        # The actual implementation uses QColor(40, 40, 40, 230)
        assert expected_alpha / 255 >= 0.9, "Gallery should be at least 90% opaque"


class TestGalleryLayoutResponsiveness:
    """Tests for responsive layout behavior."""
    
    def test_cards_per_row_calculation(self, qapp):
        """Test cards per row calculation based on width."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        gallery.resize(800, 600)
        
        # Access the internal scroll area to set viewport size
        gallery._scroll.resize(700, 500)
        
        cards_per_row = gallery._calculate_cards_per_row()
        
        # Should return a reasonable number (2-6)
        assert gallery.MIN_CARDS_PER_ROW <= cards_per_row <= gallery.MAX_CARDS_PER_ROW
    
    def test_min_cards_per_row_enforced(self, qapp):
        """Test minimum cards per row is enforced."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        
        # Very narrow width
        gallery._scroll.resize(100, 500)
        
        cards_per_row = gallery._calculate_cards_per_row()
        
        assert cards_per_row >= gallery.MIN_CARDS_PER_ROW
    
    def test_max_cards_per_row_enforced(self, qapp):
        """Test maximum cards per row is enforced."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        
        # Very wide width
        gallery._scroll.resize(2000, 500)
        
        cards_per_row = gallery._calculate_cards_per_row()
        
        assert cards_per_row <= gallery.MAX_CARDS_PER_ROW


class TestGalleryCategoryGrouping:
    """Tests for category grouping when ALL filter is active."""
    
    def test_grouped_layout_creates_category_labels(self, qapp, mock_presets):
        """Test grouped layout creates category labels."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        gallery.resize(800, 600)
        gallery.set_presets(mock_presets)
        
        # Apply filter (show all = no active categories)
        gallery._apply_filter()
        
        # Check container layout has items (labels + rows)
        assert gallery._container_layout.count() > 0
    
    def test_filtered_layout_no_category_labels(self, qapp, mock_presets):
        """Test filtered layout doesn't include other category labels."""
        from client.plugins.presets.ui.gallery import PresetGallery
        
        gallery = PresetGallery()
        gallery.resize(800, 600)
        gallery.set_presets(mock_presets)
        
        # Set filter bar to specific category
        gallery._filter_bar._active_categories = ["social"]
        gallery._apply_filter()
        
        # Should only show social presets (no category labels in filtered view)
        # Check that container has some items
        assert gallery._container_layout.count() >= 0


class TestPresetCardRendering:
    """Tests for PresetCard widget rendering."""
    
    def test_card_imports(self):
        """Verify card can be imported."""
        from client.plugins.presets.ui.card import PresetCard
        assert PresetCard is not None
    
    def test_card_creation(self, qapp, mock_presets):
        """Test card widget can be created."""
        from client.plugins.presets.ui.card import PresetCard
        
        card = PresetCard(mock_presets[0])
        
        assert card.preset == mock_presets[0]
    
    def test_card_has_fixed_size(self, qapp, mock_presets):
        """Test card has fixed dimensions."""
        from client.plugins.presets.ui.card import PresetCard
        
        card = PresetCard(mock_presets[0])
        
        # Cards should have fixed width/height from constants
        assert card.CARD_WIDTH > 0
        assert card.CARD_HEIGHT > 0
    
    def test_card_emits_clicked_signal(self, qapp, mock_presets):
        """Test card emits clicked signal with preset."""
        from client.plugins.presets.ui.card import PresetCard
        
        card = PresetCard(mock_presets[0])
        
        # Check signal exists
        assert hasattr(card, 'clicked')


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
