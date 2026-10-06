# E09 — Lecturas repetidas tras la migración PostgreSQL

## Alcance actual

El cotejo anterior conserva evidencia del backend SQLite y journals retirados por E01; sus fragmentos y hashes no describen el runtime actual. PostgreSQL es la autoridad única. La optimización no restablece esos journals ni añade otro backend.

## Repetición concreta en bootstrap

`local_game_server.replay` llamaba `STORE.characters(account_id)` independientemente para el bloque social de cuenta13873, inventarios13078, lista23548 y hojas12393. Cada llamada vuelve a hidratar progreso, merkasaco, inventarios, barra rápida, builds y selección de todos los personajes. Varios paquetes del mismo replay repetían ese trabajo.

Se añadió una carga lazy por invocación de `replay`. Los consumidores usan la misma colección; no se carga si ningún paquete la necesita. Una nueva invocación vuelve a consultar PostgreSQL, por lo que no existe caché global que requiera invalidación. El registro de sesión y las operaciones mutantes mantienen sus validaciones propias.

## Verificación pendiente

La ampliación en fuente pasó cuatro regresiones de `test_replay_hydration`, ejecutadas en Docker. El harness extrae el replay real por AST, verifica una sola carga para social/equipo/lista/hojas, ausencia de carga en paquetes independientes y lectura nueva con estado actualizado en la invocación siguiente; conserva el orden de paquetes. Tres casos aíslan conteo y ámbito con fakes; el cuarto usa PostgreSQL aislado, fixtures originales y codificadores reales de social13873, inventario13078, lista23548 y hojas12393. Comprueba bytes idénticos frente a hidrataciones independientes, colecciones sin mutación y registros de builds[0,1]/[0] con identidades correctas. El nuevo código se cargó mediante reinicio coordinado en la imagen33a78a4819e2b791eade0c67e02193a693de8545d51d649a4bfa7651dfae1f7f; contenedor healthy y `/health` PostgreSQL ok. Queda pendiente medir SQL/latencia reales.

Este cambio no cierra E09 ni0: faltan mediciones de latencia y carga, revisión del resto del camino caliente y coherencia frente a escritores concurrentes. Compartir una colección dentro del replay no convierte el conjunto de paquetes en una transacción con las operaciones concurrentes.
