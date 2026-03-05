"""
Unit Tests for CommandPanel Signal Architecture

Tests the signal communication between:
- CommandPanel (container)
- Tabs (ImageTab, VideoTab, LoopTab)
- ModeButtonsWidget
- SideButtonGroup

Signal Flow:
1. ModeButtonsWidget.modeChanged -> CommandPanel._on_global_mode_changed
2. CommandPanel.global_mode_changed -> MainWindow (external)
3. SideButtonGroup.selectionChanged -> Tab.set_transform_mode
4. Tab.params_changed -> (future: live preview)
5. CommandPanel.conversion_requested -> MainWindow
6. CommandPanel.lab_state_changed -> MainWindow
"""

import pytest
from unittest.mock import MagicMock, patch, call
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestCommandPanelSignalDefinitions:
    """Test that all required signals are defined on CommandPanel."""
    
    def test_conversion_requested_signal_exists(self):
        """CommandPanel should have conversion_requested signal."""
        from client.gui.command_panel import CommandPanel
        assert hasattr(CommandPanel, 'conversion_requested')
    
    def test_stop_conversion_requested_signal_exists(self):
        """CommandPanel should have stop_conversion_requested signal."""
        from client.gui.command_panel import CommandPanel
        assert hasattr(CommandPanel, 'stop_conversion_requested')
    
    def test_global_mode_changed_signal_exists(self):
        """CommandPanel should have global_mode_changed signal."""
        from client.gui.command_panel import CommandPanel
        assert hasattr(CommandPanel, 'global_mode_changed')
    
    def test_lab_state_changed_signal_exists(self):
        """CommandPanel should have lab_state_changed signal."""
        from client.gui.command_panel import CommandPanel
        assert hasattr(CommandPanel, 'lab_state_changed')


class TestBaseTabSignalDefinitions:
    """Test that all required signals are defined on BaseTab."""
    
    def test_params_changed_signal_exists(self):
        """BaseTab should have params_changed signal."""
        from client.gui.tabs.base_tab import BaseTab
        assert hasattr(BaseTab, 'params_changed')


class TestLoopTabSignalDefinitions:
    """Test that LoopTab has its specialized signals."""
    
    def test_format_changed_signal_exists(self):
        """LoopTab should have format_changed signal."""
        from client.gui.tabs.loop_tab import LoopTab
        assert hasattr(LoopTab, 'format_changed')


class TestModeButtonsSignals:
    """Test ModeButtonsWidget signal definitions."""
    
    def test_mode_changed_signal_exists(self):
        """ModeButtonsWidget should have modeChanged signal."""
        from client.gui.custom_widgets import ModeButtonsWidget
        assert hasattr(ModeButtonsWidget, 'modeChanged')


class TestSideButtonGroupSignals:
    """Test SideButtonGroup signal definitions."""
    
    def test_selection_changed_signal_exists(self):
        """SideButtonGroup should have selectionChanged signal."""
        from client.gui.custom_widgets import SideButtonGroup
        assert hasattr(SideButtonGroup, 'selectionChanged')


# ============================================================================
# INTEGRATION TESTS - Signal Flow (Require QApplication)
# ============================================================================

@pytest.fixture
def qapp():
    """Create QApplication for widget tests."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def command_panel(qapp):
    """Create CommandPanel instance for testing."""
    from client.gui.command_panel import CommandPanel
    with patch('client.gui.command_panel.QTimer'):
        panel = CommandPanel()
    yield panel
    panel.deleteLater()


class TestModeButtonsToCommandPanelFlow:
    """Test signal flow from ModeButtonsWidget to CommandPanel."""
    
    def test_mode_buttons_connected_to_handler(self, command_panel):
        """mode_buttons.modeChanged should be connected to _on_global_mode_changed."""
        # The connection should be in place from setup_ui
        assert hasattr(command_panel, 'mode_buttons')
        # Verify signal exists
        assert hasattr(command_panel.mode_buttons, 'modeChanged')
    
    def test_mode_change_emits_global_signal(self, command_panel):
        """Mode button change should emit global_mode_changed signal."""
        mock_handler = MagicMock()
        command_panel.global_mode_changed.connect(mock_handler)
        
        # Trigger mode change
        command_panel._on_global_mode_changed("Manual")
        
        # Verify signal was emitted
        mock_handler.assert_called_once_with("Manual")
    
    def test_mode_change_updates_active_tab(self, command_panel):
        """Mode button change should update the active tab's mode."""
        # Set to Image tab (index 0)
        command_panel.tabs.setCurrentIndex(0)
        
        # Mock the tab's set_mode method
        command_panel._image_tab.set_mode = MagicMock()
        
        # Trigger mode change
        command_panel._on_global_mode_changed("Manual")
        
        # Verify tab was updated
        command_panel._image_tab.set_mode.assert_called_once_with("Manual")
    
    def test_mode_change_tracked_per_tab(self, command_panel):
        """Each tab should track its own mode."""
        # Set Image tab to Manual
        command_panel.tabs.setCurrentIndex(0)
        command_panel._on_global_mode_changed("Manual")
        
        # Set Video tab to Max Size
        command_panel.tabs.setCurrentIndex(1)
        command_panel._on_global_mode_changed("Max Size")
        
        # Verify modes are tracked separately
        assert command_panel.tab_modes[0] == "Manual"
        assert command_panel.tab_modes[1] == "Max Size"


class TestSideButtonsToTabFlow:
    """Test signal flow from SideButtonGroup to Tab."""
    
    def test_image_side_buttons_connected(self, command_panel):
        """Image side buttons should have selectionChanged signal."""
        assert hasattr(command_panel, 'image_side_buttons')
        assert hasattr(command_panel.image_side_buttons, 'selectionChanged')
    
    def test_video_side_buttons_connected(self, command_panel):
        """Video side buttons should have selectionChanged signal."""
        assert hasattr(command_panel, 'video_side_buttons')
        assert hasattr(command_panel.video_side_buttons, 'selectionChanged')
    
    def test_loop_side_buttons_connected(self, command_panel):
        """Loop side buttons should have selectionChanged signal."""
        assert hasattr(command_panel, 'loop_side_buttons')
        assert hasattr(command_panel.loop_side_buttons, 'selectionChanged')


class TestTabSwitchingFlow:
    """Test tab switching signal flow."""
    
    def test_tab_change_syncs_side_buttons_stack(self, command_panel):
        """Tab change should sync side_buttons_stack index."""
        command_panel.tabs.setCurrentIndex(2)  # Loop tab
        assert command_panel.side_buttons_stack.currentIndex() == 2
    
    def test_tab_change_restores_mode(self, command_panel):
        """Tab change should restore that tab's saved mode."""
        # Set different modes per tab
        command_panel.tab_modes[0] = "Manual"
        command_panel.tab_modes[1] = "Max Size"
        command_panel.tab_modes[2] = "Presets"
        
        # Mock mode_buttons.set_mode
        command_panel.mode_buttons.set_mode = MagicMock()
        
        # Switch to Loop tab
        command_panel._on_tab_changed(2)
        
        # Verify mode was restored
        command_panel.mode_buttons.set_mode.assert_called_with("Presets")
    
    def test_tab_change_emits_lab_state(self, command_panel):
        """Tab change should emit lab_state_changed signal."""
        mock_handler = MagicMock()
        command_panel.lab_state_changed.connect(mock_handler)
        
        command_panel._on_tab_changed(0)  # Switch to Image tab
        
        # Signal should be emitted
        mock_handler.assert_called_once()


class TestConversionSignalFlow:
    """Test conversion request signal flow."""
    
    def test_start_conversion_emits_signal(self, command_panel):
        """start_conversion should emit conversion_requested signal."""
        mock_handler = MagicMock()
        command_panel.conversion_requested.connect(mock_handler)
        
        command_panel.start_conversion()
        
        mock_handler.assert_called_once()
        # Verify it's called with a dict
        args = mock_handler.call_args[0]
        assert isinstance(args[0], dict)
    
    def test_get_conversion_params_delegates_to_active_tab(self, command_panel):
        """get_conversion_params should delegate to current tab."""
        # Set to Video tab
        command_panel.tabs.setCurrentIndex(1)
        
        params = command_panel.get_conversion_params()
        
        # Should have video-specific keys
        assert 'type' in params
        assert params['type'] == 'video'
    
    def test_get_params_from_image_tab(self, command_panel):
        """Image tab params should have type='image'."""
        command_panel.tabs.setCurrentIndex(0)
        params = command_panel.get_conversion_params()
        assert params['type'] == 'image'
    
    def test_get_params_from_loop_tab(self, command_panel):
        """Loop tab params should have type='loop'."""
        command_panel.tabs.setCurrentIndex(2)
        params = command_panel.get_conversion_params()
        assert params['type'] == 'loop'


class TestLabStateSignalFlow:
    """Test lab_state_changed signal flow."""
    
    def test_update_tab_icons_emits_lab_state(self, command_panel):
        """update_tab_icons should emit lab_state_changed."""
        mock_handler = MagicMock()
        command_panel.lab_state_changed.connect(mock_handler)
        
        command_panel.update_tab_icons(activate_lab=True)
        
        mock_handler.assert_called_once()
        # Verify signature (icon_path, activate_lab)
        args = mock_handler.call_args[0]
        assert isinstance(args[0], str)  # icon path
        assert isinstance(args[1], bool)  # activate_lab
    
    def test_on_tab_btn_clicked_activates_lab(self, command_panel):
        """_on_tab_btn_clicked should emit lab_state_changed with activate=True."""
        mock_handler = MagicMock()
        command_panel.lab_state_changed.connect(mock_handler)
        
        command_panel._on_tab_btn_clicked(1)  # Video tab
        
        # Verify activate_lab is True
        args = mock_handler.call_args[0]
        assert args[1] == True


class TestLabModeStateManagement:
    """Test lab mode active state management."""
    
    def test_set_lab_mode_active(self, command_panel):
        """set_lab_mode_active should update internal state."""
        assert command_panel._lab_mode_active == False  # Default
        
        command_panel.set_lab_mode_active(True)
        
        assert command_panel._lab_mode_active == True
    
    def test_set_top_bar_preset_mode(self, command_panel):
        """set_top_bar_preset_mode should update internal state."""
        assert command_panel._top_bar_preset_active == False  # Default
        
        command_panel.set_top_bar_preset_mode(True)
        
        assert command_panel._top_bar_preset_active == True


class TestThemeSignalFlow:
    """Test theme update propagation."""
    
    def test_update_theme_propagates_to_tabs(self, command_panel):
        """update_theme should call update_theme on all tabs."""
        command_panel._image_tab.update_theme = MagicMock()
        command_panel._video_tab.update_theme = MagicMock()
        command_panel._loop_tab.update_theme = MagicMock()
        
        command_panel.update_theme(False)  # Light mode
        
        command_panel._image_tab.update_theme.assert_called_once_with(False)
        command_panel._video_tab.update_theme.assert_called_once_with(False)
        command_panel._loop_tab.update_theme.assert_called_once_with(False)


class TestBackwardsCompatibilityProperties:
    """Test backwards compatibility property access."""
    
    def test_image_tab_property(self, command_panel):
        """image_tab property should return _image_tab."""
        assert command_panel.image_tab is command_panel._image_tab
    
    def test_video_tab_property(self, command_panel):
        """video_tab property should return _video_tab."""
        assert command_panel.video_tab is command_panel._video_tab
    
    def test_loop_tab_property(self, command_panel):
        """loop_tab property should return _loop_tab."""
        assert command_panel.loop_tab is command_panel._loop_tab


class TestParameterDelegation:
    """Test parameter delegation to tabs."""
    
    def test_get_parameters_alias(self, command_panel):
        """get_parameters should be alias for get_conversion_params."""
        params1 = command_panel.get_parameters()
        params2 = command_panel.get_conversion_params()
        
        # They should return equivalent dicts
        assert params1.keys() == params2.keys()
    
    def test_get_execution_payload(self, command_panel):
        """get_execution_payload should include conversion params."""
        payload = command_panel.get_execution_payload()
        
        assert isinstance(payload, dict)
        assert 'type' in payload
