---
description: How to execute FFmpeg to ensure anytime interruption and hide console popup
---
# Skill: Interruptible FFmpeg Execution (No Console)

**Goal**: Run FFmpeg (`subprocess.Popen`) to allow real-time progress parsing, anytime cancellation (`kill()`), and hidden execution (Windows). Do NOT use `ffmpeg.run()`.

## 1. References
- Executor Implementation: `client/core/manual_mode/converters/base_converter.py` (`run_ffmpeg_with_progress`)
- Generator Usage: `client/core/manual_mode/converters/video_converter.py`

## 2. Command Compilation & Progress Injection
Convert `ffmpeg` AST to a list and inject `pipe:1` parsing to ensure non-blocking continuous output.
```python
import ffmpeg
args_list = list(ffmpeg.compile(output_node, cmd=ffmpeg_path))
args_list.insert(1, '-progress')
args_list.insert(2, 'pipe:1')
args_list.insert(3, '-nostats')
```

## 3. Subprocess Execution (Silent Mode)
Use `CREATE_NO_WINDOW` on Windows to suppress `cmd.exe`. 
```python
import sys, subprocess

startupinfo = None
creationflags = 0
if sys.platform == 'win32':
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    creationflags = subprocess.CREATE_NO_WINDOW

process = subprocess.Popen(
    args_list,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    universal_newlines=True,
    bufsize=1,
    startupinfo=startupinfo,
    creationflags=creationflags
)
```

## 4. Asynchronous StdErr Drain
To prevent deadlocks on Windows (unconsumed `stderr` blocking the overall process), spin a daemon thread off immediately.
```python
import threading
stderr_output = []

def read_stderr(proc, out_list):
    try:
        for line in proc.stderr: out_list.append(line)
    except: pass

t = threading.Thread(target=read_stderr, args=(process, stderr_output), daemon=True)
t.start()
```

## 5. Progress Stream Loop & Cancellation Polling
Use `stdout.readline()` which unblocks often due to `-progress pipe:1`. Poll the external `should_stop` state per tick.
```python
import re
time_pattern = re.compile(r'out_time_ms=(\d+)')
should_stop = False # External Flag toggled by Cancel Request

while True:
    if should_stop: 
        process.kill()
        return False
        
    line = process.stdout.readline()
    if not line: break
    
    match = time_pattern.search(line)
    if match and total_duration > 0:
        current_time_s = int(match.group(1)) / 1000000.0  
        progress = current_time_s / total_duration
        # -> emit_progress(progress)

if process: process.wait()
t.join(timeout=1.0)
if process.returncode != 0: raise Exception("".join(stderr_output))
```

## 6. Handling Cancellation
Trigger interruption concurrently by setting the break flag and destroying the process at the OS-level.
```python
def cancel():
    should_stop = True
    if process: process.kill()
```
