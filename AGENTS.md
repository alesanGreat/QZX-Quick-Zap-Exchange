# QZX Agent Guidelines & Documentation (AGENTS.md)

Este documento sirve como guía para agentes de IA (como Gemini, Claude, etc.) que trabajen en el codebase de **QZX - Quick Zap Exchange**.

---

## 1. Filosofía de Desarrollo: "Verbose is Gold"
A diferencia de los principios tradicionales de Unix que favorecen el silencio en ejecuciones exitosas, en **QZX** operamos bajo el principio **"Verbose is Gold"** (Lo detallado es oro).
* **Para humanos:** El silencio es elegante.
* **Para agentes de IA:** El silencio es un callejón sin salida.

### Reglas para salidas de comandos y scripts:
* **Estructura JSON:** Todo comando de QZX debe retornar un objeto estructurado que contenga al menos:
  ```json
  {
    "success": true,
    "message": "Mensaje legible y descriptivo con el estado de la operación",
    "details": { ... datos adicionales enriquecedores ... }
  }
  ```
* **Ambigüedad Cero:** Evita respuestas booleanas simples (`true`/`false`) o números huérfanos. Proveer siempre la unidad, el contexto y los valores relativos.

---

## 2. Estructura de Directorios

El repositorio está dividido en dos partes principales:
1. **Core / Backend (Python):** En la raíz del repositorio y bajo `src/qzx/`.
2. **Frontend (React/TypeScript/Vite):** Ubicado en `WebsiteQZX/`.
   > [!IMPORTANT]
   > El directorio `WebsiteQZX/` está completamente ignorado en el `.gitignore` raíz del repositorio. Las modificaciones allí deben gestionarse de forma dedicada.

### Organización de Scripts de Utilidad (`.bat` / `.sh`):
Tanto en el backend como en el frontend, los scripts de automatización están organizados en subdirectorios dentro de la carpeta `scripts/` según su propósito:
* `git/` - Operaciones y flujos del control de versiones (ej. `reset-git-history.bat`, `subir_cambios_github.bat`).
* `maintenance/` - Respaldos y limpiezas (ej. `AppBackup.bat`).
* `setup/` - Instalación de dependencias y configuración (ej. `actualizar_modulos.bat`, `shadcn-add.bat`).
* `utils/` - Generadores de documentación y metadatos (ej. `generate_json_commands_tsx.bat`).

---

## 3. Reglas Técnicas para Scripts Batch (`.bat`)
Al crear o modificar scripts en Windows, se deben seguir estas reglas para asegurar compatibilidad y robustez:
1. **Aislamiento del Directorio de Trabajo (CWD):** Nunca asumas que el script se ejecuta desde su propia carpeta. Usa siempre `pushd` y `popd` apuntando de forma relativa a `%~dp0`.
   * *Ejemplo (Script en `scripts/setup/` que necesita ejecutarse en la raíz de la web):*
     ```bat
     @echo off
     pushd "%~dp0..\.."
     call npx npm-check-updates -u
     popd
     ```
2. **Codificación:** Utiliza `chcp 65001 > nul` para forzar la compatibilidad con UTF-8 si el script imprime caracteres especiales o acentos.
3. **No utilices variables de entorno globales no inicializadas.** Siempre inicializa localmente usando `setlocal`.

---

## 4. Integridad del Código y de la Documentación
* **Comentarios:** Preserva todos los comentarios y docstrings existentes que no estén directamente relacionados con tu cambio.
* **Auto-generación de Docs:** Si añades comandos al backend de Python en `src/qzx/commands/`, ejecuta el generador de JSON para que el frontend del sitio web se mantenga actualizado:
  ```powershell
  # Ejecuta
  .\WebsiteQZX\scripts\utils\generate_json_commands_tsx.bat
  ```

## 5. Cómo Extender QZX (Añadir Nuevos Comandos)

Para que el sistema de carga dinámica y autogeneración de documentación funcione correctamente, los agentes que añadan nuevos comandos deben seguir esta estructura:

1. **Definir la Clase del Comando:** Crea una clase en Python que herede de `CommandBase`:
   ```python
   from qzx.core.command_base import CommandBase

   class MyCommand(CommandBase):
       name = "myCommand"
       description = "Descripción concisa de lo que hace el comando"
       category = "development"  # Categorías disponibles: dev, development, file, system, misc

       def execute(self, param1, param2):
           # Lógica del comando...
           return {
               "success": True,
               "result": f"{param1}, {param2}",
               "message": "Operation completed successfully."
           }
   ```
2. **Ubicación:** Guarda la clase en el directorio correspondiente bajo `src/qzx/commands/<categoría>/`. El cargador dinámico (`CommandLoader`) descubrirá y registrará automáticamente el comando.
3. **Regenerar Documentación:** Siempre que agregues un nuevo comando, recuerda regenerar el archivo JSON de comandos utilizando el script automatizado (Sección 4).

---
*Documento creado el 6 de junio de 2026 para la automatización e integración eficiente de agentes.*
