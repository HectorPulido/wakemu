# Joining an existing fight

Offline Java confirms `fight.join` (`cWS.run → bvz.d → bvy/bvC.dNf`) sends OUT13241 `coU`. Its nine-byte body is an i64 target fighter actor ID and a byte representing the native `autoLockFights` preference. The ID is not the fight ID. Native team/phase/capacity/permission checks precede sending the request.

IN13091 `cvg` carries fight ID, actor ID, actor/team fields, native myE/myF actor blobs and optional controller information. Participant handler `cjs` and external observer handler `ckT` insert the actor into their respective fight models. IN13753 `cuY → ckM` creates the external `buG` world fight context; that context is needed for the ordinary join GUI action. Its complete variable schema and joiner initialization ordering still require implementation review.

Additional placement cells alone do not implement multiplayer. Current server fight and action runtime are connection locals, actor callbacks capture the starter character, combat packets go to one socket and group leases belong to that starter generation. A shared fight registry, actor-to-fight lookup, participant membership and one synchronized action queue are prerequisites.

Implement first placement-only joining: validate owned live character in the same map/instance; atomically reserve a free native placement cell and insert the controlled actor; initialize the joining client; broadcast IN13091 and placement state to existing participants; publish external world fight context; wait for all participant readiness. Fence action acknowledgements by current actor owner and session generation. Keep the monster-group reservation until the shared fight finishes. Persist HP and finish receipts independently for every owner.

Native late-join permission, error response mapping, exact joiner bootstrap order and individual multiplayer abandonment remain unimplemented. Test two accounts, concurrent last-cell joins, readiness, owner acknowledgements, starter disconnect and exactly-once HP/reward settlement before claiming multiplayer support.

Evidence is indexed in `server/protocol/combat-multiplayer-audit.json`; the Java disassemblies are under `.runtime/local/multiplayer-*.txt`. No server runtime was changed or restarted by this audit.

## Implementación del adaptador compartido

`wakfu_server.combat_shared.Registry` mantiene una sola FSM y un runtime por
combate, índices de actores/personajes, membresía por cuenta con generación y
colas de paquetes por sesión. `live_session(Session)` verifica la lease real y
el personaje seleccionado en Store. Las acciones trabajan sobre copias de FSM
**y runtime** y solo se confirman cuando validación y serialización terminan.
Un callback no puede escribir SQLite ni enviar paquetes durante esa operación.

Integración concreta del adaptador de red:

1. Al iniciar, `register(fight, starterSession, runtime=state,
   group_lease=lease)` registra la FSM. El contexto de conexión deja de poseer
   una copia autoritativa de `fight`, pending ACKs, WP y runtime de acciones.
2. Publicar `combat_multiplayer_wire.external(value)` a observadores del mapa,
   después de las apariencias propias de todos los actores. Su IN13753 crea
   el contexto externo usado por el menú normal «Unirse».
3. Para OUT13241 llamar `join(session, body, ownedActor,
   actor_payload=..., bootstrap_packets=...)`. Reserva una casilla libre del
   equipo del jugador objetivo y produce IN13091 +13026 para participantes
   existentes. El incorporado recibe el bootstrap propio de la factory.
4. `ready` espera a todos los propietarios; `execute` valida generación,
   actor controlado, turno actual y secuencia. `execute_server` permite solo
   el turno del actor no controlado, con secuencia obligatoria.
5. Un único escritor por socket consume `drain(fightID, session)` y envía
   cada Batch sin intercalarlo con otro Batch de ese combate. El marcador
   Batch.sequence es del dispatcher; la secuencia de acción del protocolo
   nativo sigue dentro de runtime y debe ser común a todos los participantes.
6. `disconnect` no libera al grupo reservado; `takeover` exige que la lease
   previa ya no sea válida y construye snapshots propios de recuperación.
   Un finally antiguo no afecta a la sesión reemplazante.
7. La reserva del grupo sigue al combate. Usar `lease_active(groupLease)`
   como comprobación adicional; RedisGroups recibe una generación y debe usar
   `lease_generation_active(generation)` OR la comprobación normal de Store. Evitar `release_session(starterGeneration)`
   mientras dicho combate existe. El timeout/abandono debe terminar y liquidar
   el combate, no borrar la reserva por desconectar al iniciador.
8. `remove_finished(fightID, settle)` requiere fase finished y conserva estado
   ante fallo de settlement. El callback persiste HP/recompensas de **todos**
   los propietarios y finaliza el grupo con recibos idempotentes.

No hay aún integración de sockets del servidor principal. Las factories son
puntos concretos de integración, no mensajes sustitutos: deben reutilizar
`placement_messages`, `actor_stats` y `actor_effects` con personajes propios.
La recuperación en fase ACTION, el orden exacto del bootstrap del incorporado,
la respuesta nativa de rechazo y el abandono individual necesitan prueba de
cliente antes de anunciar multijugador funcional. La arquitectura no fuerza
revivir/derrotar a un participante desconectado ni inventa premios compartidos.

## Esquemas nativos completados

OUT13241: `>qB`, objetivo actor existente y bool autoLock.
IN13091: `>iqbb`, fightID/actorID/myR/team, stats con longitud signed i16,
effects con longitud i32, bool opcional SQ; SQ contiene byte tipo SR, long ID e
int parámetro. `myR` no tiene significado demostrado y se mantiene explícito.
IN13753: `>ibqqhq`, fightID/kind/myo/myp/jqi/myu; byte-count long[] myr;
short-count pares long actor/byte team; byte phase; cuatro bool; byte-count
pares short/short mys; resto es topología nativa fct/QI. **myr contiene dos
líderes**, pues ckM consulta directamente get(0) y get(1).
Enum fbZ: NONE0, PLACEMENT1, ACTION2, CREATION3, DESTRUCTION4,
ENDING_PLACEMENT5. Los campos myo/myp/jqi/myu se suministran explícitamente;
no se inventó su semántica.

`sniffer/java/VerifyCombatJoin.java` ejecutó los decodificadores reales cvg,
cuY y fct con IDs propios y topología de la instalación. La aceptación del
codec no equivale a aprobación visual del flujo de incorporación.
14 pruebas shared/FSM pasan: dos cuentas, readiness, turno y secuencia,
capacidad concurrente, leases/takeover, desconexión del iniciador, rollback
de acciones/serialización y finalización única. No se reinició el servicio.

## Barrera nativa de turnos para múltiples sesiones

`aUM.cXi` envía OUT13510 después de procesar12502. Su guarda `aTL.cXf`
comprueba que el combate corresponde al participante local; **no** comprueba
que este sea propietario del actor cuyo turno termina. Por tanto todos los
clientes participantes envían13510, con el mismo contador i32 `bvY.bhQ()`.
El primer ACK no puede liberar el siguiente turno para el resto.

`combat_ack_barrier.AckBarrier` registra una instantánea account/generation
al armar; `Registry.arm_ack` toma participantes conectados con lease válida.
`Registry.acknowledge` espera a todos y ejecuta la liberación nativa pendiente
solo una vez, generando el mismo Batch para todos. Duplicados de una cuenta
no cuentan como otra. Un ACK ajeno, viejo o con contador distinto falla.
No hay filtro por propietario del turno para13510; sí para acciones activas.

Una desconexión no se transforma en ACK. Si ocurre durante la barrera, hace
falta política explícita de aborto/recovery; `cancel_for_recovery` solo borra
barrera cuando el llamador envía recuperación nativa correcta. El avance
tras reconexión debe probarse con cliente; no se inventó ACK de timeout.

La copia de FSM/runtime usa un solo memo de deepcopy, de modo que
runtime.fight continúa apuntando a la misma FSM candidata. Factories/callbacks
con closures sobre el personaje iniciador deben convertirse a resolución por
actor/owner. Recursos por cuenta, grupo/mapa/arena, reloj/checkpoints y pending
ACK se guardan en runtime compartido, nunca en locals de conexión.
17 pruebas de adaptador/FSM pasan, incluida identidad runtime/FSM y barrera
entre dos sesiones. Estos componentes aún no prueban incorporación GUI.
