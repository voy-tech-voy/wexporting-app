@echo off
REM ============================================================================
REM  webatchify MSIX Packaging Pipeline
REM  Run this AFTER PyInstaller build completes.
REM  Prerequisites:
REM    - Windows 10/11 SDK installed (MakeAppx.exe + SignTool.exe in PATH)
REM    - A valid code-signing certificate (.pfx) matching the Publisher CN
REM    - PyInstaller output in: dist\webatchify-v1.1.2\
REM ============================================================================

setlocal enabledelayedexpansion

REM ── Configuration ────────────────────────────────────────────────────────────
set APP_NAME=webatchify
set VERSION=1.1.2.0
set ARCH=x64
set DIST_DIR=dist\webatchify-v1.1.2
set ASSETS_DIR=Assets
set MANIFEST=Package.appxmanifest
set OUT_DIR=packaging\output
set MSIX_NAME=%APP_NAME%-%VERSION%-%ARCH%.msix
set CERT_PFX=packaging\cert\voy-tech-apps.pfx

REM ── Validate prerequisites ────────────────────────────────────────────────── 
echo [1/6] Checking prerequisites...

where MakeAppx.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: MakeAppx.exe not found. Install Windows 10 SDK.
    echo        Typical path: C:\Program Files (x86)\Windows Kits\10\bin\10.0.xxxxx.0\x64\
    exit /b 1
)

where SignTool.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: SignTool.exe not found. Install Windows 10 SDK.
    exit /b 1
)

if not exist "%DIST_DIR%\" (
    echo ERROR: PyInstaller output not found at "%DIST_DIR%\"
    echo        Run PyInstaller first: pyinstaller webatchify-v1.1.2.spec
    exit /b 1
)

if not exist "%CERT_PFX%" (
    echo ERROR: Certificate not found at "%CERT_PFX%"
    echo        Place your .pfx signing certificate there.
    exit /b 1
)

REM ── Prepare staging folder ───────────────────────────────────────────────── 
echo [2/6] Preparing staging folder...
if exist "%OUT_DIR%" rmdir /s /q "%OUT_DIR%"
mkdir "%OUT_DIR%\package"

REM Copy PyInstaller output
xcopy /e /i /q "%DIST_DIR%\*" "%OUT_DIR%\package\" >nul

REM Copy manifest and Assets
copy /y "%MANIFEST%" "%OUT_DIR%\package\Package.appxmanifest" >nul
xcopy /e /i /q "%ASSETS_DIR%\*" "%OUT_DIR%\package\Assets\" >nul

REM Copy Licenses and third-party notices (required for Store compliance)
xcopy /e /i /q "Licenses\*" "%OUT_DIR%\package\Licenses\" >nul
copy /y "THIRD-PARTY-NOTICES.md" "%OUT_DIR%\package\" >nul

echo     Staging complete: %OUT_DIR%\package\

REM ── Pack MSIX ────────────────────────────────────────────────────────────── 
echo [3/6] Packing MSIX...
MakeAppx.exe pack /d "%OUT_DIR%\package" /p "%OUT_DIR%\%MSIX_NAME%" /o /nv
if errorlevel 1 (
    echo ERROR: MakeAppx failed. Check the manifest and file structure.
    exit /b 1
)
echo     Created: %OUT_DIR%\%MSIX_NAME%

REM ── Run WACK (local validation) ───────────────────────────────────────────── 
echo [4/6] Running Windows App Certification Kit (WACK)...
where appcert.exe >nul 2>&1
if errorlevel 1 (
    echo WARNING: appcert.exe not found. Skipping local WACK.
    echo          Install Windows App Certification Kit separately, or run via the Store portal.
) else (
    appcert.exe runtest -apptype desktop -packagefullname "%OUT_DIR%\%MSIX_NAME%" -reportoutputpath "%OUT_DIR%\wack_report.xml"
    echo     WACK report: %OUT_DIR%\wack_report.xml
)

REM ── Sign MSIX ────────────────────────────────────────────────────────────── 
echo [5/6] Signing MSIX...
set /p CERT_PASS=Enter certificate password: 
SignTool.exe sign /fd SHA256 /a /f "%CERT_PFX%" /p "%CERT_PASS%" "%OUT_DIR%\%MSIX_NAME%"
if errorlevel 1 (
    echo ERROR: Signing failed. Check certificate and password.
    exit /b 1
)
echo     Signed successfully.

REM ── Verify signature ──────────────────────────────────────────────────────── 
echo [6/6] Verifying signature...
SignTool.exe verify /pa "%OUT_DIR%\%MSIX_NAME%"
if errorlevel 1 (
    echo WARNING: Signature verification failed. The package may not install correctly.
) else (
    echo     Signature valid.
)

REM ── Done ─────────────────────────────────────────────────────────────────── 
echo.
echo ============================================================
echo  BUILD COMPLETE
echo  MSIX: %OUT_DIR%\%MSIX_NAME%
echo ============================================================
echo  Next step: Upload to Partner Center
echo    https://partner.microsoft.com/dashboard
echo ============================================================
echo.

endlocal
