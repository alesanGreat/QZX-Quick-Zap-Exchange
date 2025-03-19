#!/bin/bash

echo "==================================="
echo "QZX - PyPI Publishing Script"
echo "==================================="

echo
echo "Step 1: Cleaning up previous build files..."
# Limpiamos los archivos de construcción
rm -rf build/ dist/ *.egg-info
echo "Cleanup completed."

echo
echo "Step 2: Installing required tools..."
pip install --upgrade pip build twine wheel

echo
echo "Step 3: Building distribution packages..."
# Construimos el paquete
python setup.py sdist bdist_wheel
if [ $? -ne 0 ]; then
    echo
    echo "Error: Build process failed."
    echo "Please close all programs that might be using project files and try again."
    echo
    exit 1
fi

echo
echo "Step 4: Checking the distribution packages..."
twine check dist/*
if [ $? -ne 0 ]; then
    echo
    echo "Error: Package verification failed."
    echo
    exit 1
fi

echo
echo "Step 5: Uploading to PyPI..."
echo "Note: You'll be asked for your PyPI username and password."
echo
read -p "Upload to PyPI? (y/n): " UPLOAD
if [[ "$UPLOAD" =~ ^[Yy]$ ]]; then
    twine upload dist/*
    if [ $? -ne 0 ]; then
        echo
        echo "Error: Upload to PyPI failed!"
        echo "Please check your credentials and try again."
        echo "To generate an API token visit: https://pypi.org/manage/account/token/"
        echo
        exit 1
    fi
    echo
    echo "Package published to PyPI!"
    echo "Users can now install with: pip install qzx"
else
    echo
    echo "Upload cancelled. You can manually upload with:"
    echo "twine upload dist/*"
fi

echo
echo "Process completed." 