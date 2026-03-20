import glob
import re

files = glob.glob("v:/_MY_APPS/ImgApp_1/client/core/target_size/**/*_estimator_v*.py", recursive=True)
for f in files:
    if f.endswith(('v6.py', 'v7.py', 'v8.py', 'v3.py', 'v4.py', 'v25.py')):
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Issue 1: Docstring squished
        content = re.sub(
            r'(""")\s*self\._current_stop_check = stop_check',
            r'\1\n        self._current_stop_check = stop_check',
            content
        )
        content = re.sub(
            r"(''')\s*self\._current_stop_check = stop_check",
            r"\1\n        self._current_stop_check = stop_check",
            content
        )
        
        # Issue 2: return type hint squished
        content = re.sub(
            r'\) -> bool:\s*self\._current_stop_check = stop_check',
            r') -> bool:\n        self._current_stop_check = stop_check',
            content
        )

        # Issue 3: import re squished
        content = re.sub(
            r'import re\s*self\._current_stop_check = stop_check',
            r'import re\n        self._current_stop_check = stop_check',
            content
        )

        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)

print("Syntax repair complete.")
