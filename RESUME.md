# Build & Packaging Status - RESUME

## Current Status
- **App Name:** wexporting
- **Version:** 1.0.5.0
- **Executable:** Successfully built using PyInstaller (6.9 MB). Located at `V:\_MY_APPS\ImgApp_1\dist\wexporting-v1.0.5.0\wexporting-v1.0.5.0.exe`.
- **MSI Installer:** Successfully built using WiX Toolset (381.6 MB). Located at `V:\_MY_APPS\ImgApp_1\ImgApp_Releases\v1.0.5.0\wexporting-v1.0.5.0-installer.msi`.
- **Installation:** Ready to test installation to `C:\Program Files\wexporting` (or `Program Files (x86)`).

---

## What Was Fixed in v1.0.5

### Problem (v1.0.4 and earlier)
`ImportError: DLL load failed while importing QtWidgets: The specified module could not be found.`

The app crashed silently immediately after the `os.add_dll_directory()` loop when installed via MSI to `C:\Program Files (x86)\wexporting`. The debug log stopped right after that loop, never reaching Qt imports.

### Root Cause
`os.add_dll_directory()` returns a handle object. When that object is not stored persistently, Windows automatically revokes the directory registration. Under UAC-protected paths (e.g. `Program Files`), the Python garbage collector could collect the handle before the DLL loader uses it, causing silent failure.

### Fixes Applied (in `client/main.py`)

1. **Win32 `AddDllDirectory()` via ctypes** — Calls the Windows API directly through `ctypes.WinDLL('kernel32').AddDllDirectory`. The registration persists for the entire process lifetime and cannot be silently dropped.

2. **`qt.conf` written at runtime** — The frozen app now writes a `qt.conf` file next to the `.exe` on every launch:
   ```ini
   [Paths]
   Prefix = ./_internal/PySide6
   Plugins = ./_internal/PySide6/plugins
   Libraries = ./_internal/PySide6
   ```
   This tells Qt's own internal plugin loader where to find `qwindows.dll` without relying on PATH.

3. **`QT_PLUGIN_PATH` + `QT_QPA_PLATFORM_PLUGIN_PATH` env vars** — Set before any PySide6 import so Qt's platform abstraction layer finds the Windows platform plugin.

4. **Pre-loading of `Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Widgets.dll`** — These are loaded via `ctypes.WinDLL()` before the Python import, which populates the OS DLL cache and eliminates dependency resolution failures.

5. **Better logging** — Enhanced `log_startup()` to never crash (wraps in try/except), logs `sys.executable`, `sys._MEIPASS`, and the exe directory at startup so future debugging is easier.

### Other Changes
- `Package.appxmanifest` — Updated from old `webatchify` identity to `voy-techapps.wexporting` with correct version `1.0.5.0` and executable name `wexporting-v1.0.5.0.exe`.
- `client/version.json` — Bumped to `1.0.5`, build `11`.

---

## Next Step: Test the MSI Install

Install the new MSI and verify the debug log:
```
%TEMP%\imgapp_startup_debug.txt
```

The log should now show ALL 6 sections completing:
1. `=== wexporting startup ===` header with paths
2. `DLL search dirs: [...]`
3. `[OK] AddDllDirectory: <path>` for each directory
4. `[OK] QT_PLUGIN_PATH = <path>`
5. `[OK] Wrote qt.conf to <path>`
6. `[OK] Pre-loaded Qt6Core.dll` etc.
7. `DLL bootstrap complete — proceeding to PySide6 import`

If the log reaches line 7 but the app still fails, the next step is MSIX packaging (bypasses `Program Files` ACL entirely via virtual file system).

---

## After MSI Test Passes → MSIX Packaging

Use `packaging\build_msix.bat` (requires Windows SDK in PATH):
```bat
cd V:\_MY_APPS\ImgApp_1
packaging\build_msix.bat
```

Output: `packaging\output\wexporting-1.0.5.0-x64.msix`

For Microsoft Store submission, upload via Partner Center:
https://partner.microsoft.com/dashboard

---
*Updated: 2026-03-10*
