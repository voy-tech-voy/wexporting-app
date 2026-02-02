"""
Script to add logging to all estimator files.
Adds a print statement at the start of execute() method to show which estimator is being used.
"""
import os
from pathlib import Path

# Base directory
base_dir = Path(r"v:\_MY_APPS\ImgApp_1\client\core\target_size")

# Find all estimator files
estimator_dirs = [
    base_dir / "video_estimators",
    base_dir / "image_estimators",
    base_dir / "loop_estimators"
]

for estimator_dir in estimator_dirs:
    if not estimator_dir.exists():
        continue
    
    for estimator_file in estimator_dir.glob("*_estimator_v*.py"):
        print(f"Processing: {estimator_file.name}")
        
        # Read the file
        with open(estimator_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find the execute method and add logging
        modified = False
        new_lines = []
        in_execute = False
        added_log = False
        
        for i, line in enumerate(lines):
            new_lines.append(line)
            
            # Detect execute method definition
            if 'def execute(' in line and not added_log:
                in_execute = True
            
            # Add log after the docstring or first line of execute
            if in_execute and not added_log:
                # Check if next line is a docstring
                if i + 1 < len(lines) and '"""' in lines[i + 1]:
                    # Skip to end of docstring
                    continue
                elif '"""' in line and in_execute:
                    # End of docstring, add log after
                    new_lines.append(f"        print(f\"[ESTIMATOR] Using {estimator_file.name}\")\n")
                    added_log = True
                    modified = True
                    in_execute = False
        
        if modified:
            with open(estimator_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f"  ✓ Added logging to {estimator_file.name}")
        else:
            print(f"  ⚠ Could not add logging to {estimator_file.name}")

print("\nDone!")
