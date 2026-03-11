import sys
import os
import pathlib

print(f"sys.frozen: {getattr(sys, 'frozen', False)}")
if hasattr(sys, '_MEIPASS'):
    print(f"sys._MEIPASS: {sys._MEIPASS}")
    
    # List contents of _MEIPASS
    try:
        print(f"Contents of {sys._MEIPASS}:")
        for item in os.listdir(sys._MEIPASS):
            print(f" - {item}")
            if item == '_internal':
                print(f"    Contents of _internal:")
                for sub in os.listdir(os.path.join(sys._MEIPASS, '_internal')):
                    print(f"     -- {sub}")
    except Exception as e:
        print(f"Error listing _MEIPASS: {e}")
else:
    print("sys._MEIPASS not present")

try:
    from PySide6.QtWidgets import QApplication
    print("PySide6.QtWidgets imported successfully!")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Exception: {e}")

input("Press Enter to exit...")
