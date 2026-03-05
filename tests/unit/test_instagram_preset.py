import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Adjust path to find client module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Mock PyQt6 before importing ConversionEngine to avoid potential issues in headless environment
class MockSignal:
    def __init__(self, *args, **kwargs):
        self.emit = MagicMock()

mock_pyqt = MagicMock()
sys.modules['PyQt6'] = mock_pyqt
sys.modules['PyQt6.QtCore'] = mock_pyqt
mock_pyqt.QThread = MagicMock
mock_pyqt.Signal = MockSignal

# Mock ffmpeg as well
sys.modules['ffmpeg'] = MagicMock()

from client.core.conversion_engine import ConversionEngine

class TestInstagramPreset(unittest.TestCase):
    def setUp(self):
        self.params = {
            'type': 'video',
            'video_preset_social': 'Instagram',
            'video_preset_ratio': '9:16',
            'overwrite': True,
            'codec': 'H.264 (MP4)'
        }
        self.files = ['input.mp4']
        self.engine = ConversionEngine(self.files, self.params)

    @patch('ffmpeg.input')
    @patch('ffmpeg.output')
    @patch('client.core.conversion_engine.get_video_duration')
    @patch('client.core.conversion_engine.has_audio_stream')
    @patch('client.core.conversion_engine.get_video_dimensions')
    @patch('os.makedirs')
    def test_instagram_ffmpeg_params(self, mock_makedirs, mock_dims, mock_audio, mock_dur, mock_output, mock_input):
        # Setup mocks
        mock_dur.return_value = 60.0
        mock_audio.return_value = True
        mock_dims.return_value = (1920, 1080)
        
        # Mock input stream and its methods
        mock_stream = MagicMock()
        mock_input.return_value = mock_stream
        
        # Call the method
        with patch.object(self.engine, 'run_ffmpeg_with_cancellation'):
            # The engine uses self.params, which we initialized in setUp
            self.engine.convert_video("input.mp4")
        
        # Verify output args
        self.assertTrue(mock_output.called)
        _, kwargs = mock_output.call_args
        
        self.assertEqual(kwargs.get('vcodec'), 'libx264')
        self.assertEqual(kwargs.get('profile:v'), 'high')
        self.assertEqual(kwargs.get('level:v'), '4.2')
        self.assertEqual(kwargs.get('pix_fmt'), 'yuv420p')
        self.assertEqual(kwargs.get('colorspace'), 'bt709')
        self.assertEqual(kwargs.get('acodec'), 'aac')
        self.assertEqual(kwargs.get('r'), '30')
        self.assertEqual(kwargs.get('b:v'), '5000k')
        self.assertEqual(kwargs.get('f'), 'mp4')

if __name__ == '__main__':
    unittest.main()
