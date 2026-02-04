# Progress Bar Quick Reference

## For Developers: Common Tasks

### Adding a New Variant Type

**Example**: Adding "framerate variants" to video conversions

1. **Update ProgressManager** (`client/core/progress_manager.py`):
```python
def calculate_from_params(self, file_list, params):
    # ... existing code ...
    
    # Add framerate variant extraction
    framerate_variants = []
    if params.get('multiple_framerates'):
        framerate_variants = params.get('framerate_variants', [])
    
    # Update multiplier calculation
    num_framerates = max(len(framerate_variants), 1)
    variant_multiplier = num_sizes * num_resizes * num_framerates
```

2. **Update UI params** (`client/gui/tabs/*_tab.py`):
```python
def get_params(self):
    params = {
        # ... existing params ...
        'multiple_framerates': self.framerate_checkbox.isChecked(),
        'framerate_variants': self.framerate_section.get_variants()
    }
    return params
```

3. **Test**: Run conversion with multiple framerates, verify console shows correct total.

---

### Debugging Progress Issues

**Step 1**: Check console output at conversion start:
```
[ProgressManager] Valid: 5, Skipped: 2, Total Outputs: 20
[ProgressManager] Preview: 5 valid / 7 total → 20 outputs
```

**Step 2**: Verify params extraction in `calculate_from_params()`:
```python
# Add debug print
print(f"[DEBUG] Extracted variants: sizes={len(size_variants)}, resizes={len(resize_variants)}")
print(f"[DEBUG] Multiplier: {variant_multiplier}, Total: {valid_count * variant_multiplier}")
```

**Step 3**: Track progress updates:
```python
# In on_file_completed
print(f"[DEBUG] Completed: {self.progress_manager.completed_outputs}/{self.progress_manager.total_outputs}")
```

---

### Adding Progress to New Engine

**Example**: Integrating with a new compression engine

1. **Pass manager to engine**:
```python
# In MainWindow.start_conversion()
self.conversion_engine = NewCompressionEngine(files, params, self.progress_manager)
```

2. **Engine uses manager**:
```python
# In NewCompressionEngine
def __init__(self, files, params, progress_manager=None):
    self.progress_manager = progress_manager or ConversionProgressManager()
    # Note: MainWindow already called calculate_from_params()
```

3. **Emit signals**:
```python
# During conversion
self.file_progress_updated.emit(file_index, 0.5)  # 50% progress

# On completion
self.file_completed.emit(source_path, output_path)
```

4. **MainWindow handles signals** (already connected):
```python
# These are already set up in MainWindow.start_conversion()
engine.file_progress_updated.connect(self.on_file_progress)
engine.file_completed.connect(self.on_file_completed)
```

---

### Testing Checklist

Before committing progress changes:

```bash
# Test 1: Single file, no variants
python -m client.main
# Add 1 file, convert
# ✓ Green bar: 0% → 100%

# Test 2: Multiple files, single variant
# Add 3 files, convert
# ✓ Green bar: 0% → 33% → 66% → 100%

# Test 3: Multiple variants
# Add 2 files, enable 3 size variants
# ✓ Console: "Total Outputs: 6"
# ✓ Green bar: 0% → 16% → 33% → 50% → 66% → 83% → 100%

# Test 4: Second conversion
# Run another conversion immediately
# ✓ Green bar starts at 0% (not 50% or 100%)

# Test 5: Stop mid-conversion
# Start conversion, click stop after 2 outputs
# ✓ Progress resets
# ✓ Next conversion starts at 0%
```

---

## Architecture Decision Record

### Why Not Track File Progress?

**Question**: Why not show "File 2 of 5" in addition to overall progress?

**Answer**: Files can have multiple output variants. Example:
- File 1 → 4 variants (variants 1-4)
- File 2 → 4 variants (variants 5-8)
- File 3 → 4 variants (variants 9-12)

Showing "File 2 of 3" would jump from 33% → 66%, hiding that 4 more variants need processing.

**Better solution**: Show output count:
- "Output 5 of 12" (41% complete)
- Or keep current behavior: just show green bar percentage

---

### Why Auto-Reset in calculate_from_params?

**Question**: Why not require manual reset() call?

**Answer**: Defense in depth. If any completion handler fails to reset (crash, exception), the next conversion would start with stale state. Auto-reset guarantees clean slate.

**Trade-off**: Slight redundancy (reset called twice: at start + at completion), but eliminates a class of subtle bugs.

---

### Why Move Logic to ProgressManager?

**Question**: Why not keep calculation in MainWindow?

**Answer**: Separation of concerns:
- MainWindow = UI coordination (what to do)
- ProgressManager = Business logic (how to calculate)

**Benefits**:
1. Testable without GUI (unit tests for progress_manager)
2. Reusable (other engines can use same manager)
3. Maintainable (all variant extraction logic in one place)
4. Cleaner MainWindow (60 lines removed)

---

## Performance Notes

### Memory Usage
- `ConversionProgressManager` instance: ~500 bytes
- File list copies during calculation: ~100 bytes per file
- Total overhead: < 1KB per conversion

### CPU Impact
- `calculate_from_params()`: O(n) where n = file count
- `get_overall_progress()`: O(1)
- `increment_progress()`: O(1)

### UI Thread Blocking
- All progress methods are non-blocking
- Animation in `set_progress()` is async (Qt animation framework)
- No performance impact on conversion speed

---

## Related Documentation

- **Full Architecture**: [PROGRESS_BAR_ARCHITECTURE.md](PROGRESS_BAR_ARCHITECTURE.md)
- **Main Architecture**: [ARCHITECTURE_ANALYSIS.md](ARCHITECTURE_ANALYSIS.md)
- **Code Reference**: `client/core/progress_manager.py`

---

**Last Updated**: February 4, 2026
