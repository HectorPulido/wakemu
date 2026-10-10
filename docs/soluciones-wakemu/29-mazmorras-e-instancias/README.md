# 29. Mazmorras

Entrar, compartir salas, progresar y salir de mazmorras con encuentros/recompensas idempotentes.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Reconstrucción automática del recorrido natural

[Investigación y método general](../../reports/dungeons/AUTOMATIC-FLOW-REVIEW.md): extracción de geometría nativa, puertas, teletransportes y referencias Lua. Los 211 separadores candidatos **no acreditan** el orden oficial ni las condiciones de apertura. En Tofullero la conexión de entrada se resuelve usando el perfil nativo de movimiento de exploración, sin cambiar combate; los parámetros de sus puertas no contienen dependencias de combate. Ver [controlador y propuesta general](../../reports/dungeons/TOFULLERO-CONTROLLER-REVIEW.md). No se desplegó ni reinició el servidor.

## Inventario de evidencia (2026-10-09)

Inventario completo de la unión disponible: [matriz por mazmorra](../../reports/dungeons/INVENTORY.md), [datos por sala, monstruo, objeto y requisito](../../reports/dungeons/inventory.json) y [auditoría de jefes supremos](../../reports/dungeons/ULTIMATE-BOSS-AUDIT-20261009.md). Incluye **151 definiciones nativas y 5 guías legacy sin definición**, no solamente las 87 configuraciones generadas. Las 69 definiciones nativas sin guía y los campos desconocidos quedan explícitos. Los objetos y destinos de teletransporte se contrastaron con el catálogo PostgreSQL activo, en transacción de solo lectura. La presencia de configuración no acredita una mazmorra correcta: 10 de 11 jefes supremos configurados tienen composiciones duplicadas incorrectas.

## Estado y alcance

Auditoría e implementación parcial del **servidor**. La base durable de sesiones/miembros en migración 065, el resolvedor limitado a rutas verificadas y la transición atómica de roster en `maps/dungeon_transport.py`/`maps/dungeon_instances.py` están probados con PostgreSQL aislado. La entrada sigue desconectada del dispatcher: no hay caller para el evaluador de criterio/proximidad, no se emitió bootstrap de mapa y no se ha habilitado el acceso. Las pruebas no certifican el recorrido jugable.

**Estado funcional actual (2026-10-07):** el acceso normal candidato a Jalató está identificado (mapa 527, transportador 26842, destino 2504, plantilla 91). El servicio puede crear/reutilizar el run y trasladar toda la party a una instancia recién generada en una sola transacción, sin usar `cyZ` como `instance_id`. La migración 068 guarda el modo de servidor explícitamente, y el helper acepta solo `IsNeoServer()` y `not IsNeoServer()`. El cliente declara `server.group.isneo` con valor predeterminado `false`; el vínculo exacto entre el visitor del criterio y esa clave se infiere por su nombre y alcance de configuración, porque el visitor no está en los artefactos disponibles. Existe un callback de proximidad general, `teleporter_approach.callback`, y el dispatcher lo usa para teletransportadores genéricos; falta conectarlo a la ruta de mazmorra y resolver la publicación multijugador. No se abrió el acceso. Ver [diagnóstico actualizado](DIAGNOSTICO.md).

La regresión 12296 confirma que el transporte genérico mantiene el rechazo del criterio especial y no mueve al personaje. La prueba durable también confirma que el ID 91 no autoriza como ID de una instancia activa. La migración 069 añade un outbox transaccional por miembro: cada traslado guarda origen, destino, run/revisión, personaje y generación junto con el movimiento SQL. Las APIs `pending_transitions` y `acknowledge_transition` filtran por sesión vigente y membresía activa; una generación reemplazada supersede sus eventos pendientes sin volver a mover al personaje, y reentrar al mismo run no crea otra transición. El dispatcher sondea por worker en idle y antes de acciones de un mapa cargado. Sin embargo, el callback de bootstrap está cerrado: `native_transports.bootstrap` todavía codifica el `ProtoDungeon` predeterminado de un mapa no mazmorra. El consumidor no abandona `WORLD`, no cambia `POSITIONS`, no envía bootstrap y no hace ACK hasta disponer del contexto autorizado del run. El ACK, cuando el callback quede habilitado, acreditará escrituras completas del servidor, no recepción visual del cliente.

La migración 070 añade políticas `ProtoDungeon` SQL inmutables y versionadas por ruta, un puntero a la versión activa y una referencia de versión en cada run; una instancia conserva la política con la que nació aunque luego se active otra versión. No hay filas de política sembradas. La evidencia del cliente acredita los campos del protobuf, pero no los valores correctos de Jalató ni la semántica de `allowed_ids`; por eso una entrada nueva falla cerrada hasta configurar una fila explícita con procedencia. El servicio nunca convierte los miembros de la party en `allowed_ids`. `is_fight_in_progress` se exige como estado dinámico del runtime y no se guarda como política. Las capturas oficiales disponibles contienen siete `13974` en mapas 1465, 1361, 1385, 1388 y 1387; todas decodifican un contexto no mazmorra (max/min 0, dificultad 2, sin IDs), sin una muestra en el destino Jalató 1086. No sirven para sembrar valores de dungeon. No se habilitó transporte ni se tocó el dispatcher.

## Límite actual de integración tras la migración 069

La inspección del dispatcher confirma que los módulos `dungeon_instances`, `dungeon_transport` y `dungeon_criteria` aún no tienen caller en `local_game_server.py`. La ruta `12296` continúa resolviendo el transporte genérico o el tutorial; `generic_transports.resolve` rechaza los contextos especiales `cyZ >= 0` y no delega en la sesión durable. La ruta `12870` clasifica/loguea la interacción y registra Zaaps/dragopavos, pero no inicia una instancia. La migración `068_dungeon_server_mode.sql` solo inserta `dungeon_server_mode={version:1,is_neo_server:false}`; no habilita entradas.

El servicio durable sí valida la party completa, líder seleccionado, generaciones activas y callbacks estrictos de acceso; crea/reutiliza `dungeon_instances`, actualiza la ubicación SQL de todos los miembros y crea un evento de outbox por miembro dentro de la misma transacción. Esto todavía no actualiza las copias `character` locales a cada worker, `POSITIONS`, ni las membresías `WORLD`; tampoco envía bootstrap del mapa a cada socket. Por tanto, la atomicidad SQL y el outbox no equivalen todavía a un traslado jugable multijugador ni a fanout.

El siguiente cambio seguro es acreditar y construir el `ProtoDungeon` desde la sesión viva (niveles, dificultad, disponibilidad, permisos y estado de pelea), luego habilitar el callback del worker: recargar el personaje autoritativo, reconciliar `WORLD`/`POSITIONS`, enviar el bootstrap completo, unirse al mundo y devolver `True` solo tras completar las escrituras; el helper marca ACK después. El líder no debe enviar paquetes por sockets de compañeros ni asumir que todos los workers comparten `character`. Para el caller de `12296`, la primera opción a reutilizar es `teleporter_approach.callback` sobre el catálogo exacto del objeto 26842 y el movimiento aprobado; la ruta de mazmorra aún no lo llama. La evaluación local de `not IsNeoServer()` existe; la semántica del visitor que la vincula a la configuración continúa siendo una inferencia, así que la prueba de ruta debe confirmar el modo normal y rechazar el alternativo antes de abrir acceso. La alternativa Neo y otros destinos deben seguir fuera de alcance.

Esta integración tampoco resolvería por sí sola la mazmorra completa: la fuente exportada aún no acredita composición de encuentros por sala, progreso/victoria, derrota/reintento ni dificultad. Mantener el acceso cerrado hasta que el fanout sea recuperable y esos contratos estén definidos.

Revalidación offline de contratos disponibles: `PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_dungeon_transport test_generic_transports test_dungeon_criteria.DungeonCriteriaTests -v` → **12/12 aprobadas**. El gate PostgreSQL aislado con migraciones 001–069 ejecutó `server.tests.test_dungeon_instances`, `server.tests.test_dungeon_transport` y `server.tests.test_dungeon_criteria` → **26/26 aprobadas**, incluidas atomicidad de outbox/party, rollback ante fallo de inserción, privacidad por sesión, ACK idempotente solo con membresía activa, reentrada sin duplicación y reemplazo de generación. El consumidor pasó `PYTHONPATH=server python3 -m unittest server.tests.test_dungeon_transition_delivery server.tests.test_dungeon_transition_dispatch -v` → **9/9 aprobadas** para combate, generación obsoleta, mapa local no coincidente, bootstrap parcial/reintento, polling y rechazo seguro mientras no exista contexto ProtoDungeon autorizado. El ACK bloquea en orden sesión/personaje → party → instancia → membresía → outbox, igual al orden de la transición. No se usó la DB runtime ni se reinició ningún servicio. Estas pruebas no acreditan una transición de mapa jugable, fanout completo ni recorrido visual. El detalle histórico está en [PRUEBAS.md](PRUEBAS.md).

## Dependencias

12, 14, 15, 25, 30, 33. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Una party comparte una instancia; sus salas/premios no se mezclan con otras ni se duplican al entrar.

## Composición y dificultades: prioridad de investigación

[Qué está y qué no está acreditado; tablas y pruebas necesarias](REVISION-RESPUESTAS.md). La arquitectura de instancias por sí sola no resuelve monstruos por sala ni multiplicadores.

- [Salas, ciclo de victoria/derrota, interfaz y grupos: cotejo concreto](SALAS-Y-CICLO-DE-INSTANCIA.md).

- [Contexto nativo, progreso personal y pruebas de retorno](INTERFAZ-Y-PROTOCOLO.md).


Revisión de composición por sala: Jalató tiene definición90 (DUNGEON_3_ROOMS), plantilla91 y mapa1086, con seis referencias de monstruos relacionadas. El mapa contiene seis teleporters y un interactivo, pero no actores de monstruo ni plan de población para1086. No se han encontrado cantidades, niveles, posiciones por sala ni reglas de progresión fieles; los seis monstruos relacionados no prueban su reparto por sala. Política nativa versionada070 y loader en fuente:32 pruebas PostgreSQL aisladas aprobadas; sin seed de valores inventados y sin instalar.

## Current manual failures — 2026-10-08

Manual testing exposed missing exterior entrance dynamic state and private-instance fight markers. The baseline entrance snapshot omitted the native dynamic field; the marker registry explicitly rejected nonpublic instances. Both corrections are prepared but have not been deployed. Encounter formations now select the reachable room center and passed all 246 configured room formations with six player slots. Existing persisted encounters are not relocated during an active fight.

Deployment is held while the requested catalog-wide aptitude audit and session-disconnection fix are completed. A live turn acknowledgment blocked for 54.7 seconds before a generic session rejection; session-renewal diagnostics and renewal isolation are being investigated. No restart was performed during this report. These changes still require visible client acceptance.

## Session and escape update — 2026-10-08

Deployed `wakemu-world:session-20261008-r22` (`d25feb0ffce1055f88603dd4a17dc9fa0014107af93754ba7d952e76cf8f2aae`) on the existing world service, layered on the concurrent combat update. Session creation and renewal now use 300 seconds. Single-observation lease diagnostics distinguish missing, replaced, expired and renewal-failed sessions and record generation fingerprints, expiry, database time, renewal age and slow operations.

Players can use `!exitdungeon` (`!salirmazmorra` remains an alias) outside combat. The command performs an owned, transactional individual return to the configured native exterior without removing other run members. English console aliases are `!help`, `!position`, `!level`, `!teleport`, and `!monster`; `!item`, `!equip`, and `!unequip` already use English. Existing authorization is preserved.

The image passed 31 focused checks, including isolated PostgreSQL exit checks; the SQL lease observation was separately verified against an isolated schema. World health returned HTTP 200. Visible client acceptance, the requested full map-object hydration audit, login without movement and conditional aptitude completion remain pending.

## Complete interactive hydration and initial replay — 2026-10-08

Deployed `wakemu-world:world-sync-20261008-r23` (`05ae7b867ee3270d2d51f324d90c8c46f298d74c61e9162bc6f21b6cc2e07d7b`) after 25 focused image tests passed. Runtime health is HTTP 200. The installed catalog supplies object-specific dynamic field 2 for every 11,987 native interactive object across 48 types and 624 maps. Map replay preserves native hidden/disabled states and applies owned dungeon restrictions last. Story NPCs remain a separate actor-catalog investigation.

Initial login now arms the full world replay and accepts native 14689 readiness before the first movement. The existing player, monster, planting, harvest and marker snapshots are replayed after loading. This corrects the initial-login pending-state regression. Session TTL300, diagnostics and public `!exitdungeon` remain active. Visual acceptance is pending.

## Full checkout deployment — 2026-10-08

The complete server Dockerfile build `wakemu-world:complete-20261008-r24` supersedes the earlier overlay images. Its 8,101 packaged source/catalog/migration/tool files matched the shared checkout before deployment, preserving concurrent spell changes. Image SHA: `1452e7c217195a66346550545bc4e14330bf3b681cb513b66feaf7ebb1c25669`. Sixty-six focused image tests passed, including isolated PostgreSQL dungeon exit and English authorization checks, common passive ownership and effect closure, map replay, session diagnostics and aptitude coverage.

All eight native common passives now have ownership metadata, native costs and their complete 35-effect closure. At level 50 the common level 10/15/25/35 passives are owned across every class; acquisition-gated common active spells are not granted. All 31 native aptitude definitions and 864 legal allocations are recognized; conditional aptitude initialization retains native effects. Session TTL remains 300 seconds, interactive replay covers 11,987 objects and initial login requires no movement to arm the full snapshot.

Use [the complete manual acceptance procedure](MANUAL-ACCEPTANCE.md), including its initial hydration/passive/escape regression section. Visible acceptance is pending; this deployment does not claim a completed full TLS dungeon run or a new permanent story NPC placement catalog.

## Concurrent persistence and retained parties — 2026-10-08

Full image `wakemu-world:complete-20261008-r25` includes a bounded four-worker checkpoint writer. Live fights are copied under the fight lock; serialization and SQL execute after releasing that lock. Pending active saves coalesce per fight, revisions remain ordered, terminal saves are retained, and logout waits at its cleanup barrier before invalidating checkpoint ownership. Independent fights can persist concurrently. Slow SQL and real-fight detachment regressions passed.

Migration 077 retains a dissolved party identity when dungeon history references it, without live members or leader; ordinary unreferenced parties are deleted. This fixes self-leave with an offline member and retains dungeon history. Read-only group snapshots no longer acquire the global publication lock across SQL. Publication ordering is still preserved to avoid respawning already claimed monsters. Thirty-two focused image tests passed; 8,104 image files matched the current checkout. This is not a throughput certification for 100 players.

The observed fight-53 ACK took 220 seconds, of which 219 seconds were inside checkpoint persistence. Internal stage logs previously lost events due to duplicate fight-ID arguments; this diagnostic path is corrected. The historical delay cannot be attributed to a specific SQL lock or serialization stage from those incomplete logs.

### Scene partition hydration and injured-login recovery — 2026-10-08

Native `cdy` registers and unregisters interactive objects with 18×18 scene partitions; `cEX` discards updates for absent objects. Native `14689` is a currency-cache request, not a scene-ready acknowledgment. An official capture sends two dynamic-object states about 1.694 seconds after a same-map walking request. The previous dispatcher instead sent two full-map batches on every movement: 42,291 bytes per Tainela movement, measured over 75 requests, with a 700 ms maximum request duration.

The movement dispatcher now queues bounded dynamic-only hydration for entering partitions in the native 3×3 neighborhood. It retries after local travel starts, includes the destination early for running, coalesces rapid redirects, clears foreign map/instance schedules and preserves run-owned door restrictions after each batch. Walks wholly within retained partitions do not reconstruct their objects. Travel cadence is a conservative scheduling estimate, not a claim of exact native animation timing. Movement logs separate cancellation, position, publication and ecology timings. Visible return-trip acceptance remains required.

Repeated disconnections after combat were recorded as `AttributeError: 'dict' object has no attribute 'packet'`: the idle session-health dictionary shadowed the health-packet module and crashed on regeneration. Renaming that local dictionary preserves native HP updates; a regression invokes the injured-character branch. A separate asynchronous checkpoint race now adopts a validated, already-committed canonical terminal receipt without writing obsolete queued state or relaxing synchronous ownership/CAS checks.

### Follow-up after failed Tainela round trip — 2026-10-08

The r26 visible trial failed. Its neighborhood-overlap optimization incorrectly treated membership in an origin neighborhood as proof of client registration. The recorded last walk `(-241,-84)` to `(-245,-88)` consequently omitted entrance 26842. That exclusion has been removed for every native object type: each accepted walk queues delayed dynamic states for the complete local neighborhood, including overlapping partitions. Overdue relevant updates survive redirects. Logs now list exactly which object IDs were delivered. No visual pass is claimed from codec or scheduler tests.

Committed combat batches and a native chat notice are now delivered before snapshot capture and checkpoint submission; ACK-gated future packets retain their native ordering. Growth SQL has its own lock: a measured 559 ms movement spent 545 ms blocked on occupation cancellation behind plant growth. A deterministic concurrent regression verifies cancellation proceeds while growth storage is blocked.

### Dynamic object retained-instance correction (2026-10-08)

Official route evidence is recorded in `../../reports/official-tainela-dynamic-state-route-20261008.md`. The installed native 13984 handler constructs an object from raw client assets; its scene registry refuses duplicate attachments. A baseline-first server batch could therefore retain an unhydrated instance and discard subsequent dynamic instances. Initial snapshots now send dynamic state directly, preserving installed assets. Regional replay additionally sends native 12344 updates to mutate retained instances in place. This applies to the common interactive-object dispatcher across maps and types.

Validation: 39 targeted tests passed (`PYTHONPATH=server:server/tests python3 -m unittest test_world_static test_world_scene_sync test_static_map_sync_dispatch`). Complete image `wakemu-world:dynamic-complete-20261008-r29` matched 8,107 source/catalog files with zero mismatches, including concurrent combat changes. Native live registry inspection was added to the capture agent. Visual acceptance of both walking directions remains pending; packet delivery and decoder acceptance do not establish visual correctness.

### Missing interactive-region movement message (2026-10-08)

The previous retained-instance fix did not fix visual walking acceptance. A live sample at the Tainela station (-217,-39) found no raw Drago registration while the previously visited dungeon entrance remained loaded. The official same-map walk sends 12318 at partition crossings before regional states; native `cgN` calls `cdE.em(x,y)` to move interactive partitions independently of terrain movement. Our walking dispatcher omitted this message. Regional hydration now sends 12318 with the authoritative position before 13984 and retained-instance 12344 updates. The fix applies to all interactive classes and maps.

Validation: 40 targeted tests passed, including the extracted actual session closure asserting the 12318→13984→12344 order when returning to the station. Full r30 image verification matched 8,108 files. Complete deployment r31 included this fix. Hector confirmed the Gobball entrance and Tainela Drago both remain interactive when walking between them in both directions and after entering and leaving the haven bag. This is visual acceptance of that route, not a claim that every map has been manually tested.

### Solo entry rejection corrected (2026-10-08)

The live 12296 request from Npers at 19:44:21 UTC was rejected with `Character is not in a player party`. Configured dungeon entry incorrectly required an existing multiplayer party. Ungrouped players now receive a singleton roster inside the same atomic entry transaction, using the existing instance, room population and transition delivery. Member advisory locks serialize concurrent solo requests and party invitations; failed authorization or initialization rolls back the singleton roster and run. Existing grouped entry is preserved.

Validation: 21 isolated PostgreSQL instance tests passed, including solo native entry, reuse, concurrent requests, rollback and grouped entry. Another 13 transport/transition delivery tests passed. Complete r33 image verification matched 8,109 source/catalog files with zero mismatches. Manual solo entry acceptance remains pending.

### Stale foreign roster blocks solo entry (2026-10-08)

The follow-up attempt was rejected because Npers retained an active membership in an old party dungeon despite authoritative outdoor instance 0 and no current party. The verified stale membership was marked returned and its pending transitions superseded. The next live attempt delivered the new instance transition; server logs place Npers in map 1086, instance 144115188075855874, combat 79. Visual acceptance remains the user's check.

The common entry transaction now reconciles foreign active memberships only when the authoritative character is outside all instances. It preserves other members and characters still inside a run. The existing 22 instance tests passed; the two added tests initially had invalid leader-membership fixtures, corrected by transferring leadership before fixture removal, then both passed. Complete recovery image r34 matched 8,115 current source/catalog files. It is built but not deployed while Hector tests combat 79; runtime unblocking is already applied.

### Solo exit cleanup and dungeon breeding exclusion (2026-10-08)

Internally created solo parties now carry explicit origin metadata (migration 081). Individual exit and final completion dissolve only an unchanged temporary singleton after its last active membership returns. Preexisting and socially expanded parties remain intact. Authorized durable exit hydration includes native OH1049 when the original party is dissolved, including delivery retries. Validation: 29 PostgreSQL lifecycle tests and 8 cleanup/hydration tests passed; another 16 hydration, transition and death tests passed.

Dungeon populations are excluded from reproduction observation, birth attempts, timers and pending birth publication regardless of room or run status. Outdoor populations retain their existing policy. All 34 isolated PostgreSQL reproduction tests passed. Previously stored offspring are not deleted by this change.

Complete image `wakemu-world:dungeon-party-breeding-complete-20261008-r36` matched 8,121 current source/catalog files without mismatches and replaced the single world container. Manual acceptance: enter alone, finish or leave, confirm the party portrait disappears; repeat with two players and confirm their group remains. Wait in a new dungeon room beyond the reproduction interval and confirm its authored monster roster does not grow.
# Latest manual acceptance — 2026-10-09

Hector confirms that the Jalató dungeon now works correctly. This acceptance
does not extend to the installed 87-configuration bundle. Tofulailler has
monsters but its door cannot be traversed; Casa de Miabuelita
(`chez-la-mere-michou`) does not allow entry. The user reports Jalató as the
only working dungeon so far. Treat access and complete progression in other
dungeons as unaccepted, regardless of configuration population or unit gates.

Investigate entry interaction, native access criteria, interior door topology,
and victory-authorized automatic progression separately, then validate the
general solution across the installed catalog. Do not infer the cause from
the user report alone or request repeated Jalató acceptance.

### General achievement entry authority — 2026-10-09

Migration 086 and the dungeon-entry callback now use a durable, strictly
validated achievement snapshot initialized explicitly for this server's local
characters. Miabuelita's native temporary quest exclusion can therefore be
evaluated without a map-specific bypass; missing authority still fails closed.
No quest or objective is automatically completed. Two routes requiring
persistent `HasState` remain unsupported. Luna verified 47 isolated migration,
authority, native-criterion and automatic party-transition tests with zero
skips. This source change requires deployment and manual acceptance.

See [implementation limits and complete dungeon acceptance steps](ACHIEVEMENT-AUTHORITY-20261009.md).
