"""Test v5 estimators exactly as the app would use them"""
import sys, os
sys.path.append(os.getcwd())

from client.core.target_size.size_estimator_registry import get_video_estimator

# Test exactly as the app does
input_file = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\test_video.mov"
output_dir = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\output"

def test_codec(codec_name, target_mb=0.25):
    print(f"\n{'='*60}")
    print(f"Testing {codec_name} via Registry (as app does)")
    print(f"{'='*60}")
    
    target_bytes = int(target_mb * 1024 * 1024)
    output_file = os.path.join(output_dir, f"test_registry_{codec_name.replace(' ', '_')}.mp4")
    
    try:
        # Get estimator via registry (same as app)
        estimator_cls = get_video_estimator(codec_name, version='v5')
        estimator = estimator_cls()
        
        print(f"Estimator class: {estimator_cls}")
        print(f"Target: {target_mb} MB")
        
        # Estimate
        params = estimator.estimate(input_file, target_bytes, allow_downscale=False)
        print(f"Estimated params: {params}")
        
        # Execute
        def status_cb(msg):
            print(f"  [{codec_name}] {msg}")
        
        def progress_cb(p):
            if p == 0 or p >= 0.99:
                print(f"  [{codec_name}] Progress: {p*100:.0f}%")
        
        success = estimator.execute(
            input_file,
            output_file,
            target_bytes,
            status_callback=status_cb,
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
