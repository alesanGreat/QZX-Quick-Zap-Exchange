@echo off
echo ===================================
echo QZX - PyPI Cleanup Script
echo ===================================
echo.

echo Limpiando archivos generados por PyPI...
echo.

:: Eliminar carpeta build
if exist build (
    echo Eliminando carpeta 'build'...
    rmdir /s /q build
) else (
    echo Carpeta 'build' no encontrada.
)

:: Eliminar carpeta dist
if exist dist (
    echo Eliminando carpeta 'dist'...
    rmdir /s /q dist
) else (
    echo Carpeta 'dist' no encontrada.
)

:: Eliminar carpetas .egg-info
echo Buscando y eliminando carpetas .egg-info...
for /d %%i in (*.egg-info) do (
    echo Eliminando '%%i'...
    rmdir /s /q "%%i"
)

:: Limpiar archivos .pyc y carpetas __pycache__
echo Eliminando archivos .pyc y carpetas __pycache__...
:: Solo buscar en directorios relevantes para evitar errores innecesarios
for /d %%d in (Core Commands Resources tests) do (
    if exist %%d (
        echo Buscando en el directorio %%d...
        for /d /r %%d\. %%i in (__pycache__) do (
            echo Eliminando '%%i'...
            rmdir /s /q "%%i"
        )
    )
)

:: Limpiar archivos temporales
if exist *.pyc (
    echo Eliminando archivos .pyc en la raíz...
    del /q *.pyc
)

:: Verificar si hay PyPi/build y PyPi/dist
if exist PyPi\build (
    echo Eliminando carpeta 'PyPi\build'...
    rmdir /s /q PyPi\build
)

if exist PyPi\dist (
    echo Eliminando carpeta 'PyPi\dist'...
    rmdir /s /q PyPi\dist
)

:: Verificar si hay PyPi/*.egg-info
if exist PyPi (
    echo Buscando y eliminando carpetas .egg-info en PyPi...
    for /d %%i in (PyPi\*.egg-info) do (
        echo Eliminando '%%i'...
        rmdir /s /q "%%i"
    )
)

echo.
echo Limpieza completada.
echo =================================== 