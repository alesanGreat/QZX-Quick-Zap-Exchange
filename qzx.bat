@echo off
REM QZX - Quick Zap Exchange
REM Universal Command Interface wrapper for Windows

REM Get the directory where this script is located
SET "SCRIPT_DIR=%~dp0"
SET "QZX_PYTHON=%SCRIPT_DIR%qzx.py"

REM Check if Python is available
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO Error: Python is required to run QZX
    EXIT /B 1
)

REM Pass all arguments to the Python script
python "%QZX_PYTHON%" %* 