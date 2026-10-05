# E01 — Corrupción SQLite y respaldo recuperado

## Evidencia actual de archivos históricos

Se localizaron archivos conservados en `.runtime/local` y se abrieron **mode=ro/query_only**, sin reparar, hacer checkpoint ni cambiar la base viva. [Probe, tamaños y hashes](probe-backups-solo-lectura.json). Los nombres no acreditan por sí solos el boot original.

`world.corrupt-20261004.sqlite3` (2.412.544 bytes) mantiene WAL/SHM y produjo **database disk image is malformed** al comprobar integridad. Confirma un archivo histórico afectado, no la integridad de la base actualmente desplegada. No se borraron sus archivos asociados ni se abrió immutable ignorando WAL.

`world.recovered-20261004.sqlite3` (970.752 bytes) dio **quick_check=ok**, pero **foreign_key_check encontró12 violaciones**: inventory_initialized1, inventory_containers2, haven_bags1, character_regeneration1, character_professions6 y character_progression1, todas contra personajes. El resultado demuestra que pasar quick_check no acredita coherencia referencial de lo recuperado. No se publican filas privadas.

`world.pre-journal-recovery-20261004T054049Z.sqlite3` falló con «unable to open database file». No se interpreta como corrupción física: la comprobación posterior sobre copia privada se registra abajo. No se intentó abrirlo con escritura para ocultar el fallo de lectura.

## Causa y límites

Los registros históricos de8.245 errores de crecimiento y el archivo malformed son compatibles, pero falta enlazar ruta/boot con evidencia de arranque. No se atribuye el daño a equipar el bolso ni a otra sesión. Las violaciones del respaldo recuperado tampoco demuestran objetos duplicados o filas perdidas concretas sin inventario comparativo. No se determinó el origen físico del daño.

## Solución concreta del servidor y recuperación

Identificar base usada por proceso, boot, SQLite version, journal_mode/synchronous efectivos y backups. Preservar snapshot consistente con WAL/SHM y hashes antes de cualquier recuperación; no copiar solo el archivo principal de una base activa. Diagnosticar y recuperar exclusivamente sobre una copia, manteniendo el original intacto.

Preferir respaldo íntegro verificado y replay de recibos/journals posteriores por revisión, preservando identidades de objetos y evitando reentregar grants/premios. Si se usa recuperación de páginas, comparar tablas, claves, referencias y saldos con evidencia anterior antes del cutover. Las12 referencias huérfanas requieren investigar personajes ausentes y relaciones completas; no borrar las filas automáticamente ni crear personajes ficticios.

Exigir **integrity_check/quick_check y foreign_key_check**, además de invariantes del dominio: UIDs únicos, cantidades no negativas, contenedores válidos, builds existentes, recibos y wallets coherentes. Respaldos privados fuera del repositorio con política configurable en DB; probar restauración, no solo creación de backups.

En el servidor, errores físicos persistentes deben impedir nuevas mutaciones de valor y emitir diagnóstico correlacionado, evitando un loop silencioso de miles de errores. Definir rollback, recuperación y reanudación de outboxes antes de reiniciar tareas. No cambiar journal_mode ni reconstruir datos de la instancia de otra sesión dentro de esta auditoría.

## Pendientes reales

Origen físico, correspondencia boot/ruta, integridad de base viva y reconciliación del respaldo con journals. No se hizo reparación, restauración, reinicio ni implementación. Estos límites no bloquean continuar los demás issues.

## Respaldo que falló en solo lectura: copia privada comprobada

[Probe de copia](probe-respaldo-copia-privada.json): el archivo pre-journal tiene encabezado SQLite válido, versiones lectura/escritura **2/2** (WAL), permisos0600 y no conserva WAL/SHM/journal asociados. Se copió únicamente ese respaldo histórico a una carpeta privada de auditoría y se abrió la **copia** con SQLite normal; `journal_mode=wal`, **quick_check=ok** y **12 violaciones de claves foráneas**. El hash del original se comprobó intacto después.

Esto acota el error previo de lectura: no demuestra daño físico del archivo principal. La apertura de una base WAL sin auxiliares puede necesitar crearlos; no se abrió el original con escritura para hacerlo. La copia pudo leerse, pero sin WAL histórico no acredita que incluya todas las transacciones de la fecha de respaldo ni una restauración completa. Su quick_check tampoco elimina las incoherencias referenciales.

No hubo cutover, modificación de base viva ni reparación de datos. Se conserva pendiente identificar cómo se produjo el respaldo y reconciliar sus12 referencias huérfanas con personajes/journals. No usar `immutable=1` sobre bases activas para saltar WAL y declarar integridad.


## Petición PostgreSQL atendida

Se evaluó el acoplamiento real, concurrencia WAL con fixture, journals Redis, recuperación y migración. [Evaluación completa](SQLITE-VS-POSTGRESQL.md). Se recomienda PostgreSQL para persistencia multijugador; no como reparación automática de la corrupción ni mejora de rendimiento cuantificada. Versión/boot histórico y reconciliación siguen pendientes.
