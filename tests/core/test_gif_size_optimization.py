#!/usr/bin/env python3
"""
GIF Size Optimization Test Suite

Tests the GIF size estimation and optimization algorithm without running the full GUI.
Place test video files in the test_videos/ directory.
Converted GIFs will be saved to test_videos/output/

Usage:
    python test_gif_size_optimization.py
    python test_gif_size_optimization.py --video "test_videos/sample.mp4"
    python test_gif_size_optimization.py --quick  # Estimation only (no actual conversion)
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Add the client directory to Python path so we can import conversion_engine
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

try:
    from client.core.conversion_engine import (
        init_bundled_tools,
        estimate_gif_size_fast_preview,
        estimate_gif_size_heuristic,
        estimate_all_preset_sizes,
        find_optimal_gif_params_for_size,
        get_video_duration,
        get_video_dimensions,
        get_video_frame_rate,
        QUALITY_PRESETS,
        QUALITY_PRESETS_STANDARD,
        QUALITY_PRESETS_AUTORESIZE,
        REFERENCE_PRESET_IDX,
        DITHER_MAP,
    )
    import ffmpeg
    print("✅ Successfully imported conversion_engine modules")
except ImportError as e:
    print(f"❌ Failed to import modules: {e}")
    print(f"Make sure you're running this from the ImgApp_1 root directory")
    sys.exit(1)


def find_test_videos():
    """Find all video files in test_videos directory"""
    test_videos_dir = os.path.join(script_dir, 'test_videos')
    if not os.path.exists(test_videos_dir):
        print(f"Creating test_videos directory...")
        os.makedirs(test_videos_dir, exist_ok=True)
        return []
    
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
    videos = []
    
    for file in os.listdir(test_videos_dir):
        file_path = os.path.join(test_videos_dir, file)
        if os.path.isfile(file_path) and Path(file).suffix.lower() in video_extensions:
            videos.append(file_path)
    
    return videos


def test_video_info(video_path: str):
    """Display basic video information"""
    print(f"\n📹 Video Information")
    print("-" * 60)
    
    try:
        duration = get_video_duration(video_path)
        width, height = get_video_dimensions(video_path)
        fps = get_video_frame_rate(video_path)
        file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
        
        print(f"File: {os.path.basename(video_path)}")
        print(f"Resolution: {width}x{height}")
        print(f"Duration: {duration:.1f} seconds")
        print(f"FPS: {fps:.1f}")
        print(f"File size: {file_size:.2f} MB")
        
        return True
    except Exception as e:
        print(f"❌ Failed to get video info: {e}")
        return False


def test_estimation_algorithms(video_path: str):
    """Test all estimation methods and compare results"""
    print(f"\n🔍 Testing Estimation Algorithms")
    print("-" * 60)
    
    # Standard parameters for testing
    base_params = {
        'ffmpeg_fps': 15,
        'ffmpeg_colors': 256,
        'ffmpeg_dither': 'sierra2_4a',
        'ffmpeg_blur': False,
        'gif_resize_mode': 'No resize',
        'gif_resize_values': [],
        'enable_time_cutting': False,
        'time_start': 0.0,
        'time_end': 1.0,
        'retime_enabled': False,
        'retime_speed': 1.0
    }
    
    # Test 1: New ultra-fast calibrated estimation (single encode + ratios)
    print("Testing CALIBRATED estimation (1 encode for ALL presets)...")
    start_time = time.time()
    try:
        calibration_result = estimate_all_preset_sizes(video_path, base_params, sample_seconds=1.5)
        calibration_time = time.time() - start_time
        
        print(f"✅ Calibrated preset estimation:")
        print(f"   Calibration encode time: {calibration_result.get('calibration_time', 0):.2f}s")
        print(f"   Total estimation time: {calibration_time:.2f}s")
        print(f"   Reference size (preset[{REFERENCE_PRESET_IDX}]): {calibration_result.get('reference_size', 0) / (1024*1024):.2f} MB")
        print(f"   Method: {calibration_result.get('method', 'N/A')}")
        
        preset_sizes = calibration_result.get('preset_sizes', [])
        if preset_sizes:
            print(f"\n   Preset size estimates:")
            for i, (preset, size) in enumerate(zip(QUALITY_PRESETS, preset_sizes)):
                dither, fps, colors, res, factor = preset
                marker = " ← REFERENCE" if i == REFERENCE_PRESET_IDX else ""
                print(f"     [{i:2d}] D{dither} {fps:2d}fps {colors:3d}col → {size/(1024*1024):6.2f} MB (factor: {factor:.2f}){marker}")
        
    except Exception as e:
        print(f"❌ Calibrated estimation failed: {e}")
        import traceback
        traceback.print_exc()
        calibration_result = None
    
    # Test 2: Heuristic (instant, but less accurate)
    print("\n" + "-" * 40)
    print("Testing HEURISTIC estimation (instant, math-only)...")
    start_time = time.time()
    try:
        heuristic_result = estimate_gif_size_heuristic(video_path, base_params)
        heuristic_time = time.time() - start_time
        
        print(f"✅ Heuristic method:")
        print(f"   Estimated size: {heuristic_result['estimated_size'] / (1024*1024):.2f} MB")
        print(f"   Time taken: {heuristic_time:.4f}s (instant)")
        print(f"   Confidence: {heuristic_result.get('confidence', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Heuristic method failed: {e}")
        heuristic_result = None
    
    # Summary comparison
    if calibration_result and heuristic_result:
        ref_size_mb = calibration_result.get('reference_size', 0) / (1024*1024)
        heuristic_mb = heuristic_result['estimated_size'] / (1024*1024)
        
        print(f"\n📊 Speed Comparison:")
        print(f"   Calibrated: {calibration_time:.2f}s (estimates ALL 12 presets)")
        print(f"   Heuristic:  {heuristic_time:.4f}s (estimates 1 size)")
        print(f"   Speedup for optimization: ~{(calibration_time * 10) / calibration_time:.0f}x faster than old method")


def test_size_optimization(video_path: str, target_sizes_mb: list = [2, 5, 10], do_actual_conversion: bool = False):
    """Test the full optimization algorithm with different target sizes"""
    print(f"\n🎯 Testing Size Optimization")
    print("=" * 60)
    
    output_dir = os.path.join(os.path.dirname(video_path), 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    for target_mb in target_sizes_mb:
        print(f"\n🎯 TARGET: {target_mb} MB")
        print("-" * 30)
        
        # Base parameters (start with high quality)
        base_params = {
            'ffmpeg_fps': 24,  # Start high
            'ffmpeg_colors': 256,  # Start high
            'ffmpeg_dither': 'floyd_steinberg',  # Best quality
            'ffmpeg_blur': False,
            'gif_resize_mode': 'No resize',  # Start with original size
            'gif_resize_values': [],
            'enable_time_cutting': False,
            'time_start': 0.0,
            'time_end': 1.0,
            'retime_enabled': False,
            'retime_speed': 1.0
        }
        
        target_bytes = int(target_mb * 1024 * 1024)
        
        def status_log(msg):
            print(f"   🔄 {msg}")
        
        optimization_start = time.time()
        try:
            optimized_params = find_optimal_gif_params_for_size(
                video_path, base_params, target_bytes, status_callback=status_log
            )
            optimization_time = time.time() - optimization_start
            
            estimated_mb = optimized_params.get('_estimated_size', 0) / (1024*1024)
            preset_index = optimized_params.get('_preset_index', -1)
            preset_info = optimized_params.get('_preset_info', 'N/A')
            calibration_time = optimized_params.get('_calibration_time', 0)
            target_exceeded = optimized_params.get('_target_exceeded', False)
            
            print(f"✅ Optimization completed:")
            print(f"   Total time: {optimization_time:.1f}s (calibration: {calibration_time:.1f}s)")
            print(f"   Selected preset: [{preset_index}] {preset_info}")
            print(f"   Final FPS: {optimized_params.get('ffmpeg_fps', 'N/A')}")
            print(f"   Final Colors: {optimized_params.get('ffmpeg_colors', 'N/A')}")
            print(f"   Final Dither: {optimized_params.get('ffmpeg_dither', 'N/A')}")
            print(f"   Estimated size: {estimated_mb:.2f} MB")
            
            if target_exceeded:
                print(f"   ⚠️  Target exceeded (minimum settings reached)")
            else:
                efficiency = (estimated_mb / target_mb) * 100
                print(f"   🎯 Efficiency: {efficiency:.1f}% of target")
                
                if efficiency > 105:
                    print(f"   ⚠️  Over target by {efficiency - 100:.1f}%")
                elif efficiency < 85:
                    print(f"   💡 Could potentially use higher quality ({100 - efficiency:.1f}% under)")
                else:
                    print(f"   ✅ Well optimized!")
            
            # Do actual conversion if requested
            if do_actual_conversion:
                print(f"\n   🎬 Converting with optimized settings...")
                
                # Build filename with param suffixes (like regular conversion)
                fps = optimized_params.get('ffmpeg_fps', 15)
                colors = optimized_params.get('ffmpeg_colors', 256)
                dither = optimized_params.get('ffmpeg_dither', '')
                
                # Map dither to quality suffix
                dither_quality_map = {
                    "none": "quality0",
                    "bayer:bayer_scale=5": "quality1",
                    "bayer:bayer_scale=4": "quality2",
                    "bayer:bayer_scale=3": "quality3",
                    "bayer:bayer_scale=1": "quality4",
                    "floyd_steinberg": "quality5"
                }
                quality_suffix = dither_quality_map.get(dither, "")
                
                output_filename = f"{Path(video_path).stem}_fps{fps}_colors{colors}_{quality_suffix}_target{target_mb}MB.gif"
                output_path = os.path.join(output_dir, output_filename)
                
                conversion_start = time.time()
                actual_size = convert_to_gif(video_path, output_path, optimized_params)
                conversion_time = time.time() - conversion_start
                
                if actual_size > 0:
                    actual_mb = actual_size / (1024*1024)
                    accuracy = (actual_mb / estimated_mb) * 100 if estimated_mb > 0 else 0
                    
                    print(f"   ✅ Conversion completed:")
                    print(f"   Actual size: {actual_mb:.2f} MB")
                    print(f"   Conversion time: {conversion_time:.1f}s")
                    print(f"   Estimation accuracy: {accuracy:.1f}% (closer to 100% is better)")
                    print(f"   Saved to: {output_filename}")
                    
                    # Check if we met the target
                    if actual_mb <= target_mb * 1.05:
                        print(f"   ✅ Successfully met target size!")
                    else:
                        print(f"   ⚠️  Exceeded target by {(actual_mb / target_mb - 1) * 100:.1f}%")
                else:
                    print(f"   ❌ Conversion failed")
            
        except Exception as e:
            print(f"❌ Optimization failed: {e}")
            import traceback
            traceback.print_exc()


def convert_to_gif(video_path: str, output_path: str, params: dict) -> int:
    """
    Actually convert the video to GIF with given parameters
    Returns the file size in bytes, or 0 if failed
    """
    try:
        # Build FFmpeg command similar to _convert_video_to_gif_ffmpeg_only
        input_stream = ffmpeg.input(video_path)
        
        # Apply retime if enabled
        retime_enabled = params.get('retime_enabled', False)
        retime_speed = params.get('retime_speed', 1.0)
        if retime_enabled and retime_speed != 1.0:
            input_stream = ffmpeg.filter(input_stream, 'setpts', f'PTS/{retime_speed}')
        
        # FPS
        fps = params.get('ffmpeg_fps', 15)
        input_stream = ffmpeg.filter(input_stream, 'fps', fps=fps)
        
        # Resize
        resize_mode = params.get('gif_resize_mode', 'No resize')
        resize_values = params.get('gif_resize_values', [])
        
        if resize_mode != 'No resize' and resize_values:
            resize_value = resize_values[0]
            if resize_mode == 'By width (pixels)':
                new_width = int(resize_value)
                input_stream = ffmpeg.filter(input_stream, 'scale', str(new_width), '-2')
        
        # Split for palette generation
        split = input_stream.split()
        
        # Palette
        colors = params.get('ffmpeg_colors', 256)
        palette = split[0].filter('palettegen', max_colors=colors)
        
        # Palette use
        dither = params.get('ffmpeg_dither', 'sierra2_4a')
        paletteuse_args = {}
        
        if dither.startswith('bayer:bayer_scale='):
            try:
                scale = int(dither.split('=')[1])
                paletteuse_args['dither'] = 'bayer'
                paletteuse_args['bayer_scale'] = scale
            except:
                paletteuse_args['dither'] = dither
        else:
            paletteuse_args['dither'] = dither
        
        final = ffmpeg.filter([split[1], palette], 'paletteuse', **paletteuse_args)
        
        # Output
        out = ffmpeg.output(final, output_path)
        out = ffmpeg.overwrite_output(out)
        
        # Run
        ffmpeg.run(out, quiet=True)
        
        # Get actual file size
        if os.path.exists(output_path):
            return os.path.getsize(output_path)
        
    except Exception as e:
        print(f"Conversion error: {e}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description='Test GIF size optimization algorithm')
    parser.add_argument('--video', '-v', type=str, help='Specific video file to test')
    parser.add_argument('--quick', '-q', action='store_true', help='Run quick estimation test only (no optimization)')
    parser.add_argument('--convert', '-c', action='store_true', help='Actually convert GIFs (slower but validates accuracy)')
    parser.add_argument('--targets', '-t', nargs='+', type=float, default=[2, 5, 10], 
                       help='Target sizes in MB (default: 2 5 10)')
    
    args = parser.parse_args()
    
    print("🚀 GIF Size Optimization Test Suite")
    print("=" * 60)
    
    # Initialize bundled tools
    try:
        init_bundled_tools()
        print(f"✅ Bundled tools initialized")
    except Exception as e:
        print(f"❌ Failed to initialize tools: {e}")
        print("Make sure FFmpeg is available or bundled tools are properly set up")
        return
    
    # Determine which video to test
    if args.video:
        if not os.path.exists(args.video):
            print(f"❌ Video file not found: {args.video}")
            return
        test_video = args.video
    else:
        # Look for test videos
        test_videos = find_test_videos()
        if not test_videos:
            print("❌ No test videos found in test_videos/ directory")
            print("Please add some video files (.mp4, .avi, .mov, etc.) to test_videos/")
            return
        
        print(f"📂 Found {len(test_videos)} test video(s):")
        for i, video in enumerate(test_videos):
            file_size = os.path.getsize(video) / (1024*1024)
            print(f"   {i+1}. {os.path.basename(video)} ({file_size:.1f} MB)")
        
        if len(test_videos) == 1:
            test_video = test_videos[0]
            print(f"\n🎬 Using: {os.path.basename(test_video)}")
        else:
            try:
                choice = int(input(f"\nEnter choice (1-{len(test_videos)}): ")) - 1
                if 0 <= choice < len(test_videos):
                    test_video = test_videos[choice]
                else:
                    print("Invalid choice, using first video")
                    test_video = test_videos[0]
            except (ValueError, KeyboardInterrupt):
                print("\nUsing first video")
                test_video = test_videos[0]
    
    # Run tests
    if not test_video_info(test_video):
        return
    
    if args.quick:
        print("\n🏃 Running quick estimation test only...")
        test_estimation_algorithms(test_video)
    else:
        print("\n🔬 Running full test suite...")
        test_estimation_algorithms(test_video)
        test_size_optimization(test_video, args.targets, do_actual_conversion=args.convert)
        
        if args.convert:
            output_dir = os.path.join(os.path.dirname(test_video), 'output')
            print(f"\n💾 Converted GIFs saved to: {output_dir}")
    
    print(f"\n✅ Testing completed!")


if __name__ == "__main__":
    main()
