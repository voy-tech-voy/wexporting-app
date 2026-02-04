"""Base converter interface for manual mode"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import subprocess
import re


class BaseConverter(ABC):
    """
    Abstract base class for manual mode converters
    
    Follows the same pattern as target_size estimators but simplified
    for manual mode (no size estimation needed).
    """
    
    def __init__(self, params: Dict[str, Any], status_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[float], None]] = None):
        """
        Initialize converter
        
        Args:
            params: Conversion parameters from UI
            status_callback: Optional callback for status updates
            progress_callback: Optional callback for progress updates (0.0-1.0)
        """
        self.params = params
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.should_stop = False
        self.current_process = None
    
    @abstractmethod
    def convert(self, file_path: str, output_path: str) -> bool:
        """
        Convert a single file
        
        Args:
            file_path: Source file path (absolute)
            output_path: Output file path (absolute, from SuffixManager)
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> set:
        """
        Return set of supported file extensions (lowercase with dot)
        
        Example: {'.jpg', '.jpeg', '.png', '.webp'}
        """
        pass
    
    def emit_status(self, message: str):
        """Emit status update if callback available"""
        if self.status_callback:
            self.status_callback(message)
    
    def emit_progress(self, progress: float):
        """Emit progress update (0.0-1.0) if callback available"""
        if self.progress_callback:
            self.progress_callback(min(max(progress, 0.0), 1.0))
    
    def stop(self):
        """Request stop and kill current process if running"""
        self.should_stop = True
        if self.current_process:
            try:
                self.current_process.kill()
                self.current_process = None
            except Exception:
                pass
    
    def get_format_extension(self) -> str:
        """
        Get output format extension from params
        
        Returns:
            Format extension without dot (e.g., 'webp', 'mp4')
        """
        return self.params.get('format', 'jpg').lower()
    
    def run_ffmpeg_with_progress(self, ffmpeg_output, ffmpeg_cmd: str, total_duration: float) -> bool:
        """
        Run FFmpeg with real-time progress tracking
        
        Args:
            ffmpeg_output: ffmpeg-python output object
            ffmpeg_cmd: Path to FFmpeg executable
            total_duration: Total duration in seconds for progress calculation
            
        Returns:
            True if successful, False otherwise
        """
        import ffmpeg
        import threading
        
        # Get the command line arguments
        args = ffmpeg.compile(ffmpeg_output, cmd=ffmpeg_cmd)
        
        # Add progress flag for parseable output
        # Insert -progress pipe:1 after ffmpeg command
        args_list = list(args)
        args_list.insert(1, '-progress')
        args_list.insert(2, 'pipe:1')
        args_list.insert(3, '-nostats')
        
        stderr_output = []
        
        def read_stderr(proc, output_list):
            """Read stderr in separate thread to prevent deadlock"""
            try:
                for line in proc.stderr:
                    output_list.append(line)
            except:
                pass
        
        try:
            # Run FFmpeg as subprocess
            # Use CREATE_NO_WINDOW on Windows to hide console
            import sys
            startupinfo = None
            creationflags = 0
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            
            self.current_process = subprocess.Popen(
                args_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            # Start thread to read stderr (prevents deadlock on Windows)
            stderr_thread = threading.Thread(target=read_stderr, args=(self.current_process, stderr_output))
            stderr_thread.daemon = True
            stderr_thread.start()
            
            # Parse progress from stdout (pipe:1)
            time_pattern = re.compile(r'out_time_ms=(\d+)')
            
            while True:
                if self.should_stop:
                    self.current_process.kill()
                    return False
                
                line = self.current_process.stdout.readline()
                if not line:
                    break
                
                # Parse time progress
                time_match = time_pattern.search(line)
                if time_match and total_duration > 0:
                    current_time_ms = int(time_match.group(1))
                    current_time_s = current_time_ms / 1000000.0  # microseconds to seconds
                    progress = current_time_s / total_duration
                    self.emit_progress(progress)
                
                # Check for end marker
                if line.strip() == 'progress=end':
                    self.emit_progress(1.0)
                    break
            
            # Wait for process to complete
            self.current_process.wait()
            stderr_thread.join(timeout=1.0)
            
            if self.current_process.returncode != 0:
                stderr_text = ''.join(stderr_output)
                print(f"FFmpeg error: {stderr_text}")
                return False
            
            self.current_process = None
            return True
            
        except Exception as e:
            print(f"FFmpeg progress tracking error: {e}")
            import traceback
            traceback.print_exc()
            if self.current_process:
                self.current_process.kill()
                self.current_process = None
            return False
