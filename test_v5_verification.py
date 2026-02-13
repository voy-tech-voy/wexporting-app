"""Quick test of v5 estimators (H.264 and H.265) after fixes"""
import sys, os
import time
sys.path.append(os.getcwd())

from client.core.target_size.video_estimators.mp4_h264_estimator_v5 import Estimator as H264Estimator
from client.core.target_size.video_estimators.mp4_h265_estimator_v5 import Estimator as H265Estimator

input_file = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\test_video.mov"
output_dir = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\output"
target_size = 1 * 1024 * 1024  # 1MB

def run_test(name, estimator_cls, ext):
    print(f"\n{'='*50}")
    print(f"Testing {name}")
    print(f"{'='*50}")
    
    output_file = os.path.join(output_dir, f"test_{name}_fixed.{ext}")
    estimator = estimator_cls()
    
    def status_cb(msg):
        print(f"[{name}] {msg}")

    def progress_cb(p):
        if p >= 0.99 or p == 0:
            print(f"[{name}] Progress: {p*100:.1f}%")

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
            print(f"✅ SUCCESS - Output: {size_mb:.2f} MB (Time: {duration:.1f}s)")
        else:
            print(f"❌ FAILED")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

print("Starting v5 Estimator Verification...")

# Test H.264 v5
run_test("H264_v5", H264Estimator, "mp4")

# Test H.265 v5
run_test("H265_v5", H265Estimator, "mp4")
