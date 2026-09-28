# Incidente: latencia alta en projectLanguages y selección del backend nativo

Fecha local: 2026-09-25
Hora de registro: ~20:12 America/Panama
Estado: mitigado y optimizado; queda variabilidad residual de latencia por investigar
Ámbito: QZX `projectLanguages` y la infraestructura reutilizable que lo soporta
Impacto: cualquier proyecto analizado por QZX, no sólo Workspace MCP / Valis MCP Manager

## Resumen ejecutivo

Se investigó por qué una composición de lenguajes de aproximadamente 717 archivos / 4 MiB podía tardar decenas de segundos aun después de migraciones previas a Rust. La causa principal no era que Rust fuese lento: el proceso no estaba consiguiendo cargar un binario nativo correspondiente a las fuentes Rust vigentes y estaba usando correctamente el camino Python de compatibilidad. Ese fallback preservó funcionalidad, pero para este corpus estaba muy por encima del objetivo de latencia.

La campaña hizo dos cosas en paralelo:

1. recuperó de forma segura la ruta nativa, sin cargar una DLL vieja sólo por ser más rápida;
2. optimizó trabajo general de QZX tanto en la ruta Rust como en el fallback Python sin debilitar el análisis.

También se dejó explícito en el propio código que el contrato de selección es **native first cuando exista un backend compatible**, con Python como fallback de compatibilidad / recuperación, y se documentaron los próximos hotspots que pueden reducir más latencia.

La última ejecución humana del comando consumidor terminó en aproximadamente **0.917 s**. En una tanda final de diez procesos nuevos con salida JSON la mediana fue **1.651 s** y **9/10** ejecuciones quedaron por debajo de cuatro segundos. Hubo un outlier de **4.745 s** en esa tanda y tandas anteriores mostraron outliers mayores, incluyendo **16.421 s**. Por lo tanto, la mejora es material y reproducible, pero **no se certifica todavía un límite duro de <4 s para toda ejecución posible**.

## Solicitud original

El objetivo operacional era que el análisis utilizado por:

```text
C:\Team Dropbox\Valis Idealis\Scripts-y-Apps-Reusables\CodeQualityTools\code-language-composition\workspace-mcp-language-composition.cmd
```

terminara en menos de cuatro segundos, sin degradar confiabilidad y sin introducir optimizaciones particulares para MCPs. Las mejoras debían vivir en QZX y beneficiar a cualquier proyecto.

También se debía conservar el camino Python porque Rust puede no estar disponible en plataformas raras, instalaciones portables o entornos donde no exista una extensión compatible.

## Síntomas observados

El comando entregaba resultados correctos, pero demoraba varios segundos o decenas de segundos. El punto importante fue separar tres fenómenos distintos:

- velocidad del analizador Rust;
- disponibilidad / descubrimiento del binario Rust correcto;
- costo adicional de Python alrededor del backend nativo: importación, metadatos, resolución de rutas, ignore rules, agregación y presentación.

Antes de la corrección se midieron tres ejecuciones completas, arrancadas desde `C:\Windows\System32` y usando el launcher real:

- 60.726 s
- 47.087 s
- 35.947 s

Las tres finalizaron correctamente y produjeron la misma composición entre sí. El workspace estuvo recibiendo cambios concurrentes durante la campaña: el ejemplo inicial del operador tenía 103,524 líneas de contenido / 102,020 de source; el primer baseline automatizado observó 103,528 / 102,024 y el cierre vivo terminó en 104,792 / 103,288. Esos cambios de totales no se usan para demostrar paridad del optimizador; la paridad se verificó con contenido idéntico y snapshots congelados. La enorme diferencia de tiempo entre las corridas iniciales ya indicaba además que no era seguro inferir causalidad de una sola ejecución.

## Diagnóstico principal: Rust no estaba activo

La inspección de:

```python
qzx.commands.development._project_language_native.native_available()
```

devolvió inicialmente `False`.

Existían binarios antiguos bajo el cache local de QZX, pero ninguno correspondía a la huella exacta de las fuentes Rust vigentes. QZX no cargó un binario arbitrario o stale, que es el comportamiento correcto desde el punto de vista de integridad.

El fallback Python se activó y produjo resultados correctos, pero el perfil mostró que era demasiado costoso para el objetivo de latencia del corpus.

### Invariante que no debe romperse

**Nunca se debe escoger una DLL antigua sólo porque evita caer a Python.**

Una ruta nativa rápida pero construida a partir de fuentes distintas puede producir resultados incompatibles o esconder una regresión. El criterio correcto es:

1. usar extensión nativa instalada/empacada cuando sea compatible;
2. en un source checkout, aceptar cache nativo sólo cuando corresponde a la huella de las fuentes Rust;
3. permitir override explícito si existe;
4. si no hay backend nativo utilizable, usar Python;
5. si una ejecución nativa falla o declara estadísticas incompletas, reiniciar el estado y rehacer el análisis por Python.

No se debe ejecutar Rust y Python completos en paralelo para “ver cuál gana” en cada comando. Eso duplicaría I/O y destruiría la ventaja de latencia.

## Perfil del fallback Python

Se instrumentó el flujo Python sobre el corpus real. Una corrida de perfil más costosa —bajo instrumentación— mostró aproximadamente:

- `_count_lines`: 717 llamadas, ~72.26 s acumulados de pared;
- `_detect_lexer`: 719 llamadas, ~7.37 s;
- `_relative_display`: 720 llamadas, ~4.81 s;
- `_is_generated`: 719 llamadas, ~0.30 s;
- `_decode_text`: 719 llamadas, ~0.11 s;
- `_is_ignored`: ~0.004 s.

La instrumentación incrementa el costo absoluto y no debe compararse como benchmark de producción, pero sí permitió localizar dónde se consumía el tiempo.

### Optimización aplicada al contador Python

El contador anterior creaba un diccionario por línea con flags `code/comment`. Se reemplazó por un `bytearray` compacto con flags binarios:

- bit 1 = código;
- bit 2 = comentario;
- una línea con código + comentario sigue siendo línea de código.

Además:

- se reutiliza la clasificación del tipo de token;
- los tokens triviales de una sola línea evitan splits innecesarios;
- whitespace puede avanzar líneas sin materializar estructuras por línea;
- se sigue consumiendo el stream público `lexer.get_tokens()`, por lo que filtros y preprocesamiento de Pygments siguen participando.

No se implementó un parser aproximado, regex rápido ni conteo bruto de newlines para ganar velocidad.

### Verificación diferencial del contador

Se comparó la función previa con la optimizada usando exactamente el mismo contenido y lexer para cada archivo.

Resultado final:

- 717 archivos comparados;
- igualdad exacta por archivo;
- corpus completo sin divergencias;
- contador viejo CPU ~13.641 s;
- contador optimizado CPU ~13.031 s;
- wall viejo ~20.635 s;
- wall optimizado ~18.712 s.

También se agregaron pruebas con:

- 1,000 streams determinísticos aleatorios de tokens;
- lexers reales;
- filtros de Pygments;
- separadores Unicode;
- CR/LF/CRLF;
- líneas mixtas código/comentario;
- input vacío.

## Recuperación segura del backend Rust

Se construyó el backend actual usando Cargo en modo release, lockfile y un solo worker para respetar la política de recursos del workspace.

Durante un primer build las fuentes Rust cambiaron concurrentemente. El build había comenzado con una huella y terminó cuando el source ya tenía otra. En vez de instalar ese resultado, el proceso abortó deliberadamente:

```text
RuntimeError: Rust sources changed during build; refusing cache installation
```

Este fallo fue correcto y evitó asociar un binario con una huella que ya no representaba sus fuentes.

Posteriormente se dejó un constructor canónico:

```text
QZX-Source/scripts/build_native_project_languages.py
```

El constructor:

- usa `cargo build --release --locked -j 1`;
- permite un target externo;
- valida la huella antes y después;
- copia el artefacto a una ubicación temporal;
- carga la extensión en un proceso separado;
- ejecuta un smoke real de Python;
- comprueba lenguaje y líneas de código/comentario/blanco;
- verifica que `scan_projects_json` exista;
- sólo entonces instala en el cache correspondiente a la huella;
- usa staging + replace para una instalación atómica;
- si el mismo binario ya está instalado, no reemplaza innecesariamente una DLL potencialmente cargada.

La huella activa verificada durante la campaña fue:

```text
f0a471c4e44f05f8cfd92955
```

El binario verificado quedó en:

```text
%LOCALAPPDATA%\QZX\native\project_languages\f0a471c4e44f05f8cfd92955\_project_languages_native.cp313-win_amd64.pyd
```

SHA-256 observado:

```text
d8a2feabcdde9fe6e1a6e65cd0ec6eadda028217ac053de4f74bffcf467862d4
```

Estos valores sirven como evidencia histórica de esta campaña, no como valores que deban hardcodearse.

## Perfil del camino Rust después de recuperarlo

Con Rust ya activo, un perfil mostró como hotspots principales:

- `scan_projects_json` nativo: ~0.522 s;
- canonicalización / resolución de rutas: ~2.0 s acumulados bajo perfil;
- recorrido Python de metadatos: ~0.9 s;
- importaciones: ~0.33 s.

El hallazgo importante fue que la parte Rust ya era pequeña frente al overhead alrededor de ella.

### Resolución de rutas duplicada

`Path.resolve()` en Windows usa `ntpath.realpath`. Para una ruta existente, CPython puede llamar a `_getfinalpathname` una vez para resolver la identidad y otra vez para comprobar si puede retirar el prefijo extendido sólo por estética del path de salida.

QZX no necesitaba una ruta bonita para una clave interna de identidad.

Se creó:

```text
src/qzx/core/path_identity.py
```

con `canonical_path_key()`.

En Windows:

- resuelve la identidad real en cada llamada;
- conserva el prefijo extendido como parte de una clave opaca;
- evita la segunda apertura destinada a presentation normalization;
- no guarda un cache persistente de identidad.

En otras plataformas, paths faltantes o errores de la API nativa, conserva el comportamiento portable con `Path.resolve()`.

Esto **no** es un cache de symlinks. Si un enlace se redirige, la llamada posterior lo resuelve de nuevo.

### Comparación alternada old/new

Para evitar sesgo por “primera corrida” se alternaron las dos funciones de identidad dentro del mismo proceso con el backend Rust activo.

Ruta previa:

- 0.960 s
- 1.404 s
- 2.952 s

Ruta optimizada:

- 0.590 s
- 0.654 s
- 1.147 s

Todos los casos:

- 717 archivos reconocidos;
- scan completo;
- mismos contratos de análisis.

Mediana CPU aproximada:

- anterior: 0.922 s;
- optimizada: 0.703 s.

## Otras optimizaciones aplicadas

### Agregación nativa

Antes se construía un acumulador default aun cuando el lenguaje ya existía, debido al uso de `dict.setdefault(..., _new_language(...))`. Como Python evalúa los argumentos antes de llamar a `setdefault`, ese objeto se fabricaba y descartaba repetidamente.

Ahora el acumulador sólo se crea cuando falta.

### Ejemplos de archivos

El reporte sólo retiene un número acotado de ejemplos por grupo. Antes podía resolverse el display path aunque la lista ya estuviera llena.

Ahora el display path se calcula sólo mientras todavía puede agregarse al reporte.

**Todos los archivos continúan contribuyendo a bytes, líneas, counts y porcentajes.**

### Detección de encoding

`chardet` quedó lazy para el caso no UTF-8. El camino UTF-8 y el camino nativo no pagan su importación sólo por existir el fallback.

### DirEntry / recorrido de metadatos

Durante la campaña el árbol recibió mejoras concurrentes generales que reutilizan `os.DirEntry` mediante `walk_directory_entries` para reducir stats redundantes. Esos cambios se conservaron y validaron; no deben atribuirse enteramente a esta intervención ni revertirse por accidente.

## Por qué sigue existiendo un recorrido Python cuando Rust ya escaneó

El backend Tokei conoce los archivos que clasifica, pero QZX mantiene un contrato más rico:

- ignore files y reinclusiones;
- directorios ignorados;
- symlinks saltados;
- archivos desconocidos;
- archivos generated;
- binarios;
- oversized;
- errores de lectura;
- examples;
- scan_complete.

Por eso `_metadata_scan()` vuelve a recorrer metadatos incluso en la ruta nativa.

Eliminar ese segundo recorrido sin sustituir toda esa contabilidad produciría un comando más rápido pero menos confiable. No se hizo.

## Optimización futura principal

La mayor oportunidad restante, documentada también junto a `_metadata_scan()`, es mover a Rust **todo** el contrato de metadatos y no sólo el parser de lenguajes.

El objetivo correcto sería que el payload nativo incluya la información suficiente para eliminar el segundo traversal Python manteniendo paridad exacta en:

- ignores/reincludes;
- unknowns;
- generated/binary/oversized;
- symlinks;
- read errors;
- visited/ignored counters;
- scan completeness.

No se debe eliminar el traversal antes de tener pruebas diferenciales de ese contrato.

## Otras optimizaciones futuras documentadas en el código

### Evitar JSON intermedio entre Rust y Python

Actualmente Rust serializa el payload con `serde_json` y Python hace inmediatamente `json.loads()`.

Una futura extensión PyO3 podría devolver `dict/list` nativos de Python y quitar:

- serialización a string;
- copia del string;
- parse JSON.

Es una optimización general y segura en principio, pero debe conservar exactamente el payload y los errores.

### Lazy import de Pygments

La ruta nativa todavía comparte módulo con el analizador portable. `pathspec` sí participa en el contrato de ignore del recorrido nativo, pero Pygments sólo es necesario para el fallback.

Separar o cargar Pygments de forma lazy puede reducir cold-start del camino Rust. Debe preservarse:

- error de dependencias;
- API del comando;
- fallback Python inmediato;
- pruebas de importación y packaging.

### Huella de fuentes sin releer manifiestos Rust

En un source checkout sin extensión empacada se calcula la huella leyendo:

- `Cargo.toml`;
- `Cargo.lock`;
- `src/lib.rs`.

Una mejora futura podría usar un fingerprint embebido en build/install para reducir ese costo. **No** debe sustituirse por un cache basado únicamente en mtime/size, porque durante esta misma campaña se verificó que las pruebas deben detectar cambios aunque se conserven tamaño y fecha.

## Política de selección de backend

El contrato quedó documentado junto a `_load_native_module()` y `execute_project_languages()`.

### Comportamiento normal

```text
auto
  -> extensión nativa compatible si existe
  -> override/cache compatible cuando aplique
  -> Python si native no está disponible
```

### Forzar Python

```text
QZX_PROJECT_LANGUAGES_BACKEND=python
```

Esto existe para compatibilidad, diagnóstico y plataformas donde native no sea viable.

### Fallo durante un scan nativo

Si la extensión está presente pero el scan falla:

1. se descarta el state parcialmente construido;
2. se crea un state nuevo;
3. se ejecuta el analizador Python completo.

No se mezclan counts de ambos backends.

### Estadísticas nativas incompletas

Si Tokei reporta `inaccurate_languages`, el adaptador actual las trata como backend nativo no utilizable para ese scan y fuerza la recuperación portable, en vez de vender un resultado rápido pero incompleto.

## Pruebas de confiabilidad ejecutadas

La validación funcional de cierre original dio 79 tests PASS. Después de añadir este incidente y los comentarios de roadmap dentro del código se repitió el alcance ampliado, incluyendo el walker compartido concurrente:

```text
85 passed
```

Además:

- Ruff: PASS;
- `git diff --check`: PASS;
- sintaxis Python: PASS;
- fuentes relevantes estables durante una corrida final de tests.

Las pruebas cubren:

- composición Python/PHP/CSS;
- nombre C++;
- ignores;
- reinclusión desde nested .gitignore;
- generated;
- binarios;
- archivos desconocidos;
- reporting de errores acotado;
- contrato native;
- batch native;
- cache de huella;
- build que cambia de fuentes durante compilación;
- smoke fallido que no instala;
- no reemplazar una DLL idéntica;
- cambios de contenido conservando tamaño y mtime;
- cambios/eliminación de ignores;
- eliminación de archivos;
- límite de generated en las primeras 20 líneas;
- precedencia oversized > binary > generated;
- fallo Rust seguido de fallback Python limpio;
- canonicalización de rutas relativas/absolutas;
- Unicode en paths;
- prefijo extendido Windows;
- symlink retargeting sin cache stale;
- contador previo vs optimizado.

## Paridad nativa

Se creó un snapshot inmutable del input y se ejecutaron dos extensiones nativas compatibles sobre el mismo conjunto.

Resultado:

```text
full_native_payload_equal = true
records = 718
```

Los 718 registros incluyen material que luego puede excluirse. Por eso no contradice los 717 archivos reconocidos por el reporte de producción.

## Paridad portable

El contador previo y el optimizado fueron ejecutados sobre los mismos 717 archivos, alternando el orden para no favorecer siempre a uno por cache/calor.

Resultado:

```text
same_results_for_every_file = true
```

## Benchmarks finales del comando real

Diez invocaciones nuevas, cada una arrancando un proceso separado, salida JSON:

```text
1.618
1.489
1.166
1.090
1.124
2.019
3.281
4.745
1.683
2.077
```

Mediana:

```text
1.651 s
```

9/10 por debajo de 4 s.

La siguiente ejecución con la tabla humana normal terminó en:

```text
0.917 s
```

### Limitación importante

Hubo tandas anteriores post-cambio con picos más altos, incluyendo 16.421 s.

No se identificó de forma concluyente la causa de toda la variabilidad residual y no se debe inventar una explicación como “Dropbox”, “CPU” o “RAM” sin medición específica.

La conclusión correcta es:

- el procesamiento típico cayó drásticamente;
- el camino nativo está activo;
- hay mejoras intrínsecas adicionales además de simplemente habilitar Rust;
- todavía no se ha demostrado matemáticamente / operacionalmente que **toda** ejecución terminará <4 s.

## Qué NO se hizo

No se introdujo:

- cache de resultados del análisis;
- cache basado en tamaño/mtime;
- exclusión de archivos para ganar velocidad;
- sampling;
- conteo aproximado;
- shortcuts específicos de MCP;
- reducción del conjunto de lenguajes;
- debilitamiento de ignore rules;
- silenciamiento de errores;
- eliminación del fallback Python;
- compilación Rust automática en cada comando;
- carga de DLL vieja para evitar Python;
- paralelismo agresivo de compilación;
- cambios a los límites del God Code Guard.

## Resultado del God Code Guard

El gate global seguía en rojo por deuda preexistente / concurrente. Durante la campaña se observó una medición de 229 violaciones. En el cierre posterior a esta documentación reportó:

```text
209 GOD CODE VIOLATION(S)
```

La reducción global ocurrió junto a trabajo concurrente y no se atribuye a esta optimización. El primer intento de documentar el roadmap dejó accidentalmente `_metadata_scan` en 51 líneas físicas; el gate lo detectó. Los comentarios se movieron fuera de la función y el siguiente gate volvió a **209 sin ningún finding de los archivos `project_language*` tocados por esta campaña**.

El gate no se relajó, baselineó ni exceptuó.

## Archivos relevantes

Código / implementación:

```text
QZX-Source/src/qzx/commands/development/_project_language_native.py
QZX-Source/src/qzx/commands/development/_project_language_command.py
QZX-Source/src/qzx/commands/development/_project_language_scan.py
QZX-Source/src/qzx/core/path_identity.py
QZX-Source/native/project_languages/src/lib.rs
QZX-Source/scripts/build_native_project_languages.py
```

Pruebas:

```text
QZX-Source/tests/test_development_commands/test_project_languages.py
QZX-Source/tests/test_development_commands/test_project_language_counting.py
QZX-Source/tests/test_development_commands/test_project_language_freshness.py
QZX-Source/tests/test_development_commands/test_project_language_groups.py
QZX-Source/tests/test_development_commands/test_project_language_native_cache.py
QZX-Source/tests/test_path_identity.py
QZX-Source/tests/test_directory_entry_walk.py
```

Documentación:

```text
QZX-Source/docs/project-languages-performance.md
QZX-Source/docs/incidents/incident-260925-201200-projectlanguages-performance-native-selection.md
```

## Evidencia regenerable

La evidencia de esta campaña quedó fuera de Dropbox:

```text
%TEMP%\ValisIdealis\QZX\runs\20260925-language-speed\
```

Archivos particularmente útiles:

```text
baseline-timings.json
portable-phase-timings.json
portable-differential-metrics.json
native-final-timings.json
path-optimized-timings.json
acceptance-timings.json
acceptance-human.txt
path-alternating-ab.json
native-parity-inputs.json
native-parity-old.json
native-parity-new.json
native-parity-result.json
final-validation.json
final-source-manifest.json
final-verified-source.json
```

La evidencia es regenerable y por eso no debe copiarse al repositorio sólo para conservar logs.

## Procedimiento recomendado si reaparece la lentitud

### 1. Confirmar qué backend está realmente activo

No empezar perfilando Python a ciegas.

Comprobar:

- `native_available()`;
- `NATIVE_IMPORT_ERROR`;
- `_NATIVE.__file__`;
- `_source_native_fingerprint()`.

Si no hay native compatible, explicar primero el fallback.

### 2. Verificar si existe cache para la huella actual

No tomar el directorio “más nuevo” ni el primer `.pyd`.

La carpeta debe corresponder a la huella actual.

### 3. Si hace falta, aprovisionar con el builder canónico

```text
python -B scripts/build_native_project_languages.py
```

Puede reutilizarse un target externo y `--offline` si las dependencias ya existen.

### 4. Ejecutar el comando real varias veces

No basta con un microbenchmark interno. Medir un proceso nuevo desde un cwd representativo.

Registrar mediana, máximo y distribución. No esconder outliers.

### 5. Perfilar por fases si el máximo sigue superando el objetivo

Separar al menos:

- startup/imports;
- native parse;
- metadata traversal;
- path canonicalization;
- aggregation;
- output serialization/presentation.

### 6. No saltarse contratos para llegar a cuatro segundos

Si una optimización elimina:

- unknowns;
- ignore accounting;
- symlinks;
- read errors;
- generated/binary detection;
- fallback;

debe considerarse regresión aunque el benchmark mejore.

## Conocimiento reutilizable

1. **“Rust está implementado” no significa “Rust está siendo usado”.** La disponibilidad del binario compatible debe comprobarse explícitamente.
2. **El fallback correcto puede esconder una regresión de performance.** Tener resiliencia no elimina la necesidad de visibilidad del backend efectivo.
3. **Las capas alrededor de Rust pueden dominar el tiempo.** En esta campaña Tokei ya era rápido; path resolution, metadata y startup eran materialmente relevantes.
4. **No medir una sola ejecución.** Hubo variabilidad grande incluso después de la optimización.
5. **No usar una DLL stale como atajo.** La velocidad no compensa perder correspondencia con las fuentes.
6. **No usar cache mtime/size para análisis de código que promete frescura.** Se agregaron pruebas que cambian contenido manteniendo ambos.
7. **Mover trabajo a Rust debe incluir el contrato completo, no sólo el happy path.** El próximo gran paso es metadata/ignore/error accounting.
8. **La selección del backend debe ser determinística y barata.** Elegir native compatible por conocimiento arquitectónico es preferible a ejecutar ambos backends para medirlos cada vez.
9. **El fallback Python debe seguir mejorándose.** Es una ruta real para plataformas raras, no código muerto.
10. **Las optimizaciones deben ser generales.** Ningún cambio de esta campaña depende de “Workspace MCP”, “Valis MCP Manager” ni de sus extensiones concretas.

## Seguimiento recomendado

Orden de prioridad para futuras iteraciones:

1. mover el contrato completo de metadata/ignore/error accounting al backend Rust y demostrar paridad antes de retirar el segundo traversal;
2. eliminar el JSON intermedio PyO3 -> Python;
3. lazy-load/split de Pygments para reducir cold-start nativo;
4. diseñar un fingerprint de build embebido que reduzca trabajo de source-checkout sin aceptar stale binaries;
5. instrumentar la variabilidad residual del proceso completo hasta poder explicar los outliers >4 s;
6. volver a ejecutar el comando real y conservar como objetivo operacional <4 s sin convertirlo en un “PASS” artificial.

## Estado al cerrar este registro

QZX vuelve a preferir y utilizar el backend Rust compatible en el entorno probado. Python permanece como fallback. Las optimizaciones relevantes están en el código compartido de QZX y benefician a proyectos arbitrarios.

El objetivo de velocidad se cumple en la gran mayoría de las ejecuciones finales observadas y con amplio margen en la ejecución humana final, pero la garantía absoluta de menos de cuatro segundos sigue abierta debido a outliers residuales. Esta diferencia debe mantenerse explícita en futuros handoffs y no maquillarse.
