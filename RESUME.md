# Fix: H.265 encoding fails with libkvazaar (dimension constraint)

## Context
Two reported issues from logs:

### Issue 1: GPU indicator not showing in video tab
**Not a bug.** The GPU indicator IS implemented on the codec buttons (`HardwareAwareCodecButton.set_gpu_available()`). It lights up only when `hevc_nvenc`, `hevc_amf`, or `hevc_qsv` pass a live hardware probe. This machine has an AMD CPU (Ryzen, no discrete GPU) so all hardware probes fail → no GPU indicator. Behavior is correct and purely visual (badge/glow on the button). No code change needed.

### Issue 2: H.265 fails entirely (both lab mode and target size mode)
**Root cause (from logs):**
- The bundled FFmpeg has `--disable-libx265` — libkvazaar is used as HEVC fallback
- `libkvazaar` requires video dimensions to be **multiples of 8**
- Test video is 720x406 → 406 % 8 = 6 → encoder refuses to open → crash
- Error: `[libkvazaar] Video dimensions are not a multiple of 8 (720x406)`

`get_video_codec_config()` already correctly strips `x265-params` when switching to libkvazaar. The only missing fix is the dimension alignment.

## Fix

Add a `scale=trunc(iw/8)*8:trunc(ih/8)*8` filter when the resolved encoder is `libkvazaar`. This needs to be applied in two places:

### Fix A — Lab mode: `client/core/manual_mode/converters/video_converter.py`

In `convert()`, after `_apply_rotation()` and before `_build_output_args()`, add:
```python
# libkvazaar requires dimensions to be multiples of 8
if codec_config.ffmpeg_codec == 'libkvazaar':
    video_stream = ffmpeg.filter(video_stream, 'scale',
                                 w='trunc(iw/8)*8', h='trunc(ih/8)*8')
```

### Fix B — Target size mode: `client/core/target_size/video_estimators/mp4_h265_estimator_v6.py`

In `execute()`, after the vf_filters list is built (around line 206), append the alignment filter when codec is libkvazaar:
```python
# libkvazaar requires dimensions to be multiples of 8
if codec == 'libkvazaar':
    vf_filters.append('scale=trunc(iw/8)*8:trunc(ih/8)*8')
```

## Critical Files
- `client/core/manual_mode/converters/video_converter.py` — Fix A (lab mode), ~line 109
- `client/core/target_size/video_estimators/mp4_h265_estimator_v6.py` — Fix B (target size), ~line 206

## Verification
Test with the same 720x406 video:
1. Lab mode → MP4 (H.265) → should encode successfully
2. Target size mode → H.265 → should complete both passes
