import os
import glob
import re

def process_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Generic check to skip already patched
    if "run_ffmpeg_skill_standard" in content:
        return

    # Add import
    if "from .._common import get_media_metadata" in content:
        content = content.replace(
            "from .._common import get_media_metadata",
            "from .._common import get_media_metadata, run_ffmpeg_skill_standard"
        )
    elif "from client.core.target_size._common import get_ffmpeg_binary" in content:
        content = content.replace(
            "from client.core.target_size._common import get_ffmpeg_binary",
            "from client.core.target_size._common import get_ffmpeg_binary, run_ffmpeg_skill_standard"
        )
    elif "from .._common import get_ffmpeg_binary" in content:
        content = content.replace(
            "from .._common import get_ffmpeg_binary",
            "from .._common import get_ffmpeg_binary, run_ffmpeg_skill_standard"
        )

    # 1. Update execute method to register stop_check
    execute_pattern = r"(def execute\([^)]*stop_check.*?\):)"
    if re.search(execute_pattern, content, flags=re.DOTALL):
        # Insert self._current_stop_check = stop_check after def execute(...)
        content = re.sub(
            execute_pattern, 
            r"\1\n        self._current_stop_check = stop_check", 
            content, 
            flags=re.DOTALL
        )

    # 2. Patch subprocess.run inside `_run_sample` (for loop estimators)
    if "def _run_sample" in content:
        content = content.replace(
            "subprocess.run(cmd, capture_output=True, creationflags=0x08000000 if os.name == 'nt' else 0)",
            "run_ffmpeg_skill_standard(cmd, stop_check=getattr(self, '_current_stop_check', None), log_target='estimator_loop')"
        )
        content = content.replace(
            "subprocess.run(cmd, capture_output=True, creationflags=0x08000000)",
            "run_ffmpeg_skill_standard(cmd, stop_check=getattr(self, '_current_stop_check', None), log_target='estimator_loop')"
        )

    # 3. Patch execute's `subprocess.Popen` while loop (for loop estimators)
    popen_block = """try:
            proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL, creationflags=0x08000000 if os.name == 'nt' else 0)
            while proc.poll() is None:
                if stop_check and stop_check():
                    proc.terminate(); return False
                time.sleep(0.5)
            return proc.returncode == 0
        except: return False"""
    if popen_block in content:
        content = content.replace(
            popen_block,
            "return run_ffmpeg_skill_standard(cmd, stop_check=stop_check, log_target=output_path) == 0"
        )

    # 4. Patch `run_ffmpeg_hidden` in JPG/PNG estimators
    if "run_ffmpeg_hidden(stream" in content:
        content = re.sub(
            r"run_ffmpeg_hidden\(([^,]+), cmd=ffmpeg_bin, quiet=True\)",
            r"run_ffmpeg_skill_standard(ffmpeg.compile(\1, cmd=ffmpeg_bin), stop_check=getattr(self, '_current_stop_check', None), log_target='estimator')",
            content
        )

    # 5. Patch `run_ffmpeg_cmd` in WebP/AVIF and MP4 estimators
    if "def run_ffmpeg_cmd" in content:
        run_cmd_pattern = r"def run_ffmpeg_cmd\(cmd_args\):.*?return result\n"
        if re.search(run_cmd_pattern, content, flags=re.DOTALL):
            new_run_cmd = """def run_ffmpeg_cmd(cmd_args, stop_check=None):
    from .._common import run_ffmpeg_skill_standard
    rc = run_ffmpeg_skill_standard(cmd_args, stop_check=stop_check, log_target='estimator')
    class _R: pass
    r = _R(); r.returncode = rc; return r
"""
            content = re.sub(run_cmd_pattern, new_run_cmd, content, flags=re.DOTALL)
            
        # And patch calls to pass stop_check
        content = content.replace(
            "result = run_ffmpeg_cmd(cmd_args)",
            "result = run_ffmpeg_cmd(cmd_args, stop_check=getattr(self, '_current_stop_check', None))"
        )

    # Specific subprocessor.run block inside execute method of v7
    sub_run = """result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )"""
    new_run = """rc = run_ffmpeg_skill_standard(cmd, stop_check=stop_check, log_target=output_path)
            class _R: pass
            result = _R()
            result.returncode = rc
            result.stderr = b''"""
    content = content.replace(sub_run, new_run)

    # Update version strings appropriately to the incremented filenames
    if "v5" in file_path and file_path.endswith("v6.py"):
        content = content.replace('"v5"', '"v6"').replace("v5", "v6").replace("v6", "v6")
    elif "v6" in file_path and file_path.endswith("v7.py"):
        content = content.replace('"v6"', '"v7"').replace("v6", "v7").replace("v7", "v7")
    elif "v7" in file_path and file_path.endswith("v8.py"):
        content = content.replace('"v7"', '"v8"').replace("v7", "v8").replace("v8", "v8")
    elif "v2" in file_path and file_path.endswith("v3.py"):
        content = content.replace('"v2"', '"v3"').replace("v2", "v3").replace("v3", "v3")
    elif "v3" in file_path and file_path.endswith("v4.py"):
        content = content.replace('"v3"', '"v4"').replace("v3", "v4").replace("v4", "v4")
    elif "v24" in file_path and file_path.endswith("v25.py"):
        content = content.replace('"v24"', '"v25"').replace("v24", "v25").replace("v25", "v25")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


files = glob.glob("v:/_MY_APPS/ImgApp_1/client/core/target_size/**/*_estimator_v*.py", recursive=True)
for f in files:
    if f.endswith(('v6.py', 'v7.py', 'v8.py', 'v3.py', 'v4.py', 'v25.py')):
        process_file(f)

print("Patching complete.")
