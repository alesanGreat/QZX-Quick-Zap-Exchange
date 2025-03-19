#!/bin/bash

echo "==================================="
echo "QZX - PyPI Cleanup Script"
echo "==================================="
echo

echo "Limpiando archivos generados por PyPI..."
echo

# Eliminar carpeta build
if [ -d "build" ]; then
    echo "Eliminando carpeta 'build'..."
    rm -rf build
else
    echo "Carpeta 'build' no encontrada."
fi

# Eliminar carpeta dist
if [ -d "dist" ]; then
    echo "Eliminando carpeta 'dist'..."
    rm -rf dist
else
    echo "Carpeta 'dist' no encontrada."
fi

# Eliminar carpetas .egg-info
echo "Buscando y eliminando carpetas .egg-info..."
find . -name "*.egg-info" -type d -maxdepth 1 -exec echo "Eliminando '{}'..." \; -exec rm -rf {} \;

# Limpiar archivos .pyc y carpetas __pycache__ solo en directorios relevantes
echo "Eliminando archivos .pyc y carpetas __pycache__..."
for dir in Core Commands Resources tests; do
    if [ -d "$dir" ]; then
        echo "Buscando en el directorio $dir..."
        find "$dir" -name "__pycache__" -type d -exec echo "Eliminando '{}'..." \; -exec rm -rf {} \;
        find "$dir" -name "*.pyc" -type f -exec echo "Eliminando '{}'..." \; -exec rm -f {} \;
    fi
done

# Verificar si hay PyPi/build y PyPi/dist
if [ -d "PyPi/build" ]; then
    echo "Eliminando carpeta 'PyPi/build'..."
    rm -rf PyPi/build
fi

if [ -d "PyPi/dist" ]; then
    echo "Eliminando carpeta 'PyPi/dist'..."
    rm -rf PyPi/dist
fi

# Verificar si hay PyPi/*.egg-info
if [ -d "PyPi" ]; then
    echo "Buscando y eliminando carpetas .egg-info en PyPi..."
    find PyPi -name "*.egg-info" -type d -exec echo "Eliminando '{}'..." \; -exec rm -rf {} \;
fi

echo
echo "Limpieza completada."
echo "===================================" 