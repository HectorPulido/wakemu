# Clima: carrier acreditado y tarea ausente

## Prueba ejecutada

13948 (`ctm`) usa big endian **i64 + byte firmado + seis float32 + i32 precipitación**, total37bytes. Se generó un fixture sintético y se decodificó mediante `ctm.dp` y `protocol_codec`: los ocho valores numéricos y el enum se conservan. `Vl` admite0ABSENT,1LIGHT,2HEAVY,3STORM. Los floats1–6 y byte17 son sentinelas de layout, **no un clima oficial ni rangos válidos acreditados**. No etiquetar el primer long como region_id sin resolver su consumidor.

`chl` atiende13948 y construye `bRW`: aplica cinco floats al estado de transición y un segundo conjunto al estado presente; combina el byte base con el tercer float de transición y aplica el resultado al territorio actual `bLO`. Esto no se reproduce enviando únicamente reloj23354. Hay otro mensaje13895 para previsión (`cBl`→`bRV`→`bRY`), cuyo layout y calendario siguen pendientes.

## Cotejo de tareas y publicación

Cron contiene weather desactivado. `GlobalTasks.ALLOWED_TASKS` solo contiene positions_flush/builds_flush/groups_flush; registrar weather es rechazado por constructor. Pasaron dos pruebas existentes de tareas globales, incluido ese control negativo. Cambiar `enabled` no crea callback, modelo ni publicación. No se encontró emisión explícita13948 desde el dispatcher actual; esto no prueba por sí solo ausencia de algún frame histórico en la captura.

## Solución concreta de servidor

Acreditar todos los parámetros/rangos/calendario y extraer defaults por región antes de implementar generación. Mantener estado por territorio/revisión, hora y próxima transición, no sortear clima distinto por jugador. Incorporar callback weather explícito, idempotente por ocurrencia, y sus carriers13948/13895 después de fijar estado; enviar snapshot al entrar/reconectar. Filtrar destinatarios por territorio real, no broadcast mundial: el consumidor usa el territorio actual del personaje.

Integrar condiciones climáticas en las autoridades de plantación/crecimiento, no solo efecto visual. Faltan las funciones nativas que relacionan temperatura/lluvia con cada recurso. La pausa ecológica en mapas vacíos no implica automáticamente parar calendario global; cotejar reglas y separar reloj del trabajo de simulación.

## Límites

No se probó cambio climático visible ni efectos sobre plantas; no se acreditaron calendarios/rangos/formulas. [Fixture, prueba de población y hashes](probe-clima-y-ecologia.json). No hubo fixes ni cambios del cliente.
