"""
Conversion Logger
Captures detailed diagnostic and execution logs for FFmpeg operations
to the standard persistent log directory (AppData).
"""

import time
import logging
from typing import Optional, Dict, Any

from client.utils.error_reporter import get_error_reporter, log_error

class ConversionLogSession:
    """Represents a single conversion attempt."""
    def __init__(self, mode: str, command: str, input_info: str = "Unknown"):
        self.mode = mode
        self.command = command
        self.input_info = input_info
        self.start_time = time.time()
        
def log_conversion_start(mode: str, command: str, input_info: str = "Unknown") -> ConversionLogSession:
    """
    Log the start of a conversion.
    Returns a session object to be passed to success/error loggers.
    """
    reporter = get_error_reporter()
    if reporter and reporter.logger:
        reporter.logger.info(f"[{mode.upper()} CONVERSION START] Target: {input_info}")
        reporter.logger.info(f"[{mode.upper()} COMMAND] {command}")
    
    return ConversionLogSession(mode, command, input_info)

def log_conversion_success(session: ConversionLogSession):
    """Log a successful conversion."""
    duration = time.time() - session.start_time
    reporter = get_error_reporter()
    if reporter and reporter.logger:
        reporter.logger.info(f"[{session.mode.upper()} CONVERSION SUCCESS] Completed in {duration:.2f}s: {session.input_info}")

def log_conversion_error(session: ConversionLogSession, stderr: str, return_code: int = -1):
    """
    Log a failed conversion and trigger an error report JSON 
    including the exact command and full stderr.
    """
    duration = time.time() - session.start_time
    reporter = get_error_reporter()
    
    # 1. Write the failure to the main app log
    if reporter and reporter.logger:
        reporter.logger.error(f"[{session.mode.upper()} CONVERSION FAILED] Code {return_code} after {duration:.2f}s: {session.input_info}")
        reporter.logger.error(f"[{session.mode.upper()} STDERR] --------\n{stderr}\n--------")
        
    # 2. Dump a dedicated diagnostic JSON for "Full Knowledge" of preset/manual failure
    additional_data = {
        "conversion_mode": session.mode,
        "input_target": session.input_info,
        "ffmpeg_command": session.command,
        "return_code": return_code,
        "stderr_output": stderr,
        "duration_seconds": round(duration, 2)
    }
    
    log_error(
        error=RuntimeError(f"FFmpeg Execution Failed ({return_code})"),
        context=f"conversion_engine_{session.mode}",
        additional_info=additional_data
    )
