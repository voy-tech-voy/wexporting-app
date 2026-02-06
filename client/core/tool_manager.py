"""
Tool management utilities for bundled FFmpeg and other tools
Extracted from legacy conversion_engine.py
"""

import os
import sys
import subprocess
import hashlib
import json
import tempfile
from typing import Dict, Optional

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


def get_bundled_tool_path(tool_name: str) -> str:
    """
    Locate a bundled tool executable, preferring a persistent per-user cache for onefile builds.

    Order of resolution:
    1. Persistent user cache (created by _ensure_bundled_tools_unpacked) when available
    2. PyInstaller extraction dir sys._MEIPASS (when frozen)
    3. Project bundled_tools folder (development)
    4. Fallback to tool name (system PATH)
    """
    global _USER_BIN_CACHE

    # Ensure .exe extension on Windows
    if os.name == 'nt' and not tool_name.endswith('.exe'):
        tool_name += '.exe'

    # 1. Check persistent user cache (if initialized)
    if _USER_BIN_CACHE and os.path.isdir(_USER_BIN_CACHE):
        candidate = os.path.join(_USER_BIN_CACHE, tool_name)
        if os.path.exists(candidate):
            return candidate

    # 2. Check PyInstaller extraction dir (frozen builds)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        candidate = os.path.join(sys._MEIPASS, 'tools', tool_name)
        if os.path.exists(candidate):
            return candidate

    # 3. Check project bundled_tools folder (development)
    candidate = os.path.join(bundled_tools_dir, tool_name)
    if os.path.exists(candidate):
        return candidate

    # 4. Fallback to bare name (system PATH)
    return tool_name


def get_subprocess_kwargs() -> dict:
    """
    Get subprocess kwargs to hide console windows on Windows
    """
    # Use encoding='utf-8' with errors='replace' instead of text=True
    # text=True uses local system encoding which might crash on some systems
    kwargs = {
        'capture_output': True, 
        'encoding': 'utf-8',
        'errors': 'replace'
    }
    
    if os.name == 'nt':  # Windows
        # Hide console window
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    
    return kwargs


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
