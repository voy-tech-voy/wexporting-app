import glob
import re

files = glob.glob("v:/_MY_APPS/ImgApp_1/client/core/target_size/**/*_estimator_v*.py", recursive=True)
for f in files:
    if f.endswith(('v6.py', 'v7.py', 'v8.py', 'v3.py', 'v4.py', 'v25.py')):
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # The bad block looks like:
        #         def emit(msg: str):
        #         self._current_stop_check = stop_check
        #             if status_callback:
        
        bad_pattern = r"(\s+def emit\(msg: str\):\n)\s+self\._current_stop_check = stop_check\n"
        if re.search(bad_pattern, content):
            # Move self._current_stop_check = stop_check BEFORE def emit
            content = re.sub(
                bad_pattern,
                r"        self._current_stop_check = stop_check\n\1",
                content
            )
            with open(f, 'w', encoding='utf-8') as file:
                file.write(content)

print("Indentation fixed.")
