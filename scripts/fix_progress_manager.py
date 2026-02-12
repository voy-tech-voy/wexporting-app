# Simple find and replace script
with open(r'v:\_MY_APPS\ImgApp_1\client\core\progress_manager.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace in _calculate_lab_mode (around line 355)
for i in range(len(lines)):
    if i >= 354 and 'for file_path in file_list:' in lines[i]:
        # Found the first occurrence
        print(f"Found first occurrence at line {i+1}")
        lines[i] = '        for item in file_list:\n'
        lines[i+1] = '            file_path = self._get_file_path(item)\n'
        lines[i+2] = '            ext = os.path.splitext(file_path)[1].lower()\n'
        lines[i+4] = '                valid_files.append(item)\n'
        lines[i+6] = '                skipped_files.append(item)\n'
        break

# Find and replace in _calculate_preset_mode (around line 444)
for i in range(len(lines)):
    if i >= 440 and 'for file_path in file_list:' in lines[i]:
        # Found the second occurrence
        print(f"Found second occurrence at line {i+1}")
        lines[i] = '        for item in file_list:\n'
        lines[i+1] = '            file_path = self._get_file_path(item)\n'
        lines[i+2] = '            ext = os.path.splitext(file_path)[1].lower()\n'
        lines[i+4] = '                valid_files.append(item)\n'
        lines[i+6] = '                skipped_files.append(item)\n'
        break

with open(r'v:\_MY_APPS\ImgApp_1\client\core\progress_manager.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Done!")
