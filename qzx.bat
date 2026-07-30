@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM QZX - Quick Zap Exchange
REM Universal Command Interface wrapper for Windows

REM Get the directory where this script is located
SET "SCRIPT_DIR=%~dp0"
SET "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"
SET "QZX_RUNTIME="

REM Honor an explicit interpreter first.
IF DEFINED QZX_PYTHON (
    IF EXIST "%QZX_PYTHON%" (
        "%QZX_PYTHON%" -c "import platform,sys,sysconfig; raise SystemExit(0 if platform.python_implementation() == 'CPython' and sys.version_info[:2] == (3, 13) and sysconfig.get_config_var('Py_GIL_DISABLED') not in (1, True) else 1)" >nul 2>&1
        IF NOT ERRORLEVEL 1 SET "QZX_RUNTIME=%QZX_PYTHON%"
    )
)

REM Preserve an explicitly activated standard CPython 3.13 environment.
IF NOT DEFINED QZX_RUNTIME IF DEFINED VIRTUAL_ENV (
    IF EXIST "%VIRTUAL_ENV%\Scripts\python.exe" (
        "%VIRTUAL_ENV%\Scripts\python.exe" -c "import platform,sys,sysconfig; raise SystemExit(0 if platform.python_implementation() == 'CPython' and sys.version_info[:2] == (3, 13) and sysconfig.get_config_var('Py_GIL_DISABLED') not in (1, True) else 1)" >nul 2>&1
        IF NOT ERRORLEVEL 1 SET "QZX_RUNTIME=%VIRTUAL_ENV%\Scripts\python.exe"
    )
)

REM Recognize managed Python roots exposed by actions/setup-python, CMake,
REM and other professional toolchains. These locations remain available even
REM when a caller deliberately supplies a minimal PATH.
IF NOT DEFINED QZX_RUNTIME (
    FOR %%R IN ("%pythonLocation%" "%Python_ROOT_DIR%" "%Python3_ROOT_DIR%") DO (
        IF NOT DEFINED QZX_RUNTIME IF EXIST "%%~R\python.exe" (
            "%%~R\python.exe" -c "import platform,sys,sysconfig; raise SystemExit(0 if platform.python_implementation() == 'CPython' and sys.version_info[:2] == (3, 13) and sysconfig.get_config_var('Py_GIL_DISABLED') not in (1, True) else 1)" >nul 2>&1
            IF NOT ERRORLEVEL 1 SET "QZX_RUNTIME=%%~R\python.exe"
        )
    )
)

REM uv uses deterministic installation directories. Checking them directly
REM avoids several slow PATH traversals plus a separate `uv python find`
REM process on every QZX invocation.
IF NOT DEFINED QZX_RUNTIME (
    FOR %%R IN ("%UV_PYTHON_INSTALL_DIR%" "%APPDATA%\uv\python" "%LOCALAPPDATA%\uv\python") DO (
        IF NOT DEFINED QZX_RUNTIME IF EXIST "%%~R" (
            FOR /D %%D IN ("%%~R\cpython-3.13*-windows-*") DO (
                IF NOT DEFINED QZX_RUNTIME IF EXIST "%%~fD\python.exe" (
                    SET "QZX_UV_RUNTIME_NAME=%%~nxD"
                    IF "!QZX_UV_RUNTIME_NAME:+=!"=="!QZX_UV_RUNTIME_NAME!" (
                        SET "QZX_RUNTIME=%%~fD\python.exe"
                    )
                )
            )
        )
    )
)

REM Prefer a compatible Python on PATH when no managed runtime was found.
REM %%~$PATH:P is cmd.exe's built-in lookup and is much faster than spawning
REM WHERE.EXE once for every candidate.
IF NOT DEFINED QZX_RUNTIME (
    FOR %%P IN (python.exe python3.13.exe python3.exe) DO (
        IF NOT DEFINED QZX_RUNTIME IF NOT "%%~$PATH:P"=="" (
            SET "QZX_PATH_RUNTIME=%%~$PATH:P"
            "!QZX_PATH_RUNTIME!" -c "import platform,sys,sysconfig; raise SystemExit(0 if platform.python_implementation() == 'CPython' and sys.version_info[:2] == (3, 13) and sysconfig.get_config_var('Py_GIL_DISABLED') not in (1, True) else 1)" >nul 2>&1
            IF NOT ERRORLEVEL 1 SET "QZX_RUNTIME=!QZX_PATH_RUNTIME!"
        )
    )
)

REM Portable fallback for non-standard uv installation directories.
IF NOT DEFINED QZX_RUNTIME (
    SET "QZX_UV=%USERPROFILE%\.local\bin\uv.exe"
    IF EXIST "!QZX_UV!" (
        FOR /F "usebackq delims=" %%P IN (`"!QZX_UV!" python find 3.13 2^>nul`) DO (
            IF NOT DEFINED QZX_RUNTIME IF EXIST "%%P" (
                "%%P" -c "import platform,sys,sysconfig; raise SystemExit(0 if platform.python_implementation() == 'CPython' and sys.version_info[:2] == (3, 13) and sysconfig.get_config_var('Py_GIL_DISABLED') not in (1, True) else 1)" >nul 2>&1
                IF NOT ERRORLEVEL 1 SET "QZX_RUNTIME=%%P"
            )
        )
    )
)

IF NOT DEFINED QZX_RUNTIME (
    SET "QZX_JSON_REQUESTED=0"
    FOR %%A IN (%*) DO (
        IF /I "%%~A"=="--json" SET "QZX_JSON_REQUESTED=1"
    )
    IF "!QZX_JSON_REQUESTED!"=="1" (
        ECHO {"success":false,"error_code":"compatible_python_not_found","error":"Standard CPython 3.13 was not found.","message":"QZX requires the standard CPython 3.13.x build. Install it with uv or make a compatible python executable available on PATH."}
    ) ELSE (
        ECHO QZX requires the standard CPython 3.13.x build. Install it with uv or make a compatible python executable available on PATH.
    )
    ENDLOCAL
    EXIT /B 1
)

REM Pass every original argument to the QZX package and preserve its exit code.
"%QZX_RUNTIME%" -m qzx %*
SET "QZX_EXIT_CODE=%ERRORLEVEL%"
ENDLOCAL & EXIT /B %QZX_EXIT_CODE%
