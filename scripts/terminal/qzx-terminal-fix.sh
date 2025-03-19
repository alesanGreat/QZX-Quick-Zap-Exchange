#!/bin/bash
# QZX Terminal Fix - Script to launch QZX Terminal correctly
# This is a workaround for the issue with qzx.py not executing the Terminal command

echo "Starting QZX Terminal..."
python terminal.py

# If the above fails, try the fallback script
if [ $? -ne 0 ]; then
    echo "Trying alternate method..."
    python qzx_terminal.py
fi

# If both fail, show error
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start QZX Terminal."
    echo "Please try: python terminal.py"
    exit 1
fi 