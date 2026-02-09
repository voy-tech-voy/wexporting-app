import argparse
import subprocess
import sys
import os
import json
import math
import datetime

def generate_sprite(args):
    """
    Generates the sprite image using FFmpeg.
    """
    input_path = args.input
    # Output should be {output_prefix}.jpg, not {output_prefix}_videothumbnails.jpg
    output_image_path = f"{args.output_prefix}.jpg"
    
    # Calculate interval
    # We want exactly rows * cols frames.
    # FFmpeg 'fps' filter outputs a frame every x seconds.
    # Interval = Duration / Total Frames
    total_frames = args.rows * args.cols
    interval = args.duration / total_frames
    
    # FFmpeg command construction
    # fps=1/interval: extract one frame every 'interval' seconds
    # scale=width:-1: resize width, keep aspect ratio
    # tile=ColsxRows: stitch into grid
    
    # We use a slightly higher framerate to ensure we capture enough frames, 
    # but strictly limiting it with -vframes might be risky if we miss one.
    # The 'fps' filter is generally accurate. 
    # Since we want a fixed grid, 'tile' will buffer frames.
    
    filter_complex = f"fps=1/{interval},scale={args.width}:-1,tile={args.cols}x{args.rows}"
    
    cmd = [
        args.ffmpeg,
        '-y',
        '-i', input_path,
        '-vf', filter_complex,
        '-frames:v', '1', # Output only one image (the tiled sprite)
        '-q:v', str(2),   # High quality jpeg (2-31 range in ffmpeg usually, or 1-100 dependent on encoder)
                          # mjpeg q:v is 2-31 where 2 is best. Let's use 5 for good balance.
        '-map_metadata', '-1'
    ]
    
    cmd.append(output_image_path)
    
    # Run FFmpeg
    print(f"Executing: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
        print(f"Sprite generated: {output_image_path}")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg failed: {e}", file=sys.stderr)
        sys.exit(1)

    return output_image_path, interval

def generate_metadata(args, interval):
    """
    Generates the VTT or JSON metadata file.
    """
    # Use same base as sprite image
    output_base = args.output_prefix
    sprite_filename = f"{args.output_prefix}.jpg"
    
    grid_w = args.width
    # We need to know the height of the tiles to write accurate coordinates.
    # However, we don't know the aspect ratio until we run ffmpeg or probe.
    # For now, let's assume 16:9 aspect ratio for the calculation if not provided?
    # Actually, we can just assume the standard generic ratio or maybe we should query it?
    # The prompt says "Generate a .vtt file mapping the timestamps to the coordinates (#xywh=x,y,w,h)".
    # If we don't know h, we can't write it. 
    # BUT! 'scale=width:-1' implies valid height.
    # To be precise, we should run ffprobe first.
    
    # Let's run a quick probe to get video dimensions, so we can calculate tile height.
    # We use a helper function to get W and H.
    vid_w, vid_h = run_probe_dims(args.ffmpeg.replace('ffmpeg', 'ffprobe'), args.input)
    
    # Calculated tile height based on resize
    # New Width = args.width
    # Scale factor = args.width / vid_w
    # New Height = vid_h * Scale factor (rounded to even usually, but ffmpeg defaults)
    scale_factor = args.width / vid_w
    tile_h = int(vid_h * scale_factor)
    
    total_frames = args.rows * args.cols
    data = []
    
    # Generate timestamp and coordinate data
    for i in range(total_frames):
        start_time = i * interval
        end_time = (i + 1) * interval
        
        # Grid Usage: Left to Right, Top to Bottom
        col_idx = i % args.cols
        row_idx = i // args.cols
        
        x = col_idx * args.width
        y = row_idx * tile_h
        
        entry = {
            "start": start_time,
            "end": end_time,
            "x": x,
            "y": y,
            "w": args.width,
            "h": tile_h
        }
        data.append(entry)

    if args.format == 'json':
        output_file = f"{output_base}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"JSON generated: {output_file}")
        
    elif args.format == 'vtt':
        output_file = f"{output_base}.vtt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            for entry in data:
                start_s = format_timestamp(entry['start'])
                end_s = format_timestamp(entry['end'])
                # Format: 00:00:00.000 --> 00:00:05.000
                # URL fragment: #xywh=x,y,w,h
                f.write(f"{start_s} --> {end_s}\n")
                f.write(f"{os.path.basename(sprite_filename)}#xywh={entry['x']},{entry['y']},{entry['w']},{entry['h']}\n\n")
        print(f"VTT generated: {output_file}")

def format_timestamp(seconds):
    """Formats seconds into HH:MM:SS.mmm"""
    td = datetime.timedelta(seconds=seconds)
    # total_seconds() might include microseconds
    # We need to manually format to ensure 3 digit ms
    total_seconds = int(seconds)
    millis = int((seconds - total_seconds) * 1000)
    
    hours = total_frames = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"

def run_probe_dims(ffprobe_exe, input_path):
    """Returns (width, height) of the video."""
    # Assuming ffprobe is in the same folder or path if 'ffmpeg' is passed.
    # If full path to ffmpeg is given, we try to deduce ffprobe path.
    if 'ffmpeg' in ffprobe_exe.lower():
         # simplistic replacement
         pass 

    cmd = [
        ffprobe_exe, 
        '-v', 'error', 
        '-select_streams', 'v:0', 
        '-show_entries', 'stream=width,height', 
        '-of', 'csv=s=x:p=0', 
        input_path
    ]
    
    try:
        output = subprocess.check_output(cmd).decode('utf-8').strip()
        parts = output.split('x')
        return int(parts[0]), int(parts[1])
    except Exception:
        # Fallback if probe fails, though it shouldn't
        print("Warning: Could not probe video dimensions. Using 16:9 approximation.")
        return 1920, 1080

def main():
    # --- ARGUMENT CLEANING ---
    # Remove engine-injected flags that break argparse
    # The engine injects '-progress', 'pipe:1', '-nostats' when it detects ffmpeg
    cleaned_args = []
    skip_next = False
    
    for i, arg in enumerate(sys.argv[1:]):
        if skip_next:
            skip_next = False
            continue
        if arg in ['-progress', '-nostats']:
            # Skip this arg, and if it's -progress, skip the next arg too (pipe:1)
            if arg == '-progress' and i + 1 < len(sys.argv[1:]) and sys.argv[i + 2] == 'pipe:1':
                skip_next = True
            continue
        cleaned_args.append(arg)
    
    parser = argparse.ArgumentParser(description="Video Thumbnail Sprite Generator")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output_prefix", required=True, help="Output file prefix (without extension)")
    parser.add_argument("--rows", type=int, default=5, help="Number of rows")
    parser.add_argument("--cols", type=int, default=5, help="Number of columns")
    parser.add_argument("--width", type=int, default=160, help="Thumbnail width")
    parser.add_argument("--duration", type=float, required=True, help="Video duration in seconds")
    parser.add_argument("--format", choices=['vtt', 'json'], default='vtt', help="Metadata format")
    parser.add_argument("--ffmpeg", required=True, help="Path to ffmpeg executable")
    
    args = parser.parse_args(cleaned_args)
    
    # 1. Generate Sprite
    _, interval = generate_sprite(args)
    
    # 2. Generate Metadata
    generate_metadata(args, interval)

if __name__ == "__main__":
    main()
