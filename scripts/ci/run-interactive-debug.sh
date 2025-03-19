#!/bin/bash

# Construir imagen
podman build -t qzx-debug-env -f containers/Containerfile.interactive-debug .

# Ejecutar entorno interactivo con montajes para datos y resultados
podman run --rm -it \
    --security-opt seccomp=unconfined \
    --security-opt label=disable \
    --cap-drop=ALL \
    --cap-add=SYS_PTRACE \
    -v "$(pwd)/test-results:/app/test-results:Z" \
    -v "$(pwd)/test-data:/app/test-data:Z" \
    qzx-debug-env 