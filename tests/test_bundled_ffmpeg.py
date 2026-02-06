import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client.core.tool_manager import init_bundled_tools
import subprocess

def test_bundled_ffmpeg_extraction_and_usage():
    # Ensure extraction and env setup
    cache_dir = init_bundled_tools()
    ffmpeg_path = os.environ.get('FFMPEG_BINARY')
    print(f"Bundled ffmpeg path: {ffmpeg_path}")
    assert ffmpeg_path and os.path.exists(ffmpeg_path), "Bundled ffmpeg was not extracted or not found!"
    # Try running ffmpeg
    result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True, timeout=5)
    print("FFmpeg output:\n" + result.stdout)
    assert "ffmpeg version" in result.stdout.lower(), "Bundled ffmpeg did not run correctly!"

if __name__ == "__main__":
    test_bundled_ffmpeg_extraction_and_usage()
