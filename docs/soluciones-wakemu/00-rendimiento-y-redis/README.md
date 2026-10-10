# 0. Retrasos al iniciar combates y lanzar hechizos

Reducir retrasos reales de entrada, inicio y hechizos; cumplir Redis primero y flush a 20 minutos sin pérdida de autoridad.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**En revision.** Hay correcciones de ciclo y movimiento ya verificadas; sigue pendiente resolver y medir la latencia de la primera entrada sin alterar geometría, daños ni orden de acciones. Ningún benchmark aislado demuestra que la latencia de sesión esté resuelta.

## Dependencias

19, 20, 32, 34 y almacenamiento adicional. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Una solicitud de valor se aplica una vez; ninguna revisión nueva se borra por un flush antiguo; optimizar no cambia geometría legal, daños, orden de acciones o autoridad.

## Evidencia adicional ejecutada

[Cotejo posterior a las respuestas del usuario](REVISION-RESPUESTAS.md).


## Cotejo de carga fría — 6 de octubre

La primera entrada registrada tomó18,2s, de los cuales17,71s fueron `prewarm_map` antes de publicar colocación. La misma exportación337/62164 filas tarda195–211ms en procesos fríos del host y160ms en un proceso Python separado dentro de Docker world; hits0,196ms/0,013ms. El mapa1134 frío tarda596ms y existe su exportación. No se atribuye el intervalo restante a SQL/Redis ni al bridge Docker sin evidencia: se necesita medir contexto de sesión/contención/presión de memoria. Cache miss simultáneo puede duplicar carga (lru_cache no es singleflight); precalentar mapas indiscriminadamente sería costoso. Artefactos privados: `.runtime/local/forced-terrain-first-entry-diagnostic.json` y `.runtime/local/forced-terrain-docker-process-probe.json`. Sin cambios de hechizos ni ejecución de combate en esta investigación.

### Arranque con población inicial ya registrada — 2026-10-06

Los listeners del arranque4aae53dd se abrieron después de24,46s de catálogos y14,75s adicionales de validación de población. La segunda fase reconstruía geometría aunque las nueve regiones tenían marcadores permanentes. La fuente ahora lee esos marcadores antes del terreno: valida estructura e identidades del catálogo y omite geometría/siembra únicamente para habitats ya completados. Las regiones nuevas mantienen todas las comprobaciones y la transacción original.

18 pruebas PostgreSQL aisladas pasan, incluida ausencia de consultas de geometría y ausencia de reposición tras reinicio; aristas inválidas de regiones nuevas fallan cerradas. Medición en un proceso Docker separado con los9 marcadores reales:3,22ms para validar9 planes, sin mutaciones. Esto mide esa fase, no el arranque entero ni la demora de17,7s de la primera entrada a combate. La corrección aún no está cargada en el proceso world; no se reinició mientras el usuario prueba.

La imagen candidata7556e218 pasó105 pruebas sin montar fuentes/protocolos (evidencia `.runtime/local/startup-marker-image-gate-20261006.txt`). No desplegada. Se añadió en fuente medición de CPU del hilo y del proceso junto al tiempo de pared de `combat_forced_terrain_ready`, para diferenciar cálculo propio de espera/competencia antes de atribuir la demora; no cambia el calentamiento ni sus políticas. Pendiente capturar una entrada fría del proceso activo después de cargar el cambio.

Cotejo histórico adicional: `.runtime/local/forced-terrain-historical-correlation.json`. No existe snapshot/digest suficiente para demostrar que el proceso del pico cargó los mismos bytes que el código actual. Carga fría actual de337 en Docker:212,2ms de pared/211,7ms de CPU del hilo. No se atribuye la demora histórica a un lock ni a SQL/Redis sin evidencia.

Despliegue de optimización:imagen4166845e/boota0da568a healthy; transcurrieron318ms desde catálogos listos hasta listeners, incluyendo tres siembras nuevas y nueve regiones ya marcadas. Esto verifica la mejora de la fase posterior a catálogos frente a14,75s previa. Catálogos tardaron26,38s; la demora histórica17,7s de entrada a combate sigue sin reproducirse/atribuirse.

## Aviso global de guardado

Petición del usuario7octubre: chat de información global para guardados perceptibles. Fuente conecta GlobalTasks al observadorSlowSaveAnnouncements y World.information_all (todos mapas/instancias, escritura fuera de lockworld). Un guardado global >1s anuncia inicio y luego éxito/fallo; positions_flush normalcada2s queda silencioso si rápido. Checkpoints individuales y su atomicidad no se modificaron. Gate fuente40/40; imagenb14232c8 en verificación, sin despliegue.

## Despliegue merge7octubre

Imagen9af0658c (wakfu-local-world:merged-verified) desplegada healthy, PostgreSQL001–048. Gate de imagen200/200; socket de recuperación agrupada, GetAll propio, reciclado, abandono y reconexión aprobado; borrado socket validado en candidata equivalente. IA y todos los módulos de combate conservados desdee18verified. Respaldo privado pre-inventory-merge-20261007.dump. Confirmación manual UI pendiente.

## Precarga de combate medida en release de fabricación

Candidata3523:117731ms para combat_catalogs_ready (208módulos/59104efectos). Live3523:147311ms (208módulos/61227efectos), antes de listeners y seed_configured. El live reconoció los93hábitats existentes (duplicate=true); la demora ocurre antes de sembrar. La candidata fue detenida por root después del smoke, exit137 con OOMKilled=false. Se perfila por loader en instancia aislada; aún no se cambia el orden de precarga.


## Native catalog PostgreSQL and Redis migration — 2026-10-08

The native protocol catalog readers now share a versioned PostgreSQL authority and bounded Redis cache, retaining their existing in-memory entity and coordinate indexes. Plain JSON files are import artifacts; compressed JSON files were converted and removed after byte verification. See [architecture, indexed drop queries and complete manual acceptance](../../reports/native-catalog-postgres-redis.md), and [DBeaver access](../../reports/dbeaver-postgresql-access.md). Import and deployment are verified in complete build r46. World and AI are healthy, with AI preloading and a complete context seal before game listeners open. The full database dump is verified. This change does not claim all historical latency issues are resolved.

## Priority regression: checkpoint freezes — 2026-10-09

Hector reports that Redis-to-PostgreSQL checkpoints still freeze combat for minutes. This issue remains open and has top priority. [Confirmed lock amplification, source correction, 30 automated tests and full manual acceptance](CHECKPOINT-CONTENTION-2026-10-09.md). The source now separates account checkpoints, removes database/Redis I/O from the global position-buffer lock, bounds pool/row waits, preserves journal/CAS durability, and records timing stages. The first correction was deployed in r56 and the freeze recurred: a live empty checkpoint took41.43s, with fast individual SQL-pool/Redis stages. Complete release r57 now removes synchronous diagnostic-file writes from the global LIVE ownership lock and adds a five-second native thread-stack watchdog. It is deployed and healthy; live freeze acceptance remains open. A later idle stack capture did not reproduce the freeze. Do not interpret automated tests or earlier performance notes as closure.


## Optional profiling service — 2026-10-09

Complete r58 retains r57 fixes and adds bounded feature timings plus an external
py-spy sidecar that starts/stops independently. [Operation and large unmodified
findings](../../reports/health/EXTERNAL-PROFILER-20261009.md). Startup point-area
metadata preparation was sampled as expensive; no optimization is authorized
in this stage. Checkpoint freezes remain open until accepted live.
