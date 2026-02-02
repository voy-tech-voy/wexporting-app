# Video Estimator Development Guide

## Overview

This guide provides a complete template for creating new video estimators for the target size conversion system. Estimators calculate optimal encoding parameters and execute the actual video conversion.

---

## File Naming Convention

**Pattern:** `{codec_key}_estimator_{version}.py`

**Examples:**
- `mp4_h264_estimator_v3.py` - H.264/MP4 estimator version 3
- `webm_av1_estimator_v4.py` - AV1/WebM estimator version 4
- `mp4_h265_estimator_v2.py` - H.265/MP4 estimator version 2
- `webm_vp9_estimator_v3.py` - VP9/WebM estimator version 3

**Location:** `client/core/target_size/video_estimators/`

---

## Class Naming Convention

**CRITICAL:** The class MUST be named `Estimator` (not the codec name).

```python
# ✅ CORRECT
class Estimator(EstimatorProtocol):
    """VP9 Video Estimator v2"""
    pass

# ❌ WRONG - Registry won't find it!
class WebMVP9EstimatorV2(EstimatorProtocol):
    pass
```

**Why:** The registry dynamically loads estimators and looks for a class named `Estimator` in each module.

---

## Required Methods

### 1. `get_output_extension() -> str`

Returns the file extension for output files.

```python
def get_output_extension(self) -> str:
    """Return the output file extension."""
    return 'webm'  # or 'mp4', 'mkv', etc.
```

**Common extensions:**
- H.264, H.265 → `'mp4'`
- VP9, AV1 → `'webm'`
- ProRes → `'mov'`

### 2. `get_media_metadata(file_path: str) -> dict`

Extracts video metadata for estimation calculations.

```python
def get_media_metadata(self, file_path: str) -> dict:
    try:
        probe = ffmpeg.probe(file_path)
        video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        audio = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
        fmt = probe['format']
        
        duration = float(fmt.get('duration', 0))
        if duration == 0 and video:
            duration = float(video.get('duration', 0))
        
        width = int(video.get('width', 0))
        height = int(video.get('height', 0))
        
        # Parse frame rate
        fps = 30.0
        if video and 'r_frame_rate' in video:
            parts = video['r_frame_rate'].split('/')
            if len(parts) == 2 and int(parts[1]) > 0:
                fps = int(parts[0]) / int(parts[1])
            else:
                fps = float(video['r_frame_rate'])
        
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
```

### 3. `estimate(input_path: str, target_size_bytes: int, **options) -> Dict`

Calculates optimal encoding parameters to hit the target file size.

```python
def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
    """
    Calculate optimal encoding parameters.
    
    Args:
        input_path: Path to input video
        target_size_bytes: Target output size in bytes
        **options: Additional options (allow_downscale, rotation, etc.)
    
    Returns:
        Dict with encoding parameters or {} if estimation fails
    """
    meta = self.get_media_metadata(input_path)
    if meta['duration'] == 0:
        return {}
    
    allow_downscale = options.get('allow_downscale', False)
    
    # 1. Calculate bitrate budget
    container_overhead = 0.95  # 5% overhead for container
    total_bits = target_size_bytes * 8 * container_overhead
    
    # 2. Audio budget
    audio_kbps = 128 if meta['has_audio'] else 0
    audio_bits = (audio_kbps * 1000) * meta['duration']
    
    # 3. Video budget
    video_bits = total_bits - audio_bits
    video_bps = max(video_bits / meta['duration'], 10000)  # Floor at 10kbps
    
    # 4. Resolution optimization (optional)
    width = meta['width']
    height = meta['height']
    
    if allow_downscale:
        # Calculate bits per pixel (BPP)
        target_bpp = 0.05  # Adjust based on codec efficiency
        
        def get_bpp(w, h):
            pixels = w * h
            return video_bps / (pixels * meta['fps'])
        
        # Scale down if BPP is too low
        while get_bpp(width, height) < target_bpp and width > 426:
            width = int(width * 0.85)
            height = int(height * 0.85)
            # Ensure even dimensions
            width = width - (width % 2)
            height = height - (height % 2)
    
    return {
        'video_bitrate_kbps': int(video_bps / 1000),
        'audio_bitrate_kbps': audio_kbps,
        'resolution_w': width,
        'resolution_h': height,
        'codec': 'libx264'  # Codec identifier
    }
```

### 4. `execute(input_path, output_path, target_size_bytes, status_callback, stop_check, **options) -> bool`

Executes the actual video conversion with interruptible execution.

**CRITICAL:** Must follow the interruptible execution pattern (see `INTERRUPTIBLE_EXECUTION_GUIDE.md`).

```python
def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
            status_callback=None, stop_check=None, **options) -> bool:
    """
    Execute video conversion with interruptible execution.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        target_size_bytes: Target size in bytes
        status_callback: Function to call with status updates
        stop_check: Function that returns True if conversion should stop
        **options: Additional options
    
    Returns:
        True if successful, False otherwise
    """
    import subprocess
    import threading
    import time
    
    def emit(msg: str):
        """Send status update to UI."""
        if status_callback:
            status_callback(msg)
    
    def should_stop() -> bool:
        """Check if user requested stop."""
        return stop_check() if stop_check else False
    
    def drain_pipe(pipe, collected: list):
        """Drain pipe in background to prevent deadlock."""
        try:
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    break
                collected.append(chunk)
        except:
            pass
    
    # Get encoding parameters
    params = self.estimate(input_path, target_size_bytes, **options)
    if not params:
        emit("Estimation failed")
        return False
    
    try:
        # Build FFmpeg arguments
        encode_args = {
            'vcodec': params['codec'],
            'b:v': f"{params['video_bitrate_kbps']}k",
            'c:a': 'aac',
            'b:a': f"{params['audio_bitrate_kbps']}k"
        }
        
        # Add scaling if needed
        if params['resolution_w'] != params.get('original_width', params['resolution_w']):
            encode_args['vf'] = f"scale={params['resolution_w']}:{params['resolution_h']}"
        
        # Build stream
        stream = ffmpeg.input(input_path).output(output_path, **encode_args)
        stream = ffmpeg.overwrite_output(stream)
        
        # Compile and execute with subprocess
        cmd = ffmpeg.compile(stream)
        emit("Encoding video...")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Start drain thread
        stderr_chunks = []
        drain_thread = threading.Thread(target=drain_pipe, args=(process.stderr, stderr_chunks))
        drain_thread.daemon = True
        drain_thread.start()
        
        # Monitor for stop signal
        while process.poll() is None:
            if should_stop():
                process.terminate()
                try:
                    process.wait(timeout=2)
                except:
                    process.kill()
                emit("Stopped by user")
                return False
            time.sleep(0.1)
        
        drain_thread.join(timeout=1)
        
        # Check result
        if process.returncode != 0:
            error_msg = b''.join(stderr_chunks).decode('utf-8', errors='ignore')
            emit(f"Encoding failed: {error_msg[-300:]}")
            return False
        
        if os.path.exists(output_path):
            actual_mb = os.path.getsize(output_path) / (1024 * 1024)
            emit(f"✓ Complete: {actual_mb:.2f} MB")
            return True
        else:
            emit("Output file not created")
            return False
        
    except Exception as e:
        emit(f"Error: {str(e)}")
        return False
```

---

## Multi-Pass Encoding

For 2-pass encoding (e.g., H.264, H.265), execute both passes sequentially:

```python
def execute(self, input_path, output_path, target_size_bytes, status_callback, stop_check, **options):
    # ... setup code ...
    
    # PASS 1: Analysis
    emit("Pass 1/2: Analyzing...")
    
    pass1_args = encode_args.copy()
    pass1_args['f'] = 'null'
    pass1_args['pass'] = 1
    
    null_output = 'NUL' if os.name == 'nt' else '/dev/null'
    pass1_stream = ffmpeg.input(input_path).output(null_output, **pass1_args)
    
    # Execute pass 1 with interruptible pattern
    success = self._execute_stream(pass1_stream, stop_check, emit)
    if not success:
        return False
    
    # PASS 2: Encoding
    emit("Pass 2/2: Encoding...")
    
    pass2_args = encode_args.copy()
    pass2_args['pass'] = 2
    pass2_stream = ffmpeg.input(input_path).output(output_path, **pass2_args)
    
    # Execute pass 2 with interruptible pattern
    return self._execute_stream(pass2_stream, stop_check, emit)
```

---

## Complete Template

```python
import os
import time
import subprocess
import threading
import ffmpeg
from typing import Dict
from client.core.target_size._estimator_protocol import EstimatorProtocol

class Estimator(EstimatorProtocol):
    """
    [Codec Name] Video Estimator v[X]
    Strategy: [Brief description of encoding strategy]
    """

    def get_output_extension(self) -> str:
        """Return output file extension."""
        return 'mp4'  # or 'webm', 'mkv', etc.

    def get_media_metadata(self, file_path: str) -> dict:
        # See implementation above
        pass

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        # See implementation above
        pass

    def execute(self, input_path: str, output_path: str, target_size_bytes: int,
                status_callback=None, stop_check=None, **options) -> bool:
        # See implementation above
        pass
```

---

## Checklist for New Estimators

- [ ] File named: `{codec_key}_estimator_{version}.py`
- [ ] Class named: `Estimator` (not codec-specific name)
- [ ] Implements `get_output_extension()` → returns correct extension
- [ ] Implements `get_media_metadata()` → extracts video info
- [ ] Implements `estimate()` → calculates bitrate/resolution
- [ ] Implements `execute()` → uses interruptible pattern
- [ ] Uses `subprocess.Popen` (NOT `ffmpeg.run()`)
- [ ] Has background drain thread for stderr
- [ ] Checks `stop_check()` in monitoring loop
- [ ] Sends status updates via `status_callback()`
- [ ] Returns `True` on success, `False` on failure

---

## Testing

1. Add file to `client/core/target_size/video_estimators/`
2. Restart application
3. Enable dev mode in settings
4. Select codec and version from dropdown
5. Run conversion and verify:
   - Correct estimator loads: `[ESTIMATOR] Using video_estimators/{file}.py`
   - Status updates appear in UI
   - Stop button works (interruptible)
   - Output file has correct extension
   - File size is close to target

---

## Common Pitfalls

1. **Wrong class name** → Registry can't find estimator
2. **Missing `get_output_extension()`** → Output file has no extension
3. **Using `ffmpeg.run()`** → Conversion not interruptible, may deadlock
4. **No drain thread** → FFmpeg blocks on full stderr buffer
5. **Not checking `stop_check()`** → Stop button doesn't work
6. **Hardcoded paths** → Use `os.name == 'nt'` for Windows/Unix differences
7. **Collision with Python keywords** → FFmpeg flags like `-pass` conflict with Python's `pass`.
   ❌ **WRONG:** `.output(..., pass_=1)` (Results in invalid `-pass_` flag)
   ✅ **CORRECT:** `.output(..., **{'pass': 1})` (Uses proper dictionary unpacking)
8. **Ambiguous Bitrate Flags** → Always use specific flags to avoid confusion.
   ❌ **WRONG:** `-b 1000k` (Ambiguous, may apply to audio or video)
   ✅ **CORRECT:** `-b:v 1000k` (Video) and `-b:a 128k` (Audio)
9. **SVT-AV1 Specific Constraints** → Some flags work differently in `libsvtav1`.
   ⚠️ **CRITICAL:** `maxrate` and `bufsize` are **NOT SUPPORTED** in ABR mode (`-b:v`). 
   They only work with CRF/CQP. Do not use them when targeting a specific file size.

---

## Advanced: Custom Encoding Logic

Estimators can implement any encoding strategy:

- **Single-pass CBR** (fast, less accurate)
- **2-pass VBR** (slower, more accurate)
- **Multi-stage encoding** (analysis → downscale → encode)
- **Codec-specific optimizations** (SVT-AV1 presets, x264 tunes)
- **Adaptive bitrate** (adjust based on content complexity)

The `execute()` method has full control over the encoding pipeline.

## Patterns for Complex/Multistep Workflows

For estimators requiring multiple sequential operations (e.g., analyze -> crop -> stabilize -> encode), use this pattern:

```python
def execute(self, input_path, output_path, target_size_bytes, status_callback, stop_check, **options):
    # 1. Helper for safe step execution
    def run_step(step_name, stream_builder):
        emit(f"Step: {step_name}...")
        
        # Build command
        cmd = ffmpeg.compile(stream_builder, overwrite_output=True)
        
        # Execute with interruptible pattern
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # ... standard drain/monitor logic ...
        
        if process.returncode != 0:
            raise RuntimeError(f"{step_name} failed")
            
        return True

    try:
        # Step 1: Detect crop parameters
        emit("Step 1/3: Analyzing crop...")
        # ... run ffmpeg cropdetect ...
        crop_params = parse_crop_detect_log(...)
        
        # Step 2: Stabilization pass
        emit("Step 2/3: Generating stabilization data...")
        # ... run vidstabdetect ...
        
        # Step 3: Final Encode
        emit("Step 3/3: Encoding with crop and stabilization...")
        stream = ffmpeg.input(input_path)
        stream = stream.filter('crop', **crop_params)
        stream = stream.filter('vidstabtransform')
        stream = ffmpeg.output(stream, output_path, **encode_args)
        
        run_step("Final Encode", stream)
        
        return True
        
    except Exception as e:
        emit(f"Workflow failed: {str(e)}")
        # Cleanup intermediate files if needed
        return False
```

### Key Principles for Multistep:
1. **Shared State:** Use variables (like `crop_params`) to pass data between steps.
2. **Intermediate Files:** Use temp files for intermediate outputs, clean them up in `finally` block.
3. **Fail Fast:** Check return code after *every* step.
4. **Unified Progress:** Update status to reflect "Step X/Y".
