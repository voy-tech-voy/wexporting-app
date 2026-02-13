"""Quick test of v5 estimator after fix"""
import sys, os
sys.path.append(os.getcwd())

from client.core.target_size.video_estimators.mp4_h264_estimator_v5 import Estimator

input_file = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\test_video.mov"
output_file = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\output\test_v5_fixed.mp4"
target_size = 1 * 1024 * 1024  # 1MB

print("=== Testing v5 H.264 Estimator (After Fix) ===")

estimator = Estimator()

def status_cb(msg):
    print(f"[STATUS] {msg}")

def progress_cb(p):
    if p >= 0.99 or p == 0:
        print(f"[PROGRESS] {p*100:.1f}%")

try:
    success = estimator.execute(
        input_file,
        output_file,
        target_size,
        status_callback=status_cb,
        progress_callback=progress_cb,
        allow_downscale=False
    )
    
    if success and os.path.exists(output_file):
        size_mb = os.path.getsize(output_file) / (1024*1024)
        print(f"\n✅ SUCCESS - Output: {size_mb:.2f} MB")
    else:
        print(f"\n❌ FAILED")
        
except Exception as e:
    print(f"\n❌ EXCEPTION: {e}")
    import traceback
    traceback.print_exc()
