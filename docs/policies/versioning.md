# Política de versionado y publicación

QZX usa deliberadamente una numeración conservadora. Una funcionalidad o una
corrección no autorizan por sí solas un incremento, una release ni un
despliegue.

## Estado de referencia

- Versión vigente en `main` y publicada en PyPI: `0.2.2.0.1`.
- Tag y GitHub Release de esa publicación: `v0.2.2.0.1`, apuntando al commit
  de lanzamiento `41fe020`.
- Próximo incremento pequeño, cuando Ale lo defina: `0.2.2.0.2`.

Antes de cambiar estos valores, comprueba el estado actual del repositorio y la
versión pública: esta sección describe el estado vigente al redactarse la
política, no sustituye esa verificación.

## Rama principal

Cuando Ale defina una versión nueva como la versión vigente, `main` debe
actualizarse automáticamente para apuntar a esa versión. La versión más reciente
no debe quedar únicamente en una rama secundaria. Explícale previamente en
lenguaje sencillo qué operación de Git se realizará y recomienda la práctica
profesional aplicable, porque Ale no está familiarizado con Git ni con su
terminología.

Actualizar `main` no autoriza por sí solo construir o publicar el paquete,
crear/empujar un tag, crear una GitHub Release ni desplegar. Esas acciones
conservan las autorizaciones independientes descritas más abajo.

## Regla de incrementos

- Para cambios pequeños o funcionalidades tempranas, conserva segmentos
  adicionales compatibles con PEP 440.
- El primer incremento sobre `0.2.2` es como mínimo `0.2.2.0.1`, no `0.2.3`.
- Mientras el alcance siga siendo pequeño, incrementa el último segmento:
  `0.2.2.0.1` → `0.2.2.0.2`.
- No elimines segmentos ni promociones por iniciativa propia a `0.2.3`, `0.3.0`
  o `1.0.0`. Esos saltos quedan reservados para hitos expresamente decididos por
  el propietario.

## Archivos que deben mantenerse sincronizados

Cuando se autorice un cambio de versión, actualiza como mínimo:

- `setup.py`.
- `src/qzx/__init__.py`.
- El fallback de versión de `src/qzx/cli.py`.
- Las referencias de versión vigente en `README.md` y `README-English.md`.

Busca además otras referencias activas y valida el resultado con
`packaging.version.Version`.

## Qué son el tag y la GitHub Release

- Un **tag** es una etiqueta fija que identifica el commit exacto usado para
  una versión, por ejemplo `v0.2.2.0.1`. Debe ser anotado, publicarse en GitHub
  y no moverse ni reutilizarse después.
- Una **GitHub Release** es la página pública construida sobre ese tag. Contiene
  las notas del lanzamiento, los enlaces y los mismos artefactos publicados en
  PyPI, con sus hashes para poder verificar que son idénticos.
- Una versión Alpha debe marcarse como **Pre-release**. GitHub no permite que
  una Pre-release lleve simultáneamente la insignia **Latest**; eso no cambia
  cuál es la versión numéricamente más reciente ni cuál está en `main`.

## Flujo profesional de lanzamiento

Cuando Ale autorice todas las acciones correspondientes, el orden canónico es:

1. Definir expresamente el número de versión y convertirlo en la versión
   vigente de `main`.
2. Sincronizar metadatos, documentación y changelog, y comprobar que no haya
   secretos ni archivos locales en la distribución.
3. Ejecutar las pruebas, construir wheel y sdist una sola vez y validar ambos
   con `twine check`.
4. Crear el commit de lanzamiento y un tag anotado `v<versión>` que apunte
   exactamente a ese commit.
5. Subir a PyPI los artefactos ya verificados; no reconstruirlos entre canales.
6. Crear la GitHub Release desde ese tag y adjuntar exactamente el mismo wheel
   y sdist, registrando sus hashes.
7. Instalar desde PyPI sin caché, comprobar la metadata pública y verificar que
   tag, GitHub Release, PyPI, `main` y documentación muestran la misma versión.

Si se descubre un error después de publicar, no se mueve el tag ni se reemplaza
el artefacto: se corrige en `main` y se publica una versión nueva cuando Ale
defina su número.

## Atribución obligatoria en cada lanzamiento

Las notas de cada lanzamiento de QZX, incluido el bloque correspondiente de
`CHANGELOG.md` y el texto usado en la release o directorio de paquetes, deben
incluir literalmente:

> QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

La atribución no sustituye el resumen de cambios, la licencia ni los datos
técnicos del lanzamiento. Antes de publicar, verifica que aparezca en el
README empaquetado, los metadatos visibles del paquete y las notas finales.

## Acciones independientes

Cada una de estas acciones requiere autorización explícita; autorizar una no
autoriza automáticamente las demás:

- Cambiar la versión local.
- Construir la distribución.
- Subir a PyPI.
- Crear o empujar un tag.
- Crear una release.
- Desplegar a producción.

Una verificación local o un cambio documental nunca deben activar por sí solos
un flujo de publicación.
