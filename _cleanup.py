import os, shutil

ROOT = r"V:\_MY_APPS\ImgApp_1"

FILES = [
    "ffmpeg_check_new.log",
    "ffmpeg_check_new_2.log",
    "ffmpeg_check_new_3.txt",
    "ffmpeg_check_temp.log",
    "ffmpeg_check_temp.txt",
    "ffmpeg_encoders.log",
    "ffmpeg_encoders.txt",
    "ffmpeg_version.log",
    "ffmpeg_version_check_new.log",
    "ffmpeg_version_output.txt",
    "test_v5_estimator.py",
    "test_v5_quick.py",
    "verify_av1_fallback.py",
    "debug_target_size.py",
    "verify_v5_registration.task",
    "test_svt.webm",
    "test_svt_mp4_container.webm",
]

DIRS = [
    "logs",
    "temp_check",
    "temp_updates",
    ".pytest_cache",
]

for f in FILES:
    path = os.path.join(ROOT, f)
    if os.path.exists(path):
        os.remove(path)
        print(f"DEL  {f}")
    else:
        print(f"SKIP {f} (not found)")

for d in DIRS:
    path = os.path.join(ROOT, d)
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"RMDIR {d}")
    else:
        print(f"SKIP {d}/ (not found)")

print("Done.")
