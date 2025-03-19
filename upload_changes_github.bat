@echo off
git add .

:: Check if a parameter was provided for the commit message
if "%~1"=="" (
    :: If no parameter, use the default message
    git commit -m "Updates"
) else (
    :: If there is a parameter, use it as message
    git commit -m "%~1"
)

git push