"""Quick test to see if main_window loads with PySide6"""
import sys
sys.path.insert(0, "v:/_MY_APPS/ImgApp_1/client")

from PySide6.QtWidgets import QApplication

try:
    app = QApplication(sys.argv)
    
    # Try to import and create main window
    from client.gui.main_window import MainWindow
    
    window = MainWindow(is_trial=False)
    print("✓ Main window created successfully with PySide6!")
    print(f"✓ Window title: {window.windowTitle()}")
    
    # Don't actually show it, just test creation
    # window.show()
    
    print("\n✓ SUCCESS: PySide6 migration appears to be working!")
    sys.exit(0)
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
