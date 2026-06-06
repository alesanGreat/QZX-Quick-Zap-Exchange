@echo off
rem QZX Terminal Fix - Script to launch QZX Terminal correctly
set "SCRIPT_DIR=%~dp0"

echo Starting QZX Terminal...
python "%SCRIPT_DIR%launch_terminal.py"

rem If the above fails, try the fallback script
if %ERRORLEVEL% NEQ 0 (
    echo Trying alternate method...
    python "%SCRIPT_DIR%qzx_wrapper.py" terminal
)

rem If both fail, show error
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to start QZX Terminal.
    echo Please try: python "%SCRIPT_DIR%launch_terminal.py"
    exit /b 1
)
