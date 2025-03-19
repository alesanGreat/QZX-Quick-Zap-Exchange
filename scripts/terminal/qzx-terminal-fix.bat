@echo off
rem QZX Terminal Fix - Script to launch QZX Terminal correctly
rem This is a workaround for the issue with qzx.py not executing the Terminal command

echo Starting QZX Terminal...
python terminal.py

rem If the above fails, try the fallback script
if %ERRORLEVEL% NEQ 0 (
    echo Trying alternate method...
    python qzx_terminal.py
)

rem If both fail, show error
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to start QZX Terminal.
    echo Please try: python terminal.py
    exit /b 1
) 