# Leer logs y documentos por páginas, sin perder texto

[English](reading-files.md)

> **Flujo de desarrollo todavía no publicado.** Estas opciones de paginación y
> codificación están integradas en el checkout de desarrollo, no en QZX
> **0.2.2.0.9**, la versión publicada en PyPI. Instalar esa versión no incorpora
> este flujo. El ejemplo comprueba las capacidades del comando antes de leer.
> La próxima publicación coordinada debe actualizar este aviso, el paquete,
> la release de GitHub y la documentación pública del comando conjuntamente.

Un agente que inspecciona un log necesita saber si recibió todo el archivo,
qué bytes siguen, si se perdió texto y si el archivo cambió mientras trabajaba.
Una cadena sin esa información no basta.

`readFile` ofrece una interfaz JSON multiplataforma para tomar esas decisiones.
Lee archivos regulares sin ejecutar su contenido ni subirlo a un servicio.
Este flujo no exige cuentas, claves de API, un modelo de IA ni funciones de pago.

## Primer resultado sin usar datos personales

Desde `QZX-Source/`, con un entorno Python que tenga las dependencias de QZX:

```console
python examples/read_file_pages.py --demo --page-bytes 32
```

El script crea un documento UTF-16 temporal con español acentuado, japonés y un
emoji; lo lee mediante llamadas reales a la CLI de QZX; comprueba que el texto
reconstruido es exacto; y elimina únicamente su propio archivo de prueba.
Devuelve un resumen JSON compacto. Debe indicar `success: true`,
`demo_verified: true` y más de una página en `pages`. Son condiciones esperadas,
no una salida capturada ni resultados inventados.

El ejemplo utiliza el código fuente adyacente cuando existe. Distribuido por
separado, usa QZX del mismo entorno Python, no un ejecutable desconocido del
PATH. Rechaza paquetes antiguos sin paginación antes de leer el archivo.
Desactiva la telemetría en sus procesos hijos.

## Inspeccionar una página acotada

Con el punto de entrada de QZX del checkout de desarrollo:

```console
qzx readFile application.log --max-bytes 4096 --json
qzx readFile application.log --max-lines 20 --max-bytes 16384 --json
qzx readFile "ruta con espacios/documento.txt" --json
```

Sin `--json`, QZX muestra el texto y un mensaje que aclara si la lectura es
parcial. Para automatizar, usa JSON y lee `content` en el nivel superior.
El texto ya no se duplica dentro de `details`.

El valor predeterminado es **65.536 bytes del archivo por página**, más un
sondeo de cuatro bytes para reconocer la codificación. `max_bytes` admite
enteros de 1 a 16.777.216. El límite acota la lectura del archivo, no el tamaño
del JSON serializado, la cantidad de tokens ni toda la memoria del proceso.
Los metadatos y los caracteres escapados agregan bytes a la salida.

`max_lines` también limita la página, pero no desactiva el presupuesto de bytes.
Una línea muy larga puede continuar en otra página; `ends_with_partial_line`
lo informa. `max_lines=0` no solicita contenido ni ofrece continuación: no es
una instrucción para recorrer el archivo completo.

## Continuar sin repetir ni perder texto

Cada resultado exitoso incluye estos campos en `details`:

| Campo | Significado |
| --- | --- |
| `offset` / `bytes_consumed` | Región de bytes físicos consumida; incluye el BOM en la primera página |
| `encoding` | Decodificador utilizado, con el orden de bytes Unicode detectado |
| `read_complete` | La página alcanzó el final observado del archivo |
| `entire_file_read` | Esta llamada comenzó en cero y llegó al final |
| `truncated_by` | `max_bytes`, `max_lines` o null al llegar al final |
| `next_read` | Argumentos completos para continuar, o null si no se ofrece continuación |
| `fingerprint_token` | Token derivado de ruta, tamaño, mtime en nanosegundos, dispositivo e inodo |
| `source_bytes_read` | Bytes realmente leídos en esta página, incluido el sondeo de codificación |

Usa **todos** los valores de `next_read`, no una posición calculada a ojo.
Conservan la codificación, los límites y la protección `expected_fingerprint`.
Un carácter multibyte incompleto o un CRLF cortado queda para la siguiente
página. El consumidor no debe insertar saltos de línea entre páginas.
`total_lines` queda como `"unknown"` salvo que esta llamada haya leído todo el
archivo desde cero: QZX no recorre el resto del log para inventar ese dato.

El [consumidor ejecutable](../examples/read_file_pages.py) demuestra el ciclo
completo sin importar módulos privados de implementación de QZX:

```console
python examples/read_file_pages.py application.log --page-bytes 4096
python examples/read_file_pages.py "exportacion antigua.txt" --encoding cp1252
```

Comprueba capacidades, código de salida, éxito estructurado, avance, finalización,
ruta, límites, codificación y evidencia de cambios. Acumula un hash y contadores,
no todo el texto en memoria. `decoded_utf8_sha256` corresponde al texto
interpretado y vuelto a codificar como UTF-8; **no** es el hash de los bytes del
archivo original, especialmente si era UTF-16 o una codificación antigua.

Para ver los eventos de páginas hay que agregar expresamente `--emit-pages`.
Ese modo produce JSON Lines y un resumen final. Incluye contenido sin redactar.
Antes de enviarlo a un modelo o servicio externo, revisa si contiene secretos
o información personal. Un fallo posterior invalida el recorrido aunque ya se
hayan emitido páginas anteriores. El límite predeterminado de
`--max-pages 10000` evita recorridos involuntariamente enormes; agotarlo devuelve
un fallo, nunca un éxito que finja haber leído todo el archivo.

## Unicode sin sustituciones silenciosas

`encoding=auto` reconoce los BOM de UTF-8, UTF-16 y UTF-32. Sin BOM exige UTF-8
válido: no adivina una codificación antigua reemplazando bytes desconocidos.
Para archivos cuya codificación conoces:

```console
qzx readFile exportacion-windows.txt --encoding cp1252 --json
qzx readFile utf16-sin-marca.txt --encoding utf-16-le --json
```

Se admiten UTF-8/16/32, ASCII, Latin-1, CP1252, CP437 y CP850 explícitos.
UTF-16/32 sin BOM exige indicar el orden de bytes. Una codificación que contradiga
el BOM falla. No se admiten codificaciones con estado ni códecs binarios porque
no permitirían continuar de forma fiable desde un desplazamiento arbitrario.

El texto conserva los saltos CRLF, LF y CR originales. Una codificación inválida
produce `decode_failed`, no un supuesto éxito con caracteres de sustitución.
El contenido decodificado con NUL se rechaza como `binary_content`.
Un carácter que continúa en la siguiente página no se considera un error de
codificación. Si el presupuesto es demasiado pequeño para avanzar, se informa
`read_limit_too_small` en lugar de entrar en un bucle.

## Archivos cambiantes y límites de la evidencia

Dentro de cada llamada, QZX verifica el archivo regular abierto y la ruta
solicitada antes de devolver éxito. Un cambio detectado durante la lectura
produce `file_changed_during_read`. Entre llamadas, al conservar `next_read`,
los cambios habituales producen `file_changed_since_previous_read`.

No combines páginas de versiones distintas. Para un log activo, copia el archivo
a una versión estable o reinicia desde cero sin la protección anterior.
Se puede seguir un enlace simbólico ordinario, pero no leer como texto una
carpeta, un FIFO u otro archivo especial. No es una frontera de permisos del
sistema de archivos.

La huella representa **metadatos, no una instantánea inmutable ni un hash del
contenido**. Una edición que restaure deliberadamente los metadatos observados
podría pasar inadvertida. Para garantías forenses o transaccionales, consigue
primero una instantánea estable apropiada. El comando no promete esas garantías,
no sanea secuencias arbitrarias de control de terminal ni valida el significado
del contenido del archivo.

## Cuándo aporta valor QZX

Para leer un archivo UTF-8 pequeño y confiable desde Python, `Path.read_text()`
puede ser más sencillo. Un visor nativo puede ser preferible para uso interactivo.
QZX aporta valor cuando un consumidor necesita el mismo comando documentado y
la misma semántica JSON entre plataformas compatibles, límites explícitos,
decodificación estricta, continuación y evidencia de cambios.

Esta interfaz de desarrollo cambia deliberadamente el antiguo valor
predeterminado de leer todo el archivo. Los consumidores deben comprobar la
finalización y usar `content` en el nivel superior: ya no se duplica
`details.content`. QZX sigue en Alpha. Estos cambios deben explicarse en la
próxima release, no anunciarse como disponibles hoy en PyPI.

## Verificación, creador y apoyo

Las pruebas cubren Unicode/BOM, límites de bytes y líneas, codificaciones antiguas,
líneas largas, opciones inválidas, archivos cambiantes, archivos especiales,
CLI y demo ejecutable. Están en
`tests/test_file_commands/test_read_file_pages.py` y
`tests/test_examples/test_read_file_workflow.py`. No sustituyen los controles
completos de arquitectura, plataformas, empaquetado, documentación y publicación.

QZX — Quick Zap Exchange, creado y mantenido por Alejandro Sánchez.

Cuando este flujo resuelva un problema real, puedes
[apoyar el desarrollo de QZX](https://qzx.yumbale.com/es/donate).
Para integrar lectura de logs, procesamiento de documentos o agentes en un equipo,
[conversa con Alejandro sobre servicios profesionales](https://qzx.yumbale.com/es/professional-services).
QZX sigue siendo gratuito y de código abierto. Las donaciones son opcionales y
no desbloquean funciones.
