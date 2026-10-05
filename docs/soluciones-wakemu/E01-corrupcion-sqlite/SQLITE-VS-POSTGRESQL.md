# E01 — SQLite frente a PostgreSQL para Wakemu

## Recomendación

**Sí vale la pena migrar la persistencia autoritativa a PostgreSQL para el servidor multijugador**, antes de ampliar economía, gremios y sesiones compartidas de mazmorra. Por decisión posterior del usuario, la migración será definitiva: PostgreSQL como único backend, también para pruebas de persistencia; no se mantendrá retrocompatibilidad SQLite.

Es una recomendación de arquitectura basada en el código, no un resultado de benchmark ni una reparación de la corrupción histórica. PostgreSQL no arregla por sí mismo premios duplicados, transacciones parciales, referencias huérfanas ni desorden SQL/Redis. Primero preservar y reconciliar los datos de E01; no importar una base dañada y declarar el problema resuelto.

## Evidencia del repositorio

- `storage/store.py` abre una conexión SQLite por contexto, configura WAL al inicializar y espera hasta 10 segundos por bloqueo. No configura `synchronous` explícitamente ni comprueba el resultado de activar WAL. Los valores efectivos deben medirse en el proceso desplegado, no deducirse de defaults.
- Hay varios hilos de sesiones/tareas en `local_game_server.py`. Posiciones, builds, inventario, XP, recolección y grupos comparten persistencia. Se encontraron `BEGIN IMMEDIATE` en **24 archivos**, `INSERT OR IGNORE` en ocho, PRAGMA en cuatro; además `lastrowid`, `executescript`, `sqlite3.Row` y excepciones SQLite. No existe adaptador PostgreSQL en las dependencias revisadas (`requirements.txt` contiene Redis).
- Redis no elimina las escrituras SQL: `build_journal.flush` confirma un lote dentro de una transacción y hace checkpoint Redis después; `position_redis.recover` revalida leases y baseline antes de aplicar. Estas garantías deben conservarse.
- Compose monta `.runtime/local` como almacenamiento de world; el Dockerfile usa `python:3.12-slim`, sin fijar versión de SQLite. No se verificó aquí el SQLite del contenedor ni el filesystem físico de producción.

[Archivos, patrones y hashes](probe-acoplamiento-sqlite.json).

## Comparación aplicada a este servidor

| Aspecto | SQLite actual | PostgreSQL propuesto |
| --- | --- | --- |
| Escrituras concurrentes | Un escritor por base; distintas cuentas pueden esperar entre sí. | MVCC y bloqueos de filas permiten concurrencia entre entidades independientes; aún hay conflictos y deadlocks. |
| Varias instancias/hosts | WAL exige mismo host y no sirve sobre filesystem de red. | Servicio central accesible por red, con autenticación y pool. La autoridad de mundo/grupos sigue necesitando coordinación. |
| Operación | Sencillo y sin servicio adicional. | Requiere servicio, credenciales, pool, monitorización, mantenimiento y backups. |
| Recuperación | Backup consistente con API/snapshot; conservar WAL cuando corresponda. | Dumps y base backup + archivo WAL/PITR, con restauración ensayada. |
| Integridad | FK y transacciones disponibles, pero el código/recovery actual deja incoherencias. | Constraints útiles, pero también necesita transacciones de dominio y datos reconciliados. |
| Rendimiento | Puede bastar con baja concurrencia y transacciones cortas. | Beneficio esperado bajo escritores concurrentes; añade latencia de red. No sustituye índices ni reducir SQL redundante. |

SQLite documenta el único escritor y las restricciones WAL; su guía recomienda motor cliente/servidor con muchos escritores. PostgreSQL documenta MVCC y bloqueos explícitos. [SQLite WAL](https://www.sqlite.org/wal.html), [usos adecuados de SQLite](https://www.sqlite.org/whentouse.html), [PostgreSQL MVCC](https://www.postgresql.org/docs/current/mvcc-intro.html), [bloqueos](https://www.postgresql.org/docs/current/explicit-locking.html).

## Prueba ejecutada y alcance

En SQLite WAL temporal, una conexión mantuvo una escritura sobre actor1. Otra pudo leer el estado confirmado anterior, pero no empezar otra escritura, aunque fuera para actor2: `database is locked` con timeout0. Tras commit, ambas modificaciones se conservaron. **Acredita el bloqueo global de escritura; no mide usuarios soportados ni latencia del servidor.** [Fixture](probe-concurrencia-sqlite-wal.json).

No se levantó PostgreSQL, no se modificó una base existente y no hay comparación de throughput. No dar cifras de jugadores o mejoras porcentuales sin medición.

## Migración concreta

1. Extraer interfaz de almacenamiento y migraciones versionadas fuera del arranque/caminos de juego. Inventariar SQL de los 24 módulos, no adaptar únicamente `Store.connection`.
2. Usar driver PostgreSQL y pool limitado por carga medida. Sustituir `?` por parámetros del driver, `BLOB` por `bytea`, IDs/UIDs por `bigint`, `AUTOINCREMENT/lastrowid` por identidad y `RETURNING`. Conservar IDs existentes y ajustar secuencias tras importar. No convertir protobuf/bytes en texto accidentalmente.
3. Sustituir `INSERT OR IGNORE` por conflictos explícitos sobre claves previstas. Mantener `ON CONFLICT` con constraints reales. Preservar semántica de unicidad de nombres: `COLLATE NOCASE` de SQLite no equivale automáticamente a `citext`/lower Unicode; definir y probar normalización compatible antes de migrar.
4. Reemplazar `BEGIN IMMEDIATE` por transacciones y bloqueos/CAS **por agregado**: sesión/personaje para cambios de hoja/salud; wallets/inventarios de ambos participantes en orden estable para trade; instancia/encuentro y recibo para premios. Un SELECT seguido de UPDATE bajo Read Committed no replica el bloqueo previo de SQLite. Usar constraints, `SELECT FOR UPDATE` o CAS según operación y reintentar transacciones completas ante conflictos recuperables, con recibos idempotentes.
5. Conservar leases, revisiones y recuperación SQL/Redis. Commit SQL y ACK Redis no son atómicos; reconocer commit ya aplicado y no duplicar grants. No introducir dual-write sin protocolo de reconciliación. Para nuevos eventos de valor, outbox SQL en la misma transacción y consumidores idempotentes.
6. Exportar desde snapshot íntegro reconciliado, importar a PostgreSQL aislado y comprobar conteos, FK, UIDs, cantidades, HP/builds, saldos y recibos. No eliminar las 12 referencias huérfanas conocidas sin investigar. Guardar timestamps existentes con semántica explícita (segundos reales frente a milisegundos); migrar tipos después con reglas probadas.
7. Cutover posterior con ventana de escritura detenida, flush/reconciliación de journals, snapshot final, validación y cambio de configuración. El rollback no consiste en volver a un SQLite obsoleto después de nuevas escrituras: definir export/replay inverso o mantener escrituras detenidas hasta aceptación. Nada de esto se ejecutó.

## Backups y decisiones operativas

Para PostgreSQL, configurar backups fuera del host y PITR con base backup más archivo WAL continuo; probar recuperación hasta un punto elegido. `pg_dump` solo no ofrece PITR. Determinar RPO/RTO y retención operativa antes del despliegue; no inventar garantías. [Backup PostgreSQL](https://www.postgresql.org/docs/current/backup.html), [PITR](https://www.postgresql.org/docs/current/continuous-archiving.html).

Mientras siga SQLite, usar backup consistente mediante API o procedimiento acreditado, comprobar restauración/FK y preservar originales. No copiar solo el archivo principal activo. [API de backup SQLite](https://www.sqlite.org/backup.html).

## Versión SQLite: hallazgo adicional a investigar

El fixture local informa **3.51.0**. La documentación oficial describe un bug de reset WAL en versiones hasta3.51.2, corregido en3.51.3 y backports3.44.6/3.50.7, bajo ciertas carreras de escritura/checkpoint con varias conexiones. Esta arquitectura tiene WAL y múltiples conexiones, pero **no se conoce la versión del boot corrupto ni se reprodujo esa carrera**: es hipótesis a contrastar, no causa demostrada. Registrar `sqlite_version`, build/opciones y versión del contenedor/boot antes de atribuir el daño. No se actualizó ningún runtime. [Descripción oficial](https://www.sqlite.org/wal.html#walreset).

## Validación exigida antes de adoptar PostgreSQL

Comparar misma carga y datos: conexión/selección, movimientos con flush, inventario/recolección, cambio de builds y premios idempotentes; hechizos siguen fuera de esta sesión. Medir p50/p95/p99, duración de transacciones, esperas/bloqueos, errores y conexiones. Inyectar caída antes/después de commit y antes de ACK Redis; restaurar backup y verificar invariantes. Probar dos jugadores y varios escritores con entidades iguales y distintas. La recomendación queda fundada; **rendimiento y migración efectiva siguen sin verificar**.


[Inventario completo y migración tabla por tabla](MIGRACION-POSTGRESQL-TABLAS.md). Esta especificación posterior fija el alcance sin backend dual.
