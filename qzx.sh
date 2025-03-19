#!/bin/bash

# QZX - Quick Zap Exchange
# Universal Command Interface wrapper for Unix/Linux

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
QZX_PYTHON="$SCRIPT_DIR/qzx.py"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required to run QZX"
    exit 1
fi

# Make sure the Python script is executable
chmod +x "$QZX_PYTHON" 2>/dev/null

# Pass all arguments to the Python script
python3 "$QZX_PYTHON" "$@" 