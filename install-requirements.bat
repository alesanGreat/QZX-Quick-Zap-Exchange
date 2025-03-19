@echo off
rem QZX Terminal Dependencies Installer
rem This script installs the necessary dependencies for QZX Terminal

echo Installing QZX Terminal dependencies...

rem Check for Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    exit /b 1
)

rem Install pyreadline3 for Windows (readline equivalent)
echo Installing pyreadline3 for command history and editing...
python -m pip install pyreadline3

echo Installation complete!
echo You can now run QZX Terminal using one of these commands:
echo - python terminal.py
echo - qzx-terminal-fix.bat

pause 