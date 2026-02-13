"""Test v5 estimators EXACTLY as the app does - via run_video_conversion"""
import sys, os
sys.path.append(os.getcwd())

from client.core.target_size.size_estimator_registry import run_video_conversion

input_file = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\test_video.mov"
output_dir = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\output"

def test_codec(codec_name, target_mb=0.25):
    print(f"\n{'='*60}")
    print(f"Testing {codec_name} via run_video_conversion (EXACT app flow)")
    print(f"{'='*60}")
    
    target_bytes = int(target_mb * 1024 * 1024)
    output_file = os.path.join(output_dir, f"test_app_flow_{codec_name.replace(' ', '_').replace('(', '').replace(')', '')}.mp4")
    
    def status_cb(msg):
        print(f"  [STATUS] {msg}")
    
    def progress_cb(p):
        if p == 0 or p >= 0.99:
            print(f"  [PROGRESS] {p*100:.0f}%")
    
    try:
        # Call EXACTLY as the app does
        success = run_video_conversion(
            input_path=input_file,
            output_path=output_file,
            target_size_bytes=target_bytes,
            codec_pref=codec_name,
            estimator_version='v5',
            status_callback=status_cb,
            stop_check=lambda: False,
            progress_callback=progress_cb,
            allow_downscale=False
        )
        
        if success and os.path.exists(output_file):
            size_mb = os.path.getsize(output_file) / (1024*1024)
            print(f"✅ SUCCESS - {size_mb:.2f} MB")
            return True
        else:
            print(f"❌ FAILED - success={success}, exists={os.path.exists(output_file)}")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test both codecs
h264_ok = test_codec('MP4 (H.264)', 0.25)
h265_ok = test_codec('MP4 (H.265)', 0.25)

print(f"\n{'='*60}")
print(f"RESULTS: H.264={'✅' if h264_ok else '❌'}, H.265={'✅' if h265_ok else '❌'}")
print(f"{'='*60}")
