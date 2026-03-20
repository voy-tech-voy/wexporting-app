@echo off
setlocal EnableDelayedExpansion

title wexporting - MSI Builder

set "APP_ROOT=%~dp0"
set "VENV_PY=%APP_ROOT%imgapp_venv\Scripts\python.exe"
set "BUILD_SCRIPT=%APP_ROOT%build\scripts\build_msi.py"

echo.
echo ================================================
echo   wexporting MSI Builder
echo ================================================
echo.

rem Check venv exists
if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment not found at:
    echo         %VENV_PY%
    echo.
    echo Run: python -m venv imgapp_venv
    echo Then: imgapp_venv\Scripts\pip install -r requirements.txt
    goto :error
)

rem Optional version override via argument: BUILD_MSI.bat 1.0.5.0
if not "%~1"=="" (
    set "BUILD_VERSION=%~1"
    echo [INFO] Version override: %BUILD_VERSION%
    echo.
)

rem Run from project root so all relative paths resolve correctly
pushd "%APP_ROOT%"
"%VENV_PY%" "%BUILD_SCRIPT%"
set "EXIT_CODE=!ERRORLEVEL!"
popd

if !EXIT_CODE! neq 0 goto :error

echo.
echo ================================================
echo   BUILD COMPLETE
echo ================================================
echo.
pause
exit /b 0

:error
echo.
echo ================================================
echo   BUILD FAILED  (exit code: !EXIT_CODE!)
echo ================================================
echo.
pause
exit /b !EXIT_CODE!
