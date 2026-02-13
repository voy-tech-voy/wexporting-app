# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['V:\\_MY_APPS\\ImgApp_1\\client\\main.py'],
    pathex=[],
    binaries=[('V:\\_MY_APPS\\ImgApp_1\\tools\\ffmpeg.exe', 'tools'), ('V:\\_MY_APPS\\ImgApp_1\\tools\\gifsicle.exe', 'tools')],
    datas=[('V:\\_MY_APPS\\ImgApp_1\\client\\gui', 'client/gui'), ('V:\\_MY_APPS\\ImgApp_1\\client\\core', 'client/core'), ('V:\\_MY_APPS\\ImgApp_1\\client\\utils', 'client/utils'), ('V:\\_MY_APPS\\ImgApp_1\\client\\config', 'client/config'), ('V:\\_MY_APPS\\ImgApp_1\\client\\assets', 'client/assets'), ('V:\\_MY_APPS\\ImgApp_1\\client\\plugins\\presets', 'client/plugins/presets'), ('V:\\_MY_APPS\\ImgApp_1\\client\\version.py', 'client'), ('V:\\_MY_APPS\\ImgApp_1\\tools\\licenses', 'tools/licenses'), ('V:\\_MY_APPS\\ImgApp_1\\THIRD-PARTY-NOTICES.md', '.')],
    hiddenimports=['client.utils.crash_reporter', 'client.utils.error_reporter', 'client.utils.hardware_id', 'requests', 'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# SECURITY: Exclude local_config.py from production builds (dev-only file)
a.datas = [x for x in a.datas if not x[0].endswith('local_config.py')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ImgApp-v5.0.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['V:\\_MY_APPS\\ImgApp_1\\client\\assets\\icons\\app_icon.ico'],
)
