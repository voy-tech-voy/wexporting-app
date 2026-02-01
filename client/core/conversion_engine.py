"""
Core conversion engine for graphics files
Integrates FFmpeg operations with bundled tools
"""


import os
import sys
import subprocess
import hashlib
import json
import time
import tempfile

from client.version import APP_NAME

# Set the FFmpeg executable path BEFORE importing ffmpeg
bundled_tools_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'tools')

# Default cache path (lazy init). We keep PATH untouched until tools are explicitly initialized.
_USER_BIN_CACHE = ""

def _ensure_bundled_tools_unpacked() -> str:
    """Ensure bundled tools are available as distinct files.

    For onefile PyInstaller builds, PyInstaller extracts bundled files into sys._MEIPASS.
    This helper copies them into a persistent cache directory (per-user) so we have stable file paths
    and avoid re-extraction overhead. Returns the path to the cache directory.
    """
    # Choose platform-specific cache dir
    try:
        if os.name == 'nt':
            cache_root = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA') or os.path.expanduser('~')
        else:
            cache_root = os.getenv('XDG_CACHE_HOME') or os.path.expanduser('~/.cache')
        app_cache_dir = os.path.join(cache_root, APP_NAME, 'bin')
        os.makedirs(app_cache_dir, exist_ok=True)

        # If running frozen, copy from sys._MEIPASS/bundled_tools into cache
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            src_tools = os.path.join(sys._MEIPASS, 'tools')

            def _sha256_of_file(path: str) -> str:
                h = hashlib.sha256()
                with open(path, 'rb') as fh:
                    for chunk in iter(lambda: fh.read(8192), b''):
                        h.update(chunk)
                return h.hexdigest()

            def _read_checksums_from_dir(d: str) -> dict:
                # look for JSON or .sha256 files
                possible_names = ['checksums.json', 'bundled_tools_checksums.json', 'checksums.sha256']
                for fname in possible_names:
                    fpath = os.path.join(d, fname)
                    if os.path.exists(fpath):
                        try:
                            if fname.endswith('.json'):
                                with open(fpath, 'r', encoding='utf-8') as fh:
                                    data = json.load(fh)
                                    if isinstance(data, dict):
                                        return {k: str(v) for k, v in data.items()}
                            else:
                                checks = {}
                                with open(fpath, 'r', encoding='utf-8') as fh:
                                    for line in fh:
                                        parts = line.strip().split()
                                        if len(parts) >= 2:
                                            h = parts[0]
                                            name = parts[-1]
                                            checks[name] = h
                                return checks
                        except Exception:
                            pass
                return {}

            expected_checksums = _read_checksums_from_dir(src_tools) if os.path.isdir(src_tools) else {}

            if os.path.isdir(src_tools):
                for name in os.listdir(src_tools):
                    src = os.path.join(src_tools, name)
                    dst = os.path.join(app_cache_dir, name)
                    try:
                        # Only copy if not present or sizes differ
                        if (not os.path.exists(dst)) or (os.path.getsize(src) != os.path.getsize(dst)):
                            # write to temporary then move to be atomic
                            tmp = dst + '.tmp'
                            with open(src, 'rb') as sf, open(tmp, 'wb') as df:
                                df.write(sf.read())
                            try:
                                os.replace(tmp, dst)
                            except Exception:
                                # fallback
                                try:
                                    os.remove(tmp)
                                except Exception:
                                    pass
                                import shutil
                                shutil.copy2(src, dst)
                            # ensure executable on unix
                            if os.name != 'nt':
                                try:
                                    os.chmod(dst, 0o755)
                                except Exception:
                                    pass

                            # verify checksum if expected available
                            try:
                                expected = expected_checksums.get(name)
                                if expected:
                                    actual = _sha256_of_file(dst)
                                    if actual.lower() != expected.lower():
                                        # Attempt second copy and re-verify
                                        try:
                                            os.remove(dst)
                                        except Exception:
                                            pass
                                        tmp2 = dst + '.tmp2'
                                        with open(src, 'rb') as sf, open(tmp2, 'wb') as df:
                                            df.write(sf.read())
                                        try:
                                            os.replace(tmp2, dst)
                                        except Exception:
                                            try:
                                                os.remove(tmp2)
                                            except Exception:
                                                pass
                                        if os.name != 'nt':
                                            try:
                                                os.chmod(dst, 0o755)
                                            except Exception:
                                                pass
                                        try:
                                            actual2 = _sha256_of_file(dst)
                                            if actual2.lower() != expected.lower():
                                                # checksum mismatch; remove broken file
                                                try:
                                                    os.remove(dst)
                                                except Exception:
                                                    pass
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                    except Exception:
                        # ignore single-file copy errors (we'll fallback to sys._MEIPASS path)
                        pass

        # If a checksums.json was not already created in the cache, generate one (frozen runs)
        try:
            src_tools = os.path.join(sys._MEIPASS, 'tools') if (getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')) else None
            checks_dst = os.path.join(app_cache_dir, 'checksums.json')
            if src_tools and os.path.isdir(src_tools) and not os.path.exists(checks_dst):
                checks = {}
                for name in os.listdir(src_tools):
                    # skip checksum files themselves
                    if name.lower().endswith(('.json', '.sha256')):
                        continue
                    p_in_cache = os.path.join(app_cache_dir, name)
                    s = None
                    try:
                        if os.path.exists(p_in_cache):
                            s = hashlib.sha256(open(p_in_cache, 'rb').read()).hexdigest()
                        else:
                            srcp = os.path.join(src_tools, name)
                            if os.path.exists(srcp):
                                s = hashlib.sha256(open(srcp, 'rb').read()).hexdigest()
                    except Exception:
                        s = None
                    if s:
                        checks[name] = s
                if checks:
                    try:
                        with open(checks_dst, 'w', encoding='utf-8') as fh:
                            json.dump(checks, fh)
                    except Exception:
                        pass
        except Exception:
            pass

        return app_cache_dir
    except Exception:
        # Fallback to temp dir
        return tempfile.gettempdir()

# Lazy initialization of bundled tools (used by onefile builds). Call once after login.
_BUNDLED_TOOLS_INITIALIZED = False

def init_bundled_tools() -> str:
    """Initialize bundled tools (unpack and set PATH/FFMPEG envs). Safe to call multiple times."""
    global _USER_BIN_CACHE, _BUNDLED_TOOLS_INITIALIZED
    if _BUNDLED_TOOLS_INITIALIZED and _USER_BIN_CACHE:
        return _USER_BIN_CACHE

    _USER_BIN_CACHE = _ensure_bundled_tools_unpacked()

    # For frozen onefile builds, add the persistent user cache to PATH so subprocesses can find binaries
    if getattr(sys, 'frozen', False) and os.path.isdir(_USER_BIN_CACHE):
        os.environ['PATH'] = _USER_BIN_CACHE + os.pathsep + os.environ.get('PATH', '')
    elif not getattr(sys, 'frozen', False):
        # Dev runs: keep bundled_tools on PATH for convenience
        os.environ['PATH'] = bundled_tools_dir + os.pathsep + os.environ.get('PATH', '')

    # Set FFMPEG_BINARY environment variable to point to correct ffmpeg binary when available
    ffmpeg_candidate = None
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        ffmpeg_candidate = os.path.join(sys._MEIPASS, 'tools', 'ffmpeg.exe')
        if not os.path.exists(ffmpeg_candidate):
            ffmpeg_candidate = os.path.join(_USER_BIN_CACHE, 'ffmpeg.exe')
    else:
        ffmpeg_candidate = os.path.join(bundled_tools_dir, 'ffmpeg.exe')

    if ffmpeg_candidate and os.path.exists(ffmpeg_candidate):
        os.environ['FFMPEG_BINARY'] = ffmpeg_candidate

    # Set ffprobe as well (used by ffmpeg.probe())
    ffprobe_candidate = None
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        ffprobe_candidate = os.path.join(sys._MEIPASS, 'tools', 'ffprobe.exe')
        if not os.path.exists(ffprobe_candidate):
            ffprobe_candidate = os.path.join(_USER_BIN_CACHE, 'ffprobe.exe')
    else:
        ffprobe_candidate = os.path.join(bundled_tools_dir, 'ffprobe.exe')

    if ffprobe_candidate and os.path.exists(ffprobe_candidate):
        os.environ['FFPROBE_BINARY'] = ffprobe_candidate

    _BUNDLED_TOOLS_INITIALIZED = True
    return _USER_BIN_CACHE

import ffmpeg
from pathlib import Path
from typing import List, Dict, Optional, Callable
from PyQt6.QtCore import QThread, pyqtSignal
import tempfile
from client.core.presets import (
    SOCIAL_PLATFORM_PRESETS,
    RATIO_MAPS,
    BG_STYLE_BLURRED,
    BG_STYLE_FILL_ZOOM,
    BG_STYLE_BLACK_BARS
)

# Hide subprocess consoles on Windows without altering ffmpeg-python signatures
if os.name == 'nt':
    _orig_popen = subprocess.Popen

    def _popen_no_console(*args, **kwargs):
        """Wrap subprocess.Popen to suppress console windows on Windows"""
        creationflags = kwargs.get('creationflags', 0) | subprocess.CREATE_NO_WINDOW
        kwargs['creationflags'] = creationflags

        startupinfo = kwargs.get('startupinfo')
        if startupinfo is None:
            startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs['startupinfo'] = startupinfo

        return _orig_popen(*args, **kwargs)

    subprocess.Popen = _popen_no_console


def get_bundled_tool_path(tool_name: str) -> str:
    """
    Locate a bundled tool executable, preferring a persistent per-user cache for onefile builds.

    Order of resolution:
    1. Persistent user cache (created by _ensure_bundled_tools_unpacked) when available
    2. PyInstaller extraction dir sys._MEIPASS (when frozen)
    3. Project bundled_tools folder (development)
    4. Fallback to tool name (system PATH)
    """
    # On Windows the bundled files are .exe; on *nix they are assumed to be the tool name as-is
    tool_filename = f"{tool_name}.exe" if os.name == 'nt' else tool_name

    # Ensure tools are initialized before resolving paths
    init_bundled_tools()

    candidates = []

    # 1) persistent user cache
    try:
        if _USER_BIN_CACHE:
            candidates.append(os.path.join(_USER_BIN_CACHE, tool_filename))
    except Exception:
        pass

    # 2) PyInstaller extracted bundled_tools
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, 'tools', tool_filename))

    # 3) repo bundled_tools for development
    candidates.append(os.path.join(bundled_tools_dir, tool_filename))

    for path in candidates:
        if os.path.exists(path):
            # Ensure executable permission on non-Windows
            try:
                if os.name != 'nt':
                    st = os.stat(path)
                    # Grant owner execute bit if not present
                    if not (st.st_mode & 0o100):
                        os.chmod(path, st.st_mode | 0o100)
            except Exception:
                pass
            return path

    # Fallback: return the bare tool name so system PATH resolution can be used
    return tool_name

def get_subprocess_kwargs():
    """
    Get subprocess kwargs to hide console windows on Windows
    """
    kwargs = {'capture_output': True, 'text': True}
    
    if os.name == 'nt':  # Windows
        # Hide console window
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    
    return kwargs


from client.core.ffmpeg_utils import (
    map_ui_quality_to_crf,
    get_image_dimensions,
    get_video_dimensions,
    get_video_duration,
    has_audio_stream,
    clamp_resize_width,
    calculate_longer_edge_resize,
    ensure_output_directory_exists
)
from client.core.gif_converter import GifConverter
from client.core.suffix_manager import SuffixManager


class ConversionEngine(QThread):
    """Main conversion engine running in separate thread"""
    
    progress_updated = pyqtSignal(int)  # Progress percentage
    file_progress_updated = pyqtSignal(int, float)  # (file_index, progress 0.0-1.0) for individual file progress
    status_updated = pyqtSignal(str)    # Status message
    file_completed = pyqtSignal(str, str)  # (source, output) file paths
    conversion_finished = pyqtSignal(bool, str)  # (success, message)
    
    def __init__(self, files: List[str], params: Dict):
        super().__init__()
        self.files = files
        self.params = params
        self.should_stop = False
        self.current_process = None
        self._current_file_index = 0
        self._total_files = len(files)
        # Initialize sub-converters
        self.gif_converter = GifConverter(self)

    def run_ffmpeg_with_cancellation(self, stream_spec, **kwargs):
        """Run FFmpeg with cancellation support and progress tracking"""
        import re
        import threading
        import time
        
        try:
            # Add -progress pipe:1 to output progress to stdout in parseable format
            stream_spec = stream_spec.global_args('-progress', 'pipe:1', '-stats_period', '0.1')
            
            # Use run_async with pipes for progress tracking
            self.current_process = ffmpeg.run_async(
                stream_spec, 
                pipe_stderr=True,
                pipe_stdout=True,
                **{k: v for k, v in kwargs.items() if k != 'quiet'}
            )
            
            stderr_data = []
            stdout_data = []
            last_progress_percent = -1.0  # Use float for smooth progress tracking
            duration = None
            duration_lock = threading.Lock()
            
            # Thread to read stderr (for duration and errors)
            def read_stderr():
                nonlocal duration
                for line in iter(self.current_process.stderr.readline, b''):
                    stderr_data.append(line)
                    line_str = line.decode('utf-8', errors='replace')
                    
                    # Extract duration from FFmpeg output
                    if 'Duration:' in line_str:
                        duration_match = re.search(r'Duration: (\d+):(\d+):(\d+[\.,]\d+)', line_str)
                        if duration_match:
                            h, m, s = duration_match.groups()
                            s = s.replace(',', '.')
                            with duration_lock:
                                duration = int(h) * 3600 + int(m) * 60 + float(s)
            
            # Thread to read stdout (for progress)
            def read_stdout():
                nonlocal last_progress_percent
                buffer = ""
                for line in iter(self.current_process.stdout.readline, b''):
                    stdout_data.append(line)
                    buffer += line.decode('utf-8', errors='replace')
                    
                    # Parse progress output: out_time_ms=123456
                    if 'out_time_ms=' in buffer:
                        out_time_match = re.search(r'out_time_ms=(\d+)', buffer)
                        if out_time_match:
                            with duration_lock:
                                dur = duration
                            if dur and dur > 0:
                                out_time_ms = int(out_time_match.group(1))
                                current_time = out_time_ms / 1000000.0  # microseconds to seconds
                                
                                # Calculate smooth file progress (0.0 to 1.0)
                                smooth_file_progress = min(0.95, current_time / dur)
                                
                                # Emit smooth file progress for list item visualization
                                if hasattr(self, '_current_file_index'):
                                    self.file_progress_updated.emit(self._current_file_index, smooth_file_progress)
                                
                                # Calculate smooth overall progress as float (0-100)
                                file_progress_float = min(95.0, (current_time / dur) * 100.0)
                                
                                # Emit progress for every 0.5% change for smooth animation
                                if abs(file_progress_float - last_progress_percent) >= 0.5:
                                    last_progress_percent = file_progress_float
                                    
                                    if hasattr(self, '_current_file_index') and hasattr(self, '_total_files'):
                                        base_progress = (self._current_file_index * 100.0) / self._total_files
                                        file_weight = 100.0 / self._total_files
                                        overall = base_progress + (file_progress_float * file_weight) / 100.0
                                        self.progress_updated.emit(int(overall))
                                    else:
                                        self.progress_updated.emit(int(file_progress_float))
                        
                        # Clear buffer after parsing progress block
                        if 'progress=' in buffer:
                            buffer = ""
            
            # Start reader threads
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread.start()
            stdout_thread.start()
            
            # Wait for process while checking for cancellation
            while self.current_process.poll() is None:
                if self.should_stop:
                    self.current_process.kill()
                    return False
                time.sleep(0.1)
            
            # Wait for threads to finish
            stderr_thread.join(timeout=2)
            stdout_thread.join(timeout=2)
                
            # Check exit code
            if self.current_process.returncode != 0:
                if self.should_stop:
                    return False
                    
                stderr_str = b''.join(stderr_data).decode('utf-8', errors='replace')
                error_msg = f"FFmpeg process exited with code {self.current_process.returncode}"
                if stderr_str:
                    error_msg += f"\nStderr: {stderr_str}"
                raise Exception(error_msg)
                
            return True
        except Exception as e:
            if self.should_stop:
                return False
            raise e
        finally:
            self.current_process = None
        
    def run(self):
        """Main conversion thread execution"""
        print(f"Starting conversion with {len(self.files)} files")
        print(f"Conversion parameters: {self.params}")
        try:
            total_files = len(self.files)
            successful_conversions = 0
            
            # Calculate total operations for progress tracking
            total_operations = 0
            for file_path in self.files:
                file_ext = Path(file_path).suffix.lower()
                conversion_type = self.params.get('type', 'image')
                
                if conversion_type == 'image' and self.params.get('multiple_qualities', False):
                    quality_variants = self.params.get('quality_variants', [])
                    total_operations += len(quality_variants) if quality_variants else 1
                else:
                    total_operations += 1
            
            current_operation = 0
            
            for i, file_path in enumerate(self.files):
                if self.should_stop:
                    break
                
                # Set current file index for progress tracking
                self._current_file_index = i
                    
                self.status_updated.emit(f"Processing: {os.path.basename(file_path)}")
                print(f"Processing file {i+1}/{total_files}: {file_path}")
                
                # Emit progress at the START of each file (shows progress bar immediately)
                progress_start = int(current_operation * 100 / total_operations)
                self.progress_updated.emit(progress_start)
                
                # Emit file-specific progress start
                print(f"🔵 EMITTING file_progress_updated({i}, 0.0)")
                self.file_progress_updated.emit(i, 0.0)
                
                # For non-FFmpeg conversions (images), emit progress updates during conversion
                # Simulate progress: 0% at start, then 50% midway, 100% when done
                print(f"🔵 EMITTING file_progress_updated({i}, 0.1)")
                self.file_progress_updated.emit(i, 0.1)  # 10% when starting
                
                result = self.convert_file(file_path)
                
                # Emit near-complete progress for image conversions (instant completion)
                print(f"🔵 EMITTING file_progress_updated({i}, 0.95)")
                self.file_progress_updated.emit(i, 0.95)  # 95% when file conversion completes
                
                if result is None:
                    # Skipped file
                    print(f"Skipped file: {file_path}")
                    # Don't increment successful_conversions
                elif result:
                    successful_conversions += 1
                    print(f"Successfully converted: {file_path}")
                else:
                    print(f"Failed to convert: {file_path}")
                    
                # Update progress based on operations completed
                file_ext = Path(file_path).suffix.lower()
                conversion_type = self.params.get('type', 'image')
                
                if conversion_type == 'image' and self.params.get('multiple_qualities', False):
                    quality_variants = self.params.get('quality_variants', [])
                    current_operation += len(quality_variants) if quality_variants else 1
                else:
                    current_operation += 1
                    
                progress = int(current_operation * 100 / total_operations)
                self.progress_updated.emit(progress)
                
            # Finish
            if self.should_stop:
                print("Conversion cancelled by user")
                self.conversion_finished.emit(False, "Conversion cancelled by user")
            else:
                # Calculate actual processed count (excluding skipped)
                # We don't have a separate counter for skipped, but successful_conversions tracks successes.
                # If we want to report "X/Y files processed successfully" where Y is only relevant files:
                # But the user asked: "If you converted 2 video files and skipped 5 photos, dont tell in teh popup converted 7 files, but say converted 2 files"
                # So we should just report successful_conversions.
                
                message = f"Conversion completed: {successful_conversions} files processed successfully"
                print(message)
                self.conversion_finished.emit(True, message)
                
        except Exception as e:
            error_msg = f"Error during conversion: {str(e)}"
            print(error_msg)
            self.conversion_finished.emit(False, error_msg)
            
    def convert_file(self, file_path: str) -> bool:
        """Convert a single file based on parameters"""
        try:
            file_ext = Path(file_path).suffix.lower()
            conversion_type = self.params.get('type', 'image')
            
            # Define valid extensions
            image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp', '.gif'}
            video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
            
            # Filter files based on conversion type
            if conversion_type == 'image':
                if file_ext not in image_exts:
                    self.status_updated.emit(f"Skipping non-image file: {os.path.basename(file_path)}")
                    return None  # Return None to indicate skipped
                return self.convert_image(file_path)
                
            elif conversion_type == 'video':
                if file_ext not in video_exts:
                    self.status_updated.emit(f"Skipping non-video file: {os.path.basename(file_path)}")
                    return None  # Return None to indicate skipped
                    
                video_variants = self.params.get('video_variants', [])
                quality_variants = self.params.get('quality_variants', [])
                
                # Check if we need multiple variants (either size or quality)
                # MUST check the toggle flags explicitly
                multiple_size_variants = self.params.get('multiple_size_variants', False)
                multiple_qualities = self.params.get('multiple_qualities', False)
                
                has_multiple_variants = (multiple_size_variants and video_variants and len(video_variants) > 1) or \
                                      (multiple_qualities and quality_variants and len(quality_variants) > 1)
                
                if has_multiple_variants:
                    print(f"Creating multiple video variants for {file_path}")
                    return self._convert_video_multiple_variants(file_path)
                else:
                    # If single variant, set width/scale from video_variants[0] if available
                    if video_variants and len(video_variants) == 1:
                        v = video_variants[0]
                        if isinstance(v, str) and v.endswith('%'):
                            self.params['scale'] = True
                            self.params['width'] = v
                        else:
                            try:
                                self.params['width'] = int(v)
                                self.params['scale'] = True
                            except Exception:
                                self.params['width'] = 1920
                                self.params['scale'] = True
                    return self.convert_video(file_path)
            elif conversion_type == 'gif':
                if file_ext not in video_exts:
                    self.status_updated.emit(f"Skipping non-video file for GIF conversion: {os.path.basename(file_path)}")
                    return None  # Return None to indicate skipped
                    
                if file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v']:
                    return self.video_to_gif(file_path)
                else:
                    return self.gif_converter.optimize_gif(file_path)
            elif conversion_type == 'loop':
                # Loop tab - route to GIF or WebM based on loop_format
                loop_format = self.params.get('loop_format', 'GIF')
                
                if file_ext not in video_exts:
                    self.status_updated.emit(f"Skipping non-video file for loop conversion: {os.path.basename(file_path)}")
                    return None
                
                if loop_format == 'GIF':
                    # Map loop tab GIF parameters to video_to_gif expected names
                    if 'gif_fps' in self.params:
                        self.params['ffmpeg_fps'] = self.params['gif_fps']
                    if 'gif_colors' in self.params:
                        self.params['colors'] = self.params['gif_colors']
                    if 'gif_dither' in self.params:
                        self.params['dither'] = self.params['gif_dither']
                    if 'gif_blur' in self.params:
                        self.params['blur'] = self.params['gif_blur']
                    
                    # Map resize values for GIF
                    # Map resize values for GIF
                    if self.params.get('multiple_resize') and self.params.get('resize_variants'):
                         self.params['gif_resize_values'] = self.params.get('resize_variants')
                    else:
                         current_resize = self.params.get('current_resize')
                         if not current_resize and self.params.get('auto_resize'):
                              mode = self.params.get('resize_mode')
                              val = self.params.get('resize_value')
                              if val:
                                  if mode == 'By width (pixels)':
                                      current_resize = str(val)
                                  elif mode == 'By longer edge (pixels)':
                                      current_resize = f"L{val}"
                                  elif mode == 'By percentage':
                                      current_resize = f"{val}%"
                         
                         if current_resize:
                             self.params['gif_resize_values'] = [current_resize]
                    
                    self.params['gif_resize_mode'] = self.params.get('resize_mode', 'By width (pixels)')
                    
                    # Map GIF variant parameters if multivariant enabled
                    if self.params.get('gif_multiple_variants'):
                        fps_variants = self.params.get('gif_fps_variants', [])
                        colors_variants = self.params.get('gif_colors_variants', [])
                        dither_variants = self.params.get('gif_dither_variants', [])
                        
                        # Only create gif_variants if at least one has values
                        if fps_variants or colors_variants or dither_variants:
                            self.params['gif_variants'] = {
                                'fps': fps_variants,
                                'colors': colors_variants,
                                'dither': dither_variants,
                            }
                    
                    # Route to GIF conversion
                    return self.video_to_gif(file_path)
                else:
                    # WebM (AV1) or WebM (VP9) - route to video conversion
                    # Map loop_format to codec
                    if 'AV1' in loop_format:
                        self.params['codec'] = 'WebM (AV1, slower)'
                    else:
                        self.params['codec'] = 'WebM (VP9, faster)'
                    
                    if 'webm_quality' in self.params:
                        self.params['quality'] = self.params['webm_quality']
                    
                    # Check for multiple quality variants (ONLY if toggle is enabled)
                    if self.params.get('webm_multiple_variants'):
                        webm_quality_variants = self.params.get('webm_quality_variants', [])
                        if webm_quality_variants and len(webm_quality_variants) > 1:
                            self.params['multiple_qualities'] = True
                            self.params['quality_variants'] = webm_quality_variants
                    
                    # Check for multiple resize variants (Loop tab)
                    if self.params.get('multiple_resize') and self.params.get('resize_variants'):
                         self.params['multiple_size_variants'] = True
                         self.params['video_variants'] = self.params.get('resize_variants')

                    # Dispatch
                    if self.params.get('multiple_qualities') or self.params.get('multiple_size_variants'):
                        return self._convert_video_multiple_variants(file_path)
                    else:
                        return self.convert_video(file_path)
            else:
                self.status_updated.emit(f"Unknown conversion type: {conversion_type}")
                return False
                
        except Exception as e:
            self.status_updated.emit(f"Error converting {os.path.basename(file_path)}: {str(e)}")
            return False
            
    def convert_image(self, file_path: str) -> bool:
        """Convert image using FFmpeg"""
        try:
            format_ext = self.params.get('format', 'jpg').lower()
            
            # Handle resize parameter if present but current_resize is not set
            if 'resize' in self.params and 'current_resize' not in self.params:
                self.params['current_resize'] = str(self.params['resize'])
            
            # Check if Max Size mode is enabled
            image_size_mode = self.params.get('image_size_mode', 'manual')
            if image_size_mode == 'max_size':
                target_mb = self.params.get('image_max_size_mb')
                auto_resize = self.params.get('image_auto_resize', False)
                
                if target_mb and target_mb > 0:
                    target_bytes = int(target_mb * 1024 * 1024)
                    
                    # Find optimal parameters for target size
                    self.status_updated.emit(f"Optimizing for target size: {target_mb:.1f} MB...")
                    
                    optimal = find_optimal_image_params_for_size(
                        file_path, format_ext, target_bytes,
                        status_callback=lambda msg: self.status_updated.emit(msg),
                        auto_resize=auto_resize
                    )
                    
                    # Apply optimized quality
                    self.params['quality'] = optimal.get('quality', self.params.get('quality', 75))
                    
                    # Apply resolution scale if present
                    if '_resolution_scale' in optimal:
                        scale = optimal['_resolution_scale']
                        self.params['_max_size_resolution_scale'] = scale
                        
                        # Calculate and store actual output resolution for suffix
                        try:
                            from client.core.ffmpeg_utils import get_video_dimensions
                            orig_width, orig_height = get_video_dimensions(file_path)
                            if orig_width > 0 and orig_height > 0:
                                out_width = int(orig_width * scale)
                                out_height = int(orig_height * scale)
                                self.params['_output_resolution'] = (out_width, out_height)
                        except:
                            pass
                            
                        self.status_updated.emit(f"Applied resolution scale: {int(scale * 100)}%")
                    else:
                        # No scaling - output resolution is same as input
                        try:
                            from client.core.ffmpeg_utils import get_video_dimensions
                            orig_width, orig_height = get_video_dimensions(file_path)
                            if orig_width > 0 and orig_height > 0:
                                self.params['_output_resolution'] = (orig_width, orig_height)
                        except:
                            pass
                    
                    # Log optimization result
                    preset_info = optimal.get('_preset_info', '')
                    est_size = optimal.get('_estimated_size', 0)
                    self.status_updated.emit(
                        f"✓ Optimized: {preset_info} (est. {est_size/(1024*1024):.2f} MB)"
                    )
            
            # Check if multiple qualities or resize variants are requested
            has_multiple_qualities = self.params.get('multiple_qualities', False) and self.params.get('quality_variants')
            has_resize_variants = self.params.get('resize_variants', [])
            
            if has_multiple_qualities or (has_resize_variants and len(has_resize_variants) > 1):
                return self._convert_image_multiple_variants(file_path, format_ext)
            else:
                # Single conversion
                output_path = self.get_output_path(file_path, format_ext)
                return self._convert_single_image(file_path, output_path, format_ext)
                
        except Exception as e:
            self.status_updated.emit(f"Image conversion error: {str(e)}")
            return False
            
    def _convert_image_multiple_variants(self, file_path: str, format_ext: str) -> bool:
        """Convert image with multiple quality and/or resize variants"""
        # Check if multiple qualities is enabled AND has variants
        multiple_qualities = self.params.get('multiple_qualities', False)
        quality_variants = self.params.get('quality_variants', [])
        if not multiple_qualities or not quality_variants:
            quality_variants = [self.params.get('quality', 75)]
        
        # Check if multiple resize is enabled AND has variants
        multiple_resize = self.params.get('multiple_resize', False)
        resize_variants = self.params.get('resize_variants', [])
        if not multiple_resize or not resize_variants:
            resize_variants = [None]
        
        successful_conversions = 0
        total_variants = len(quality_variants) * len(resize_variants)
        
        for quality in quality_variants:
            if self.should_stop:
                break
            for resize in resize_variants:
                if self.should_stop:
                    break
                try:
                    # Create output path with quality and/or resize suffix
                    output_path = self.get_output_path_with_variants(file_path, format_ext, quality, resize)
                    
                    # Temporarily set the parameters for this conversion
                    original_quality = self.params.get('quality')
                    original_resize = self.params.get('current_resize')
                    self.params['quality'] = quality
                    self.params['current_resize'] = resize
                    
                    # Convert with these parameters
                    success = self._convert_single_image(file_path, output_path, format_ext)
                    
                    if success:
                        successful_conversions += 1
                        variant_desc = f"Quality {quality}%"
                        if resize:
                            variant_desc += f", Resize {resize}"
                        self.status_updated.emit(f"✓ {variant_desc} completed")
                    else:
                        variant_desc = f"Quality {quality}%"
                        if resize:
                            variant_desc += f", Resize {resize}"
                        self.status_updated.emit(f"✗ {variant_desc} failed")
                    
                    # Restore original parameters
                    self.params['quality'] = original_quality
                    self.params['current_resize'] = original_resize
                    
                except Exception as e:
                    self.status_updated.emit(f"Variant conversion error: {str(e)}")
        
        if self.should_stop:
            self.status_updated.emit(f"Image variants conversion stopped by user")
        
        return successful_conversions > 0
        
    def _convert_single_image(self, file_path: str, output_path: str, format_ext: str) -> bool:
        """Convert a single image with current settings using FFmpeg"""
        return self._convert_image_ffmpeg(file_path, output_path)
            
    def _convert_image_ffmpeg(self, file_path: str, output_path: str) -> bool:
        """Convert image using FFmpeg"""
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
        input_stream = ffmpeg.input(file_path)
        
        # Apply filters
        stream = input_stream
        
        # Apply Max Size mode resolution scale FIRST (before other resize)
        max_size_scale = self.params.get('_max_size_resolution_scale')
        if max_size_scale and max_size_scale < 1.0:
            stream = ffmpeg.filter(stream, 'scale', f'iw*{max_size_scale}', f'ih*{max_size_scale}')
        
        # Handle resize based on current_resize parameter
        current_resize = self.params.get('current_resize')
        if current_resize:
            if current_resize.endswith('%'):
                # Percentage resize
                percent = float(current_resize[:-1]) / 100
                orig_w, orig_h = get_image_dimensions(file_path)
                if orig_w > 0:
                    target_w = int(orig_w * percent)
                    target_w = clamp_resize_width(orig_w, target_w)
                    target_h = int((target_w * orig_h) / orig_w) if orig_h else -1
                    stream = ffmpeg.filter(stream, 'scale', target_w, target_h)
                else:
                    stream = ffmpeg.filter(stream, 'scale', f'iw*{percent}', f'ih*{percent}')
            elif current_resize.startswith('L'):
                # Longer edge resize (no upscaling)
                target_longer_edge = int(current_resize[1:])
                orig_w, orig_h = get_image_dimensions(file_path)
                longer_edge = max(orig_w, orig_h)
                # Don't upscale if longer edge is already smaller than target
                if longer_edge >= target_longer_edge:
                    if orig_w > orig_h:
                        # Width is longer: scale by width
                        stream = ffmpeg.filter(stream, 'scale', target_longer_edge, -1)
                    else:
                        # Height is longer: calculate width to maintain aspect ratio
                        ratio = target_longer_edge / orig_h
                        new_w = int(orig_w * ratio)
                        # Ensure even dimensions for codec compatibility
                        new_w = new_w if new_w % 2 == 0 else new_w - 1
                        stream = ffmpeg.filter(stream, 'scale', new_w, target_longer_edge)
            else:
                # Pixel resize (width-based, maintain aspect ratio)
                width = int(current_resize)
                orig_w, orig_h = get_image_dimensions(file_path)
                width = clamp_resize_width(orig_w, width)
                stream = ffmpeg.filter(stream, 'scale', width, -1)
        elif self.params.get('resize', False):
            # Legacy resize mode - use width only, maintain aspect ratio
            width = self.params.get('width', 1920)
            orig_w, orig_h = get_image_dimensions(file_path)
            width = clamp_resize_width(orig_w, int(width)) if width is not None else width
            stream = ffmpeg.filter(stream, 'scale', width, -1)
            
        # Aspect Ratio Presets (Image)
        preset_ratio = self.params.get('image_preset_ratio')
        # Also check for Instagram preset for images
        is_instagram = self.params.get('image_preset_social') == 'Instagram'
        if is_instagram or preset_ratio:
            target_ratio = preset_ratio or ('9:16' if is_instagram else None)
            if target_ratio:
                ratio_map = {
                    '4:3': (1440, 1080),
                    '1:1': (1080, 1080),
                    '16:9': (1920, 1080),
                    '9:16': (1080, 1920)
                }
                if target_ratio in ratio_map:
                    tw, th = ratio_map[target_ratio]
                    self.status_updated.emit(f"Applying image preset ratio: {target_ratio} ({tw}x{th})")
                    stream = ffmpeg.filter(stream, 'scale', tw, th, force_original_aspect_ratio='decrease')
                    stream = ffmpeg.filter(stream, 'pad', tw, th, '(ow-iw)/2', '(oh-ih)/2')
            
        # Handle rotation (skip rotation when using longer edge resize unless explicitly toggled)
        rotation_angle = self.params.get('rotation_angle')
        # Skip rotation for longer edge mode UNLESS rotation is explicitly set to a real rotation value
        skip_rotation_for_longer_edge = (
            current_resize and 
            current_resize.startswith('L') and 
            (not rotation_angle or rotation_angle == "No rotation")
        )
        if rotation_angle and rotation_angle != "No rotation" and not skip_rotation_for_longer_edge:
            if rotation_angle == "90° clockwise":
                stream = ffmpeg.filter(stream, 'transpose', 1)  # 90 degrees clockwise
            elif rotation_angle == "180°":
                stream = ffmpeg.filter(stream, 'transpose', 2)  # 180 degrees
                stream = ffmpeg.filter(stream, 'transpose', 2)  # Apply twice for 180
            elif rotation_angle == "270° clockwise":
                stream = ffmpeg.filter(stream, 'transpose', 2)  # 270 degrees clockwise (or 90 counter-clockwise)
            
        # Output with quality settings
        output_args = {}
        format_type = self.params.get('format', 'jpg').lower()
        
        if format_type in ['jpg', 'jpeg']:
            quality = int(self.params.get('quality', 85))
            # FFmpeg q:v scale is 1-31 (lower is better), convert from 1-100 scale
            output_args['q:v'] = max(1, min(31, int((100 - quality) * 31 / 100)))
        elif format_type == 'png':
            quality = int(self.params.get('quality', 85))
            output_args['compression_level'] = min(9, max(0, (100 - quality) // 10))
        elif format_type == 'webp':
            quality = int(self.params.get('quality', 85))
            output_args['quality'] = quality
            
        output = ffmpeg.output(stream, output_path, **output_args)
        
        if self.params.get('overwrite', False):
            output = ffmpeg.overwrite_output(output)
            
        # Run with error capture
        try:
            # Use run_ffmpeg_with_cancellation instead of direct run
            self.run_ffmpeg_with_cancellation(output, overwrite_output=self.params.get('overwrite', False))
        except Exception as e:
            error_msg = str(e)
            raise Exception(f"FFmpeg conversion failed: {error_msg}")
            
        self.file_completed.emit(file_path, output_path)
        return True
        

            
    def convert_video(self, file_path: str) -> bool:
        """Convert video using FFmpeg"""
        try:
            # Determine output format based on codec
            format_map = {
                'H.264 (MP4)': 'mp4',
                'H.265 (MP4)': 'mp4', 
                'WebM (VP9, faster)': 'webm',
                'WebM (AV1, slower)': 'webm',
                'AV1 (MP4)': 'mp4'
            }
            
            selected_codec = self.params.get('codec', 'H.264 (MP4)')
            output_format = format_map.get(selected_codec, 'mp4')
            
            # Check if Max Size mode is enabled
            video_size_mode = self.params.get('video_size_mode', 'manual')
            if video_size_mode == 'max_size':
                target_mb = self.params.get('video_max_size_mb')
                auto_resize = self.params.get('video_auto_resize', False)
                
                if target_mb and target_mb > 0:
                    target_bytes = int(target_mb * 1024 * 1024)
                    
                    # Find optimal parameters for target size
                    self.status_updated.emit(f"Optimizing for target size: {target_mb:.1f} MB...")
                    
                    optimal = find_optimal_video_params_for_size(
                        file_path, selected_codec, self.params, target_bytes,
                        status_callback=lambda msg: self.status_updated.emit(msg),
                        auto_resize=auto_resize
                    )
                    
                    # Apply optimized CRF and audio bitrate
                    optimized_crf = optimal.get('crf', 28)
                    optimized_audio = optimal.get('audio_bitrate', 96)
                    
                    # Store for use in output_args
                    self.params['_optimized_crf'] = optimized_crf
                    self.params['_optimized_audio_bitrate'] = optimized_audio
                    self.params['_encoding_mode'] = optimal.get('encoding_mode')
                    self.params['_video_bitrate_kbps'] = optimal.get('video_bitrate_kbps')
                    
                    # Apply resolution scale if present
                    if '_resolution_scale' in optimal:
                        scale = optimal['_resolution_scale']
                        self.params['_max_size_resolution_scale'] = scale
                        
                        # Calculate and store actual output resolution for suffix
                        try:
                            from client.core.ffmpeg_utils import get_video_dimensions
                            orig_width, orig_height = get_video_dimensions(file_path)
                            if orig_width > 0 and orig_height > 0:
                                out_width = int(orig_width * scale)
                                out_height = int(orig_height * scale)
                                # Ensure even dimensions for video encoding
                                out_width = out_width - (out_width % 2)
                                out_height = out_height - (out_height % 2)
                                self.params['_output_resolution'] = (out_width, out_height)
                        except:
                            pass
                        
                        self.status_updated.emit(f"Applied resolution scale: {int(scale * 100)}%")
                    else:
                        # No scaling - output resolution is same as input
                        try:
                            from client.core.ffmpeg_utils import get_video_dimensions
                            orig_width, orig_height = get_video_dimensions(file_path)
                            if orig_width > 0 and orig_height > 0:
                                self.params['_output_resolution'] = (orig_width, orig_height)
                        except:
                            pass
                    
                    # Log optimization result
                    preset_info = optimal.get('_preset_info', '')
                    est_size = optimal.get('_estimated_size', 0)
                    self.status_updated.emit(
                        f"✓ Optimized: {preset_info} (est. {est_size/(1024*1024):.2f} MB)"
                    )
            
            # Debug: Print the command being executed
            self.status_updated.emit(f"DEBUG: Video conversion - Codec: {selected_codec}, Output format: {output_format}")
            
            output_path = self.get_output_path(file_path, output_format)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Handle time cutting - apply to input for better performance and compatibility
            input_args = {}
            enable_time_cutting = self.params.get('enable_time_cutting', False)
            if enable_time_cutting:
                time_start = self.params.get('time_start')
                time_end = self.params.get('time_end')
                if time_start is not None and time_end is not None and time_start < time_end:
                    # Get video duration to convert normalized time to actual time
                    video_duration = get_video_duration(file_path)
                    if video_duration > 0:
                        start_time = time_start * video_duration
                        end_time = time_end * video_duration
                        self.status_updated.emit(f"DEBUG: Applying time cutting - start: {start_time:.2f}s, end: {end_time:.2f}s (duration: {video_duration:.2f}s)")
                        input_args['ss'] = start_time
                        input_args['to'] = end_time
                    else:
                        self.status_updated.emit("DEBUG: Could not determine video duration for time cutting")
            
            input_stream = ffmpeg.input(file_path, **input_args)
            video_stream = input_stream.video
            
            # Check if video has audio stream before creating reference
            has_audio = has_audio_stream(file_path)
            audio_stream = input_stream.audio if has_audio else None

            # Apply retime (speed change) after cutting and before other filters
            retime_enabled = self.params.get('retime_enabled') or self.params.get('enable_retime')
            retime_speed = self.params.get('retime_speed', 1.0)
            if retime_enabled and retime_speed and retime_speed != 1.0:
                try:
                    speed = float(retime_speed)
                    speed = max(0.1, min(3.0, speed))
                    self.status_updated.emit(f"DEBUG: Applying retime at {speed:.2f}x (setpts/atempo)")
                    video_stream = video_stream.filter('setpts', f'PTS/{speed}')
                    if audio_stream is not None:
                        try:
                            if speed <= 2.0:
                                audio_stream = audio_stream.filter('atempo', speed)
                            else:
                                # Chain atempo to stay within valid range per filter
                                audio_stream = audio_stream.filter('atempo', 2.0).filter('atempo', speed / 2.0)
                        except Exception as audio_err:
                            self.status_updated.emit(f"DEBUG: Skipping audio retime due to error: {audio_err}")
                            audio_stream = None
                    else:
                        self.status_updated.emit("DEBUG: No audio stream detected for retime")
                except Exception as e:
                    self.status_updated.emit(f"DEBUG: Skipping retime due to error: {e}")
            else:
                video_stream = video_stream
            
            # Video encoding options
            codec_map = {
                'H.264 (MP4)': 'libx264',
                'H.265 (MP4)': 'libx265', 
                'WebM (VP9, faster)': 'libvpx-vp9',
                'WebM (AV1, slower)': 'libaom-av1',
                'AV1 (MP4)': 'libaom-av1'
            }
            
            codec = codec_map.get(selected_codec, 'libx264')
            
            # Debug: Print FFmpeg codec being used
            self.status_updated.emit(f"DEBUG: FFmpeg codec: {codec}")
            
            output_args = {'vcodec': codec}
            
            # Check if using bitrate-based encoding (v2 Max Size mode with 2-pass)
            encoding_mode = self.params.get('_encoding_mode')
            video_bitrate_kbps = self.params.get('_video_bitrate_kbps')
            
            # Get quality parameter - use optimized CRF in Max Size mode
            optimized_crf = self.params.get('_optimized_crf')
            optimized_audio = self.params.get('_optimized_audio_bitrate')
            quality = self.params.get('quality')
            
            # Social Presets Overrides (e.g. Instagram)
            # Use presets from configuration
            preset_social = self.params.get('video_preset_social')
            social_config = SOCIAL_PLATFORM_PRESETS.get(preset_social)
            
            if social_config:
                self.status_updated.emit(f"Applying specialized settings for {preset_social}")
                # Apply core settings from config, excluding internal logic keys
                logic_keys = ['scaling_flags', 'f', 'force_original_aspect_ratio', 'use_padding', 'supported_background_styles']
                
                # Update output_args with social config
                for k, v in social_config.items():
                    if k not in logic_keys:
                        output_args[k] = v
                        
                # Ensure format is set
                output_args['f'] = social_config.get('f', 'mp4')
                
                # Override codec if specified (e.g. force h264 for insta)
                if 'vcodec' in social_config:
                    codec = social_config['vcodec']
                    
            elif encoding_mode == '2-pass' and video_bitrate_kbps:
                # Use bitrate-based encoding for Max Size mode (v2 estimator)
                self.status_updated.emit(f"DEBUG: Using 2-pass bitrate mode: {video_bitrate_kbps}kbps")
                
                # Set video bitrate with buffer constraints
                output_args['b:v'] = f'{video_bitrate_kbps}k'
                output_args['maxrate'] = f'{int(video_bitrate_kbps * 1.5)}k'
                output_args['bufsize'] = f'{int(video_bitrate_kbps * 2)}k'
                
                # Set format based on codec
                if selected_codec in ['WebM (VP9, faster)', 'WebM (AV1, slower)']:
                    output_args['f'] = 'webm'
                    # WebM: Strip audio completely
                    audio_stream = None
                    output_args['an'] = None
                    
                    # Optimize AV1 speed
                    if codec == 'libaom-av1':
                        output_args['cpu-used'] = 4
                        self.status_updated.emit("DEBUG: Applied AV1 speed optimization (cpu-used=4)")
                else:
                    output_args['f'] = 'mp4'
                    
                    # Optimize AV1 speed for MP4 container too
                    if codec == 'libaom-av1':
                        output_args['cpu-used'] = 4
                        self.status_updated.emit("DEBUG: Applied AV1 speed optimization (cpu-used=4)")
                    
                    # Set audio bitrate if audio exists
                    if has_audio and optimized_audio:
                        output_args['b:a'] = f'{optimized_audio}k'
                        self.status_updated.emit(f"DEBUG: Audio bitrate set to {optimized_audio}k (2-pass mode)")
                    
            else:
                # For WebM/VP9/AV1, we need to handle audio codec and format-specific parameters
                if selected_codec in ['WebM (VP9, faster)', 'WebM (AV1, slower)']:
                    # WebM: Strip audio completely (no audio stream)
                    audio_stream = None  # Remove audio stream
                    output_args['an'] = None  # No audio flag
                    output_args['f'] = 'webm'  # WebM container format
                    
                    # Apply CRF quality - use optimized value if in Max Size mode
                    if optimized_crf is not None:
                        output_args['crf'] = optimized_crf
                        self.status_updated.emit(f"DEBUG: WebM CRF set to {optimized_crf} (max size optimized)")
                    elif quality is not None:
                        crf_value = map_ui_quality_to_crf(quality, codec)
                        output_args['crf'] = crf_value
                        self.status_updated.emit(f"DEBUG: WebM CRF set to {crf_value} (quality: {quality})")
                    
                    # No audio bitrate needed since we're stripping audio
                    
                    # Optimize AV1 speed
                    if codec == 'libaom-av1':
                        output_args['cpu-used'] = 4
                        self.status_updated.emit("DEBUG: Applied AV1 speed optimization (cpu-used=4)")
                else:
                    # For MP4 codecs, ensure MP4 format
                    output_args['f'] = 'mp4'
                    
                    # Optimize AV1 speed for MP4 container too
                    if codec == 'libaom-av1':
                        output_args['cpu-used'] = 4
                        self.status_updated.emit("DEBUG: Applied AV1 speed optimization (cpu-used=4)")
                    
                    # Apply CRF quality - use optimized value if in Max Size mode
                    if optimized_crf is not None:
                        output_args['crf'] = optimized_crf
                        self.status_updated.emit(f"DEBUG: MP4 CRF set to {optimized_crf} (max size optimized)")
                    elif quality is not None:
                        crf_value = map_ui_quality_to_crf(quality, codec)
                        output_args['crf'] = crf_value
                        self.status_updated.emit(f"DEBUG: MP4 CRF set to {crf_value} (quality: {quality})")
                    
                    # Apply optimized audio bitrate if in Max Size mode
                    if optimized_audio is not None:
                        output_args['audio_bitrate'] = f'{optimized_audio}k'
                        self.status_updated.emit(f"DEBUG: Audio bitrate set to {optimized_audio}k (max size optimized)")
                
            # Frame rate (always use original as per user request)
            # fps = self.params.get('fps', 'Keep Original')
            # if fps != 'Keep Original':
            #     output_args['r'] = fps
                
            # Apply Max Size mode resolution scale FIRST (before other resize)
            max_size_scale = self.params.get('_max_size_resolution_scale')
            if max_size_scale and max_size_scale < 1.0:
                scale_w = f'trunc(iw*{max_size_scale}/2)*2'
                scale_h = f'trunc(ih*{max_size_scale}/2)*2'
                video_stream = ffmpeg.filter(video_stream, 'scale', scale_w, scale_h)
                self.status_updated.emit(f"DEBUG: Applied max size resolution scale: {int(max_size_scale * 100)}%")
            
            # Aspect Ratio & Smart Scaling
            preset_ratio = self.params.get('video_preset_ratio')
            bg_style = self.params.get('video_background_style')
            
            # Default to social preset ratio if not manually set
            target_ratio = preset_ratio
            if not target_ratio and social_config:
                 target_ratio = '9:16' # Default for social
            
            if target_ratio and target_ratio in RATIO_MAPS:
                 tw, th = RATIO_MAPS[target_ratio]
                 self.status_updated.emit(f"Applying smart scaling: {target_ratio} ({tw}x{th})")
                 
                 # 'Fit & Blur' Safety: Vertical input -> Widescreen output
                 try:
                     original_width, original_height = get_video_dimensions(file_path)
                     if target_ratio == '16:9' and original_height > original_width:
                         self.status_updated.emit("Safety: Vertical video detected in Widescreen mode. Forcing 'Fit & Blur'.")
                         bg_style = BG_STYLE_BLURRED
                 except Exception as e:
                     self.status_updated.emit(f"Warning: Could not check dimensions for safety logic: {e}")

                 # Determine strategy
                 is_blurred = bg_style == BG_STYLE_BLURRED
                 is_fill = bg_style == BG_STYLE_FILL_ZOOM
                 # Default to Black Bars if no style selected or explicit Black Bars, unless Fill forced in logic (but here handled by style)
                 
                 scaling_flags = social_config.get('scaling_flags', 'lanczos') if social_config else 'lanczos'
                 
                 if is_blurred:
                      self.status_updated.emit("Scaling Mode: Blurred Background")
                      s1, s2 = video_stream.split()
                      
                      # Background: Fill + Blur
                      bg = s1.filter('scale', tw, th, force_original_aspect_ratio='increase', flags=scaling_flags)
                      bg = bg.filter('crop', tw, th)
                      bg = bg.filter('boxblur', '20:10')
                      
                      # Foreground: Fit
                      fg = s2.filter('scale', tw, th, force_original_aspect_ratio='decrease', flags=scaling_flags)
                      
                      # Overlay
                      video_stream = ffmpeg.overlay(bg, fg, x='(W-w)/2', y='(H-h)/2')
                      
                 elif is_fill:
                      self.status_updated.emit("Scaling Mode: Fill/Zoom")
                      video_stream = video_stream.filter('scale', tw, th, force_original_aspect_ratio='increase', flags=scaling_flags)
                      video_stream = video_stream.filter('crop', tw, th)
                      
                 else:
                      # Default: Black Bars (Fit with Padding)
                      # Or just Fit if padding not required (logic from presets use_padding)
                      use_pad = social_config.get('use_padding', True) if social_config else True
                      
                      self.status_updated.emit("Scaling Mode: Black Bars (Fit)")
                      video_stream = video_stream.filter('scale', tw, th, force_original_aspect_ratio='decrease', flags=scaling_flags)
                      if use_pad:
                          video_stream = video_stream.filter('pad', tw, th, '(ow-iw)/2', '(oh-ih)/2')
                      
                 # Disable other scaling as this takes precedence
                 self.params['scale'] = False
            
            # Handle current_resize parameter (from Lab mode)
            current_resize = self.params.get('current_resize')
            if current_resize:
                original_width, original_height = get_video_dimensions(file_path)
                
                if current_resize.startswith('L'):
                    # Longer edge resize
                    target_longer_edge = int(current_resize[1:])
                    longer_edge = max(original_width, original_height)
                    
                    # Don't upscale if longer edge is already smaller than target
                    if longer_edge >= target_longer_edge:
                        if original_width > original_height:
                            # Width is longer: scale by width
                            video_stream = ffmpeg.filter(video_stream, 'scale', target_longer_edge, -2, flags='lanczos')
                        else:
                            # Height is longer: scale by height
                            video_stream = ffmpeg.filter(video_stream, 'scale', -2, target_longer_edge, flags='lanczos')
                        self.status_updated.emit(f"DEBUG: Applied longer edge scaling: {target_longer_edge}px")
                elif current_resize.endswith('%'):
                    # Percentage resize
                    percent = float(current_resize[:-1]) / 100.0
                    target_w = int(original_width * percent) if original_width else None
                    if target_w:
                        target_w = clamp_resize_width(original_width, target_w)
                        # Use -2 for height to ensure even dimensions
                        video_stream = ffmpeg.filter(video_stream, 'scale', target_w, -2, flags='lanczos')
                    else:
                        scale_w = f'trunc(iw*{percent}/2)*2'
                        scale_h = f'trunc(ih*{percent}/2)*2'
                        video_stream = ffmpeg.filter(video_stream, 'scale', scale_w, scale_h, flags='lanczos')
                    self.status_updated.emit(f"DEBUG: Applied percentage scaling: {percent*100}%")
                else:
                    # Width-based resize
                    new_width = int(current_resize)
                    if not self.params.get('allow_upscaling', False):
                        new_width = clamp_resize_width(original_width, new_width)
                    video_stream = ffmpeg.filter(video_stream, 'scale', new_width, -2, flags='lanczos')
                    self.status_updated.emit(f"DEBUG: Applied width scaling: {new_width}px")
            
            # Legacy scaling (for backwards compatibility)
            elif self.params.get('scale', False):
                width = self.params.get('width', None)
                if width is not None:
                    self.status_updated.emit(f"DEBUG: Applying video scaling - width: {width}")
                    if isinstance(width, str) and width.endswith('%'):
                        percent = float(width[:-1]) / 100.0
                        original_width, original_height = get_video_dimensions(file_path)
                        target_w = int(original_width * percent) if original_width else None
                        if target_w:
                            target_w = clamp_resize_width(original_width, target_w)
                            target_h = int((target_w * original_height) / original_width) if original_height else -1
                            video_stream = ffmpeg.filter(video_stream, 'scale', target_w, target_h, flags='lanczos')
                        else:
                            scale_w = f'trunc(iw*{percent}/2)*2'
                            scale_h = f'trunc(ih*{percent}/2)*2'
                            video_stream = ffmpeg.filter(video_stream, 'scale', scale_w, scale_h, flags='lanczos')
                        self.status_updated.emit(f"DEBUG: Applied percentage scaling: {percent*100}%")
                    else:
                        new_width = int(width)
                        original_width, _ = get_video_dimensions(file_path)
                        
                        # Only clamp if upscaling is disabled (default)
                        if not self.params.get('allow_upscaling', False):
                            new_width = clamp_resize_width(original_width, new_width)
                            
                        video_stream = ffmpeg.filter(video_stream, 'scale', new_width, -1, flags='lanczos')
                        self.status_updated.emit(f"DEBUG: Applied width scaling: {new_width}px")
                else:
                    self.status_updated.emit("DEBUG: Scale enabled but no width parameter found")
                
            # Handle rotation (skip rotation when using longer edge resize unless explicitly toggled)
            current_resize = self.params.get('current_resize')
            rotation_angle = self.params.get('rotation_angle')
            # Skip rotation for longer edge mode UNLESS rotation is explicitly set to a real rotation value
            skip_rotation_for_longer_edge = (
                current_resize and 
                current_resize.startswith('L') and 
                (not rotation_angle or rotation_angle == "No rotation")
            )
            if rotation_angle and rotation_angle != "No rotation" and not skip_rotation_for_longer_edge:
                if rotation_angle == "90° clockwise":
                    video_stream = ffmpeg.filter(video_stream, 'transpose', 1)  # 90 degrees clockwise
                elif rotation_angle == "180°":
                    video_stream = ffmpeg.filter(video_stream, 'transpose', 2)  # 180 degrees
                    video_stream = ffmpeg.filter(video_stream, 'transpose', 2)  # Apply twice for 180
                elif rotation_angle == "270° clockwise":
                    video_stream = ffmpeg.filter(video_stream, 'transpose', 2)  # 270 degrees clockwise
            
            # Apply extra args (e.g. from Loop presets)
            if 'extra_ffmpeg_args' in self.params:
                output_args.update(self.params['extra_ffmpeg_args'])

            # Check for 2-pass encoding mode
            encoding_mode = self.params.get('_encoding_mode')
            video_bitrate = self.params.get('_video_bitrate_kbps')
            
            if encoding_mode == '2-pass' and video_bitrate:
                try:
                    self.status_updated.emit(f"Starting 2-Pass Encoding at {video_bitrate} kbps...")
                    
                    # Cleanup conflicting args for 2-pass
                    pass_args = output_args.copy()
                    pass_args.pop('crf', None)
                    pass_args['video_bitrate'] = f"{video_bitrate}k"
                    
                    # --- PASS 1 ---
                    self.status_updated.emit("Running Pass 1/2 (Analysis)...")
                    pass1_args = pass_args.copy()
                    pass1_args['pass'] = 1
                    pass1_args['f'] = 'null'
                    # Remove audio for pass 1
                    pass1_args['an'] = None 
                    
                    # Output to null device
                    # On Windows, use NUL. On others /dev/null
                    null_dev = 'NUL' if os.name == 'nt' else '/dev/null'
                    
                    # Note: We reuse video_stream filter graph
                    pass1_out = ffmpeg.output(video_stream, null_dev, **pass1_args)
                    pass1_out = ffmpeg.overwrite_output(pass1_out)
                    
                    # Check cancellation
                    if self.should_stop: return False
                    self.run_ffmpeg_with_cancellation(pass1_out)
                    
                    # --- PASS 2 ---
                    self.status_updated.emit("Running Pass 2/2 (Export)...")
                    pass2_args = pass_args.copy()
                    pass2_args['pass'] = 2
                    
                    if audio_stream is not None:
                         output = ffmpeg.output(video_stream, audio_stream, output_path, **pass2_args)
                    else:
                         output = ffmpeg.output(video_stream, output_path, **pass2_args)

                    if self.params.get('overwrite', False):
                        output = ffmpeg.overwrite_output(output)

                    if self.should_stop: return False
                    self.run_ffmpeg_with_cancellation(output)
                    
                    # Clean up ffmpeg 2-pass log files
                    try:
                        cwd = os.getcwd()
                        for f in os.listdir(cwd):
                            if f.startswith('ffmpeg2pass') and f.endswith('.log'):
                                try:
                                    os.remove(os.path.join(cwd, f))
                                except: pass
                    except: pass
                    
                    self.file_completed.emit(file_path, output_path)
                    return True
                    
                except Exception as e2pass:
                    # 2-Pass Failed - Fallback to 1-Pass
                    self.status_updated.emit(f"Warning: 2-Pass encoding failed ({str(e2pass)}). Falling back to CRF encoding.")
                    
                    # Reset params for fallback
                    if 'crf' not in output_args:
                        # Ensure we have a CRF value (default to 23 or user quality)
                        if self.params.get('quality'):
                            output_args['crf'] = map_ui_quality_to_crf(self.params.get('quality'), codec)
                        else:
                            output_args['crf'] = 23
                    
                    # Fallthrough to standard 1-pass execution below
                    pass
            
            # Standard 1-pass (CRF or Quality) - Also serves as fallback
            if audio_stream is not None:
                output = ffmpeg.output(video_stream, audio_stream, output_path, **output_args)
            else:
                output = ffmpeg.output(video_stream, output_path, **output_args)
            
            if self.params.get('overwrite', False):
                output = ffmpeg.overwrite_output(output)
                
            # Check for cancellation before starting
            if self.should_stop:
                return False
                
            # Use run_ffmpeg_with_cancellation
            self.run_ffmpeg_with_cancellation(output)
            
            # Clean up ffmpeg 2-pass log files
            try:
                # FFmpeg creates ffmpeg2pass-0.log in CWD
                cwd = os.getcwd()
                for f in os.listdir(cwd):
                    if f.startswith('ffmpeg2pass') and f.endswith('.log'):
                        try:
                            os.remove(os.path.join(cwd, f))
                        except: pass
            except: pass
            
            self.file_completed.emit(file_path, output_path)
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"CRITICAL ERROR in convert_video: {e}")
            error_msg = f"FFmpeg error: {str(e)}"
            if hasattr(e, 'stderr') and e.stderr:
                stderr_output = e.stderr.decode('utf-8', errors='ignore')
                error_msg += f" (stderr: {stderr_output})"
            self.status_updated.emit(error_msg)
            return False
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"CRITICAL GENERIC ERROR in convert_video: {e}")
            self.status_updated.emit(f"Video conversion error: {e}")
            return False
            
    def video_to_gif(self, file_path: str) -> bool:
        """Convert video to GIF using FFmpeg (delegated to GifConverter)"""
        return self.gif_converter.video_to_gif(file_path)
    
    def _convert_video_multiple_variants(self, file_path: str) -> bool:
        """Convert video with multiple size and quality variants"""
        try:
            # Check if multiple size variants is enabled AND has variants
            multiple_size_variants = self.params.get('multiple_size_variants', False)
            video_variants = self.params.get('video_variants', [])
            if not multiple_size_variants or not video_variants:
                video_variants = []
            
            # Check if multiple qualities is enabled AND has variants
            multiple_qualities = self.params.get('multiple_qualities', False)
            quality_variants = self.params.get('quality_variants', [])
            if not multiple_qualities or not quality_variants:
                quality_variants = []
            
            # If no variants, fallback to single conversion
            if not video_variants and not quality_variants:
                return self.convert_video(file_path)
            
            # If only one type of variant, treat as single list
            if not video_variants:
                video_variants = [None]  # No size variants
            if not quality_variants:
                quality_variants = [None]  # No quality variants
            
            all_success = True
            total_combinations = len(video_variants) * len(quality_variants)
            current_combination = 0
            
            self.status_updated.emit(f"Creating {total_combinations} video variants")
            
            # Generate all combinations of size and quality variants
            for size_variant in video_variants:
                if self.should_stop:
                    break
                for quality_variant in quality_variants:
                    if self.should_stop:
                        break
                    current_combination += 1
                    
                    try:
                        # Determine output format based on codec
                        format_map = {
                            'H.264 (MP4)': 'mp4',
                            'H.265 (MP4)': 'mp4', 
                            'WebM (VP9, faster)': 'webm',
                            'WebM (AV1, slower)': 'webm',
                            'AV1 (MP4)': 'mp4'
                        }
                        selected_codec = self.params.get('codec', 'H.264 (MP4)')
                        output_format = format_map.get(selected_codec, 'mp4')
                        
                        # Generate output path with both size and quality variant suffixes
                        output_path = self.get_output_path_with_video_variants(file_path, output_format, size_variant, quality_variant)
                        
                        # Ensure output directory exists
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        
                        if not self.params.get('overwrite', False) and os.path.exists(output_path):
                            self.status_updated.emit(f"Skipping existing file: {os.path.basename(output_path)}")
                            continue
                        
                        variant_desc = []
                        if size_variant:
                            variant_desc.append(f"Size: {size_variant}")
                        if quality_variant is not None:
                            variant_desc.append(f"Quality: {quality_variant}")
                        variant_info = ", ".join(variant_desc) if variant_desc else "default"
                        
                        self.status_updated.emit(f"Processing variant {current_combination}/{total_combinations}: {variant_info}")
                        
                        # Prepare video input
                        input_args = {}
                        
                        # Handle time cutting first (apply to input)
                        enable_time_cutting = self.params.get('enable_time_cutting', False)
                        if enable_time_cutting:
                            time_start = self.params.get('time_start', 0.0)
                            time_end = self.params.get('time_end', 1.0)
                            if time_start is not None and time_end is not None and time_start < time_end:
                                video_duration = get_video_duration(file_path)
                                if video_duration and video_duration > 0:
                                    start_time = time_start * video_duration
                                    end_time = time_end * video_duration
                                    input_args['ss'] = start_time
                                    input_args['to'] = end_time
                        
                        input_stream = ffmpeg.input(file_path, **input_args)
                        video_stream = input_stream.video
                        
                        # Check if video has audio stream before creating reference
                        has_audio = has_audio_stream(file_path)
                        audio_stream = input_stream.audio if has_audio else None
                        
                        # Apply retime (speed change) after cutting and before other filters
                        retime_enabled = self.params.get('retime_enabled') or self.params.get('enable_retime')
                        retime_speed = self.params.get('retime_speed', 1.0)
                        if retime_enabled and retime_speed and retime_speed != 1.0:
                            try:
                                speed = float(retime_speed)
                                speed = max(0.1, min(3.0, speed))
                                self.status_updated.emit(f"DEBUG: Applying retime at {speed:.2f}x to variant")
                                video_stream = video_stream.filter('setpts', f'PTS/{speed}')
                                if audio_stream is not None:
                                    try:
                                        if speed <= 2.0:
                                            audio_stream = audio_stream.filter('atempo', speed)
                                        else:
                                            # Chain atempo to stay within valid range
                                            audio_stream = audio_stream.filter('atempo', 2.0).filter('atempo', speed / 2.0)
                                    except Exception as audio_err:
                                        self.status_updated.emit(f"DEBUG: Skipping audio retime: {audio_err}")
                                        audio_stream = None
                            except Exception as e:
                                self.status_updated.emit(f"DEBUG: Skipping retime: {e}")
                        
                        # Video encoding options
                        codec_map = {
                            'H.264 (MP4)': 'libx264',
                            'H.265 (MP4)': 'libx265', 
                            'WebM (VP9, faster)': 'libvpx-vp9',
                            'WebM (AV1, slower)': 'libaom-av1',
                            'AV1 (MP4)': 'libaom-av1'
                        }
                        
                        codec = codec_map.get(selected_codec, 'libx264')
                        output_args = {'vcodec': codec}
                        
                        # For WebM/VP9/AV1, we need to handle audio codec and format-specific parameters
                        if selected_codec in ['WebM (VP9, faster)', 'WebM (AV1, slower)']:
                            # WebM: Strip audio completely (no audio stream)
                            variant_audio_stream = None  # Remove audio stream
                            output_args['an'] = None  # No audio flag
                            output_args['f'] = 'webm'  # WebM container format
                            
                            # Apply CRF quality for VP9
                            if quality_variant is not None:
                                output_args['crf'] = map_ui_quality_to_crf(quality_variant, codec)
                            
                            # Optimize AV1 speed
                            if codec == 'libaom-av1':
                                output_args['cpu-used'] = 4
                        else:
                            # For MP4 codecs, ensure MP4 format
                            output_args['f'] = 'mp4'
                            
                            # Apply CRF quality for MP4 codecs
                            if quality_variant is not None:
                                output_args['crf'] = map_ui_quality_to_crf(quality_variant, codec)
                            
                            # Optimize AV1 speed for MP4 container too
                            if codec == 'libaom-av1':
                                output_args['cpu-used'] = 4
                                
                        # Frame rate (always use original as per user request)
                        # fps = self.params.get('fps', 'Keep Original')
                        # if fps != 'Keep Original':
                        #     output_args['r'] = fps
                        
                        # Apply video size variant
                        if size_variant:
                            original_width, original_height = get_video_dimensions(file_path)
                            
                            if str(size_variant).startswith('L'):
                                # Longer edge resize
                                target_longer_edge = int(str(size_variant)[1:])
                                longer_edge = max(original_width, original_height)
                                
                                # Don't upscale if longer edge is already smaller than target
                                if longer_edge >= target_longer_edge:
                                    if original_width > original_height:
                                        # Width is longer: scale by width
                                        video_stream = ffmpeg.filter(video_stream, 'scale', target_longer_edge, -2, flags='lanczos')
                                    else:
                                        # Height is longer: scale by height
                                        video_stream = ffmpeg.filter(video_stream, 'scale', -2, target_longer_edge, flags='lanczos')
                            elif str(size_variant).endswith('%'):
                                # Percentage resize
                                percent = float(str(size_variant)[:-1]) / 100
                                scale_w = f"trunc(iw*{percent}/2)*2"
                                scale_h = f"trunc(ih*{percent}/2)*2"
                                video_stream = ffmpeg.filter(video_stream, 'scale', scale_w, scale_h)
                            else:
                                # Width-based resize (maintain aspect ratio)
                                new_width = int(size_variant)
                                video_stream = ffmpeg.filter(video_stream, 'scale', str(new_width), '-2')  # -2 maintains aspect ratio and ensures even height
                        
                        # Combine video and audio streams for output
                        if audio_stream is not None:
                            output = ffmpeg.output(video_stream, audio_stream, output_path, **output_args)
                        else:
                            output = ffmpeg.output(video_stream, output_path, **output_args)
                        
                        if self.params.get('overwrite', False):
                            output = ffmpeg.overwrite_output(output)
                        
                        # Check for cancellation
                        if self.should_stop:
                            return False
                            
                        # Run video conversion with cancellation support
                        self.run_ffmpeg_with_cancellation(output)
                        
                        self.file_completed.emit(file_path, output_path)
                        self.status_updated.emit(f"✓ Video variant {variant_info} completed")
                        
                    except Exception as e:
                        # More detailed FFmpeg error reporting
                        error_msg = f"FFmpeg error with video variant {current_combination}: {str(e)}"
                        self.status_updated.emit(error_msg)
                        all_success = False
                        continue
                    except Exception as e:
                        self.status_updated.emit(f"Error with video variant {current_combination}: {str(e)}")
                        all_success = False
                        continue
            
            if self.should_stop:
                self.status_updated.emit(f"Video variants conversion stopped by user: {current_combination}/{total_combinations} completed")
            else:
                self.status_updated.emit(f"Video variants completed: {total_combinations} files created")
            
            return all_success
            
        except Exception as e:
            self.status_updated.emit(f"Error in video multiple variants conversion: {str(e)}")
            return False
    
    def get_output_path(self, file_path: str, format_ext: str) -> str:
        """Generate output path for converted file"""
        return SuffixManager.get_output_path(file_path, self.params, format_ext)

    def get_output_path_with_video_variants(self, file_path: str, format_ext: str, size_variant: str = None, quality_variant: int = None) -> str:
        """Generate output path for video variant with size and quality suffixes"""
        variants = []
        if size_variant:
            variants.append({'type': 'size', 'value': size_variant})
        if quality_variant is not None:
             variants.append({'type': 'quality', 'value': quality_variant})
             
        return SuffixManager.get_output_path(file_path, self.params, format_ext, variants)

    def get_output_path_with_variants(self, file_path: str, format_ext: str, quality_variant: int = None, size_variant: str = None) -> str:
        """Generate output path for image variants with quality and resize"""
        variants = []
        if quality_variant is not None:
             variants.append({'type': 'quality', 'value': quality_variant})
        if size_variant:
             variants.append({'type': 'resize', 'value': size_variant})
             
        return SuffixManager.get_output_path(file_path, self.params, format_ext, variants)


        
    def stop_conversion(self):
        """Stop the conversion process"""
        self.should_stop = True


class ToolChecker:
    """Check if required tools are available"""
    
    @staticmethod
    def check_ffmpeg() -> bool:
        """Check if FFmpeg is available"""
        try:
            ffmpeg_path = get_bundled_tool_path('ffmpeg')
            kwargs = get_subprocess_kwargs()
            kwargs['timeout'] = 5
            result = subprocess.run([ffmpeg_path, '-version'], **kwargs)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
            
    @staticmethod
    def get_tool_status() -> Dict[str, bool]:
        """Get status of all tools"""
        return {
            'ffmpeg': ToolChecker.check_ffmpeg()
        }
        
    @staticmethod
    def get_detailed_status() -> Dict[str, str]:
        """Get detailed status information"""
        status = {}
        
        # Check FFmpeg
        try:
            ffmpeg_path = get_bundled_tool_path('ffmpeg')
            kwargs = get_subprocess_kwargs()
            kwargs['timeout'] = 5
            result = subprocess.run([ffmpeg_path, '-version'], **kwargs)
            if result.returncode == 0:
                # Extract version from first line
                first_line = result.stdout.split('\n')[0]
                status['ffmpeg'] = f"Available - {first_line}"
            else:
                status['ffmpeg'] = "Not working properly"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            status['ffmpeg'] = "Not found - Please install FFmpeg"
            
        # ImageMagick and Pillow not needed - using FFmpeg for everything
        status['imagemagick'] = "Not needed - Using FFmpeg for all image/video processing"
                
        return status


def verify_bundled_tools(timeout: int = 5) -> Dict[str, Dict[str, Optional[str]]]:
    """Run a quick verification of bundled tools by calling their version commands.

    Returns a mapping of tool -> {path, returncode, stdout, stderr}.
    This function intentionally does not raise on missing tools; it's a runtime probe helper.
    """
    tools = ['ffmpeg']
    results: Dict[str, Dict[str, Optional[str]]] = {}

    # load expected checksums from cache if available
    expected_checks = {}
    try:
        if os.path.isdir(_USER_BIN_CACHE):
            checks_path = os.path.join(_USER_BIN_CACHE, 'checksums.json')
            if os.path.exists(checks_path):
                try:
                    expected_checks = json.load(open(checks_path, 'r', encoding='utf-8'))
                except Exception:
                    expected_checks = {}
    except Exception:
        expected_checks = {}

    for t in tools:
        path = get_bundled_tool_path(t)
        cmd = [path, '-version'] if t == 'ffmpeg' else [path, '--version']
        try:
            kwargs = get_subprocess_kwargs()
            kwargs['timeout'] = timeout
            proc = subprocess.run(cmd, **kwargs)
            results[t] = {
                'path': path,
                'returncode': proc.returncode,
                'stdout': proc.stdout.strip() if proc.stdout else '',
                'stderr': proc.stderr.strip() if proc.stderr else ''
            }
            # compute checksum if file exists and is a real path (not bare name)
            try:
                if os.path.exists(path) and os.path.isfile(path):
                    sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
                    results[t]['sha256'] = sha
                    exp = expected_checks.get(os.path.basename(path)) if isinstance(expected_checks, dict) else None
                    if exp:
                        results[t]['expected_sha256'] = exp
                        results[t]['checksum_match'] = (sha.lower() == str(exp).lower())
            except Exception:
                pass
        except FileNotFoundError:
            results[t] = {'path': path, 'returncode': None, 'stdout': None, 'stderr': 'not found'}
        except subprocess.TimeoutExpired:
            results[t] = {'path': path, 'returncode': None, 'stdout': None, 'stderr': 'timeout'}
        except Exception as e:
            results[t] = {'path': path, 'returncode': None, 'stdout': None, 'stderr': str(e)}

    return results

