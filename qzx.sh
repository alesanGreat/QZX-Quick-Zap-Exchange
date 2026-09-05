#!/bin/sh

# QZX - Quick Zap Exchange
# Universal Command Interface wrapper for Unix/Linux

# Get the directory where this script is located without depending on Bash.
SCRIPT_DIR="$(
    CDPATH= cd -- "$(dirname -- "$0")" >/dev/null 2>&1 && pwd -P
)"
export PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

QZX_RUNTIME=""

is_compatible_python() {
    "$1" -c 'import platform, sys, sysconfig; raise SystemExit(0 if platform.python_implementation() == "CPython" and sys.version_info >= (3, 11) and sysconfig.get_config_var("Py_GIL_DISABLED") != 1 else 1)' \
        >/dev/null 2>&1
}

if [ -n "${QZX_PYTHON:-}" ] && [ -x "$QZX_PYTHON" ] \
    && is_compatible_python "$QZX_PYTHON"; then
    QZX_RUNTIME="$QZX_PYTHON"
fi

if [ -z "$QZX_RUNTIME" ] && [ -n "${VIRTUAL_ENV:-}" ] \
    && [ -x "$VIRTUAL_ENV/bin/python" ] \
    && is_compatible_python "$VIRTUAL_ENV/bin/python"; then
    QZX_RUNTIME="$VIRTUAL_ENV/bin/python"
fi

if [ -z "$QZX_RUNTIME" ]; then
    for uv_root in \
        "${UV_PYTHON_INSTALL_DIR:-}" \
        "${XDG_DATA_HOME:-${HOME:-}/.local/share}/uv/python"; do
        [ -n "$uv_root" ] && [ -d "$uv_root" ] || continue
        for series in 3.13 3.14 3.12 3.11; do
            for candidate in "$uv_root"/cpython-"$series"*/bin/python"$series" \
                "$uv_root"/cpython-"$series"*/bin/python; do
                case "$candidate" in
                    *"+"*) continue ;;
                esac
                [ -x "$candidate" ] || continue
                is_compatible_python "$candidate" || continue
                QZX_RUNTIME="$candidate"
                break 3
            done
        done
    done
fi

if [ -z "$QZX_RUNTIME" ]; then
    for candidate in python3.13 python3.14 python3.12 python3.11 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 \
            && is_compatible_python "$candidate"; then
            QZX_RUNTIME="$(command -v "$candidate")"
            break
        fi
    done
fi

if [ -z "$QZX_RUNTIME" ] && command -v uv >/dev/null 2>&1; then
    for series in 3.13 3.14 3.12 3.11; do
        uv_python="$(uv python find "$series" 2>/dev/null || true)"
        if [ -n "$uv_python" ] && [ -x "$uv_python" ] \
            && is_compatible_python "$uv_python"; then
            QZX_RUNTIME="$uv_python"
            break
        fi
    done
fi

if [ -z "$QZX_RUNTIME" ]; then
    json_requested=false
    for argument in "$@"; do
        if [ "$argument" = "--json" ]; then
            json_requested=true
            break
        fi
    done
    if [ "$json_requested" = true ]; then
        printf '%s\n' \
            '{"success":false,"error_code":"compatible_python_not_found","error":"Compatible standard CPython was not found.","message":"QZX requires standard CPython 3.11 or newer; CPython 3.13.x is the cross-platform certification runtime. Install a compatible runtime with uv or make it available on PATH."}'
    else
        printf '%s\n' \
            'QZX requires standard CPython 3.11 or newer; CPython 3.13.x is the cross-platform certification runtime. Install a compatible runtime with uv or make it available on PATH.'
    fi
    exit 1
fi

# Pass all arguments to the QZX package
"$QZX_RUNTIME" -B -m qzx "$@"
