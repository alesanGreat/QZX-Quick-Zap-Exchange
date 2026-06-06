#!/bin/bash

# Construir imagen
podman build -t qzx-debug-env -f infra/containers/Containerfile.debug .

# Ejecutar entorno interactivo con montajes para datos y resultados
podman run --rm -it \
    --security-opt seccomp=unconfined \
    --security-opt label=disable \
    --cap-drop=ALL \
    --cap-add=SYS_PTRACE \
    -v "$(pwd)/artifacts/tests/results:/app/artifacts/tests/results:Z" \
    -v "$(pwd)/artifacts/tests/data:/app/artifacts/tests/data:Z" \
    qzx-debug-env
