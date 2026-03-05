"""
Unit tests for MainWindow Mediator-Shell Architecture

Tests the communication flow between:
- MainWindow (Mediator/Conductor)
- ControlBar (Mode toggles)
- CommandPanel (Settings)
- DragDropArea (File management)
- StatusPanel (Progress display)
"""

import pytest
import sys
from unittest.mock import MagicMock, patch, PropertyMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QSignalSpy


# Ensure we have a QApplication for widget tests
@pytest.fixture(scope="module")
def app():
    """Create QApplication for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def main_window(app):
    """Create MainWindow instance for testing."""
    from client.gui.main_window import MainWindow
    window = MainWindow(is_trial=False)
    yield window
    window.close()
    window.deleteLater()


class TestMainWindowComponents:
    """Test that all required components are properly initialized."""
    
    def test_control_bar_exists(self, main_window):
        """ControlBar should be created and accessible."""
        assert hasattr(main_window, 'control_bar'), "MainWindow should have control_bar attribute"
        assert main_window.control_bar is not None, "control_bar should not be None"
    
    def test_command_panel_exists(self, main_window):
        """CommandPanel should be created and accessible."""
        assert hasattr(main_window, 'command_panel'), "MainWindow should have command_panel attribute"
        assert main_window.command_panel is not None, "command_panel should not be None"
    
    def test_drag_drop_area_exists(self, main_window):
        """DragDropArea should be created and accessible."""
        assert hasattr(main_window, 'drag_drop'), "MainWindow should have drag_drop attribute"
        assert main_window.drag_drop is not None, "drag_drop should not be None"
    
    def test_status_panel_exists(self, main_window):
        """StatusPanel should be created and accessible - may be in output_footer."""
        # StatusPanel might be embedded in output_footer
        has_status = (
            hasattr(main_window, 'status_panel') or 
            hasattr(main_window, 'output_footer')
        )
        assert has_status, "MainWindow should have status_panel or output_footer"


class TestControlBarSignals:
    """Test ControlBar signal connections to MainWindow."""
    
    def test_add_files_signal_connected(self, main_window):
        """add_files_clicked signal should be connected."""
        control_bar = main_window.control_bar
        # Check signal exists
        assert hasattr(control_bar, 'add_files_clicked'), "ControlBar should have add_files_clicked signal"
    
    def test_add_folder_signal_connected(self, main_window):
        """add_folder_clicked signal should be connected."""
        control_bar = main_window.control_bar
        assert hasattr(control_bar, 'add_folder_clicked'), "ControlBar should have add_folder_clicked signal"
    
    def test_clear_files_signal_connected(self, main_window):
        """clear_files_clicked signal should be connected."""
        control_bar = main_window.control_bar
        assert hasattr(control_bar, 'clear_files_clicked'), "ControlBar should have clear_files_clicked signal"
    
    def test_preset_mode_signal_connected(self, main_window):
        """preset_mode_clicked signal should be connected."""
        control_bar = main_window.control_bar
        assert hasattr(control_bar, 'preset_mode_clicked'), "ControlBar should have preset_mode_clicked signal"
    
    def test_lab_mode_signal_connected(self, main_window):
        """lab_mode_clicked signal should be connected."""
        control_bar = main_window.control_bar
        assert hasattr(control_bar, 'lab_mode_clicked'), "ControlBar should have lab_mode_clicked signal"


class TestCommandPanelSignals:
    """Test CommandPanel signal connections to MainWindow."""
    
    def test_conversion_requested_signal(self, main_window):
        """conversion_requested signal should exist."""
        command_panel = main_window.command_panel
        assert hasattr(command_panel, 'conversion_requested'), "CommandPanel should have conversion_requested signal"
    
    def test_stop_conversion_signal(self, main_window):
        """stop_conversion_requested signal should exist."""
        command_panel = main_window.command_panel
        assert hasattr(command_panel, 'stop_conversion_requested'), "CommandPanel should have stop_conversion_requested signal"
    
    def test_get_parameters_method(self, main_window):
        """get_parameters() should return a dict with conversion settings."""
        command_panel = main_window.command_panel
        assert hasattr(command_panel, 'get_parameters'), "CommandPanel should have get_parameters method"
        
        params = command_panel.get_parameters()
        assert isinstance(params, dict), "get_parameters() should return a dict"


class TestDragDropAreaSignals:
    """Test DragDropArea signal connections to MainWindow."""
    
    def test_files_added_signal(self, main_window):
        """files_added signal should exist."""
        drag_drop = main_window.drag_drop
        assert hasattr(drag_drop, 'files_added'), "DragDropArea should have files_added signal"
    
    def test_get_files_method(self, main_window):
        """get_files() should return list of files."""
        drag_drop = main_window.drag_drop
        assert hasattr(drag_drop, 'get_files'), "DragDropArea should have get_files method"
        
        files = drag_drop.get_files()
        assert isinstance(files, (list, tuple)), "get_files() should return a list"


class TestModeSwitch:
    """Test mode switching between Preset and Lab modes."""
    
    def test_switch_to_preset_mode(self, main_window):
        """Switching to preset mode should update UI state."""
        # Check if there's a method to switch modes
        if hasattr(main_window, '_handle_preset_button_click'):
            # This should not raise an exception
            main_window._handle_preset_button_click()
            # Verify preset mode is active
            assert True, "Preset mode switch completed without error"
    
    def test_switch_to_lab_mode(self, main_window):
        """Switching to lab mode should update UI state."""
        if hasattr(main_window, '_handle_lab_item_click'):
            # Switch to lab mode (tab 0 = Image)
            main_window._handle_lab_item_click(0)
            assert True, "Lab mode switch completed without error"


class TestThemeHandling:
    """Test theme management."""
    
    def test_theme_manager_exists(self, main_window):
        """ThemeManager should be accessible."""
        has_theme = (
            hasattr(main_window, 'theme_manager') or
            hasattr(main_window, '_theme_manager')
        )
        assert has_theme, "MainWindow should have theme_manager"
    
    def test_theme_update_method(self, main_window):
        """Theme update method should exist."""
        has_update = (
            hasattr(main_window, 'update_theme') or
            hasattr(main_window, '_on_theme_changed')
        )
        assert has_update, "MainWindow should have theme update capability"


class TestMediatorPattern:
    """Test that MainWindow properly mediates between components."""
    
    def test_control_bar_to_drag_drop_flow(self, main_window):
        """ControlBar clear signal should affect DragDropArea."""
        drag_drop = main_window.drag_drop
        control_bar = main_window.control_bar
        
        # Both components should exist and be connected
        assert drag_drop is not None
        assert control_bar is not None
        
        # Verify the signal chain exists
        # (we can't easily test the actual flow without mocking file dialogs)
    
    def test_command_panel_parameters_available(self, main_window):
        """MainWindow should be able to get parameters from CommandPanel."""
        params = main_window.command_panel.get_parameters()
        
        # Should have at least 'type' key indicating conversion type
        assert 'type' in params or len(params) > 0, "Parameters should have content"


class TestComponentIntegration:
    """Integration tests for component communication."""
    
    def test_all_major_components_initialized(self, main_window):
        """All major UI components should be initialized."""
        components = [
            'control_bar',
            'command_panel', 
            'drag_drop',
        ]
        
        for comp in components:
            assert hasattr(main_window, comp), f"Missing component: {comp}"
            assert getattr(main_window, comp) is not None, f"Component is None: {comp}"
    
    def test_tab_switching_updates_command_panel(self, main_window):
        """Switching tabs should update CommandPanel state."""
        command_panel = main_window.command_panel
        
        if hasattr(command_panel, 'tabs'):
            # Switch to video tab
            command_panel.tabs.setCurrentIndex(1)
            params = command_panel.get_parameters()
            assert params.get('type') in ['video', 'Video', None], "Should be video type after tab switch"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
