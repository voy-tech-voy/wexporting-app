"""Quick test of H.264 v5 estimator ONLY"""
import sys, os
import time
sys.path.append(os.getcwd())

from client.core.target_size.video_estimators.mp4_h264_estimator_v5 import Estimator as H264Estimator

input_file = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\test_video.mov"
output_dir = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\output"
target_size = 1 * 1024 * 1024  # 1MB

print("=== Testing H.264 v5 Estimator ===")

output_file = os.path.join(output_dir, f"test_H264_v5_final.mp4")
estimator = H264Estimator()

def status_cb(msg):
    print(f"[STATUS] {msg}")

def progress_cb(p):
    if p >= 0.99 or p == 0:
        print(f"[PROGRESS] {p*100:.1f}%")

try:
    start_time = time.time()
    success = estimator.execute(
        input_file,
        output_file,
        target_size,
        status_callback=status_cb,
        progress_callback=progress_cb,
        allow_downscale=False
    )
    duration = time.time() - start_time
    
    if success and os.path.exists(output_file):
        size_mb = os.path.getsize(output_file) / (1024*1024)
        print(f"\n✅ SUCCESS - Output: {size_mb:.2f} MB (Time: {duration:.1f}s)")
    else:
        print(f"\n❌ FAILED")
        
except Exception as e:
    print(f"\n❌ EXCEPTION: {e}")
    import traceback
    traceback.print_exc()
