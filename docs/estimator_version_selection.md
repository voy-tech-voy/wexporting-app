# Estimator Version Selection System

## Overview

The estimator version selection system provides smart, format-aware version resolution for image, video, and loop conversions. Each format/codec can have its own default version, and the system automatically selects the best version based on a well-defined fallback chain.

---

## Architecture

### Core Components

1. **PRODUCTION_DEFAULTS** (`config.py`)
   - Central configuration for default versions per format/codec
   - Easy to update when new estimator versions are released
   - Organized by media type (image, video, loop)

2. **Smart Version Resolution** (`size_estimator_registry.py`)
   - `_resolve_version()` function implements fallback chain
   - No global state pollution
   - Per-request version resolution

3. **Estimator Getters** (`size_estimator_registry.py`)
   - `get_video_estimator(codec_pref, version=None)`
   - `get_image_estimator(output_format, version=None)`
   - `get_loop_estimator(loop_format, version=None)`

---

## Version Resolution Fallback Chain

When an estimator is requested, the system resolves the version using this priority:

```
1. Explicit version from UI (dev mode override)
   ↓ (if None)
2. PRODUCTION_DEFAULTS for this specific format/codec
   ↓ (if not found)
3. Highest available version for this format/codec
   ↓ (if none exist)
4. DEFAULT_VERSION ('v2')
```

### Example Flow

**Scenario:** Loop tab requests WebM (AV1) estimator with no explicit version

```python
# User selects WebM (AV1) in Loop tab, dev mode is OFF
loop_format = "WebM (AV1)"
version = None  # No explicit version

# Registry normalizes format
format_key = _normalize_loop_format("WebM (AV1)")  # -> 'webm_av1_loop'

# Smart resolution
resolved = _resolve_version('loop', 'webm_av1_loop', None)
# Step 1: version is None, skip
# Step 2: PRODUCTION_DEFAULTS['loop']['webm_av1_loop'] = 'v6' ✓
# Returns: 'v6'

# Load estimator
estimator = _load_estimator_class('loop', 'webm_av1_loop', 'v6')
# Loads: loop_estimators/webm_av1_loop_estimator_v6.py
```

---

## Configuration

### Adding New Formats/Codecs

Edit `client/core/target_size/config.py`:

```python
PRODUCTION_DEFAULTS = {
    'image': {
        'jpg': 'v5',
        'webp': 'v6',
        'png': 'v5',
        # Add new format here
        'avif': 'v1',  # Example
    },
    'video': {
        'mp4_h264': 'v4',
        'mp4_h265': 'v4',
        'webm_vp9': 'v3',
        'webm_av1': 'v6',
        # Add new codec here
        'webm_vp8': 'v2',  # Example
    },
    'loop': {
        'gif': 'v4',
        'webm_loop': 'v2',
        'webm_av1_loop': 'v6',
        # Add new loop format here
    }
}
```

### Updating Default Versions

When a new estimator version is released and tested:

1. Create the new estimator file (e.g., `webm_av1_loop_estimator_v7.py`)
2. Test thoroughly
3. Update `PRODUCTION_DEFAULTS` in `config.py`:
   ```python
   'webm_av1_loop': 'v7',  # Changed from v6
   ```
4. The system will automatically use v7 for all new conversions

---

## Dev Mode Override

In development mode, users can manually select estimator versions via the UI dropdown. This overrides the production defaults.

### How It Works

```python
# Dev mode: User selects v5 from dropdown
version = 'v5'  # Explicit from UI

# Resolution
resolved = _resolve_version('loop', 'webm_av1_loop', 'v5')
# Step 1: version='v5' is provided ✓
# Returns: 'v5' (skips all other steps)
```

### UI Integration

Each tab has an estimator version selector that:
- Only visible in dev mode
- Automatically populates based on available estimator files
- Defaults to highest version
- Passes selected version to `get_*_estimator()`

---

## File Naming Convention

Estimator files must follow this pattern:

```
{format_key}_estimator_{version}.py
```

**Examples:**
- `webm_av1_loop_estimator_v6.py`
- `mp4_h264_estimator_v4.py`
- `webp_estimator_v6.py`
- `gif_estimator_v4.py`

The system scans for these files using glob patterns and extracts version numbers automatically.

---

## Format/Codec Normalization

The system normalizes user-facing format/codec names to internal keys:

### Image Formats

| User Input | Normalized Key |
|------------|----------------|
| "JPG", "JPEG", "jpg" | `jpg` |
| "WebP", "webp" | `webp` |
| "PNG", "png" | `png` |

### Video Codecs

| User Input | Normalized Key |
|------------|----------------|
| "H.264 (MP4)", "MP4 (H.264)" | `mp4_h264` |
| "H.265/HEVC", "MP4 (H.265)" | `mp4_h265` |
| "WebM (VP9)", "VP9" | `webm_vp9` |
| "WebM (AV1)", "MP4 (AV1)" | `webm_av1` |

### Loop Formats

| User Input | Normalized Key |
|------------|----------------|
| "GIF" | `gif` |
| "WebM (VP9)" | `webm_loop` |
| "WebM (AV1)" | `webm_av1_loop` |

---

## API Reference

### `_resolve_version(media_type, format_key, requested_version=None)`

Smart version resolution with fallback chain.

**Parameters:**
- `media_type` (str): 'image', 'video', or 'loop'
- `format_key` (str): Normalized format/codec key
- `requested_version` (str, optional): Explicit version from UI

**Returns:**
- `str`: Resolved version (e.g., 'v6')

**Example:**
```python
version = _resolve_version('loop', 'webm_av1_loop', None)
# Returns: 'v6' (from PRODUCTION_DEFAULTS)
```

---

### `get_video_estimator(codec_pref, version=None)`

Get a video estimator instance with smart version resolution.

**Parameters:**
- `codec_pref` (str): Codec preference (e.g., 'MP4 (AV1)')
- `version` (str, optional): Explicit version override

**Returns:**
- `Estimator`: Estimator class instance or None

**Example:**
```python
estimator = get_video_estimator('MP4 (AV1)')
# Uses PRODUCTION_DEFAULTS['video']['webm_av1'] = 'v6'
```

---

### `get_image_estimator(output_format, version=None)`

Get an image estimator instance with smart version resolution.

**Parameters:**
- `output_format` (str): Output format (e.g., 'WebP')
- `version` (str, optional): Explicit version override

**Returns:**
- `Estimator`: Estimator class instance or None

**Example:**
```python
estimator = get_image_estimator('WebP')
# Uses PRODUCTION_DEFAULTS['image']['webp'] = 'v6'
```

---

### `get_loop_estimator(loop_format, version=None)`

Get a loop estimator instance with smart version resolution.

**Parameters:**
- `loop_format` (str): Loop format (e.g., 'WebM (AV1)')
- `version` (str, optional): Explicit version override

**Returns:**
- `Estimator`: Estimator class instance or None

**Example:**
```python
estimator = get_loop_estimator('WebM (AV1)')
# Uses PRODUCTION_DEFAULTS['loop']['webm_av1_loop'] = 'v6'
```

---

## Debugging

### Enable Debug Logging

The registry prints debug information to console:

```
[Registry] get_loop_estimator: loop_format='WebM (AV1)' -> format_key='webm_av1_loop', version='v6'
[ESTIMATOR] Using loop_estimators/webm_av1_loop_estimator_v6.py
```

### Common Issues

**Issue:** Wrong version being used

**Solution:** Check these in order:
1. Is dev mode ON? Check if UI dropdown is overriding
2. Check `PRODUCTION_DEFAULTS` in `config.py`
3. Verify estimator file exists with correct naming
4. Check console logs for fallback messages

**Issue:** Estimator not found

**Solution:**
1. Verify file naming: `{format_key}_estimator_{version}.py`
2. Check file is in correct directory (`image_estimators/`, `video_estimators/`, `loop_estimators/`)
3. Ensure `Estimator` class is defined in the file
4. Check console for import errors

---

## Migration Notes

### Deprecated Functions

The following functions are deprecated but kept for backward compatibility:

- `get_estimator_version()` - Returns global version (use PRODUCTION_DEFAULTS instead)
- `set_estimator_version(version)` - Sets global version (use per-format selection instead)

**Migration Path:**
- Old code using global version will continue to work
- New code should rely on `PRODUCTION_DEFAULTS`
- Eventually, global version state will be removed

---

## Best Practices

### 1. Always Use PRODUCTION_DEFAULTS

Don't hardcode version numbers in code. Use the config:

```python
# ❌ Bad
estimator = get_loop_estimator('WebM (AV1)', version='v6')

# ✓ Good
estimator = get_loop_estimator('WebM (AV1)')
# Uses PRODUCTION_DEFAULTS automatically
```

### 2. Test New Versions in Dev Mode First

Before updating `PRODUCTION_DEFAULTS`:
1. Create new estimator file
2. Test in dev mode by manually selecting version
3. Verify output quality and file sizes
4. Update `PRODUCTION_DEFAULTS` only after thorough testing

### 3. Keep Estimator Files Immutable

Once an estimator version is released:
- Never modify the file
- Create a new version instead
- This ensures reproducibility

### 4. Document Breaking Changes

If a new version has breaking changes:
- Add comments in `config.py`
- Update this documentation
- Consider gradual rollout

---

## Future Enhancements

### Planned Improvements

1. **Reusable UI Component**
   - Create `EstimatorVersionSelector` widget
   - Eliminate duplicate code across tabs
   - Automatic version detection

2. **Per-User Preferences**
   - Allow users to override defaults
   - Save preferences to config file

3. **Version Metadata**
   - Add version descriptions
   - Show changelog in UI
   - Display performance metrics

---

## Summary

The smart estimator selection system provides:

✓ **Format-aware defaults** - Each codec gets its own version  
✓ **No global pollution** - Versions resolved per-request  
✓ **Automatic fallback** - Graceful degradation if version missing  
✓ **Dev mode override** - Manual testing of new versions  
✓ **Easy configuration** - Single source of truth in `config.py`  
✓ **Scalable** - Adding new formats/versions is trivial  

This architecture ensures correct, maintainable, and flexible version management across the entire application.
