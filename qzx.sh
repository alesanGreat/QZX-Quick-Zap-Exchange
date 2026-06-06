#!/bin/bash

# QZX - Quick Zap Exchange
# Universal Command Interface wrapper for Unix/Linux

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required to run QZX"
    exit 1
fi

# Pass all arguments to the QZX package
python3 -m qzx "$@"
