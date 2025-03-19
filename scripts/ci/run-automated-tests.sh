#!/bin/bash

# Construir imagen
podman build -t qzx-test-env -f containers/Containerfile.automated-tests .

# Ejecutar pruebas con restricciones de seguridad
podman run --rm \
    --security-opt seccomp=unconfined \
    --security-opt label=disable \
    --cap-drop=ALL \
    --cap-add=SYS_PTRACE \
    --pids-limit=100 \
    --memory=256m \
    --cpu-shares=512 \
    -v "$(pwd)/test-results:/app/test-results:Z" \
    qzx-test-env "$@" 