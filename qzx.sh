#!/bin/bash

# QZX - Quick Zap Exchange
# Universal Command Interface wrapper for Unix/Linux

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

QZX_PYTHON=""

is_compatible_python() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)' \
        >/dev/null 2>&1
}

for candidate in python3.13 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && is_compatible_python "$candidate"; then
        QZX_PYTHON="$(command -v "$candidate")"
        break
    fi
done

if [[ -z "$QZX_PYTHON" ]] && command -v uv >/dev/null 2>&1; then
    uv_python="$(uv python find 3.13 2>/dev/null || true)"
    if [[ -n "$uv_python" ]] && [[ -x "$uv_python" ]] && is_compatible_python "$uv_python"; then
        QZX_PYTHON="$uv_python"
    fi
fi

if [[ -z "$QZX_PYTHON" ]]; then
    json_requested=false
    for argument in "$@"; do
        if [[ "$argument" == "--json" ]]; then
            json_requested=true
            break
        fi
    done
    if [[ "$json_requested" == true ]]; then
        printf '%s\n' \
            '{"success":false,"error_code":"compatible_python_not_found","error":"CPython 3.13 or newer was not found.","message":"QZX requires CPython 3.13 or newer. Install it with uv or make a compatible python executable available on PATH."}'
    else
        printf '%s\n' \
            'QZX requires CPython 3.13 or newer. Install it with uv or make a compatible python executable available on PATH.'
    fi
    exit 1
fi

# Pass all arguments to the QZX package
"$QZX_PYTHON" -m qzx "$@"
