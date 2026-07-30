#!/bin/bash

# QZX - Quick Zap Exchange
# Universal Command Interface wrapper for Unix/Linux

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

QZX_RUNTIME=""

is_compatible_python() {
    "$1" -c 'import platform, sys, sysconfig; raise SystemExit(0 if platform.python_implementation() == "CPython" and sys.version_info[:2] == (3, 13) and sysconfig.get_config_var("Py_GIL_DISABLED") != 1 else 1)' \
        >/dev/null 2>&1
}

if [[ -n "${QZX_PYTHON:-}" ]] && [[ -x "$QZX_PYTHON" ]] \
    && is_compatible_python "$QZX_PYTHON"; then
    QZX_RUNTIME="$QZX_PYTHON"
fi

if [[ -z "$QZX_RUNTIME" ]] && [[ -n "${VIRTUAL_ENV:-}" ]] \
    && [[ -x "$VIRTUAL_ENV/bin/python" ]] \
    && is_compatible_python "$VIRTUAL_ENV/bin/python"; then
    QZX_RUNTIME="$VIRTUAL_ENV/bin/python"
fi

if [[ -z "$QZX_RUNTIME" ]]; then
    uv_roots=(
        "${UV_PYTHON_INSTALL_DIR:-}"
        "${XDG_DATA_HOME:-$HOME/.local/share}/uv/python"
    )
    for uv_root in "${uv_roots[@]}"; do
        [[ -d "$uv_root" ]] || continue
        for candidate in "$uv_root"/cpython-3.13*/bin/python3.13 \
            "$uv_root"/cpython-3.13*/bin/python; do
            if [[ -x "$candidate" ]] && [[ "$candidate" != *"+"* ]] \
                && is_compatible_python "$candidate"; then
                QZX_RUNTIME="$candidate"
                break 2
            fi
        done
    done
fi

if [[ -z "$QZX_RUNTIME" ]]; then
    for candidate in python3.13 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 \
            && is_compatible_python "$candidate"; then
            QZX_RUNTIME="$(command -v "$candidate")"
            break
        fi
    done
fi

if [[ -z "$QZX_RUNTIME" ]] && command -v uv >/dev/null 2>&1; then
    uv_python="$(uv python find 3.13 2>/dev/null || true)"
    if [[ -n "$uv_python" ]] && [[ -x "$uv_python" ]] && is_compatible_python "$uv_python"; then
        QZX_RUNTIME="$uv_python"
    fi
fi

if [[ -z "$QZX_RUNTIME" ]]; then
    json_requested=false
    for argument in "$@"; do
        if [[ "$argument" == "--json" ]]; then
            json_requested=true
            break
        fi
    done
    if [[ "$json_requested" == true ]]; then
        printf '%s\n' \
            '{"success":false,"error_code":"compatible_python_not_found","error":"Standard CPython 3.13 was not found.","message":"QZX requires the standard CPython 3.13.x build. Install it with uv or make a compatible python executable available on PATH."}'
    else
        printf '%s\n' \
            'QZX requires the standard CPython 3.13.x build. Install it with uv or make a compatible python executable available on PATH.'
    fi
    exit 1
fi

# Pass all arguments to the QZX package
"$QZX_RUNTIME" -m qzx "$@"
