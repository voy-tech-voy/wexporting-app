# Target Size Conversion Architecture

## Overview

The target size conversion system uses a **Strategy Pattern** with **self-contained estimators** that own their complete encoding pipeline. Each estimator version is an independent strategy that can define multi-step operations like 2-pass encoding, custom filter chains, and different encoding modes.

---

## Design Pattern: Strategy Pattern

Each estimator is a **strategy** that encapsulates:
1. **Parameter estimation** - Calculate optimal encoding parameters for target size
2. **Execution pipeline** - Complete encoding workflow (analyze, scale, encode)

This allows different versions (v2, v3, v4...) to use completely different approaches:
- v2: 2-pass CBR encoding
- v3 (future): CRF mode with custom filters
- v4 (future): Single-pass encoding with adaptive bitrate

---

## Architecture Components

### 1. EstimatorProtocol (Abstract Base Class)

**File:** [`_estimator_protocol.py`](file:///v:/_MY_APPS/ImgApp_1/client/core/target_size/_estimator_protocol.py)

Defines the interface all estimators must implement:

```python
class EstimatorProtocol(ABC):
    @abstractmethod
    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict[str, Any]:
        """Calculate optimal encoding parameters for target size."""
        pass
    
    @abstractmethod
    def execute(self, input_path: str, output_path: str, target_size_bytes: int,
                status_callback=None, stop_check=None, **options) -> bool:
        """Execute the complete encoding pipeline."""
        pass
    
    @property
    def version(self) -> str:
        """Return version identifier (e.g., 'v2')."""
        pass
    
    def get_output_extension(self) -> str:
        """Return output file extension (e.g., 'mp4', 'webm')."""
        pass
```

---

### 2. Estimator Registry

**File:** [`size_estimator_registry.py`](file:///v:/_MY_APPS/ImgApp_1/client/core/target_size/size_estimator_registry.py)

**Responsibilities:**
- Load estimator classes dynamically based on format and version
- Provide public API for conversions: `run_video_conversion()`, `run_image_conversion()`
- Manage active estimator version (v2, v5, etc.)

**Key Functions:**

```python
def get_video_estimator(codec_pref: str) -> EstimatorProtocol:
    """Load video estimator for specified codec."""
    
def run_video_conversion(input_path, output_path, target_size_bytes, codec_pref, **options) -> bool:
    """Execute video conversion using appropriate estimator."""
    
def get_image_estimator(output_format: str) -> EstimatorProtocol:
    """Load image estimator for specified format."""
    
def run_image_conversion(input_path, output_path, target_size_bytes, output_format, **options) -> bool:
    """Execute image conversion using appropriate estimator."""
```

**Codec Normalization:**
- `_normalize_video_codec()` - Maps UI codec names to estimator keys
  - "MP4 (H.264)" → `mp4_h264`
  - "MP4 (H.265)" → `mp4_h265`
  - "WebM (VP9)" → `webm_vp9`
  - "WebM (AV1)" → `webm_av1`

---

### 3. Conversion Engine (Orchestrator)

**File:** [`target_size_conversion_engine.py`](file:///v:/_MY_APPS/ImgApp_1/client/core/target_size/target_size_conversion_engine.py)

**Responsibilities:**
- Iterate through files and target size variants
- Validate file types match conversion mode
- Emit progress signals to UI
- Delegate actual encoding to estimators via registry

**Flow:**
```
run() 
  → _determine_conversion_mode()
  → _is_compatible_file()
  → _convert_video() / _convert_image() / _convert_loop()
    → registry.run_*_conversion()
      → estimator.execute()
```

**File Type Validation:**
- Image mode: Only processes image files (JPG, PNG, WebP, etc.)
- Video mode: Only processes video files (MP4, WebM, AVI, etc.)
- Loop mode: Accepts both videos and GIFs

---

### 4. Estimator Implementations

#### Video Estimators

**Directory:** `video_estimators/`

| File | Codec | Strategy | Efficiency |
|------|-------|----------|------------|
| `mp4_h264_estimator_v2.py` | H.264 | 2-pass CBR | 1.0x (baseline) |
| `mp4_h265_estimator_v2.py` | H.265/HEVC | 2-pass CBR | 1.5x |
| `webm_vp9_estimator_v2.py` | VP9 | 2-pass CBR (no audio) | 1.3x |
| `webm_av1_estimator_v2.py` | AV1 | 2-pass CBR (no audio) | 1.8x |

**Common Pattern:**
```python
class Estimator(EstimatorProtocol):
    def estimate(self, input_path, target_size_bytes, **options):
        # 1. Get media metadata
        # 2. Calculate bitrate budget
        # 3. Determine resolution scaling
        # 4. Return parameters dict
        
    def execute(self, input_path, output_path, target_size_bytes, **options):
        # 1. Get parameters from estimate()
        # 2. Build ffmpeg stream with filters
        # 3. PASS 1: Analyze (output to null)
        # 4. PASS 2: Encode (output to file)
        # 5. Verify output and return success
```

#### Image Estimators

**Directory:** `image_estimators/`

| File | Format | Strategy |
|------|--------|----------|
| `jpg_estimator_v5.py` | JPG | Binary search on qscale |
| `png_estimator_v5.py` | PNG | Binary search on compression_level |
| `webp_estimator_v5.py` | WebP | Binary search on quality |

**Common Pattern:**
```python
class Estimator(EstimatorProtocol):
    def estimate(self, input_path, target_size_bytes, **options):
        # Binary search to find optimal quality parameter
        # Returns: {'quality': X, 'scale': Y}
        
    def execute(self, input_path, output_path, target_size_bytes, **options):
        # 1. Get parameters from estimate()
        # 2. Build ffmpeg command with scaling/rotation
        # 3. Execute encoding
        # 4. Verify output
```

---

## How to Add a New Estimator

### Example: Adding H.264 v3 with CRF Mode

**1. Create estimator file:**
```
video_estimators/mp4_h264_estimator_v3.py
```

**2. Implement EstimatorProtocol:**

```python
from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata
import ffmpeg
import os

class Estimator(EstimatorProtocol):
    @property
    def version(self) -> str:
        return "v3"
    
    @property
    def description(self) -> str:
        return "H.264 CRF mode with custom filters"
    
    def get_output_extension(self) -> str:
        return "mp4"
    
    def estimate(self, input_path: str, target_size_bytes: int, **options):
        """Calculate CRF value based on target size."""
        meta = get_media_metadata(input_path)
        
        # Your custom estimation logic
        target_bpp = (target_size_bytes * 8) / (meta['width'] * meta['height'] * meta['frame_count'])
        crf = self._bpp_to_crf(target_bpp)
        
        return {
            'crf': crf,
            'preset': 'medium',
            'codec': 'libx264'
        }
    
    def execute(self, input_path: str, output_path: str, target_size_bytes: int,
                status_callback=None, stop_check=None, **options) -> bool:
        """Execute CRF encoding with optional filters."""
        
        def emit(msg):
            if status_callback:
                status_callback(msg)
        
        params = self.estimate(input_path, target_size_bytes, **options)
        
        # Build stream with custom filters
        stream = ffmpeg.input(input_path)
        
        # Apply custom filters (denoise, sharpen, etc.)
        if options.get('denoise'):
            stream = ffmpeg.filter(stream, 'hqdn3d')
        
        # Encode with CRF
        stream = ffmpeg.output(
            stream, 
            output_path,
            vcodec='libx264',
            crf=params['crf'],
            preset=params['preset']
        )
        
        try:
            ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
            emit(f"✓ Encoded with CRF {params['crf']}")
            return os.path.exists(output_path)
        except ffmpeg.Error as e:
            emit(f"✗ Encoding failed: {e.stderr.decode()[:200]}")
            return False

# Backward compatibility
_estimator = Estimator()
def optimize_video_params(file_path, target_size_bytes, **kwargs):
    return _estimator.estimate(file_path, target_size_bytes, **kwargs)
```

**3. Registry automatically detects it:**
- File naming: `{format}_estimator_{version}.py`
- Class name: `Estimator`
- The registry scans for `mp4_h264_estimator_v*.py` files

**4. UI automatically shows v3 in dropdown** (dev mode)

---

## Key Design Decisions

### 1. Self-Contained Estimators
**Why:** Each version can use completely different encoding strategies without affecting others.

**Before:**
```
estimator.py → calculate params
encoder.py → hardcoded 2-pass encoding
```

**After:**
```
estimator_v2.py → calculate params + 2-pass encoding
estimator_v3.py → calculate params + CRF encoding
```

### 2. Strategy Pattern
**Why:** Easy to add new versions, test different approaches, and maintain backward compatibility.

### 3. Registry-Based Loading
**Why:** Dynamic discovery of estimators, version switching without code changes.

### 4. Separation of Concerns
- **Estimator:** Encoding strategy
- **Registry:** Discovery and loading
- **Engine:** Orchestration and progress
- **UI:** User interaction

### 5. Version Suffix Selection Flow
**Why:** The output filename suffix should reflect the estimator version selected in the UI dropdown, not the hardcoded version in the estimator file.

**Flow:**
```
UI Dropdown Selection
  → Tab.get_params() includes 'estimator_version'
  → ConversionEngine receives params with version
  → SuffixManager.generate_target_size_suffix()
    → Checks params['estimator_version'] FIRST (UI selection)
    → Falls back to optimal['estimator_version'] (estimator's version)
  → Filename: {base}_v2_TargetSize1MB_1920x1080.mp4
```

**Implementation:**
1. **UI Tabs** (`video_tab.py`, `image_tab.py`, `loop_tab.py`):
   ```python
   def get_params(self) -> dict:
       params = {
           # ... other params ...
           'estimator_version': self.estimator_version_combo.currentText() 
                                if self.estimator_version_combo.isVisible() 
                                else None,
       }
   ```

2. **Suffix Manager** (`suffix_manager.py`):
   ```python
   # Prioritize UI selection from params, fallback to estimator's version
   version_str = ""
   if params and 'estimator_version' in params and params['estimator_version']:
       version_str = f"_{params['estimator_version']}"
   elif optimal and 'estimator_version' in optimal:
       version_str = f"_{optimal['estimator_version']}"
   ```

**Result:** When user selects v2 in dropdown → filename shows `_v2`, even if using `mp4_h264_estimator_v3.py`

---

## Error Handling

### Video Estimators
```python
try:
    ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
except ffmpeg.Error as e:
    error_msg = e.stderr.decode() if e.stderr else str(e)
    emit(f"Pass 1 failed: {error_msg[:200]}")
    return False
```

### Common Issues
1. **Invalid codec options** → Use `capture_stderr=True` to see errors
2. **Blocking execution** → Use `ffmpeg.run()` not `run_async()` with `quiet=True`
3. **0KB output files** → Check for invalid parameters in encode_args

---

## Testing New Estimators

1. **Enable dev mode** in UI to see version dropdown
2. **Select your new version** (e.g., v3)
3. **Test with various inputs:**
   - Different resolutions
   - Different durations
   - Different target sizes
4. **Check output:**
   - File size matches target
   - Quality is acceptable
   - No encoding errors

---

## Future Enhancements

### Possible v3 Features
- **CRF mode** instead of CBR
- **Custom filter chains** (denoise, sharpen, color correction)
- **Single-pass encoding** for faster processing
- **Adaptive bitrate** based on scene complexity
- **Hardware acceleration** (NVENC, QSV, AMF)

### Adding New Formats
1. Create estimator: `{format}_estimator_v2.py`
2. Implement `EstimatorProtocol`
3. Add format to `_normalize_video_codec()` or image format detection
4. Registry automatically discovers it

---

## File Structure

```
target_size/
├── target_size_architecture.md  # This file (architecture documentation)
├── _estimator_protocol.py       # ABC for all estimators
├── _common.py                   # Shared utilities (get_media_metadata)
├── size_estimator_registry.py  # Dynamic loading and version management
├── target_size_conversion_engine.py  # Orchestrator
├── suffix_manager.py            # Output filename generation
├── video_estimators/
│   ├── mp4_h264_estimator_v2.py
│   ├── mp4_h264_estimator_v3.py
│   ├── mp4_h265_estimator_v2.py
│   ├── mp4_h265_estimator_v3.py
│   ├── webm_vp9_estimator_v2.py
│   ├── webm_vp9_estimator_v3.py
│   ├── webm_av1_estimator_v2.py
│   └── webm_av1_estimator_v3.py
├── image_estimators/
│   ├── jpg_estimator_v5.py
│   ├── png_estimator_v5.py
│   └── webp_estimator_v5.py
└── loop_estimators/
    └── gif_estimator_v2.py
```

---

## Summary

The target size conversion system is built on the **Strategy Pattern**, where each estimator version is a self-contained strategy that owns its complete encoding pipeline. This design provides:

✅ **Flexibility** - Easy to add new encoding strategies  
✅ **Maintainability** - Each version is independent  
✅ **Testability** - Test versions in isolation  
✅ **Extensibility** - Add new formats/codecs without touching existing code  
✅ **Backward Compatibility** - Old versions continue to work
