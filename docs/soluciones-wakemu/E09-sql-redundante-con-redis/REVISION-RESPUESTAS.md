# E09 — SQL repetido pese al journal Redis

## Código y prueba actuales

`Store.character` lee primero SQL: personaje, progresión/wallet, merkasaco, contenedores, objetos y builds. Solo al final aplica `BuildJournal.overlay`. Un hit de journal sustituye las hojas, pero no evita las consultas anteriores. Además `_units` valida referencias contra SQL: el journal no es una caché completa del personaje ni de propiedad de inventario.

[Revalidación actual](probe-lecturas-actuales.json): guardar una build sin decks ni aptitudes y cargar tres veces con MemoryRedis y traza SQL. Cada carga produjo **9 SELECT, 7 CREATE IF NOT EXISTS, 1 PRAGMA y 3 INSERT idempotentes**. La build del journal estuvo visible en las tres. La traza también observó BEGIN implícito de las inserciones. No son tres objetos nuevos; son inicializaciones de dominios. No se midió Redis real ni se atribuyen20s a estas consultas.

## Solución concreta del servidor

Sacar DDL, PRAGMA de migración e inicializaciones de loaders calientes. Migrar esquema al arrancar y crear dominios del personaje al registrarlo; loaders normales deben leer, sin reparar continuamente toda la estructura. La migración debe soportar personajes antiguos de manera explícita.

Dividir snapshots en dominios con autoridad y revisión: catálogo inmutable, personaje/progresión/salud, inventario/propiedad, builds y merkasaco. Leer Redis primero para dominios hidratados y pedir SQL solo ante ausencia real, no después de recuperar todas sus filas. No devolver inventario SQL viejo si Redis está indisponible con mutaciones pendientes: podría resucitar consumos y duplicar objetos. Diferenciar miss, caída y corrupción.

Los UIDs de hojas necesitan validación contra el inventario autoritativo del mismo snapshot/revisión; quitar `_units` sin reemplazo elimina una garantía de ownership. Inventariar writers de grant, consumo, equipamiento, transferencias, recompensas e identificación y hacer que todos actualicen/invalide la misma revisión, incluyendo herramientas administrativas. Evitar caché de `Store.character` sin invalidación: mezclaría salud reciente con equipo viejo.

Aplicar journal de20min donde la autoridad durable lo permite; leases, propiedad y recibos deben confirmarse antes de ACK. Flush por revisión con comparación de baseline y recuperación idempotente, no un hilo que sobrescriba SQL a ciegas. Parámetros e intervalos se administran en DB con snapshot versionado. Medir AOF y fsync del Redis cargado, no solo lo declarado en Compose.

## Límites pendientes

El conteo está confirmado sobre código actual y fixture privada. Falta trazar todos los writers y medir carga del Redis desplegado, contención y p95/p99. No se modificaron fuentes ni servicios; la propuesta no promete que eliminar nueve SELECT solucione por sí solo el retraso global del issue0.

## Dependencia de integridad comprobada

Se reprodujo una hoja confirmada en Redis seguida de rollback SQL de salud: [evidencia E06](../E06-nivel-y-hojas-sin-atomicidad/probe-cas-redis-y-rollback-sql.json). Reducir SQL o diferir escrituras no debe ocultar esta frontera. Antes de ampliar la caché, definir recibos/revisiones y recuperación de transiciones incompletas; las lecturas deben devolver una revisión coherente de salud y hojas.
