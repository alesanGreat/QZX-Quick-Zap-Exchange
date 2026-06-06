#!/bin/bash
# QZX Terminal Fix - Script to launch QZX Terminal correctly
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting QZX Terminal..."
python3 "$SCRIPT_DIR/launch_terminal.py"

# If the above fails, try the fallback script
if [ $? -ne 0 ]; then
    echo "Trying alternate method..."
    python3 "$SCRIPT_DIR/qzx_wrapper.py" terminal
fi

# If both fail, show error
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start QZX Terminal."
    echo "Please try: python3 $SCRIPT_DIR/launch_terminal.py"
    exit 1
fi
