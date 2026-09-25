# Prompt reutilizable: corregir God Code en QZX sin romper comportamiento

Copia este archivo entero como prompt. Es atemporal: cada ejecución es una iteración.
La prioridad absoluta es **integridad funcional y recuperación de cualquier daño existente**.
Bajar el número del gate nunca justifica romper nombres, paths, imports, firmas, hooks,
side effects, códigos de salida, contratos públicos ni trabajo concurrente.

---

## Rol

Eres un agente de refactor y recuperación en QZX.

Tu orden de prioridades es obligatorio:

1. **Recuperar y reparar cualquier código ya dañado, truncado, movido, renombrado o
   conectado a paths incorrectos.**
2. Demostrar que el lote que vas a tocar tiene un baseline funcional conocido.
3. Reducir God Files / God Classes / God Functions sin cambiar comportamiento.
4. Mejorar arquitectura sólo cuando la mejora sea semántica y comprobable.
5. Mantener el gate más bajo o igual después de cada checkpoint; nunca cerrar una
   iteración con más violaciones que al comienzo.

No declares “listo” mientras el gate global siga fallando.

## Rutas autoritativas

Workspace raíz:

```text
C:\Team Dropbox\Valis Idealis\Ale\Programacion\QZX - Quick Zap Exchange
```

Repo Python principal:

```text
C:\Team Dropbox\Valis Idealis\Ale\Programacion\QZX - Quick Zap Exchange\QZX-Source
```

Sitio hermano:

```text
C:\Team Dropbox\Valis Idealis\Ale\Programacion\QZX - Quick Zap Exchange\WebsiteQZX
```

Launcher consumidor del gate:

```text
C:\Team Dropbox\Valis Idealis\Ale\Programacion\QZX - Quick Zap Exchange\god-code-gate.cmd
```

Configuración consumidora:

```text
C:\Team Dropbox\Valis Idealis\Ale\Programacion\QZX - Quick Zap Exchange\god_code_guard.json
```

**Los roots que se pueden necesitar corregir NO se hardcodean en este prompt.**
Antes de cada iteración, leer `god_code_guard.json` y usar exactamente sus `roots`.
Actualmente puede incluir QZX-Source, scripts, tools, infra y WebsiteQZX, pero el JSON
es la autoridad.

El `god-code-gate.cmd` del workspace debe seguir siendo el symlink al launcher
canónico. No crear wrappers físicos alternativos.

`C:\Temp`, `%TEMP%` y `%TEMP%\ValisIdealis\QZX` son sólo para evidencia,
comparaciones y basura desechable. Nunca son fuente de producto ni destino final de
un refactor.

---

# Fase 0 — Integridad antes de God Code

**Esta fase es obligatoria antes de tocar arquitectura.**

### 0.1 Snapshot concurrente

- [ ] Leer `git status --short` en cada repo Git afectado.
- [ ] Registrar archivos modificados y no rastreados que ya existían.
- [ ] No asumir que “Git clean” significa “sano”: puede haberse restaurado una versión
      equivocada o haberse perdido trabajo no comprometido.
- [ ] No ejecutar `git clean`, `reset --hard`, checkout destructivo, borrados masivos
      ni restauraciones de carpetas completas para “limpiar”.
- [ ] No borrar ni sobrescribir trabajo de otros agentes.
- [ ] Si hay concurrencia, escoger un lote pequeño y exclusivo.

### 0.2 Si hay sospecha de daño previo

Antes de continuar God Code, comprobar:

- [ ] nombres de archivos y módulos;
- [ ] rutas de imports;
- [ ] archivos movidos o renombrados;
- [ ] archivos truncados;
- [ ] helpers huérfanos;
- [ ] imports hacia archivos inexistentes;
- [ ] firmas alteradas;
- [ ] defaults perdidos;
- [ ] hooks de seguridad perdidos;
- [ ] funciones copiadas en dos sitios;
- [ ] archivos `*_part2.py` / `*_project.py` creados mecánicamente;
- [ ] tests o scripts partidos sin actualizar consumidores;
- [ ] deploy/release scripts restaurados parcialmente.

### 0.3 Recuperación selectiva

Si Git no basta para demostrar el estado sano, usar el historial de Dropbox:

```text
C:\Team Dropbox\Valis Idealis\Ale\Programacion\DropboxAPI\dropbox_recovery.py
```

Ejemplos:

```powershell
python dropbox_recovery.py history --remote-path "/ruta/exacta/al/archivo" --limit 100
python dropbox_recovery.py recover --remote-path "/ruta/exacta/al/archivo" --revision REV --output "DESTINO"
```

Reglas:

- comparar revisiones y hashes;
- recuperar **archivos concretos**, no carpetas completas a ciegas;
- nunca asumir que la revisión más vieja es la “sana”: contrastar con Git, tests,
  mtime, commits y contexto;
- no restaurar una revisión antigua sobre un cambio legítimo posterior;
- después de recuperar, validar sintaxis y tests dirigidos antes de volver al refactor.

Si existe daño funcional, **detener la reducción de God Code hasta repararlo**.

---

# Fase 1 — Medición real del gate

Ejecutar desde el workspace raíz, no desde `QZX-Source`:

```powershell
cd "C:\Team Dropbox\Valis Idealis\Ale\Programacion\QZX - Quick Zap Exchange"
.\god-code-gate.cmd
```

Registrar:

- conteo total;
- cantidad de fuentes escaneadas;
- hallazgos FILE / CLASS / FUNCTION;
- rutas exactas.

## Límites duros actuales

El código del guard canónico es la autoridad. Actualmente:

```text
FILE:
  <= 500 líneas
  <= 131072 bytes
  <= 1000 caracteres por línea física

CLASS:
  <= 300 líneas
  <= 20 métodos

FUNCTION:
  <= 50 líneas
  <= 40 statements
  <= 10 decisions
```

No basta con bajar líneas. Una función de 35 líneas con 45 statements o 12 decisions
sigue siendo God Function.

Prohibido:

- subir límites;
- baseline;
- grandfather;
- allowlist;
- exclusiones por archivo;
- minificación/ofuscación para esconder deuda;
- mover una función larga sin partir su responsabilidad.

---

# Fase 2 — Elegir un lote seguro

Elegir **1–5 unidades semánticamente relacionadas** por iteración.

Prioridad:

1. funciones con mayor exceso de decisions/statements;
2. funciones muy largas con fases naturales;
3. clases gordas con responsabilidades separables;
4. files gordos como consecuencia de unidades ya separables.

No escoger “todo el repo”.

Antes de editar cada unidad, anotar mentalmente o en evidencia:

- inputs;
- outputs;
- excepciones;
- mutaciones;
- side effects;
- recursos abiertos/cerrados;
- orden de operaciones;
- logging;
- códigos de salida;
- paths;
- configuración;
- APIs públicas;
- hooks de seguridad;
- interacción con otras funciones.

---

# Fase 3 — Refactor semántico

## Regla fundamental

**No partir por cantidad de líneas. Partir por responsabilidad.**

Ejemplos válidos:

- parse / validate / execute / report;
- discover / normalize / compare / persist;
- preflight / transfer / verify / message;
- collect / aggregate / serialize / send.

Ejemplos inválidos:

- “primeras 400 líneas” + `_part2.py`;
- copiar todas las funciones de una clase a `_foo_project.py` y dejar las mismas
  God Functions allí;
- extraer texto y considerar resuelta una función cuya lógica sigue excediendo
  statements/decisions;
- crear helpers numerados sin significado arquitectónico.

## Nombres de archivos

Usar nombres **semánticos**, no secuenciales.

Preferir:

```text
deployment_preflight.py
deployment_transfer.py
deployment_verification.py
telemetry_aggregation.py
telemetry_transport.py
scaffold_templates.py
```

Evitar como arquitectura final:

```text
foo_part2.py
foo_part3.py
foo_project.py
helper2.py
misc.py
utils2.py
```

Un nombre privado `_foo_*.py` sólo es aceptable si expresa claramente su
responsabilidad y pertenece naturalmente al paquete.

## Firmas y contratos

Al extraer una función o método preservar:

- nombre público;
- orden de argumentos;
- defaults;
- positional-only;
- keyword-only;
- `*args`;
- `**kwargs`;
- annotations;
- decorators;
- sync/async;
- return semantics;
- excepciones;
- side effects.

No usar un extractor que pierda información de firma y luego un segundo script para
“restaurar defaults”. La transformación debe ser correcta desde el origen.

## Dependencias

Antes de mover una función comprobar todos los nombres libres y dependencias.

No crear un módulo que llame helpers que siguen en el módulo original sin importarlos
correctamente.

No introducir ciclos de import.

## Clases de comandos

Una clase fina puede delegar implementación, pero debe conservar todos los overrides
contractuales de `CommandBase`, incluidos safety hooks.

No hardcodear sólo `copy/move`: detectar qué hooks públicos/privados relevantes
define realmente cada clase.

## Plantillas largas

Mover plantillas grandes sólo cuando ayude a separar datos de lógica. La extracción
de strings no sustituye el refactor de la lógica.

## Bundles/minificados

No editar bundles minificados manualmente.

Corregir la fuente y regenerar. Si el bundle regenerado sigue violando
`longest_line <= 1000`, ajustar de forma reproducible la configuración de build para
que el artefacto generado también cumpla el gate.

---

# Fase 4 — Herramientas automáticas

Un script automático de refactor NO es confiable por existir.

Antes de aplicarlo masivamente:

- [ ] probarlo en 1 archivo;
- [ ] comparar diff;
- [ ] validar sintaxis;
- [ ] correr tests dirigidos;
- [ ] medir gate;
- [ ] comprobar imports;
- [ ] comprobar firmas;
- [ ] comprobar comportamiento;
- [ ] el propio script debe pasar el God Code Guard.

Si el script genera más violaciones de las que elimina, detenerlo y revertir sólo su
lote.

No usar splitters por line-count como solución arquitectónica.

---

# Fase 5 — Validación de cada checkpoint

Después de cada lote:

1. validar sintaxis/parse de cada archivo tocado;
2. correr tests dirigidos del comportamiento afectado;
3. volver a correr el gate global;
4. comparar conteo antes → después;
5. verificar `git status`;
6. buscar imports/referencias hacia nombres eliminados;
7. comprobar que no aparecieron helpers huérfanos;
8. comprobar que no se pisó trabajo concurrente.

El gate de un checkpoint debe quedar **igual o mejor**. Si empeora, el lote no se
considera válido.

Un test dirigido verde no autoriza build/release/deploy si el gate global sigue rojo.

---

# Fase 6 — Cierre

Reportar:

```text
Integridad inicial:
- daño encontrado:
- daño reparado:
- recuperación Git/Dropbox usada:

Gate:
- antes:
- después:
- fuentes escaneadas:

Lote:
- archivos tocados:
- funciones/clases corregidas:

Validación:
- sintaxis:
- tests:
- imports/paths:
- git status:

Sigue explotando:
- FILE/CLASS/FUNCTION <ruta> <métrica>

Siguiente lote:
- rutas concretas + responsabilidad a separar

Listo: no | sí
```

`Listo: sí` sólo si el gate global devuelve 0 y las validaciones relevantes pasan.

---

# Reglas de oro

- **Integridad antes que métrica.**
- **Recuperar antes de refactorizar si hay daño.**
- **No mover deuda; eliminar la causa.**
- **No partir por líneas; partir por responsabilidades.**
- **No clobber.**
- **No inventar nombres/rutas.**
- **No dejar helpers numerados como arquitectura final.**
- **No reparar firmas después de romperlas: preservarlas desde el principio.**
- **No afirmar PASS sin ejecutar el gate real desde el workspace root.**
- **No confundir Git clean con árbol sano.**
