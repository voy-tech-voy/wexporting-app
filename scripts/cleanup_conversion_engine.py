"""
Helper script to remove all extracted code from conversion_engine.py
"""

# Read conversion_engine.py
with open(r'V:\_MY_APPS\ImgApp_1\client\core\conversion_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the start and end of the section to remove
# Start: line 537 (# GIF Quality Presets for Size Optimization)
# End: line 1512 (before # VIDEO MAX SIZE ESTIMATION AND OPTIMIZATION ends)

# We need to remove lines 537-1512 (0-indexed: 536-1511)
# Keep everything before line 537 and everything after line 1512

new_lines = lines[:536] + lines[1512:]

# Write back
with open(r'V:\_MY_APPS\ImgApp_1\client\core\conversion_engine.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

removed_count = len(lines) - len(new_lines)
print(f'✓ Removed {removed_count} lines from conversion_engine.py')
print(f'✓ New file size: {len(new_lines)} lines (was {len(lines)} lines)')
print(f'✓ Reduction: ~{removed_count} lines (~{(removed_count/len(lines)*100):.1f}%)')
