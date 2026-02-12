
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client.core.tool_registry import get_registry
from client.gui.advanced_settings_window import AdvancedSettingsWindow
from PyQt6.QtWidgets import QApplication

class TestAdvancedSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create QApplication instance if it doesn't exist
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_registry_bundled_path(self):
        """Test that get_bundled_path exists and works"""
        registry = get_registry()
        
        # Test ffmpeg
        ffmpeg_path = registry.get_bundled_path('ffmpeg')
        print(f"FFmpeg bundled path: {ffmpeg_path}")
        
        # Test magick
        magick_path = registry.get_bundled_path('magick')
        print(f"ImageMagick bundled path: {magick_path}")
        
        # We don't assert it's not None because it depends on environment,
        # but the method should exist and not raise error.

    def test_window_instantiation(self):
        """Test that AdvancedSettingsWindow can be instantiated"""
        try:
            # Mock get_ffmpeg_settings to avoid file I/O issues during test
            with patch('client.gui.advanced_settings_window.get_ffmpeg_settings') as mock_get_settings:
                mock_settings = MagicMock()
                mock_settings.get_mode.return_value = 'bundled'
                mock_settings.get_custom_path.return_value = ''
                mock_settings.get_bundled_ffmpeg_path.return_value = 'mock/path/ffmpeg.exe'
                mock_get_settings.return_value = mock_settings
                
                # Mock registry to avoid complications
                with patch('client.gui.advanced_settings_window.get_registry') as mock_get_registry:
                    mock_registry = MagicMock()
                    mock_registry.get_tool_mode.return_value = 'bundled'
                    mock_registry.get_custom_path.return_value = ''
                    mock_registry.get_bundled_path.return_value = 'mock/path/magick.exe'
                    mock_get_registry.return_value = mock_registry
                    
                    window = AdvancedSettingsWindow()
                    self.assertIsNotNone(window)
                    self.assertEqual(window.minimumWidth(), 720)
                    print("AdvancedSettingsWindow instantiated successfully")
                    
        except Exception as e:
            self.fail(f"Failed to instantiate AdvancedSettingsWindow: {e}")

if __name__ == '__main__':
    unittest.main()
