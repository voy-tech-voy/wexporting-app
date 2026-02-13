import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from client.core.target_size.video_estimators.mp4_h264_estimator_v5 import Estimator
from client.utils.gpu_detector import get_gpu_detector
from client.core.tool_registry import get_ffmpeg_path

print("--- Diagnostics ---")
try:
    ffmpeg_path = get_ffmpeg_path()
    print(f"FFmpeg Path: {ffmpeg_path}")
    
    detector = get_gpu_detector(ffmpeg_path)
    print("GPU Detector initialized")
    
    codec, type = detector.get_best_encoder('MP4 (H.264)', prefer_gpu=True)
    print(f"Resolved Codec: {codec} ({type})")
    
    est = Estimator()
    print("Estimator initialized")
    
    # Create dummy file for metadata check if needed, or mock it
    # For now just check if we can reach the codec resolution logic which is inside estimate()
    # But estimate() relies on get_media_metadata. 
    # Let's just check if the import worked and codec resolution works manually.
    
except Exception as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()

