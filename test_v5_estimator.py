"""
Deep diagnostic: Why does v5 estimator fail?
Tests multiple approaches to isolate the ffmpeg-python command construction issue.
"""
import sys, os
sys.path.append(os.getcwd())

import subprocess
import ffmpeg
from client.core.target_size._common import get_ffmpeg_binary

INPUT = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\test_video.mov"
OUTPUT_DIR = r"C:\Users\V\Pictures\IMAGE_CONVERT_APP_testing\output"
FFMPEG_BIN = get_ffmpeg_binary()

def run_test(name, cmd):
    """Run a test command and print the result."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"CMD:  {' '.join(cmd)}")
    print(f"{'='*60}")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    )
    stdout, stderr = process.communicate(timeout=30)
    stderr_text = stderr.decode('utf-8', errors='ignore')
    
    output_file = None
    for arg in cmd:
        if arg.endswith('.mp4'):
            output_file = arg
            break
    
    if process.returncode == 0:
        if output_file and os.path.exists(output_file):
            size_kb = os.path.getsize(output_file) / 1024
            print(f"✅ SUCCESS - Output: {size_kb:.1f} KB")
        else:
            print(f"✅ SUCCESS (no output file expected)")
    else:
        # Extract the last meaningful error line
        error_lines = [l for l in stderr_text.strip().split('\n') if l.strip()]
        last_errors = error_lines[-3:] if len(error_lines) >= 3 else error_lines
        print(f"❌ FAILED (code {process.returncode})")
        for line in last_errors:
            print(f"   ERR: {line.strip()}")
    
    return process.returncode == 0


# ================================================================
# PHASE 1: Probe the test video streams
# ================================================================
print("\n" + "="*60)
print("PHASE 1: VIDEO PROBE")
print("="*60)

probe = ffmpeg.probe(INPUT, cmd=FFMPEG_BIN.replace('ffmpeg', 'ffprobe'))
for stream in probe['streams']:
    codec_type = stream.get('codec_type', '?')
    codec_name = stream.get('codec_name', '?')
    index = stream.get('index', '?')
    print(f"  Stream #{index}: {codec_type} ({codec_name})")

# ================================================================
# PHASE 2: Raw FFmpeg commands (no ffmpeg-python)
# ================================================================
print("\n" + "="*60)
print("PHASE 2: RAW FFMPEG COMMANDS")
print("="*60)

# Test 2a: Basic h264_nvenc with audio
out_2a = os.path.join(OUTPUT_DIR, "test_2a_raw_basic.mp4")
run_test("Raw: h264_nvenc + AAC audio", [
    FFMPEG_BIN, '-i', INPUT,
    '-c:v', 'h264_nvenc', '-b:v', '1865k',
    '-c:a', 'aac', '-b:a', '64k',
    out_2a, '-y'
])

# Test 2b: Raw with -progress pipe:1 (like v5 tries)
out_2b = os.path.join(OUTPUT_DIR, "test_2b_raw_progress.mp4")
run_test("Raw: h264_nvenc + AAC + -progress pipe:1", [
    FFMPEG_BIN, '-i', INPUT,
    '-c:v', 'h264_nvenc', '-b:v', '1865k',
    '-c:a', 'aac', '-b:a', '64k',
    '-progress', 'pipe:1', '-nostats',
    out_2b, '-y'
])

# Test 2c: Raw with maxrate/bufsize
out_2c = os.path.join(OUTPUT_DIR, "test_2c_raw_maxrate.mp4")
run_test("Raw: h264_nvenc + maxrate + bufsize + audio", [
    FFMPEG_BIN, '-i', INPUT,
    '-c:v', 'h264_nvenc', '-b:v', '1865k', '-maxrate:v', '2797k', '-bufsize:v', '3730k',
    '-c:a', 'aac', '-b:a', '64k',
    out_2c, '-y'
])

# Test 2d: Raw - explicitly map only video + audio (skip data stream)
out_2d = os.path.join(OUTPUT_DIR, "test_2d_raw_mapped.mp4")
run_test("Raw: h264_nvenc + explicit stream mapping (skip data)", [
    FFMPEG_BIN, '-i', INPUT,
    '-map', '0:v:0', '-map', '0:a:0',
    '-c:v', 'h264_nvenc', '-b:v', '1865k',
    '-c:a', 'aac', '-b:a', '64k',
    out_2d, '-y'
])


# ================================================================
# PHASE 3: ffmpeg-python command construction tests
# ================================================================
print("\n" + "="*60)
print("PHASE 3: FFMPEG-PYTHON COMMAND CONSTRUCTION")
print("="*60)

# Test 3a: v5's current approach (the broken one)
out_3a = os.path.join(OUTPUT_DIR, "test_3a_v5_approach.mp4")
encode_args_3a = {
    'c:v': 'h264_nvenc',
    'b:v': '1865k',
    'maxrate:v': '2797k',
    'bufsize:v': '3730k',
    'c:a': 'aac',
    'b:a': '64k',
    'progress': 'pipe:1',
    'nostats': None,
}
stream_3a = ffmpeg.input(INPUT)
stream_3a = ffmpeg.output(stream_3a, out_3a, **encode_args_3a)
stream_3a = ffmpeg.overwrite_output(stream_3a)
cmd_3a = list(ffmpeg.compile(stream_3a))
cmd_3a[0] = FFMPEG_BIN
print(f"\n  [3a] ffmpeg-python generated command:")
print(f"       {' '.join(cmd_3a)}")
run_test("ffmpeg-python: v5 approach (c:v, c:a, progress in args)", cmd_3a)

# Test 3b: Using vcodec/acodec INSTEAD of c:v/c:a
out_3b = os.path.join(OUTPUT_DIR, "test_3b_vcodec.mp4")
encode_args_3b = {
    'vcodec': 'h264_nvenc',
    'b:v': '1865k',
    'maxrate': '2797k',
    'bufsize': '3730k',
    'acodec': 'aac',
    'b:a': '64k',
    'progress': 'pipe:1',
    'nostats': None,
}
stream_3b = ffmpeg.input(INPUT)
stream_3b = ffmpeg.output(stream_3b, out_3b, **encode_args_3b)
stream_3b = ffmpeg.overwrite_output(stream_3b)
cmd_3b = list(ffmpeg.compile(stream_3b))
cmd_3b[0] = FFMPEG_BIN
print(f"\n  [3b] ffmpeg-python generated command:")
print(f"       {' '.join(cmd_3b)}")
run_test("ffmpeg-python: vcodec/acodec (like v4)", cmd_3b)

# Test 3c: Using chained .output() instead of ffmpeg.output()
out_3c = os.path.join(OUTPUT_DIR, "test_3c_chained.mp4")
encode_args_3c = {
    'vcodec': 'h264_nvenc',
    'b:v': '1865k',
    'maxrate': '2797k',
    'bufsize': '3730k',
    'acodec': 'aac',
    'b:a': '64k',
}
stream_3c = ffmpeg.input(INPUT).output(out_3c, **encode_args_3c)
stream_3c = ffmpeg.overwrite_output(stream_3c)
cmd_3c = list(ffmpeg.compile(stream_3c))
# Insert progress/nostats AFTER compile (like v4 does)
cmd_3c.insert(1, '-progress')
cmd_3c.insert(2, 'pipe:1')
cmd_3c.insert(3, '-nostats')
cmd_3c[0] = FFMPEG_BIN
print(f"\n  [3c] ffmpeg-python generated command (v4-style post-compile insert):")
print(f"       {' '.join(cmd_3c)}")
run_test("ffmpeg-python: chained + post-compile progress insert (v4 style)", cmd_3c)

# Test 3d: Explicit stream selection with ffmpeg-python
out_3d = os.path.join(OUTPUT_DIR, "test_3d_explicit_streams.mp4")
encode_args_3d = {
    'vcodec': 'h264_nvenc',
    'b:v': '1865k',
    'acodec': 'aac',
    'b:a': '64k',
}
inp = ffmpeg.input(INPUT)
stream_3d = ffmpeg.output(inp.video, inp.audio, out_3d, **encode_args_3d)
stream_3d = ffmpeg.overwrite_output(stream_3d)
cmd_3d = list(ffmpeg.compile(stream_3d))
cmd_3d[0] = FFMPEG_BIN
print(f"\n  [3d] ffmpeg-python generated command (explicit video+audio streams):")
print(f"       {' '.join(cmd_3d)}")
run_test("ffmpeg-python: explicit video+audio stream selection", cmd_3d)

# Test 3e: No progress in args at all, simplest possible
out_3e = os.path.join(OUTPUT_DIR, "test_3e_simplest.mp4")
encode_args_3e = {
    'vcodec': 'h264_nvenc',
    'b:v': '1865k',
    'acodec': 'aac',
    'b:a': '64k',
}
stream_3e = ffmpeg.input(INPUT)
stream_3e = ffmpeg.output(stream_3e, out_3e, **encode_args_3e)
stream_3e = ffmpeg.overwrite_output(stream_3e)
cmd_3e = list(ffmpeg.compile(stream_3e))
cmd_3e[0] = FFMPEG_BIN
print(f"\n  [3e] ffmpeg-python generated command (simplest, no progress):")
print(f"       {' '.join(cmd_3e)}")
run_test("ffmpeg-python: simplest possible (no progress, no maxrate)", cmd_3e)


# ================================================================
# SUMMARY
# ================================================================
print("\n" + "="*60)
print("DONE - Review results above to identify root cause")
print("="*60)
