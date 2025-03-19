@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul


:: ====================================================
:: QZX - Quick Zap Exchange: Sistema de Backup Automático
:: ====================================================

:: Asegurar que el script use su propia ubicación como referencia
pushd "%~dp0"
echo Directorio de trabajo actual: %CD%

:: Configuración
set "BACKUP_DESTINATION=%CD%\Backups"
echo Destino de backup: %BACKUP_DESTINATION%

:: Verificar si existe el directorio de destino de backups
if not exist "%BACKUP_DESTINATION%" (
    mkdir "%BACKUP_DESTINATION%"
    echo Directorio de backups creado.
)

:: Obtener el nombre de la carpeta actual
for %%a in ("%CD%\.") do set "foldername=%%~nxa"
echo Nombre de la carpeta del proyecto: %foldername%

:: Configurar la fecha y hora para el nombre del archivo
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set "YYYY=%datetime:~0,4%"
set "MM=%datetime:~4,2%"
set "DD=%datetime:~6,2%"
set "HH=%datetime:~8,2%"
set "Min=%datetime:~10,2%"

:: Configurar nombre del backup
set "backupname=%BACKUP_DESTINATION%\%foldername%-AppBackup-%YYYY%-%MM%-%DD%--%HH%-%Min%.zip"
echo Nombre del archivo de backup: %backupname%

:: Buscar 7-Zip en Program Files
if exist "%ProgramFiles%\7-Zip\7z.exe" (
    set "zip=%ProgramFiles%\7-Zip\7z.exe"
    echo 7-Zip encontrado en: %zip%
) else if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" (
    set "zip=%ProgramFiles(x86)%\7-Zip\7z.exe"
    echo 7-Zip encontrado en: %zip%
) else (
    echo 7-Zip no encontrado. Descargando e instalando...
    powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://www.7-zip.org/a/7z2301-x64.exe', '7z-install.exe')"
    7z-install.exe /S
    set "zip=%ProgramFiles%\7-Zip\7z.exe"
    del 7z-install.exe
)

:: Crear archivo temporal de exclusiones
echo Creando lista de exclusiones...
(
    :: Carpetas y archivos de desarrollo Python
    echo __pycache__
    echo *.pyc
    echo *.pyo
    echo *.pyd
    echo .pytest_cache
    echo .coverage
    echo htmlcov
    echo .tox
    echo .nox
    echo .pytype
    echo .mypy_cache
    echo venv
    echo env
    echo .venv
    echo .env
    echo .python-version
    
    :: Carpetas de desarrollo
    echo node_modules
    echo .vscode
    echo .idea
    echo .git
    echo .github
    echo dist
    echo build
    echo coverage
    echo .next
    echo .nuxt
    
    :: Carpetas específicas del proyecto QZX
    echo android
    echo electron
    echo rust_upload
    echo release
    echo tmp
    echo temp
    echo .tmp
    echo .temp
    
    :: Archivos de desarrollo
    echo *.exe
    echo *.dll
    echo *.pdb
    echo *.cache
    echo *.zip
    echo *.rar
    echo *.user
    echo *.suo
    echo *.log
    echo *.tmp
    echo *.temp
    echo *.bat
    echo !AppBackup.bat
    echo !qzx.bat
    echo *.py
    echo !qzx.py
    echo !qzx_*.py
    echo !Core\*.py
    echo *.jks
    echo *.apk
    
    :: Archivos de configuración local
    echo .env
    echo .env.local
    echo .env.development
    echo .env.production
    
    :: Archivos del sistema
    echo .DS_Store
    echo Thumbs.db
    
    :: Archivos de dependencias
    echo bun.lockb
    echo package-lock.json
    echo yarn.lock
    echo pnpm-lock.yaml
    
    :: Archivos de caché
    echo .vite
    echo .cache
) > "%CD%\ignore_items.txt"

:: Crear el backup
echo Creando backup en: %backupname%
"%zip%" a -tzip "%backupname%" "." -xr@"%CD%\ignore_items.txt"

:: Limpiar
del "%CD%\ignore_items.txt"

echo Backup creado: %backupname%

:: Mantener la ventana abierta para ver mensajes
echo.
echo Presiona cualquier tecla para cerrar...
pause > nul
popd