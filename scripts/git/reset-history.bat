@REM reset-git-history.bat
@echo off
setlocal enabledelayedexpansion

echo Creando nueva rama temporal sin historial...
git checkout --orphan temp

echo Agregando todos los archivos actuales...
git add .

echo Realizando commit inicial...
git commit -m "Estado inicial"

echo Eliminando rama principal...
git branch -D main 2>nul
if %errorlevel% neq 0 (
    echo La rama main no existia. Continuando...
) else (
    echo Rama main eliminada.
)

echo Renombrando rama temporal a main...
git branch -m main

echo Verificando si existe un remoto 'origin'...
git remote -v | findstr "origin" >nul
if %errorlevel% neq 0 (
    echo No se encontro un remoto 'origin'. Saltando push y configuracion de upstream.
    echo Para agregar un remoto, use: git remote add origin URL_DEL_REPOSITORIO
) else (
    echo Remoto 'origin' encontrado, intentando push...
    git push -f origin main 2>nul
    if %errorlevel% neq 0 (
        echo No se pudo hacer push al remoto. Compruebe los permisos y la conectividad.
        echo El historial local se ha resetado correctamente.
    ) else (
        echo Push completado exitosamente.
        echo Configurando el upstream de la rama main...
        git branch --set-upstream-to=origin/main main 2>nul
        if %errorlevel% neq 0 (
            echo No se pudo configurar el upstream, pero el historial local se ha resetado correctamente.
        ) else (
            echo Upstream configurado correctamente.
        )
    )
)

echo Proceso completado.
pause