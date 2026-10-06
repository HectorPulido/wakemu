# Issue 33 — Abandono y retorno al mundo

## Comportamiento implementado

`combat_abandon.prepare` valida participante propio, único controlado, fase y request vacío antes de preparar 12238/13420. Persiste salud, heridas y recibo de salida junto con `combat_fights.status = aborted` en una sola transacción. Un fallo al guardar el estado revierte también salud y recibo; la fase, contador, ACK y acciones pendientes en memoria solo cambian después del commit. No concede XP, kamas ni objetos.

El retorno12925 valida identidad del combate y dueño. Acepta flags nativos0/1 para el abandono ya autorizado: el flag de presentación no convierte el aborto en victoria. Repeticiones no aplican otra salida. El dispatcher restaura posición/transporte y presencia, libera el grupo como disponible y elimina las referencias de combate de la sesión.

## Verificación

**61 pruebas PostgreSQL pasan**, con migraciones001–008. Incluyen rollback inyectado de la actualización de estado, rechazo de combate durable finalizado, retorno repetido, salud, checkpoints y grupos; abandono seguido de transporte ZAAP y nuevo combate durable; desconexión sin callback y selección posterior. Véase [matriz y comando](PRUEBAS.md).

## Límites pendientes

El recorrido compuesto de los tests llama funciones directamente; no acredita el dispatcher/socket ni el recorrido visual completo. Falta inyección de fallos entre commits y publicación/liberación de grupos del handler. La limpieza de desconexión también necesita protección frente a un error persistente de checkpoint que interrumpa operaciones posteriores. El abandono por participante en combates compartidos sigue sin implementar. El cierre atómico nuevo está en fuente; su imagen se está preparando y no se atribuye todavía al contenedor activo.

## Carga comprobada

Imagen `9894e928a3b93f660ba2b44cc79004fc05ed3a6006e4e469346f55055a5b4187` cargada en Docker; contenedor healthy y `/health` devuelve PostgreSQL ok. Los pendientes gráficos y de recuperación indicados arriba se conservan.

## Desconexión: misma barrera transaccional

Ampliación en fuente: `persist_aborted_fight` guarda salud/recibo y aborta la identidad durable mediante una conexión compartida. Se retiró el aborto incondicional en `finally`: ante un error SQL ya no se confirma el estado terminal después de fallar la persistencia de salud. Una sesión sustituida sigue sin poder actualizar salud; solo puede liberar su antigua identidad de combate. `fight_store.abort` exige transacción activa al recibir conexión prestada. Esta ampliación está pendiente de regresión/carga; no se confunde con la imagen9894 ya desplegada.

La ampliación de desconexión pasó **64 pruebas PostgreSQL**, con migraciones001–008. El fallo SQL al abortar revierte HP/heridas/muerte, recibo y estado; el reintento posterior funciona. Una lease sustituida no cambia salud ni recibos actuales y termina únicamente el combate antiguo. La conexión autocommit prestada se rechaza sin mutaciones. No se repitió la suite completa; estos resultados corresponden al gate dirigido ampliado.

## Desconexión atómica cargada

Imagen `534cb756edfa9d9490ec568c07554a46b3b4a65ea91f449c19e87533a5b15a7c` activa; contenedor healthy y `/health` PostgreSQL ok. Los64 tests del gate corresponden a esta ampliación. Persisten las comprobaciones de dispatcher, publicación y recuperación detalladas arriba.

## Cierre de sesión: reintentos por etapa

El cotejo del `finally` mostró dos interrupciones adicionales: el checkpoint SQL podía impedir toda limpieza posterior, y `POSITIONS.release` podía fallar al retirar el registro Redis después del flush. Además, el grupo se liberaba antes de confirmar las heridas.

Se añadió `storage/session_cleanup.retry_step`, utilizado por el dispatcher para checkpoint, salud, flush y liberación de posiciones, liberación de grupos, salida del mapa y cierre de sesión. Cada etapa reintenta errores transitorios de conexión/pool/registro Redis, renueva la sesión y solo avanza después del éxito. Las etapas completadas no se repiten al fallar una posterior. Salud y posiciones se confirman antes de liberar el grupo. La retirada de `LIVE` conserva el control de generación para no eliminar una sesión nueva.

Los fallos de invariantes y programación se propagan; esta implementación no acredita recuperación de cualquier excepción. Tampoco ofrece atomicidad entre PostgreSQL, Redis y sockets. Regresión del dispatcher y carga de esta ampliación pendientes; los64 tests anteriores no se atribuyen al nuevo recorrido.

La ampliación pasó el gate de **88 pruebas** de cleanup/Redis/world/protocolo/chat/API, sin sumar su cobertura a gates anteriores. El harness ejecuta el `finally` real extraído por AST, sin inicializar el servidor: inyecta errores transitorios, comprueba orden y sesión sustituida; Redis distingue indisponibilidad de conflicto CAS y verifica recuperación tras commit SQL y fallo de ACK. La compilación del dispatcher pasó en Docker. Imagen `3d5aee9d6c2e9e46389dbce16e64078bcbd2b536cdd1abaa043b9a13afa8fcd5` cargada; `/health` PostgreSQL ok y Docker healthy. Sigue pendiente el recorrido visual y la recuperación de fallos permanentes/publicación posterior al commit.

## Ruta precisa para la prueba nativa

El constructor UI `cVt` registra `giveUpButton` (28×28, estilo `flagNegativeXS`) dentro de `fightActionsWidget` (240×42), con acción `wakfu.fightAction:giveUpFight` y tooltip `descGiveUpFightPopup`. La disponibilidad depende de `canGiveUpFight`/`giveUpDisabled`. La acción llega a `dba.fco`, abre `question.giveUpFight` y la confirmación envía `13952`. Esta identificación permite probar el botón real sin confundirlo con cerrar Wakfu; todavía no acredita haber completado el abandono visual.

## Evidencia de sesión real posterior

Durante la intervención manual del usuario, el log registra personaje1/combate2: `combat_abandoned_waiting_return` a2026-10-06T04:49:41.117064Z y `combat_return_to_world` a04:49:41.672984Z. PostgreSQL conserva combate2 como `aborted`. Después, `!ayuda` y `!mob` terminan con `outcome=ok` (04:50:32 y04:50:45), acreditando que la sesión volvió a aceptar comandos de mundo. Un ACK de turno tardío entre abandono y retorno se rechazó como obsoleto sin impedir el retorno. Esta evidencia confirma el recorrido del servidor en una sesión real; no identifica qué control pulsó el usuario ni sustituye las pruebas pendientes de transporte/nuevo combate y publicación recuperable.
