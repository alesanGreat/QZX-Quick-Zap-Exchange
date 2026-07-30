@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM QZX - Quick Zap Exchange
REM Universal Command Interface wrapper for Windows

REM Get the directory where this script is located
SET "SCRIPT_DIR=%~dp0"
SET "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"
SET "QZX_PYTHON="

REM Prefer a compatible Python already on PATH.
FOR %%P IN (python.exe python3.13.exe python3.exe) DO (
    IF NOT DEFINED QZX_PYTHON (
        WHERE %%P >nul 2>&1
        IF NOT ERRORLEVEL 1 (
            %%P -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
            IF NOT ERRORLEVEL 1 SET "QZX_PYTHON=%%P"
        )
    )
)

REM Fall back to the reusable CPython 3.13 installation managed by uv.
IF NOT DEFINED QZX_PYTHON (
    SET "QZX_UV=%USERPROFILE%\.local\bin\uv.exe"
    IF EXIST "!QZX_UV!" (
        FOR /F "usebackq delims=" %%P IN (`"!QZX_UV!" python find 3.13 2^>nul`) DO (
            IF NOT DEFINED QZX_PYTHON IF EXIST "%%P" SET "QZX_PYTHON=%%P"
        )
    )
)

IF NOT DEFINED QZX_PYTHON (
    SET "QZX_JSON_REQUESTED=0"
    FOR %%A IN (%*) DO (
        IF /I "%%~A"=="--json" SET "QZX_JSON_REQUESTED=1"
    )
    IF "!QZX_JSON_REQUESTED!"=="1" (
        ECHO {"success":false,"error_code":"compatible_python_not_found","error":"CPython 3.13 or newer was not found.","message":"QZX requires CPython 3.13 or newer. Install it with uv or make a compatible python executable available on PATH."}
    ) ELSE (
        ECHO QZX requires CPython 3.13 or newer. Install it with uv or make a compatible python executable available on PATH.
    )
    ENDLOCAL
    EXIT /B 1
)

REM Pass every original argument to the QZX package and preserve its exit code.
"%QZX_PYTHON%" -m qzx %*
SET "QZX_EXIT_CODE=%ERRORLEVEL%"
ENDLOCAL & EXIT /B %QZX_EXIT_CODE%
