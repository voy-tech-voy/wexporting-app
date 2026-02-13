"""Debug script to see the actual error when executing v5 estimators"""
import sys, os
sys.path.append(os.getcwd())

from client.core.target_size.size_estimator_registry import run_video_conversion

input_file = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\test_video.mov"
output_file = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\output\debug_v5_error.mp4"
target_bytes = int(0.22 * 1024 * 1024)  # 0.22 MB like in the log

print("="*60)
print("Testing H.264 v5 with FULL error output")
print("="*60)

def status_cb(msg):
    print(f"[STATUS] {msg}")

def progress_cb(p):
    print(f"[PROGRESS] {p*100:.0f}%")

try:
    success = run_video_conversion(
        input_path=input_file,
        output_path=output_file,
        target_size_bytes=target_bytes,
        codec_pref='MP4 (H.264)',
        estimator_version='v5',
        status_callback=status_cb,
        stop_check=lambda: False,
        progress_callback=progress_cb,
        allow_downscale=False
    )
    
    print(f"\nResult: success={success}")
    if os.path.exists(output_file):
        size = os.path.getsize(output_file) / (1024*1024)
        print(f"Output file: {size:.2f} MB")
    else:
        print("Output file does NOT exist")
        
except Exception as e:
    print(f"\n{'='*60}")
    print("EXCEPTION CAUGHT:")
    print(f"{'='*60}")
    print(f"{type(e).__name__}: {e}")
    print(f"\nFull traceback:")
    import traceback
    traceback.print_exc()
