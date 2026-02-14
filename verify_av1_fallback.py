
import sys
import types
from unittest.mock import MagicMock, patch

# Define valid dummy classes to avoid typing/syntax errors
class QThread_Dummy:
    pass

class QObject_Dummy:
    pass

class pyqtSignal_Dummy:
    def __init__(self, *args): pass
    def emit(self, *args): pass

# Create a dummy module for QtCore
qt_core = types.ModuleType('PyQt6.QtCore')
qt_core.QThread = QThread_Dummy
qt_core.QObject = QObject_Dummy
qt_core.pyqtSignal = pyqtSignal_Dummy

# Register it in sys.modules
sys.modules['PyQt6'] = types.ModuleType('PyQt6')
sys.modules['PyQt6.QtCore'] = qt_core
sys.modules['PyQt6.QtWidgets'] = types.ModuleType('PyQt6.QtWidgets')
sys.modules['PyQt6.QtGui'] = types.ModuleType('PyQt6.QtGui')

# Add project root to path
sys.path.append('v:\\_MY_APPS\\ImgApp_1')

# Now import project modules
import ffmpeg
from client.utils.gpu_detector import GPUDetector, EncoderType, EncoderInfo
from client.core.manual_mode.converters.video_converter import VideoConverter

def verify_fallback():
    print("--- Starting AV1 Fallback Verification ---")
    
    # 1. Setup mocks
    with patch('client.utils.gpu_detector.GPUDetector.detect_encoders') as mock_detect, \
         patch('client.utils.gpu_detector.GPUDetector.get_best_encoder', return_value=('av1_nvenc', EncoderType.NVIDIA)), \
         patch('client.core.manual_mode.converters.video_converter.get_video_duration', return_value=10.0), \
         patch('client.core.manual_mode.converters.video_converter.has_audio_stream', return_value=False), \
         patch('os.makedirs'), \
         patch('ffmpeg.probe'), \
         patch('ffmpeg.input') as mock_input, \
         patch('ffmpeg.output') as mock_output, \
         patch('ffmpeg.overwrite_output'): # Mock overwrite too
        
        # Simulate encoder detection
        mock_detect.return_value = ['av1_nvenc', 'libsvtav1']
        
        # Setup ffmpeg mocks to return dummy stream objects
        mock_stream = MagicMock()
        mock_input.return_value = mock_stream
        mock_stream.video = mock_stream # video stream is just the stream itself for simplicity
        mock_stream.audio = None
        
        # output() returns a runnable object
        mock_runnable = MagicMock()
        mock_output.return_value = mock_runnable
        
        # Mock ffmpeg.run to FAIL on first call and SUCCEED on second
        mock_ffmpeg_run = MagicMock()
        mock_ffmpeg_run.side_effect = [
            ffmpeg.Error(cmd=['ffmpeg', '...'], stdout=b'', stderr=b'Codec not supported'),
            (b'', b'') # Success tuple
        ]
        
        with patch('ffmpeg.run', mock_ffmpeg_run):
            # Create a dummy converter
            params = {
                'codec': 'AV1',
                'quality': 85,
                'overwrite': True
            }
            converter = VideoConverter(params, lambda x: print(f"[STATUS] {x}"), lambda x: None)
            
            # Create dummy file paths
            input_file = "test_input.mp4"
            output_file = "test_output.mp4"
            
            print("Attempting conversion...")
            success = converter.convert(input_file, output_file)
            
            print(f"Conversion success: {success}")
            
            # Verify calls
            print(f"ffmpeg.run called {mock_ffmpeg_run.call_count} times")
            if mock_ffmpeg_run.call_count == 2:
                print("✅ Correctly retried once")
            else:
                print("❌ Did not retry correct number of times")
                
            if success:
                print("✅ Fallback allowed success")
            else:
                print("❌ Fallback failed")

if __name__ == "__main__":
    try:
        verify_fallback()
    except Exception as e:
        print(f"Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
