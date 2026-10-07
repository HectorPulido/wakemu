# Inventario para un puente táctico actor-completo

Este documento describe las APIs y el estado presentes en el checkout al 2026-10-07. Es un inventario para diseñar un único puente ampliable; no cambia el runtime ni habilita simulación de reglas en `ai-service`. El servicio propone/ordena planes. La autoridad del servidor sigue certificando cada transición con el runtime nativo y conserva el commit, ACK, persistencia y protocolo del cliente.

## Qué hay hoy y qué falta

`server/wakfu_server/combat/combat_tactical_ai.py` ya calcula una petición v2 y espera del servicio la primera acción certificada. El productor `NativeProvider.roster()` solo transmite id, equipo, control, posición, HP, PA, PM, WP, armadura y dirección. `build_request()` conserva terrain y hash completos en world, pero manda al servicio el footprint geométrico de las acciones candidatas certificadas. No serializa los snapshots nativos completos de `Fight`/`Actor`, la autoridad de cada PC, el contexto de efectos retenidos, ni el estado de las callbacks.

El validador v2 del servicio (`server/ai-service/wakfu_ai/planning/tactical.py::_actors`) hace `dict(entry)` y comprueba los campos esenciales sin rechazar los campos adicionales. Por tanto, el transporte puede llevar extensiones completas versionadas por actor sin una allowlist de campos nativos. El scorer actual solo interpreta sus métricas declaradas y no ejecuta efectos. Las extensiones son datos para decisiones/features, no una fuente para inventar costes, targeting o resultados.

## Estado que debe formar la fuente y la revisión

`combat_geometry_snapshot.source_snapshot(fight)` ya es un buen punto de partida sin lista blanca: copia cada `Fight.__dict__` salvo `actors`, y luego copia todos los `actor.__dict__`. `fight_checkpoint_store._plain()` serializa recursivamente diccionarios, listas/tuplas, sets/frozensets y `StateLedger` completo (`actor_id` y `entries` vía `dataclasses.asdict`). Rechaza otros objetos en lugar de omitirlos silenciosamente. `source_snapshot()` usa ese serializador. Los sets se normalizan y los atributos dinámicos nuevos de Fight o Actor se incluyen automáticamente.

Campos iniciales de `Actor` visibles en `combat_state.py`: `id`, `team`, `position`, `hp`, `ap`, `mp`, `initiative`, `effective_level`, `owner_id`, `controlled`, `turn_count`, `max_hp`, `max_ap`, `max_mp`, `state_ledger`, `effect_stats`, `effect_maxima`, `effect_minima`, `effect_frozen`, `spell_ap_cost_modifiers`, `physical_radius`, `native_obstacle_id`, `native_los_height`. Runtime añade más atributos dinámicos, por ejemplo `direction`, `effect_percentages`, `effect_base_maxima`, `effect_base_minima`, `native_hud_breed` y atributos de efectos/contextos. La serialización debe incluirlos por reflexión y reservar un `nativeExtensions`/`contextVersion` explícito solo si el envoltorio necesita distinguir el namespace; no replicar aquí esa lista como allowlist cerrada.

`Fight.__dict__` contiene al menos: `id`, `walkable`, `placement`, `edges`, `phase`, `native_spell_usage`, `native_start_event_delivered`, `native_turn_event_deliveries`, `native_table_turn`, `winner`, `native_los_ignored_affiliations`, `native_walk_ignored_affiliations`, `native_timeline_policy`, `native_base_turn_order`, `order`, `turn_index`, `turn_id`, `ready_owners`, `events`, `_resolution_depth`, `sequence`, `native_effect_uid_next`, `native_owned_area_effects`, `native_owned_group_effects`, `native_owned_state_containers`, `native_retained_records`, `native_retained_order`, `native_retained_tracking`, `owned_stat_effects`, `native_retired_area_managers`, `native_active_spell_id`, `native_spell_grants`, `state_wire_payloads`, además de cualquier campo dinámico. `_plain()` retiene esos campos, no identifica si una ausencia en una instancia significa “vacío” o “aún no inicializado”; los valores `None`, `{}` y `frozenset()` deben conservarse literalmente.

`RuntimeMessages` mantiene estado separado de Fight: `fight`, `duration`, `action_id`, `native_action_id`, `last_native_delivery`, `awaiting_ack`, `pending`, `round`, `clock`, `turn_deadline`, `deadline_turn`, `turn_start_provider`, `area_started_turn`, `turn_end_provider`, `stats_serializer`. Callbacks, `clock` y serializadores son objetos Python no transportables y no forman parte del checkpoint. Para el fingerprint de petición sí deben estar representados mediante el estado serializable y una identidad/configuración de callbacks; no se deben ejecutar callbacks capturados durante un `deepcopy` si cierran sobre el runtime vivo.

La clave antistale debe cubrir, como mínimo:

1. `source_snapshot(fight)` completo, incluida la colección de atributos futuros y los registros/counters de `native_spell_usage`, grants, estados, invocaciones y retained effects.
2. Estado serializable de `RuntimeMessages`: `action_id`, `native_action_id`, `awaiting_ack`, hash de `pending` (o el pending completo de forma canónica), `round`, `area_started_turn`, `duration`, `turn_deadline`/`deadline_turn` cuando definan aceptación de acción.
3. Identidad/configuración de la fuente de autoridad por PC/NPC/summon, builds/decks activos, mapa/topología/LOS, perfiles y flags de callback; `catalogVersion` para reglas/archivos y una revisión propia para esos datos.
4. `requestId`, `fightInstanceId`, `turnId` y una revisión monotónica más un hash de fuente. Hoy el bridge pone `stateRevision=fight.sequence` y `_source_key()` además cifra fight, contadores runtime, pending/ACK, focus y `provider.context_key`; son guardas útiles, pero `fight.sequence` solo no detecta modificaciones externas/DB de autoridad y el contexto debe incluir a *todos* los actores.

El envelope debe tener un `sourceRevision`/`stateRevision` reproducible y validar idénticamente la respuesta antes de certificar/commit. La respuesta actualmente repite `requestId`, `stateKey`, `fightInstanceId`, `turnId`, `stateRevision`, `catalogVersion`, `policyVersion`; el servidor debe volver a comparar el fingerprint completo, no confiar en el plan ni en el cliente.

## Autoridad completa para todos los participantes

### Personajes controlados

`Store.character(account_id, character_id, db=None)` (storage/store.py) es account-scoped y carga la fila de personaje, build catalogs (`sheet`, `equipment`, `deck`, `aptitudes` como hex), `active_build_index`, `build_selection_revision`, `effective_level`, progresión, inventario y otros stores de personaje. Para cada actor controlado de un combate no basta con la sesión conectada. Identidad/propietario persistidos están en `combat_fight_participants(character_id, account_id, team)` (`migrations/004_combat_ecosystem.sql`; consultado también por `fight_store.py` y checkpoints). El armado completo debe leer participantes del fight y, dentro de la misma transacción/snapshot DB, recuperar cada `(account_id, character_id)` con `STORE.character(account_id, character_id, db)`; validar que cada uno corresponde exactamente a un actor `controlled=True`, `owner_id=account_id`, y que no hay actor controlado sin autoridad o autoridad extra.

El deck de cast ordinario es el blob del build seleccionado: `character["builds"][character["active_build_index"]]["deck"]` decodificado de hex a bytes; usar el build seleccionado real, no el build 0 por defecto. `validate_deck(blob, breed, level)` verifica slot count, level cap, breed/unlock/slots. `OrdinaryActorAuthority` exige `decks` y `excluded_decks` indexados exactamente por las claves de `characters`; el runtime actual fija los decks excluidos vacíos. Si una función nativa futura introduce exclusiones/ownership diferentes, se debe añadir esa autoridad explícitamente y versionarla, no inferirla del roster.

`characters` también es fuente de datos de efectos nativos que consultan inventario, nivel, breed, items equipados y builds. `OrdinaryActorAuthority.item_quantity()` usa `inventory_items`. No mandar solo id/breed/deck si se pretende ejecutar efectos que leen otras propiedades de la ficha.

### NPCs

El descriptor autoritativo que hoy consume combate llega por `TEST_MONSTERS_BY_ID`/grupo de combate; se requiere descriptor completo por cada actor NPC (id, `ref`, `level`, `map_id` y todos los campos usados por la authority/rules provider). `combat_npc_spell.owned_spells(fight, monsters)` deriva el catálogo del `ref` y nivel mediante `native_abilities()`, y mezcla grants temporales del `Fight`. `NativeProvider` existente recibe un único `character`, `monsters` y deck porque toma el contexto de la sesión, pero esa forma no sirve para varias fichas o enemigos controlados.

### Invocaciones, compañeros y actores envueltos

Una invocación no es un NPC ordinario. `Fight.native_summon_registrations` conserva `SummonRegistration` serializado, incluida `NativeActorAuthority`, origen/controlador/raíz, propiedades y autoridad de timeline; Actor conserva los snapshots nativos. `RegisteredSummonAuthority(ordinary)` retira los summon IDs de la vista ordinaria y resuelve sus metadatos de la registration. Exige que el roster coincida y rechaza inventario de invocación no provisto, callbacks de propiedad summon y ciertas combinaciones timeline/property no auditadas. Si aparece un actor companion/carried/wrapped sin su registro nativo, no puede certificar la acción completa: no degradar a un Actor normal por signo del ID.

### API exacta que necesita una factoría general

La factoría actual `server_runtime(character, monsters, deck_blob, *, action_id, critical, rng=None, compiled=None)` construye mapas con **un solo** `character` y deck. Una factoría por encuentro debe construir el mismo runtime sin cambiar su semántica: `OrdinaryActorAuthority(characters=characters_by_id, monsters=npc_by_id, decks=active_spell_sets_by_pc, excluded_decks=excluded_by_pc, catalog=...)`, envolverlo con `RegisteredSummonAuthority(ordinary)`, crear `ordinary_cast_authority(actors=authority, timing=NativeEffectTimingProvider(states_catalog()), rng=transaction_rng, critical=explicit_bool)`, luego `NativeServerRuntimeAdapter(actor_authority=authority, cast=cast, viewer_id=explicit_viewer)` y `NativeEffectRuntimeFactory(...)` con los mismos inputs/compiled catalogs de `server_runtime`. `viewer_id` es contexto explícito; para projection no debe cambiar la autoridad de los actores. Se debe validar igualdad exacta entre actor roster y unión de las fuentes ordinarias + summons registradas.

Esto es una especificación de wiring a partir de APIs existentes, no una API pública ya presente. No pasar un character de un rival como impersonación ni usar los datos del cliente/actor seleccionado para representar otros PCs.

## Catálogos nativos: datos/versionado

El runtime resuelve catálogos en `DATA_ROOT` con loaders y caches (entre paréntesis, consumidores directos relevantes):

- Efectos y estados: `spell-effect-trees.json` (`characters/spell_audit.catalog`), `combat-state-definitions.json.gz` (`states_catalog`), `spell-costs.json` (`costs_catalog`, `combat_spells`/`combat_event_costs`), `effect-characteristic-registry.json` (`characteristic_registry`, handlers/expiration), `characteristic-condition-aliases.json`, `conditional-spell-costs.json`.
- Cast común: `combat-spell-rules.json`; `native-spell-casting.json.gz`; `granted-spell-effect-trees.json.gz` (solo si `WAKFU_NATIVE_GRANTED_CAST=1`); `native-spell-references.json`; `native-spell-limits.json`; `native-direct-target-policies.json.gz`; `native-self-cast-policies.json`; `native-critical-availability.json`; `native-spell-elements.json`; `native-target-ordering.json`; `native-pt-preflight.json.gz`; `state-decurse-rules.json`.
- Efectos nativos/retención: `native-area-effect-trees.json.gz`, `native-effect-areas.json`, `native-point-areas.json`, `native-retained-effect-metadata.json`, `native-zone-trigger-policies.json.gz`, `native-runner-registration-owners.json`, `native-fight-properties.json`, `native-world-properties.json`, `native-actor-properties.json`, `native-actor-characteristics.json.gz`, `native-runner-corpse-policy.json`, catálogos de weapon/melee/class initialization según acción.
- NPC y acciones auxiliares: `native-npc-spell-effect-trees.json`, `native-spell-casting.json.gz`, `native-spell-limits.json`, `unarmed-combat.json`, `weapon-combat-rules.json`, `weapon-combat-effects.json.gz`, `breed-innate-definitions.json`, `iop*-combat.json`, `xelor754-combat.json`.
- Geometría/LOS: `native-los-ray-program.json`, `native-los-topology/<map_id>.json.gz`, `combat-los/<map_id>.json.gz`, `amakna-combat-los.json`, `combat-maps/*`, `*-test-arena.json`, `amakna-test-arena.json`, `forced-transitions/<map_id>.json.gz`. Cada ataque certificado debe usar los datos nativos de su mapa, footprint, obstáculo, altura y obstáculos vivos; un edge cardinal no demuestra LOS.
- Inventario/actor source adicionales: `spells.json`, `native-actor-characteristics.json.gz`, builds/equipment/aptitude/characteristic catalogs referenciados por `equipment_stats`, `combat_actor_snapshot`, `combat_initialization_policy`.

`combat_tactical_ai.catalog_version()` actualmente hashea un subconjunto de archivos combat (entre ellos native-NPC trees, spell-casting/limits, class/native states/effects, area trees, registry y `content-manifest.json`) y todos los `.py` de su package. No representa por sí mismo las topologías de todos los mapas, datos del store, entorno de flags, ni las fuentes por actor. Un bridge definitivo debe versionar/hasear las entradas realmente usadas por ese encounter, dejando explícito el `mapId` y la política de callbacks. Evitar serializar grandes catálogos estáticos en cada request si un digest de contenido/verificación y capabilities derivadas pueden referirlos sin pérdida.

## Cast nativo: APIs y límites

### PC spell cast ordinario

`prepare_server_spell(body, character, monsters, fight, owner_id, deck_blob, *, action_id, line_of_sight, critical, rng=None)` en `combat_server_spell.py` devuelve un `SpellTransaction` (privado) vía `prepare_spell_transaction`. `body` tiene 26 bytes, `struct.pack(">qqiih", actor_id, spell_uid, x, y, z)`. UID ordinario `(actor_id << 32) | spell_id`; grant temporal usa UID nativo del registro.

`prepare_spell_transaction(...)` recibe explícitamente `runtime_factory`, `wp_current`, `conditional_context` opcional, `line_of_sight`, `critical` y `action_id`. Clona el Fight, valida con `prepare_spell_cast()` (actor actual/controlado, owner, ID, deck/grant, recursos, rango, target, LOS), descuenta costes en copia, ejecuta todas las raíces nativas con dispatcher privado y rechaza el spell completo si una rama obligatoria no tiene handler. Retorna `SpellTransaction(fight, plan, wp_remaining, outcomes, packets, events, source_state, action_id)`. No muta Fight origen ni envía. `commit_spell_transaction(runtime, transaction, stats_serializer=...)` revalida `source_state`, acción/paquetes y ACK, serializa antes de adoptar y comete; **no** se invoca para forecast.

`server_runtime()` es el constructor concreto de factory/adapter del cast común y hoy limita authority a un solo PC. `prepare_npc_spell(fight, action, character, monsters, deck_blob, *, action_id, rng=None)` separa NPC: verifica `owned_spells`, native casting definition/usage/target/LOS y retorna `SpellTransaction`; no impersona PC. Los helpers pueden certificar cast de otro PC solo al recibir el registro y deck propios de ese actor, usando una factory general por encuentro.

La rama critical debe ser explícita. `critical=False` da un preview normal, no el valor esperado; si el productor no proyecta ambas ramas o la probabilidad nativa, anotar dependencia `critical_branch_not_sampled`/uncertainty. El RNG debe ser una copia por hipótesis para que el preview no consuma aleatoriedad de ejecución; el wrapper `rollback_external_rng` guarda/restaura RNG externo al fallar.

Usage/decks no son un catálogo de spell allowlist fijo: la propiedad/deck autoritativo decide spells. `native_spell_usage` registra conteos por caster y spell, turno, objetivo e interval; `validate_usage()` consulta límites + footprint completo y `consume_usage()` actualiza solo en el preview que ejecutó el cast. `native_spell_grants` trae grants efímeros de `Fight`. Nunca reconstruir o resetear esos maps entre estados.

## Movimiento, orientación, LOS y geometría

`Fight.move(owner_id, actor_id, path)` (PC) y `Fight.server_move(actor_id, path)` (NPC) validan owner/current/control, celdas walkable, ocupación, pasos cardinales, edges nativos y MP y mutan el Fight receptor; primero deben correrse sobre una copia. Ambas comparten `_move_actor`; el camino contiene destinos XYZ sin origen y cada transición usa un edge dirigido real. Dirección se actualiza por la última transición con `combat_cast_facing.DIRECTIONS` y se conserva en snapshots/serializadores.

`combat_movement_runtime.apply_client(runtime, owner_id, body, stats_serializer, direction=..., area_provider=...)` prepara el packet 13624/refresh de stats, ejecuta el movimiento, y si hay areas usa `_with_areas()` que clona/adopta el RuntimeMessages suministrado. Sobre runtime original es commit; para preview se debe pasar runtime nuevo/copied con proveedores ligados al snapshot privado. `apply_ai()` es legacy NPC path que llama `combat_ai.plan`; el bridge táctico nativo actual implementa su preview sobre copia y no es una autoridad genérica de PC.

`authoritative_visible(map_id, source, destination, fight, blocking_footprints=...)` requiere el footprint explícito de todo actor vivo; con `native-los-topology` además usa `native_los_height` origen/destino; sin cobertura suficiente en archivos ray falla con `ValueError`, nunca presume claridad. Obstáculo/afiliación son `native_obstacle_id`, `native_los_ignored_affiliations`, huellas `combat_obstacle_condition.footprint` y altura; no equiparar team, walkability y LOS.

Movimiento puede activar reacciones de áreas. `prepare_area_movement(character, monsters, fight, deck_blob, actor_id, action_id, path, origin, rng=None)` solo trabaja si `WAKFU_NATIVE_AREA_CALLBACKS=1`, exige final actor pos=destino y retorna copy/packets con callback por cada paso. `prepare_area_event(... event="movement"|"turn_start")` también devuelve preview/callbacks, bajo flag. Estas firmas actuales usan un `character`/deck y deben consumir authority map en la versión general.

## Inicio y fin de turno, ACK y callbacks

- `prepare_server_turn_end(character, monsters, fight, deck_blob, *, actor_id, action_id, rng=None)` clona Fight, ejecuta `deliver_turn_end` en `effect_resolution` y retorna `(candidate, packets)`.
- `prepare_server_turn_start(character, monsters, fight, deck_blob, *, actor_id, action_id, rng=None, native_events=True, area_callbacks=False)` exige que Fight ya esté en turno activo del actor, clona y entrega `turn_started` y callbacks nativos opcionales; retorna `(candidate, packets)`.
- `prepare_timed_expiration(candidate, actor_id, round_number, phase, action_id, round_cleanup=False)` devuelve una segunda copia y packets cuando toca expirar reloj. Runtime hace round cleanup antes de start expiry; al final ejecuta end callback, luego expiración end.
- `RuntimeMessages.end_turn()` (jugador) y `end_server_turn()` (NPC) aplican `_end_owned`, advance FSM, `turn_started()` del siguiente actor, dejan la presentación pendiente y ponen `awaiting_ack` al `turn_id` anterior. `acknowledge_turn(body)` solo consume un int32 exacto coincidente y libera `pending`. `13510` es ACK de turno existente: una proyección privada puede transitar la barrera en su copia, pero nunca genera ACK por acción ni modifica el socket real.
- Para evaluar una alternativa que abarca fin/start, fork de RuntimeMessages+Fight y providers puros reconstruidos desde authority maps; callbacks/clock serializadores no se copian como datos. No llamar a las callbacks capturadas del runtime vivo. Cada movimiento/cast/end debe volver a comprobar deadline y fingerprint fuente.

## Factory por encuentro y cobertura actor-completa

Un registro exacto por encuentro debe separar `actorId` y clase de autoridad, sin derivarlos solo del signo del ID:

- PC: actor live snapshot + `character` cargado con el propietario real + selected build y bytes deck + inventario, breed/level/map, efectos base; su actor se controla por `owner_id` real.
- NPC: actor snapshot + descriptor monster `id/ref/level/map_id` completo + capacidades nativas por catálogo.
- summon: actor snapshot completo + `native_summon_registrations[actor_id]` completa; controller/master/root/propiedades/orden nativos.
- Otros actores: tipo/authority registrada explícita (companions/carried/remote state managers, etc.). `OrdinaryActorAuthority` rechaza extras sin registro; falta de una authority no es desconocido-cero ni razón para omitir esa entidad.

`OrdinaryActorAuthority` solo acepta roster exactamente igual a sus `characters | monsters`, y PC/decks/empty-exclusions con claves exactamente PC IDs. `RegisteredSummonAuthority` amplía esa fuente vía registros persistidos en el Fight. Al crear un “runtime factory completo”, recibir todos esos mapas más compiled catalogs, status/area providers, transaction-owned RNG, initialization/LOS/geometry context y IDs de acción; armar context fresco para cada preview state, no compartir handler/outbox/adapter mutables entre estados.

Esta autoridad completa es precondición del cast: una sesión/store que solo cargue personaje local no puede producir casts legales de otros jugadores. La tabla de `combat_fight_participants` da el enlace accountId/personaje del fight; la seguridad exige query/lease/ownership validada por servidor antes de llamar `Store.character`. No confiar en owner/deck listados por `ai-service`.

## Transporte íntegro, no fragmentado

El requisito operativo para el puente final es transportar el grafo **completo**, sin proyección de campos, actores, historia, efectos, catálogos o archivos y sin límites de tamaño total. No simplificar porque el scorer de hoy ignore un dato: el contexto íntegro sirve para decidir ahora y para extender características futuras sin cambiar de contrato ni perder evidencia. Errores de serialización/tipo deben fallar explícitamente; una propiedad no serializable no se omite.

En `server/ai-service/wakfu_ai/context/native_context.py`, `encode(value)` recorre todos los atributos de instancia `__dict__`, dataclass fields y `__slots__` de toda la MRO. Representa referencias/alias/ciclos por nodos, bytes con base64, fechas/Decimal tipados, clases de contenedor y callables como descriptores sin ejecutarlos. `NativeOracle.complete_state()` aplica esto al RuntimeMessages completo, authority maps, flags y source. Deben preservarse igualmente los unknown/dynamic fields añadidos en versiones futuras; no convertir el grafo a una allowlist JSON.

`CompleteContextExporter` descubre recursivamente todos los archivos de cada raíz y suma archivos engine indicados. El manifiesto content-addressed registra path, SHA-256 y byte size de cada archivo; el protocolo v3 entrega objetos grandes por bloques verificados, con ACK offsets/reintentos, y solo sella el manifiesto cuando todos los blobs completos tienen hash/size correcto. El inventario de protocolos actual puede tener cientos de MB y miles de archivos: se transmite completo. El cache solo evita retransmitir un objeto ya presente y verificado por hash y size; no reduce la fuente, sus entradas ni los bytes que definen el objeto.

La transacción completa debe incluir RuntimeMessages/Fight/Actors reflexivos y con identidad de alias preservada; fuente de autoridad completa de **todos** PCs, NPCs, summons y actores registrados; todos los flags, perfiles, callbacks como descriptores/configuración, engines sources y metadata; todo el directorio `DATA_ROOT` (`server/protocol`) y fuentes/catálogos/metadata del motor. Los roots/files del exportador deben declararse exhaustivamente; si no se puede recorrer una raíz o descubrir un archivo, el export se rechaza.

Mantener v2 como la envoltura de decisión si conviene, pero asociarla a referencias verificadas del contexto completo: `fightInstanceId`, `turnId`, `stateRevision`, `catalogVersion`, `policyVersion`, root/state/transition identities y el hash del grafo completo. `source_snapshot()`/`_plain()` son un precedente, pero `_plain` rechaza objetos no soportados y no conserva todos los aliases; el formato de graph evita ese aplanado y preserva futuros slots. No reconstruir el graph en el servicio para ejecutar código. El servicio valida identidad/schema/aliases y devuelve referencias de acción; el oracle world confirma el fingerprint y certifica la acción de nuevo sobre copia fresca.

### Gates de integridad

| Gate | Aceptación requerida | Fallo esperado |
| --- | --- | --- |
| Grafo nativo | dynamic attrs, inherited slots, dataclasses, integer keys, referencias alias/ciclos, bytes/date/Decimal/sets conservan tipos y referencias tras JSON round-trip | tipo/field/ciclo sin codec produce error explícito; nunca se omite |
| Fuente viva | todos los campos de Fight, cada Actor, RuntimeMessages y future attrs están en `complete_state`; identidad de Fight/Actor preservada cuando se referencia varias veces | falta/autoridad/rama no serializable aborta snapshot |
| Roster/ownership | un registro exacto para cada actor PC/NPC/summon, decks/builds y ownership DB de cada PC, y registrations native completas | mapa incompleto o clase ambigua rechazada antes de decidir |
| Native oracle | cast PC usa su propio actor/deck/owner/level/usage; cast NPC diferencial coincide con API nativa existente; movimiento usa edges dirigidos, ocupación, MP, dirección y callbacks; end/start/timer en fork con ACK13510 solo privado | cualquier preview distinto/stale/unsupported no publica ni consume estado live |
| Archivos | manifiesto contiene recursivamente cada fichero en todos los roots, incluido hidden/futuro/extensión desconocida, y metadata fuente declarada; SHA/size verificados | fichero perdido/cambiado/symlink no enumerado/hashing erróneo impide sellar contexto |
| Transfer | payload de grafo y blobs arbitrariamente grandes se dividen en bloques; offsets, retries, contenido repetido, checksum y reanudación probados; manifiesto requiere todos los blobs | incomplete/corrupt/conflicting upload no queda verified ni usable |
| Cache | solo hash+size completo se reutiliza; corrupción invalida el hit y obliga recibir bytes completos | no se acepta status sin verificación del blob íntegro |
| Respuesta | IDs/revisión/hash completos coinciden; acción pertenece a la respuesta y vuelve a pasar preview nativo sobre fuente actual | timeout, response vieja o acción ilegal toma fallback seguro explícito, sin mutar fight/counters |

El límite de frames se aplica a cada bloque HTTP, no al grafo, contexto o catálogo total. Los números de schema que ya limitan candidatos/rosters no justifican truncar el source; representan límites semánticos del planner y deben reportar error en lugar de elidir contexto. `threat.validate_forecasts()` exige roster completo por paso con mode/dependencies y cobertura consistente. Nunca pedir al servicio que ejecute código, resuelva spells o finja autoridad nativa: el server manda todos los datos y mantiene el único oráculo de certificación/commit.

## Fuera del alcance de un DTO

`ai-service` no tiene callable autoridad del servidor, resolvers, base de datos, RNG del encuentro, topología, callbacks ni packets. No importa módulos del juego y no recibe conexiones para consultar Store. Enviar “todos los datos” no hace al planner simulador seguro. La arquitectura de una pieza debe tener un único contrato completo de request/response, schemas extensibles, un builder world actor-completo y un native certifier/commit en world. Evitar checkpoints nuevos, campos o servicios del cliente y duplicar reglas en Python del servicio.
