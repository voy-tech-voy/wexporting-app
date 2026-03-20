"""
Target Size Module - Common utilities shared across estimators.
"""
import os
import sys
import subprocess
import threading
import tempfile
import ffmpeg
from typing import Dict


def get_ffmpeg_binary() -> str:
    """
    Get the configured FFmpeg binary path.
    
    Returns the path from FFMPEG_BINARY environment variable if set,
    otherwise falls back to 'ffmpeg' (system PATH).
    """
    return os.environ.get('FFMPEG_BINARY', 'ffmpeg')


def get_ffprobe_binary() -> str:
    """
    Get the configured FFprobe binary path.
    
    Derives ffprobe path from FFMPEG_BINARY by replacing 'ffmpeg' with 'ffprobe'.
    Falls back to 'ffprobe' (system PATH) if not found.
    """
    ffmpeg_path = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
    
    # If using custom ffmpeg, try to derive ffprobe path
    if ffmpeg_path != 'ffmpeg':
        # Replace 'ffmpeg' with 'ffprobe' in the path
        ffprobe_path = ffmpeg_path.replace('ffmpeg', 'ffprobe')
        if os.path.exists(ffprobe_path):
            return ffprobe_path
    
    # Fallback to system ffprobe
    return 'ffprobe'


def get_media_metadata(file_path: str) -> Dict:
    """Extract media metadata using ffprobe."""
    try:
        ffprobe_bin = get_ffprobe_binary()
        probe = ffmpeg.probe(file_path, cmd=ffprobe_bin)
        video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        audio = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
        fmt = probe['format']
        duration = float(fmt.get('duration', 0))
        if duration == 0 and video:
            duration = float(video.get('duration', 0))
        width = int(video.get('width', 0)) if video else 0
        height = int(video.get('height', 0)) if video else 0
        fps = 30.0
        if video and 'r_frame_rate' in video:
            fps_str = video['r_frame_rate']
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                if den > 0:
                    fps = num / den
            else:
                fps = float(fps_str)
        return {
            'duration': duration,
            'width': width,
            'height': height,
            'fps': fps,
            'has_audio': audio is not None
        }
    except:
        return {
            'duration': 0,
            'width': 0,
            'height': 0,
            'fps': 30,
            'has_audio': False
        }


def get_temp_filename(extension: str) -> str:
    """Generate a temporary filename with the given extension."""
    f = tempfile.NamedTemporaryFile(suffix=f'.{extension}', delete=False)
    f.close()
    return f.name


def run_ffmpeg_skill_standard(cmd: list, stop_check=None, log_target: str = '') -> int:
    """
    Run an FFmpeg command using the skill-standard Popen pattern.

    Features:
    - Silent execution (CREATE_NO_WINDOW on Windows, no console popup)
    - Asynchronous stderr drain thread to prevent deadlocks
    - stop_check polling on every stdout line for anytime cancellation
    - Returns process returncode, or -1 if cancelled via stop_check

    Args:
        cmd:         Full command list (e.g. [ffmpeg_bin, '-i', ...])
        stop_check:  Optional callable() -> bool; kill process if True
        log_target:  Optional label for debug prints (e.g. output path)

    Returns:
        returncode (0 = success, non-zero = ffmpeg error, -1 = cancelled)
    """
    # --- §3: Silent Popen setup (Win32) ---
    startupinfo = None
    creationflags = 0
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )

    # --- §4: Async stderr drain (prevents deadlock on Windows) ---
    stderr_output = []

    def _read_stderr(proc, out_list):
        try:
            for line in proc.stderr:
                out_list.append(line)
        except Exception:
            pass

    t = threading.Thread(target=_read_stderr, args=(process, stderr_output), daemon=True)
    t.start()

    # --- §5: Progress-stream loop + cancellation polling ---
    while True:
        if stop_check and stop_check():
            process.kill()
            t.join(timeout=1.0)
            return -1

        line = process.stdout.readline()
        if not line:
            break  # Process exited or stdout closed

    process.wait()
    t.join(timeout=1.0)

    if process.returncode != 0:
        err = ''.join(stderr_output)
        print(f"[run_ffmpeg_skill_standard] FFmpeg error (target={log_target}):\n{err}")

    return process.returncode
