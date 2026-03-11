import sys
# Apply dll fix if frozen
if getattr(sys, 'frozen', False):
    import os
    import pathlib
    _pyside6_dir = pathlib.Path(sys._MEIPASS) / 'PySide6'
    _shiboken6_dir = pathlib.Path(sys._MEIPASS) / 'shiboken6'
    for _d in (_pyside6_dir, _shiboken6_dir):
        if _d.is_dir():
            os.add_dll_directory(str(_d))
            os.environ['PATH'] = str(_d) + os.pathsep + os.environ.get('PATH', '')

from PySide6.QtWidgets import QApplication, QLabel

def main():
    app = QApplication(sys.argv)
    label = QLabel("Hello World PySide6")
    label.show()
    print("PySide6 initialized successfully!")
    # auto exit after 1 second
    import threading
    threading.Timer(1.0, app.quit).start()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
