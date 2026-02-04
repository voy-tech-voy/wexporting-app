# Progress Bar Architecture Documentation

## Overview

The application features a dual progress bar system that accurately tracks conversion progress across multiple output variants (size variants, quality variants, resize variants). The system was refactored in February 2026 to move from file-based progress to output-based progress tracking.

---

## Architecture Components

### 1. ConversionProgressManager
**Location**: `client/core/progress_manager.py`

**Purpose**: Smart, mode-aware progress calculation and tracking.

**Responsibilities**:
- Validate files against format constraints (tab-specific, preset-specific)
- Calculate total output count based on variants
- Track completed outputs incrementally
- Provide real-time progress percentage
- Auto-reset state between conversions

**Key Classes**:
```python
class AppMode(Enum):
    PRESET = "preset"  # Preset mode (no variants)
    LAB = "lab"        # Lab mode (with variants)

class LabSubMode(Enum):
    MAX_SIZE = "max_size"  # Target size optimization
    MANUAL = "manual"      # Direct quality control

class LabTab(Enum):
    IMAGE = 0  # Image conversion tab
    VIDEO = 1  # Video conversion tab
    LOOP = 2   # Loop/GIF conversion tab
```

**Core Methods**:

| Method | Purpose | Usage |
|--------|---------|-------|
| `calculate_from_params(files, params)` | Smart extraction from raw params dict | Called at conversion start |
| `calculate(files, app_mode, ...)` | Explicit calculation with mode/variants | Advanced usage |
| `get_overall_progress(current_progress)` | Get 0.0-1.0 progress for green bar | Called during file progress |
| `increment_progress(count)` | Mark outputs completed, return % | Called when output finishes |
| `reset()` | Clear all state for new conversion | Auto-called in calculate_from_params |

---

## 2. Progress Bar UI Components

**Location**: `client/gui/components/panels/status_panel.py`

### StatusPanel Structure
```
StatusPanel (QWidget)
├── file_progress_bar (CustomProgressBar) - Blue, 3px height
│   └── Color: #2196F3 (Blue)
│   └── Purpose: Current file/output progress (0-100%)
└── total_progress_bar (CustomProgressBar) - Green, 3px height
    └── Color: #4CAF50 (Green)
    └── Purpose: Overall batch progress (0-100%)
```

**CustomProgressBar Features**:
- Animated gradient effect
- Smooth transitions
- Configurable duration (default 500ms)
- Handles fractional progress (0.0-1.0)

---

## 3. Progress Calculation Logic

### Formula by Mode

**Lab Max Size Mode**:
```
total_outputs = valid_files × len(size_variants) × len(resize_variants)
```

Example: 3 files × 3 sizes (5MB, 10MB, 15MB) × 2 resizes (1920x1080, 1280x720) = **18 outputs**

**Lab Manual Mode**:
```
total_outputs = valid_files × len(quality_variants) × len(resize_variants)
```

Example: 3 files × 3 qualities (CRF 18, 23, 28) × 2 resizes = **18 outputs**

**Preset Mode**:
```
total_outputs = valid_files × 1  (no variants)
```

Example: 5 files → **5 outputs**

### Progress Updates

**During Conversion**:
```python
# Blue bar: Current file progress (emitted by engine)
on_file_progress(file_index, 0.35)  # 35% of current file
→ file_progress_bar.set_progress(0.35)

# Green bar: Overall progress (calculated by manager)
→ overall = manager.get_overall_progress(0.35)
→ total_progress_bar.set_progress(overall)
```

**On Output Completion**:
```python
on_file_completed(source, output)
→ progress_percentage = manager.increment_progress(count=1)
→ total_progress_bar.set_progress(progress_percentage / 100.0)
```

---

## 4. Signal Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         MainWindow                                │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 1. start_conversion(params)                                  │ │
│  │    └─> progress_manager.calculate_from_params(files, params)│ │
│  │        • Auto-resets state                                   │ │
│  │        • Detects mode, tab, sub-mode                        │ │
│  │        • Extracts variants                                   │ │
│  │        • Returns CalculationResult                           │ │
│  │        • Sets manager.total_outputs                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 2. ConversionEngine.start()                                  │ │
│  │    Emits signals:                                            │ │
│  │    • file_progress_updated(file_index, progress)            │ │
│  │    • file_completed(source, output)                         │ │
│  │    • conversion_completed(success, failed, skipped, stopped)│ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 3. on_file_progress(index, progress)                        │ │
│  │    file_progress_bar.set_progress(progress)  ← BLUE         │ │
│  │    overall = manager.get_overall_progress(progress)         │ │
│  │    total_progress_bar.set_progress(overall)  ← GREEN        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 4. on_file_completed(source, output)                        │ │
│  │    progress_pct = manager.increment_progress(1)             │ │
│  │    total_progress_bar.set_progress(progress_pct / 100)      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 5. on_conversion_finished(success, message)                 │ │
│  │    manager.reset()  ← Clean state for next conversion       │ │
│  │    file_progress_bar.set_progress(0)                        │ │
│  │    total_progress_bar.set_progress(0)                       │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. State Management

### ConversionProgressManager State
```python
completed_outputs: int = 0      # How many outputs finished
total_outputs: int = 0          # How many outputs total
valid_files: List[str] = []     # Files that match format
skipped_files: List[str] = []   # Files that don't match format
_last_result: CalculationResult # Cached calculation result
```

### Reset Locations (Defense in Depth)

**Primary Defense** - Auto-reset at calculation start:
```python
def calculate_from_params(files, params):
    self.reset()  # Always clean slate
    # ... calculation logic
```

**Secondary Defense** - Explicit resets at completion:
1. `on_conversion_finished()` - Lab/Manual conversions
2. `_on_target_size_completed()` - Target size conversions
3. `_start_preset_conversion() → on_finished()` - Preset conversions

**Why Both?**
- Primary ensures next conversion starts clean (even if completion handler fails)
- Secondary ensures immediate cleanup (don't carry state until next run)

---

## 6. Format Validation

### Tab-Specific Formats (Lab Mode)
```python
TAB_FORMATS = {
    LabTab.IMAGE: {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'},
    LabTab.VIDEO: {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v', '.wmv'},
    LabTab.LOOP: {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v', '.wmv', '.gif'}
}
```

### Preset-Specific Formats (Preset Mode)
From `preset.constraints.accepted_extensions`:
```yaml
constraints:
  accepted_types: ["video"]
  accepted_extensions: [".mp4", ".mov", ".mkv"]
```

**Fallback Logic**:
1. Use `accepted_extensions` if present
2. Otherwise, map `accepted_types` to `TYPE_FORMATS`
3. If no constraints, accept all common formats

---

## 7. Integration Points

### MainWindow Integration (Minimal Code)

**At Conversion Start** (3 lines):
```python
def _calculate_conversion_totals(self, files, params):
    result = self.progress_manager.calculate_from_params(files, params)
    print(f"[ProgressManager] Valid: {result.valid_count}, Total: {result.total_outputs}")
```

**During Progress** (2 lines):
```python
def on_file_progress(self, file_index, progress):
    overall = self.progress_manager.get_overall_progress(progress)
    self.total_progress_bar.set_progress(overall)
```

**On Completion** (1 line):
```python
def on_file_completed(self, source, output):
    progress_pct = self.progress_manager.increment_progress()
```

---

## 8. Console Output

When conversion starts:
```
[ProgressManager] Valid: 5, Skipped: 2, Total Outputs: 20
[ProgressManager] Preview: 5 valid / 7 total → 20 outputs
```

**Interpretation**:
- 7 files added total
- 5 files match the current tab's format constraints
- 2 files skipped (wrong format for this tab)
- 20 total outputs will be generated (accounting for variants)

---

## 9. Common Scenarios

### Scenario 1: Multi-Variant Conversion
**Setup**: 3 videos, Max Size mode, 3 target sizes, 2 resizes
**Calculation**: 3 × 3 × 2 = 18 outputs
**Progress Updates**: Every output completion increments by 1/18 (5.56%)

### Scenario 2: No Variants
**Setup**: 5 images, Manual mode, single quality, no resize
**Calculation**: 5 × 1 × 1 = 5 outputs
**Progress Updates**: Every output completion increments by 1/5 (20%)

### Scenario 3: Mixed File Types
**Setup**: 5 videos + 3 images, Video tab
**Calculation**: 5 valid (videos only) × variants
**Result**: 3 images skipped, shown in console

---

## 10. Troubleshooting

### Problem: Green bar jumps to 50% immediately on second conversion

**Cause**: `completed_outputs` not reset from previous conversion

**Fix**: Already implemented - `calculate_from_params()` auto-resets

**Verify**: Check console for "Valid: X, Total: Y" at start of each conversion

---

### Problem: Green bar reaches 100% before all files finish

**Cause**: `total_outputs` doesn't account for all variants

**Fix**: Verify params contain correct variant lists:
- `multiple_max_sizes`, `max_size_variants` (Max Size mode)
- `multiple_qualities`, `quality_variants` (Manual mode)
- `multiple_resize`, `resize_variants` (both modes)

**Debug**: Add breakpoint in `calculate_from_params()` to inspect extracted variants

---

### Problem: Green bar never moves

**Cause**: `manager.total_outputs = 0` or `get_overall_progress()` not called

**Fix**: Check that `_calculate_conversion_totals()` runs before engine starts

**Verify**: Console should show total_outputs > 0

---

## 11. Future Enhancements

### Potential Features

1. **Real-Time Preview in UI**
   - Connect `totals_changed` signal to update convert button label
   - Display "5 valid → 20 outputs" before conversion starts
   - Show warning if skipped_count > 0

2. **Per-File Progress Bar**
   - Add third progress bar for individual file variants
   - Show "File 1 of 3: Variant 2 of 6"

3. **Duration Estimation**
   - Track average time per output
   - Display "~5 minutes remaining" based on completed_outputs rate

4. **Preset Mode Variants**
   - Add support for multi-quality presets
   - Would require updating `PresetDefinition` model

---

## 12. Testing Checklist

When modifying progress tracking:

- [ ] Test Lab Max Size mode with multiple size variants
- [ ] Test Lab Max Size mode with multiple resize variants
- [ ] Test Lab Max Size mode with BOTH size + resize variants
- [ ] Test Lab Manual mode with multiple quality variants
- [ ] Test Preset mode (no variants)
- [ ] Test second conversion starts at 0% (not 50%)
- [ ] Test stopping conversion mid-way resets state
- [ ] Test failed conversion resets state
- [ ] Test mixed file types (some skipped)
- [ ] Verify console output shows correct totals

---

## 13. Code Ownership

| Component | File | Owner | Last Updated |
|-----------|------|-------|--------------|
| Progress Manager | `client/core/progress_manager.py` | Core Team | 2026-02-04 |
| Status Panel | `client/gui/components/panels/status_panel.py` | UI Team | 2024-XX-XX |
| MainWindow Integration | `client/gui/main_window.py` | UI Team | 2026-02-04 |
| Conversion Engine | `client/core/target_size/target_size_conversion_engine.py` | Core Team | 2026-02-04 |

---

## 14. Performance Considerations

### Memory
- `ConversionProgressManager` is lightweight (~500 bytes per instance)
- Stores file lists temporarily (cleared on reset)
- No persistent state between conversions

### CPU
- `calculate_from_params()` is O(n) where n = file count
- Format validation is simple string comparison
- Progress calculation is O(1)

### UI Thread
- All progress updates run on UI thread (PyQt signals)
- `set_progress()` with animation may cause slight delay (500ms)
- No blocking operations in progress manager

---

## End of Document

**Last Updated**: February 4, 2026
**Document Version**: 1.0
**Maintained By**: Development Team
