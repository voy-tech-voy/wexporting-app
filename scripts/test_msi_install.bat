@echo off
REM Test the MSI installation

echo Testing MSI installation...
echo.

REM Uninstall any previous version
echo Uninstalling previous version (if exists)...
msiexec /x "V:\_MY_APPS\ImgApp_1\ImgApp_Releases\v9.0\webatchify-v9.0-installer.msi" /quiet /norestart

REM Wait for uninstall
timeout /t 3 /nobreak

REM Install fresh
echo.
echo Installing MSI...
msiexec /i "V:\_MY_APPS\ImgApp_1\ImgApp_Releases\v9.0\webatchify-v9.0-installer.msi" /passive /norestart

REM Check installation
echo.
echo Checking installation...
timeout /t 3 /nobreak

if exist "C:\Program Files\webatchify\webatchify-v9.0.exe" (
    echo [OK] Executable found at: C:\Program Files\webatchify\webatchify-v9.0.exe
) else (
    echo [ERROR] Executable NOT found at: C:\Program Files\webatchify\webatchify-v9.0.exe
    echo Listing contents of C:\Program Files\webatchify:
    dir "C:\Program Files\webatchify" 2>nul || echo (directory does not exist)
)

REM Check Start Menu shortcut
echo.
echo Checking Start Menu...
if exist "%ProgramData%\Microsoft\Windows\Start Menu\Programs\webatchify" (
    echo [OK] Start Menu folder found
    dir "%ProgramData%\Microsoft\Windows\Start Menu\Programs\webatchify"
) else (
    echo [ERROR] Start Menu folder NOT found
)

REM Check registry
echo.
echo Checking Apps & Features registry entry...
reg query "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\webatchify" /v DisplayName >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] App registered in Apps & Features
    reg query "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\webatchify"
) else (
    echo [ERROR] App NOT registered in Apps & Features
)

echo.
pause
