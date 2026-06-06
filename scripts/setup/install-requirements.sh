#!/bin/bash
# QZX Terminal Dependencies Installer
# This script installs the necessary dependencies for QZX Terminal

echo "Installing QZX Terminal dependencies..."

# Check for Python
if ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH."
    echo "Please install Python using your package manager."
    exit 1
fi

# Check platform and install appropriate dependencies
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "macOS detected, readline should be available by default."
    echo "If you have issues, install it with: brew install readline"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "Linux detected, checking for readline..."
    if ! python -c "import readline" &> /dev/null; then
        echo "Installing readline development library..."
        if command -v apt-get &> /dev/null; then
            # Debian/Ubuntu
            sudo apt-get install -y libreadline-dev
        elif command -v yum &> /dev/null; then
            # RHEL/CentOS/Fedora
            sudo yum install -y readline-devel
        else
            echo "Warning: Unsupported package manager. Please install the readline library manually."
        fi
    else
        echo "readline is already available."
    fi
else
    # Other platform
    echo "Unknown platform: $OSTYPE"
    echo "You may need to install readline manually."
fi

echo "Installation complete!"
echo "You can now run QZX Terminal using one of these commands:"
echo "- python terminal.py"
echo "- ./qzx-terminal-fix.sh" 