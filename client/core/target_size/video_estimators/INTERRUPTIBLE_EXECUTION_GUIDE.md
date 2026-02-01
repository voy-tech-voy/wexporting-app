# Interruptible FFmpeg Execution Guide

## Overview

This guide documents the implementation pattern for executing FFmpeg commands in a way that allows reliable interruption (stopping) without deadlocks. This pattern applies to **all** video formats and estimators (H.264, H.265, VP9, AV1, GIFs, etc.).

---

## The Core Problem: Pipe Buffers

When you run FFmpeg and capture its output (stderr/stdout) to process progress or errors, you are using system pipes.

1. **FFmpeg writes to stderr** (progress info, logs)
2. **Pipe buffer fills up** (typically 64KB)
3. **FFmpeg blocks** waiting for the buffer to drain
4. **Python waits** for the process to finish
5. **Result:** DEADLOCK (Process hangs, cannot be stopped)

---

## The Solution: Background Drain Thread

To support interruption, we must:
1. Use `subprocess.Popen` instead of `ffmpeg.run()`
2. continuously read (drain) the pipe in a background thread
3. Monitor for stop signal in the main loop

### Universal Execution Pattern

```python
import subprocess
import threading
import ffmpeg
import os
import time

def execute_interruptible(stream, output_path, stop_check_callback):
    """
    Executes an FFmpeg stream with interruptibility.
    
    Args:
        stream: ffmpeg-python stream object
        output_path: Final output file path
        stop_check_callback: Function returning True if should stop
    """
    
    # 1. Define drain function
    def drain_pipe(pipe, collected_list):
        """Continuously read from pipe to prevent blocking."""
        try:
            while True:
                chunk = pipe.read(4096)  # Read 4KB at a time
                if not chunk:
                    break
                collected_list.append(chunk)
        except:
            pass
            
    # 2. Compile and Start Process
    cmd = ffmpeg.compile(stream, overwrite_output=True)
    
    # Use CREATE_NO_WINDOW on Windows to avoid console popups
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creation_flags
    )
    
    # 3. Start Drain Thread
    stderr_chunks = []
    drain_thread = threading.Thread(target=drain_pipe, args=(process.stderr, stderr_chunks))
    drain_thread.daemon = True  # Ensure thread dies if main process dies
    drain_thread.start()
    
    # 4. Monitoring Loop
    while process.poll() is None:
        # CHECK FOR INTERRUPTION
        if stop_check_callback and stop_check_callback():
            try:
                process.terminate()  # Polite stop
                process.wait(timeout=2)
            except:
                process.kill()       # Force stop
            return False, "Stopped by user"
            
        time.sleep(0.1)  # Small sleep to prevent CPU spinning
        
    # 5. Cleanup and Result
    drain_thread.join(timeout=1)  # Ensure we have all logs
    
    encoded_error = b''.join(stderr_chunks).decode('utf-8', errors='ignore')
    
    if process.returncode != 0:
        return False, encoded_error
        
    return True, None
```

---

## Usage Example (Any Codec)

Whether you are doing a 1-pass fast encode or a 2-pass high quality encode, the execution part remains the same.

```python
# Setup your specific encoding parameters (H.264, AV1, etc)
stream = ffmpeg.input('input.mp4')
stream = ffmpeg.output(stream, 'output.mp4', **my_codec_params)

# Run properly
success, error = execute_interruptible(stream, 'output.mp4', should_stop)

if not success:
    print(f"Error: {error}")
```

---

## checklist for Implementation

- [ ] **Import** `subprocess` and `threading`
- [ ] **Define** `drain_pipe` helper
- [ ] **Use** `subprocess.Popen` (NOT `ffmpeg.run`)
- [ ] **Start** drain thread immediately after Popen
- [ ] **Check** stop condition in `while process.poll() is None` loop
- [ ] **Clean up** by joining thread and checking return code
