# Averiguar qué proceso está usando un puerto en Windows, Linux o macOS con QZX

QZX — Quick Zap Exchange, creado y mantenido por Alejandro Sánchez.

Usá este flujo cuando un servidor de desarrollo, una base de datos, una API local, un contenedor u otro servicio no pueda iniciar porque un puerto TCP o UDP ya está ocupado. El objetivo es identificar al proceso que lo posee con evidencia antes de cambiar el estado de ningún proceso.

Síntomas típicos incluyen mensajes como `address already in use`, `port is already allocated` o un servicio local que está escuchando inesperadamente en el puerto que necesitás.

## 1. Instalá o actualizá QZX

```bash
python -m pip install --upgrade qzx
```

Para una instalación aislada del CLI, usá `pipx install qzx`. Si pip informa `externally-managed-environment`, preferí pipx en lugar de forzar el Python del sistema. Consultá la [guía de instalación](installing-qzx.md).

QZX sigue en Alpha. Antes de construir una automatización de larga duración, verificá el contrato instalado:

```bash
qzx help inspectPort
```

## 2. Hacé una sola pregunta cross-platform

Para saber qué está usando el puerto 3000:

```bash
qzx inspectPort 3000 --json
```

El mismo comando QZX funciona en entornos compatibles de Windows, Linux y macOS. No necesitás dividir tu automatización entre una receta de PowerShell, una utilidad de sockets específica de Linux y otra búsqueda de procesos para macOS sólo para responder la primera pregunta diagnóstica.

Por ejemplo, para un puerto típico de PostgreSQL:

```bash
qzx inspectPort 5432 --json
```

Quitá `--json` cuando prefieras la presentación normal para terminal.

## 3. Leé el resultado antes de actuar

Empezá por estos campos:

- `status`: `free` o `in_use` cuando QZX pudo completar la inspección.
- `port`: el puerto local exacto que se inspeccionó.
- `in_use`: forma booleana del resultado de ocupación.
- `observed_pids`: identificadores de los procesos observados como propietarios cuando el sistema operativo los expone.
- `processes`: evidencia del proceso —como nombre, PID, hora de creación, ejecutable, línea de comandos, usuario y memoria— cuando el host permite leerla.
- `limitations`: evidencia que QZX no pudo obtener en ese host.
- `errors`: errores no fatales al obtener detalles de procesos dentro de una inspección que siguió siendo útil.

Que el diagnóstico termine correctamente significa que QZX completó la inspección. **No** significa que el proceso sea seguro de terminar, innecesario o el que esperabas encontrar.

Si el puerto está libre, el resultado estructurado no contiene propietario. Si está ocupado pero el sistema operativo no expone un PID, QZX informa esa limitación en lugar de inventarlo.

## 4. Tratá la identidad del proceso como evidencia, no como permiso

Un PID puede reutilizarse después de que un proceso termina. Si pensás realizar más tarde una acción sobre ese proceso, volvé a inspeccionar el puerto inmediatamente antes y compará el PID y la hora de creación actuales con la evidencia que revisaste.

`inspectPort` es deliberadamente de sólo lectura. No termina el proceso que escucha ni modifica su estado. QZX mantiene diagnóstico y mutación separados para que un agente o una persona pueda razonar primero sobre la evidencia.

Las pruebas enfocadas del repositorio abren sockets reales y usan un proceso hijo controlado para verificar que la inspección detecte la ocupación sin terminar al proceso: [`tests/test_system_commands/test_inspect_port.py`](../tests/test_system_commands/test_inspect_port.py).

## 5. Revisá la salida antes de compartirla

Inspeccionar localmente quién posee un puerto puede ser inocuo mientras que **el resultado puede contener contexto sensible**.

Según los permisos del sistema operativo, `processes` puede incluir:

- la ruta completa del ejecutable;
- la línea de comandos y sus argumentos;
- un nombre de usuario local;
- nombres de proyectos o directorios incluidos en los argumentos.

Algunas aplicaciones colocan tokens, credenciales, URLs, identificadores de clientes u otros secretos en argumentos de línea de comandos. Antes de pegar un resultado de `inspectPort` en un issue público, chat, ticket, foro o conversación con una IA, revisá y ocultá los campos que no sean necesarios para el diagnóstico.

No publiques salida cruda simplemente porque el comando sea de sólo lectura.

## 6. Secuencia práctica de decisión

Usá la evidencia en este orden:

1. **Inspeccioná** — ejecutá `qzx inspectPort PUERTO --json`.
2. **Confirmá la ocupación** — revisá `status` e `in_use`.
3. **Identificá al propietario** — revisá PID, nombre del proceso, hora de creación y ejecutable cuando estén disponibles.
4. **Decidí si es esperado** — un servidor de desarrollo, base de datos, VPN, runtime de contenedores, helper del IDE o servicio del sistema puede ocupar legítimamente el puerto.
5. **Volvé a inspeccionar antes de cualquier mutación** — no confíes en un PID viejo después de que haya pasado tiempo.
6. **Cambiá el estado por separado** — detener o terminar un proceso es otra operación, con otro límite de riesgo; hacelo sólo cuando entiendas quién es el propietario y cuáles son las consecuencias.
7. **Verificá** — inspeccioná el puerto nuevamente después de un cambio intencional en lugar de asumir que quedó libre.

El límite es deliberado: **inspeccionar → comprender → decidir → cambiar por separado → verificar**.

## 7. Dale a un agente de IA la evidencia útil, no toda la máquina

Después de revisar el resultado y retirar campos sensibles, un prompt enfocado puede ser tan pequeño como:

> Ejecuté `qzx inspectPort 3000 --json`. El puerto está ocupado. Revisá el PID, nombre del proceso, hora de creación, ejecutable, limitaciones y errores que te proporcione. Explicá la propiedad más probable sin asumir que hay que matar el proceso. Proponé primero una sola comprobación de sólo lectura. Tratá los campos ausentes como desconocidos, no como prueba de que no existen.

Así el agente queda anclado a campos observables y un conflicto sencillo de puerto no se convierte en administración especulativa de procesos.

## Por qué este flujo es útil

Los conflictos de puerto muestran bien el valor central de QZX: la *pregunta* es la misma entre sistemas operativos aunque el vocabulario diagnóstico nativo no lo sea. QZX da a personas, scripts, CI y agentes de IA un nombre de comando y una forma estructurada de resultado para la operación compatible.

Eso no convierte QZX en un reemplazo del shell ni en un sandbox de seguridad. Elimina una bifurcación evitable por sistema operativo dentro de un workflow diagnóstico frecuente.

## Recursos relacionados

- [Referencia de `inspectPort`](https://qzx.yumbale.com/es/comandos/inspect-port)
- [Catálogo de comandos QZX](https://qzx.yumbale.com/es/comandos)
- [Evidencia de compatibilidad](https://qzx.yumbale.com/es/compatibilidad)
- [Seguridad y telemetría](https://qzx.yumbale.com/es/seguridad)
- [Quickstart para agentes de IA](https://qzx.yumbale.com/es/inicio-rapido-agentes-ia)
- [Servicios profesionales](https://qzx.yumbale.com/es/servicios-profesionales)
- [Apoyar el desarrollo de QZX](https://qzx.yumbale.com/es/donar)

QZX es gratuito y open source. Si este workflow te ahorra tiempo y querés ayudar a sostener su desarrollo, la página de apoyo enumera formas opcionales de contribuir. Si necesitás convertirlo en un diagnóstico de producción, gate de despliegue, workflow para una flota o integración a medida, Alejandro Sánchez también ofrece trabajo profesional con alcance definido sin cambiar el conjunto gratuito de funciones de QZX.
