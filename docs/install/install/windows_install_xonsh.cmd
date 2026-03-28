@echo off
:: Portable xonsh installer for Windows (no admin rights required)
::
:: Usage:
::   1. Open cmd.exe or PowerShell
::   2. Run: curl -L -o install_xonsh.cmd https://xon.sh/install/windows_install_xonsh.cmd
::   3. Run: install_xonsh.cmd
::   4. Run: %USERPROFILE%\xonsh-env\Scripts\xonsh.exe
::

set XONSH_DIR=%USERPROFILE%\xonsh-env
set PYTHON_VERSION=3.13.3
set PYTHON_ZIP=python-3.13.3-embed-amd64.zip
set PYTHON_PTH=python313._pth

echo === Installing portable xonsh to %XONSH_DIR% ===
echo.

if exist "%XONSH_DIR%\python.exe" (
    echo Python already installed, skipping download.
    goto install_xonsh
)

echo [1/4] Downloading Python %PYTHON_VERSION% embeddable...
mkdir "%XONSH_DIR%" 2>nul
curl -L -o "%XONSH_DIR%\python.zip" "https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_ZIP%"
if errorlevel 1 (
    echo ERROR: Failed to download Python.
    exit /b 1
)

echo [2/4] Extracting Python...
powershell -Command "Expand-Archive -Path '%XONSH_DIR%\python.zip' -DestinationPath '%XONSH_DIR%' -Force"
del "%XONSH_DIR%\python.zip"

echo import site>> "%XONSH_DIR%\%PYTHON_PTH%"

echo [3/4] Installing pip...
curl -L -o "%XONSH_DIR%\get-pip.py" "https://bootstrap.pypa.io/get-pip.py"
if errorlevel 1 (
    echo ERROR: Failed to download get-pip.py.
    exit /b 1
)
"%XONSH_DIR%\python.exe" "%XONSH_DIR%\get-pip.py" --no-warn-script-location -q
del "%XONSH_DIR%\get-pip.py"

:install_xonsh
echo [4/4] Installing xonsh...
"%XONSH_DIR%\python.exe" -m pip install "xonsh[full]" --no-warn-script-location -q
if errorlevel 1 (
    echo ERROR: Failed to install xonsh.
    exit /b 1
)

echo.
echo === Done! ===
echo.
echo Run xonsh:
echo   %XONSH_DIR%\Scripts\xonsh.exe
echo.
echo Add to PATH (optional, run once):
echo   setx PATH "%XONSH_DIR%\Scripts;%%PATH%%"
echo.
