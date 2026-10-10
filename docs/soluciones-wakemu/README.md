> 2026-10-10: parallel cross-system optimization audit completed. Ranked measured findings, source risks, language cleanup and non-green AI regression results: [audit](../reports/health/OPTIMIZATION-AUDIT-20261010.md). No gameplay optimization or deployment performed for this audit.

<!-- 2026-10-10 11:52: full world r73 deployed; native timeline-round correction, NPC root catalog, position contention retry. Automated verification passed as recorded in MORNING-LATENCY-20261010.md. Manual acceptance pending; cold-surface latency and duplicate interactive publication remain open. -->
<!-- LIVE ACCEPTANCE FAILED for r72 wire-counter assumption: new summon/recovery captures contradict blanket SY+1; native global-round caller under verification. Death ACK now advances; Wonejo did receive AI turn but native casting metadata resolution failed. Do not mark performance or summon end-turn accepted. -->
<!-- Osamodas follow-up: complete r72 source verified in running heroes-owned-stats-20261010 image (692 files, SHA d66f191...). Native controlled-summon end-turn counter and defeated-current ACK sequencing corrected; 14 + 66 focused tests pass. Profiler liveness health deployed, 17 tests pass; historical coverage gaps explicit. Manual acceptance and client duplicate-publication issues remain open. See docs/reports/health/MORNING-LATENCY-20261010.md. -->
<!-- Morning incidents 2026-10-10: r71 deployed complete and verified (692 server files). Duel static terrain preparation moved outside participant SQL locks; !mob reuses validated immutable topology with fresh occupancy. 67 geometry/lifecycle + 4 PostgreSQL + 23 console/channel tests passed. Client UI delay and duplicate interactive publication remain open; unsafe update-only retry was not deployed. See docs/reports/health/MORNING-LATENCY-20261010.md for exact acceptance and limits. -->
<!-- Cast latency follow-up: complete r70 (692 server files) adds bounded private criterion AST caching and fresh linear retained-container liveness scans. New regressions 6/6 and retained core 33/33 pass; uncached authority baseline reproduces existing fixture failures; concurrent dungeon tests 103/103 pass. See docs/reports/health/CAST-LATENCY-20261010.md. Live latency improvement still requires acceptance. -->
<!-- AI service audit 2026-10-10: see docs/reports/health/AI-SERVICE-AUDIT-20261010.md. 130 focused AI/context/monitor tests passed; 47 targeted concurrent server tests validated after fixture reruns. Complete r69 image verified against 690 current server files; r69 deployed with deadline accounting, byte metadata transport and bounded GC telemetry; world health OK and continuous profiler active. Live acceptance remains pending. -->
<!-- Performance follow-up 2026-10-10 02:07 local: r68 fixes confirmed lazy AI dictionary traversal and repeated retained-effect identity parsing. 95 focused AI + 25 combat tests pass; complete 688-file image verified. r68 deployed to the single world container; health OK and continuous profiler resumed with one-hour retention. Live acceptance pending; do not claim all latency eliminated. -->
> 2026-10-10 r67 follow-up (deployed and verified): the 01:20 incident recorded 45.81 seconds in AI file inventory ordering, with Path comparison dominating two captures. Inventory now sorts precomputed relative component keys, preserving complete manifest ordering and fresh-file validation. The running shared `titles-ownership-fix-20261010` image matches all 687 r67 source/migration hashes; mounted AI ordering is verified, health passes, and the continuous profiler is active. 39 AI inventory, 45 shared-effect and 30 duel/placement tests passed. Live latency acceptance remains pending. PvP now automatically starts duelists on opposite native interior sides; durable exterior return coordinates stay unchanged. Placement freeze retains spread and border avoidance. Details: [inventory incident](../reports/health/LIVE-SLOW-COMBAT-20261010-0620.md), [ordering validation](../reports/health/AI-INVENTORY-PATH-SORT-20261010.md), [duel starts](../reports/health/DUEL-ARENA-AND-TEAM-SPREAD-20261010.md).

> 2026-10-10 r66 follow-up: friendly duel settlement distinguishes validated controlled summons from the two consented character owners, fixing beacon-related surrender rejection. Duel native arenas request a separate 30×30 minimum (max 2,500); team placement spreads over opposing reachable regions and PvE NPC initial formation uses the distant side. The 00:42 lag investigation identified one 32.24-second CPU source fingerprint. Streaming hashing preserves the exact digest and now enforces the existing AI deadline, rejecting expired decisions with end-turn fallback. The potentially expensive lazy catalog traversal remains an investigation, not a claimed full fix. Complete current image is deployed as `heroes-combat-fix-20261010`, with all 687 running source/migration hashes matching validated r66; health and game ports pass. AI source verified and continuous profiler reattached. Manual acceptance pending. Validation and live deployment status: [duel exit](../reports/health/FRIENDLY-DUEL-SUMMON-EXIT-20261010.md), [placement](../reports/health/DUEL-ARENA-AND-TEAM-SPREAD-20261010.md), [AI deadline](../reports/health/AI-SOURCE-GUARD-DEADLINE-20261010.md).

> 2026-10-09 r65 ecology coordination: reproduction and maturation now release global group/harvest fences between observations, individual attempts and per-group publications. Each operation refreshes player presence and harvest exclusions; publication revalidates only its selected group and preserves remove/spawn/ack order. Validated policy is loaded once per cycle outside fences. New profiler labels separate guard wait from held time. 247 combined ecology/combat/spectator/duel tests passed with no skips; additional current-manifest coverage passed 378 tests with one skip. Complete r65 image deployed, healthy, with all 680 source/migration hashes verified; continuous profiler resumed. Whole-cycle serialization is removed; individual SQL operations still hold their required fences, so this does not certify all latency resolved. See [implementation, validation and limits](../reports/health/REPRODUCTION-OPERATION-FENCES-20261010.md).

> 2026-10-09 22:57 incident, r64 correction: profiler preserved both receive threads waiting roughly 20 seconds in idle harvest availability maintenance while reproduction held the harvest fence. Socket maintenance now polls without waiting and retains due cooldowns for the next successful drain. Friendly duel challenges were independently trapped by expired invitations whose retry retirement restarted quarantine and rolled back; expiry now uses its original deadline, preserving finite stale-reply fencing. 258 combined combat/spectator/duel/harvest tests passed with no skips, including isolated PostgreSQL regressions. Deployment and live acceptance are tracked in [idle contention](../reports/health/R63-IDLE-HARVEST-CONTENTION-20261010.md) and [duel retry](../reports/health/DUEL-EXPIRY-RETRY-20261010.md). Global ecology lock scope remains a separate performance follow-up.

> 2026-10-09 r63 follow-up: surrender sword cleanup remains accepted. Spectator placement movement now forwards 13652, native action flush 13420 is preserved, and late snapshots replay recorded summon creation descriptors before current effects/stats. Focused validation: 100 passed, 15 isolated-database cases skipped; 43 AI inventory/cache tests passed. AI inventory avoids duplicate physical validations within each fresh scan. Placement/active marker publication no longer waits for the global ecology group fence; terminal publication remains fenced. Full current checkout built and running source verified against 674 hashes. Live spectator and latency acceptance remain pending; global ecology lock contention and repeated actor metadata work remain documented investigations. See [spectator follow-up](../reports/health/SPECTATOR-ENTITY-PLACEMENT-SYNC-20261010.md), [marker contention](../reports/health/R62-LIVE-COMBAT-MARKER-CONTENTION-20261010.md), and [AI scan](../reports/health/AI-INVENTORY-SCAN-20261009.md).

> r62 manual follow-up: surrender sword cleanup accepted by Hector. Combat action streaming for spectators now works, but placement presentation differs between clients and existing summons remain invisible on late entry (fights 126/127). Performance remains open: profiler records 17.6 s Ready, 11.4 s start, 11.8 s AI peaks; ongoing stack investigation. Do not treat spectator or performance issues as closed.

> 2026-10-09 r62 deployed: committed surrender removes external swords without waiting for reward settlement; individual withdrawal keeps the active encounter marker. Direct constructor states establish their own retained-effect container scope, fixing spectator snapshot rejection after summons. Existing spectators keep committed events if a refresh fails; stale snapshots cannot admit new observers. Full current image verified against 657 source hashes, health/game ports available. Focused validation recorded in [spectator investigation](../reports/health/SPECTATOR-CONTAINER-SYNC-20261010.md) and [surrender investigation](../reports/health/SURRENDER-MARKER-CLEANUP-20261009.md); fresh manual acceptance pending.

> 2026-10-09 r61: roomier arenas vary minimum dimensions from 5–7 per axis, preserve feasible original enemy separation, and prefer interior placement with maneuvering margin. No rendered border overlaps actor/placement cells; narrow native terrain has a best-effort fallback. 65 focused tests passed. See [release and acceptance steps](../reports/health/ROOMIER-ARENAS-R61-20261009.md). Live acceptance pending; interactive registration remains open.

> 2026-10-09 r60: adaptive ordinary arenas now aim for 25 native cells and expand for roster/return-path capacity, capped at 2,500. Published geometry validation and adjacency are reused per catalog revision. Focused validation passed; full-suite and live latency acceptance remain pending. See [release and exact acceptance steps](../reports/health/ADAPTIVE-ARENA-RELEASE-R60-20261009.md). Duplicate interactive registration after combat remains open; unsafe update-only retry prototype was withdrawn.

## Consolidated review status — current user feedback

Read this snapshot before the historical implementation table below. Latest verified deployment is a single `wakemu-world:titles-ownership-fix-20261010`, source-equivalent to the r67 validation snapshot.
Source and deployed code are compared per investigation, not assumed globally
identical. Focused checks do not constitute a passing full suite. Shared combat
and performance follow-up belong to the other agent.

| Original issue | Current status | Remaining scope |
| --- | --- | --- |
| 0 Performance | Improved, open | Current complete deployment includes r72 performance changes. Automated focused checks pass; residual live latency, client UI delay and duplicate interactive publication remain under the other agent. |
| 1 Seeds | Accepted | Immediate consumption/refresh. |
| 2 Monster maturation | Accepted | Balance adjustments are separate. |
| 3 Reproduction | Implemented, partial acceptance | Natural timing and recovery of offspring after restart. |
| 4 Planting probability | Partial | Wider terrain/climate/bonus coverage and effective configuration. |
| 5 Resource permissions | Accepted | Preserve public flora harvesting. |
| 6 Flora stages | Partial | Normal Cardo accepted; Fresno/general species coverage remains. |
| 7 Wakfu/Stasis | Accepted | Preserve confirmed ecology progression. |
| 8 Profession XP | Accepted | Gathering, planting and tested crafting. |
| 9 Combat XP | Accepted | Preserve transactional rewards. |
| 10 Drops/kamas | Core accepted, partial catalog coverage | Complex criteria and roll limits remain. |
| 11 Exchange | Accepted by user | Historical partial-stack reports retained as historical evidence. |
| 12 Duels | Expired-invitation retry regression corrected in r64; live acceptance pending | Finite quarantine and stale-reply protection covered by isolated PostgreSQL tests; challenge/return lifecycle must be reconfirmed. |
| 13 Chat/privacy | Accepted tested channels and contacts/ignored | DND and remaining specialized channels not accepted. |
| 14 Joining combat | Basic joining accepted | Full shared lifecycle owned by another agent. |
| 15 Parties | Accepted | Invitations, membership, leadership, dissolution and group chat. |
| 16 Spectators | r63 deployed, live acceptance pending | r62 action streaming accepted; r63 repairs placement movement and existing summon entity/flush delivery. Mob cleanup/no spectator rewards accepted. |
| 17 Aptitudes | Core accepted | General runtime consumers and mount-related zero-stat regression are not certified. |
| 18 Placement facing | Accepted | Peer visibility remains E23. |
| 19 Independent movement | Accepted | Global performance is issue0. |
| 20 Initial population | Accepted observed maps | Published runtime catalog scope must not be inferred from an absent checkout asset. |
| 21 Remote configuration | Partial | End-to-end connection from another device not certified. |
| 22 Identification/enchantment | Identification accepted; socket/equipment corrections deployed, acceptance pending | Socket costs, duplicate-equipment sacrifice, shard installation, rollback and native inventory refresh have automated coverage. Identified sword equipment refresh is corrected; Hector must still retry equipping it. Complete socket cost/effect/persistence and sublimation combat acceptance remain pending. |
| 23 Stacked Sadida bag | Accepted | Preserve split/equip/reconnect behavior. |
| 24 Passport | Failed visual acceptance | Still Amaknian; neutral packets alone do not validate the UI. |
| 25 Dimensional rifts | Solo play accepted within tested scope; group/final rewards pending | Six-member DEV capacity and configurable random equipment, shards, BASIC sublimations and costumes are implemented. Hero reward ownership and terminal settlement fixes are included in the complete deployed checkout and covered by focused tests. Party/reconnect/final reward acceptance remains pending. Definitive rifts remain disabled until atomic key consumption is implemented. |
| 26 Haven Bag | Owner journey provisionally accepted; guest access failed | Guest room permissions, configuration UI and bag zaap remain. Account chest41 manually accepted separately. |
| 27 Weather | Partial | Regional visual behavior; not a complete official weather simulation. |
| 28 Area bonus | Partial | Visual propagation and regional transition acceptance. |
| 29 Dungeons | Tofullero accepted; 26 validated native dungeon flows active | Runtime readback confirms 16 physical and 10 teleport flows active at version 3: 18 additions, eight preserved including accepted Tofullero. Isolated PostgreSQL gates cover 67 room victories and 201 reward receipts for three players; 12 focused activation tests pass. The eight new physical flows use explicit local room composition adaptations. Remaining definitions have per-entry blockers; boss spells/mechanics and ultimate-boss correctness remain incomplete. [Activation, blockers and manual priorities](../reports/dungeons/EXPANDED-ACTIVATION-20261010.md). No restart was needed; existing runs retain pinned versions. |
| 30 Worktables | Accepted by user | Guest bag workshop authorization is separate issue26. |
| 31 Placement variety | Implemented, unaccepted | Complete visual variety/coherence acceptance; coordinate with other combat agent. |
| 32 Admin permissions | Accepted | Preserve authorization boundaries. |
| 33 Surrender | Individual accepted; shared review ongoing | Other agent owns complete shared lifecycle. |
| 34 Builds | Core accepted, partial | Unlock thresholds, full capacity, modulation/health and selected combat deck. |
| 35 Zaap loading | Provisionally accepted interactives | Worktable confirmation alone does not close complete travel coverage. |
| 36 Recycling/destruction | General reward journey accepted | Historical individual README remains stale; do not infer all eligibility/options covered. |
| 38 Character deletion | Accepted | User confirms the deletion journey works perfectly. |
| 39 Feeding/mount stats | Mounting/appearance accepted; equipment-stat regression not closed | Hector confirms Dragopavos work. Earlier intermittent zero characteristics on equip/unequip have no explicit full regression acceptance; feeding and multi-mount refresh coverage remain partial. |
| 40 Monster corpses | Corpse appearance and hand-resource harvesting accepted | Hector collected the molleja. Lifetime defaults to3600 seconds and is configurable in the database. Hourly expiry acceptance remains pending. Seed button remains visible and disabled after Hector restarted the client: manual acceptance failed. The attempted capture-agent menu patch has been withdrawn. A server/protocol solution remains under investigation; no client asset modifications are allowed. |
| 41 Haven Bag chest | Accepted by Hector | User confirms: Cofre funciona perfecto. Shared account storage and transfers; recorded automated verification remains valid. |
| 42 Kama shop | Pending | DB-configured products/prices and atomic purchase service. |
| 43 Exploration secrets | Deferred by explicit user instruction | Existing artifacts and movement-power implementation retained; do not spend current acceptance time on secrets. |
| 44 Costume learning/appearance | Titles, costumes, emotes, auras and mount appearances accepted | Hector confirms titles work after the owned-list publication correction. Emotes default unlocked with configurable locking policy. Sprint and other cosmetic categories remain separately unaccepted or unsupported. |
| Heroes (additional request) | Core hero journey accepted by Hector | Hector confirms heroes, HP bars, PvM combat, surrender and removing a member work. These checks supersede the earlier pending HP/bar and core combat acceptance. Removing both heroes followed by a main-only fight and reconnect persistence have not been explicitly confirmed. Spell casting engine remains owned by another agent. |
| Character capacity (additional request) | Accepted | Default18, configurable1–127; character selection accepted by Hector. |
| Mining veins (additional review) | Expanded local distribution prepared; not deployed | Fixed slots are separated from ecology, with database-configurable respawn (default300 seconds). The full local plan covers2881 unambiguous accessible slots on46 maps and51/51 mineral references;18 references use explicitly marked local terrain rules. Native extraction inspected961 map pairs:196 ambiguous-height records and1 inaccessible target are excluded;1509 native chunk decoding failures remain documented, so official spawn completeness is not claimed. Automated lifecycle, product and navigation checks pass; migration/catalog/import and graphical acceptance remain pending. See [implementation and acceptance](../reports/mining/FIXED-VEIN-IMPLEMENTATION.md). |
| Default professions (additional request) | Implemented and automatically tested; not deployed | All15 catalog professions learned at level0 on world entry for new and existing accounts; existing progress preserved. Profession suite10/10 passed. |
| Forced combat outcomes (additional request) | Implemented and automatically tested; not deployed | Authorized `!winfight` and `!losefight` end an active fight through normal settlement for the complete team. Combat command and lifecycle regression gate59/59 passed. See [manual acceptance](../reports/COMBAT-OUTCOME-COMMANDS.md). |
| Nearby group combat invitation (additional request) | Implemented and automatically tested; not deployed | Native join modal for nearby online party members on the same map and instance; native acceptance12197 and manual join13241 share the authoritative join handler. Ten focused tests and the62-test shared combat regression gate passed; refusal/timeout do not join. Graphical acceptance remains pending. Client assets unchanged. See [complete acceptance](../reports/GROUP-COMBAT-JOIN-PROMPT-20261010.md). |

Prepared complete world image and title/emote acceptance: [release instructions](../reports/cosmetics/TITLES-EMOTES-RELEASE-20261010.md).

Focused investigations: [late spectators](16-espectadores-y-marcadores/STATUS-REVIEW-20261009.md),
[sockets](22-identificacion-elementos-y-encantamiento/STATUS-REVIEW-20261009.md),
[passport](24-nacion-y-pasaporte-neutral/STATUS-REVIEW-20261009.md),
[guest room permissions](26-insertar-y-retirar-merkagemas/STATUS-REVIEW-20261009.md).
These reviews have not applied gameplay corrections.

There is no issue37 directory in this inventory:44 original issues including0,
plus23 E issues =67 tracked issues.

| Extra issues | Current status |
| --- | --- |
| E01/E03/E04/E07/E08/E10/E14/E16/E20 | Previously accepted/resolved in their recorded scope. |
| E02 | Inventory recovery implemented; malformed-recovery UI acceptance pending. |
| E05 | Partial; combat still has build/deck0 accesses. |
| E06 | Level atomicity implemented; full modulation/library scope remains partial. |
| E09 | Partial replay/cache optimization; complete latency/concurrency acceptance remains. |
| E11 | Historical fixture/terrain issue, reserved to another session. |
| E12 | Wound preservation implemented; controlled regeneration acceptance pending. |
| E13 | Overlaps13; old private-chat failure text is stale. Specialized channels remain open. |
| E15 | Full guild system pending. |
| E17 | Mounting/visibility accepted; broader equipment zero-stat regression tracked with39. |
| E18 | Basic NPC movement accepted; complete tactical attack behavior not certified. |
| E19 | Full achievement progress/journal/rewards pending; minimal dungeon criterion authority exists. |
| E21 | Zurkalia access pending. |
| E22 | Attack-facing behavior under investigation. |
| E23 | Orientation persistence/publication implemented; peer visual acceptance pending. |

## Manual acceptance: contacts and ignored players

Hector confirms all five review steps work perfectly: adding a contact survives
reconnect; private messages arrive normally; ignoring the sender blocks delivery;
the ignored entry and blocking survive reconnect; removing the ignored entry
restores private-message delivery. Contacts and ignored-player behavior under13
is manually accepted. This test does not cover DND or remaining guild/intergame/
admin/political/PvP channels. Do not request these five checks again.

## Follow-up: late spectators, identification and passport

Hector assigns shared-combat acceptance step1 to another agent; do not duplicate
that work in this review. Late spectator entry still fails: the observer cannot
see summons, beacons and similar actors, and can become blocked. This report
specifically concerns observers arriving after combat has started. Defeated mobs
disappear for everyone and observers receive no rewards; both paths are accepted.
Keep late snapshot actor/effect publication and blocking open under16.

Identification works according to Hector. Socket/enchantment operations have
not been tested and remain pending under22; visible sockets do not establish
that their modification, costs or persistence work. Do not treat the acceptance
of identification as acceptance of socket operations.

Passport acceptance under24 failed: Hector still sees an Amaknian passport.
The source's neutral serialization and historical codec tests do not establish
correct live presentation. Keep the visible passport defect open.

# Auditoría y soluciones de Wakemu

## Latest Haven Bag follow-up

Hector clarifies that the guest cannot move into other rooms; the owner can.
The screenshot displays native `Esta sala está inaccesible` on a wheat-seed
gathering action. Guest room access under26 remains open. The remainder of the
reviewed journey appears to work according to Hector and is provisionally
accepted. The responsible permission rule remains unconfirmed.

## Latest review feedback — mount stats, worktables and deletion

Hector confirms worktables (30) and character deletion (38) work. Character
deletion is manually accepted. Equipping or unequipping a Dragopavo intermittently
zeros character characteristics; reconnecting or changing spells/characteristics
restores them. This is an open equipment synchronization defect, not accepted
mount behavior. Server-state versus client-display divergence is not established.
See [current acceptance](USER-ACCEPTANCE-20261009.md).

## Current deployment — 2026-10-09, r59

The user authorized performance optimization after live combat stalls. The
complete shared `wakemu-world:performance-20261009-r59` image is deployed and
healthy; all 648 Python/protocol/migration files matched the running container.
It avoids no-op expiry copies, retains injected runtime services outside owned
transaction copies, and shares an internal immutable actor-property view while
preserving the public catalog contract. The final targeted set passed 67 tests;
the full suite is not passing and its baseline failures are documented. Live
combat latency acceptance remains pending. Continuous profiling is enabled on
the restarted world. Beacon fixes are deferred at the user's explicit request.
See [changes, evidence, limitations and exact manual acceptance](../reports/health/PERFORMANCE-RELEASE-R59-20261009.md).

### Previous complete release — r58

Complete shared image `wakemu-world:external-profiler-20261009-r58` is running
and healthy;647 source/migration/tool files matched at build time. Subsequent
shared combat source edits are not implicitly deployed. It retains all r57 changes
and adds bounded feature timings, asynchronous summary export, and administrative
`!perfil` commands. Optional external service `profiler` can start/stop without
restarting world and captures external py-spy profiles. See [operation, exact
acceptance and limitations](../reports/health/EXTERNAL-PROFILER-20261009.md).
At r58 Tofullero failed live acceptance because its first encounter was behind a
closed gate and included Tofu Real. Later physical-room changes superseded that
failure; the latest acceptance and remaining party defects are recorded above.

At r58 Hector requested diagnostics only. The later r59 authorization and
performance correction above supersede that earlier restriction.
The external profiler now records continuously while on, retaining one hour of
profiles and metrics, deployed without restarting world. See
[continuous profiler validation](../reports/health/CONTINUOUS-PROFILER-20261009.md).

### Previous complete release — r57

The complete shared image `wakemu-world:shared-bag-dungeons-checkpoint-20261009-r57`
is running and its health endpoint returns HTTP 200. Startup applied migrations
085 and 086. All 642 runtime source/migration files matched the built image.
See [release evidence](../reports/admin-chat/RELEASE-R57-20261009.md).

This release replaces captured player characteristics with owned values,
repairs defeated-mob cleanup for spectators, publishes bag furniture and recovered
gems, shares bags by account, adds exterior visitor entry, and supplies trusted
achievement state for dungeon criteria. Diagnostic logging is asynchronous and a
five-second checkpoint watchdog records thread stacks. These are automated-verified
changes awaiting manual acceptance; the severe checkpoint freeze remains open.
Fully close and relaunch clients to load the updated capture agent.

Hector also reports momentary overhead HP-bar flickering. It may share the stale
characteristics cause, but remaining HP/current-max refresh paths are under review.
Sublimation combat effects, native dungeon room fidelity, and unsupported HasState
entry criteria remain pending. See the current acceptance record below.

### Previous complete release — r55

The complete shared checkout is deployed as `wakemu-world:chat-admin-20261009-r55`,
with catalog release `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.
All 548 server Python files were compared with the built image without differences.
This includes concurrent combat/spell changes, checkpoint isolation, combined item
identification, external sword coordinates, feeding protocol/refresh fixes and
the Haven Bag extensions. Deployment does not replace manual acceptance.

New administrative chat commands: `!kamas`, `!checkpoint`, `!buscar`, and optional
final player targets for level, items, kamas, mobs and teleport.
See [commands and complete acceptance steps](../reports/admin-chat/COMMANDS-20261009.md).
The older image versions and source-only deployment notes below are historical.

**Current user feedback:** [acceptance and remaining work](USER-ACCEPTANCE-20261009.md)
is authoritative over the historical notes below. Chat commands, identification
with sockets, sword placement, joining, spectating reward eligibility, garden
planting and gem persistence are accepted. Exchange is accepted and dynamic
interactives provisionally accepted. Defeated-mob cleanup, account-wide bag
sharing and decoration persistence are now accepted. Remaining failures include
checkpoint freezes, late spectator/beacon publication, multi-mount identity,
bag management/visitor permissions and Tofullero access/encounter ordering.
Low-level mount scaling is accepted; complete refresh and scaling coverage remain open.

Parallel review is complete across performance/checkpoints, spectators/beacons,
mount identity, Haven Bag permissions, dungeons and sublimation/state effects.
See [findings and remaining work](../reports/health/PARALLEL-ISSUE-REVIEW-20261009.md).
This review does not claim gameplay fixes or authorize performance optimization.

## Historical implementation and acceptance notes

## Haven Bag extension — 2026-10-09

Decorative gem assignment is user-confirmed; persistence is explicitly reported
missing or not accepted and must be checked before additions. Inventory decoration transfers,
private gardening and portable native crafting are included in r55 with the
published furniture catalog; manual acceptance remains pending. Sales are
deferred. Follow the [complete test journey](26-insertar-y-retirar-merkagemas/HAVEN-BAG-SYSTEM-ACCEPTANCE.md),
which records item commands and limitations separately from historical images.

## Latest user acceptance — 2026-10-09

Hector confirms that interactive elements work, joining another player's fight works, and friendly challenges work. Do not request those same basic acceptance probes again. The remaining reported defect is the external fight marker: swords were absent near a newly started fight, although they were visible in the Jalató dungeon. Hector suspects that they appear away from the initiator's original world position. Incorrect positioning is a reported hypothesis, not yet a demonstrated root cause. Track this under issue 16; do not describe the whole joining or duel system as unavailable. Full lifecycle checks remain separate from these accepted basic interactions.

The deployment descriptions below are historical snapshots, not a reliable current image inventory. Read-only inspection during this review found world r53 running; the normal database contains 87 active dungeon context policies. Marker delivery logs alone do not establish correct client placement or visibility.

Carpetas y seguimiento para **42 issues originales reportados por el usuario** y **23 issues adicionales (E)**: **65 en total**. Cada carpeta conserva contexto, solución propuesta, pruebas y pendientes; la columna **status** distingue implementación y aceptación.

Versión instalada en Docker: **r19 / `cbc3a4ce`**, único contenedor `wakfu-local-world-1`, base habitual `wakemu_runtime`, healthy. **113 pruebas de combate de r18 aprobadas; r19 añade 41 pruebas PostgreSQL de autenticación/autorización aprobadas, sin omisiones** y dos recorridos TLS completos con tres jugadores: retirada durante colocación y durante combate activo, victoria, dos premios durables sin premio al retirado, reconexión sin duplicados y pelea posterior. **343 módulos preservados respecto a r17; r19 conserva los 354 módulos ajenos a API de r18**. Copia de seguridad previa al despliegue disponible. La aceptación visual del issue 14 sigue pendiente; no declarar totalmente solucionado. Conexión remota 21 y mazmorras 29 continúan en revisión; la composición por salas aún no está acreditada.

**Prueba conjunta lista:** [caso completo con comandos y resultados esperados](16-espectadores-y-marcadores/PRUEBA-COMPLETA-14-16-33-MAPA.md). No declarar totalmente solucionados 12/16/33 antes de aceptación. Los cambios usan el mismo servicio `world`.

## Documentación por issue

| ID | Problema | Carpeta |
| --- | --- | --- |
| 0 | Improved, open | Current complete deployment includes r72 performance changes. Automated focused checks pass; residual live latency, client UI delay and duplicate interactive publication remain under the other agent. |
| 1 | Las semillas solo disminuyen al reconectar | [Abrir](01-semillas-sin-refresco/README.md) |
| 2 | Un bebé tofu nunca crece | [Abrir](02-maduracion-de-monstruos/README.md) |
| 3 | Los monstruos no se reproducen ni amplían grupos | [Abrir](03-reproduccion-sin-respawn/README.md) |
| 4 | El porcentaje de plantación mostrado no es real | [Abrir](04-probabilidad-de-plantacion/README.md) |
| 5 | Plantas y árboles (Cardo, fresnos y otros) aparecen como recursos ajenos | [Abrir](05-permisos-y-recoleccion-de-cardo/README.md) |
| 6 | Cardo no llega a su etapa final | [Abrir](06-etapas-completas-de-cardo/README.md) |
| 7 | No sube Wakfu ni Stasis | [Abrir](07-wakfu-y-stasis/README.md) |
| 8 | No aumenta la experiencia de los oficios | [Abrir](08-experiencia-de-oficios/README.md) |
| 9 | No hay experiencia ni subida de nivel por combate | [Abrir](09-experiencia-de-combate/README.md) |
| 10 | No hay drops ni kamas | [Abrir](10-drops-y-kamas/README.md) |
| 11 | No se puede intercambiar con otros personajes | [Abrir](11-intercambio-entre-personajes/README.md) |
| 12 | No se puede pelear contra otros personajes | [Abrir](12-duelos-pvp/README.md) |
| 13 | Mensajes privados y otros canales de chat | [Abrir](13-chat-privado-y-canales/README.md) |
| 14 | No se puede entrar al combate de otra persona | [Abrir](14-unirse-a-combates/README.md) |
| 15 | No hay grupos de jugadores | [Abrir](15-grupos-de-jugadores/README.md) |
| 16 | No se pueden ver los combates | [Abrir](16-espectadores-y-marcadores/README.md) |
| 17 | No se pueden subir características | [Abrir](17-aptitudes-y-calculo-de-estadisticas/README.md) |
| 18 | No se puede elegir hacia dónde mirar en colocación | [Abrir](18-orientacion-en-colocacion/README.md) |
| 19 | Todos los monstruos se mueven a la vez | [Abrir](19-movimiento-aleatorio-eficiente/README.md) |
| 20 | Pocos mobs iniciales, reproducción y pausa sin jugadores | [Abrir](20-poblacion-inicial-y-zonas-activas/README.md) |
| 21 | Tools con configuración `.env` del servidor | [Abrir](21-conexion-remota-y-configuracion/README.md) |
| 22 | Identification accepted; socket/equipment corrections deployed, acceptance pending | Socket costs, duplicate-equipment sacrifice, shard installation, rollback and native inventory refresh have automated coverage. Identified sword equipment refresh is corrected; Hector must still retry equipping it. Complete socket cost/effect/persistence and sublimation combat acceptance remain pending. |
| 23 | Bolso Sadida apilado rompe la interfaz hasta reiniciar | [Abrir](23-bolso-sadida-apilado/README.md) |
| 24 | Pasaporte de Amakna por defecto | [Abrir](24-nacion-y-pasaporte-neutral/README.md) |
| 25 | Solo play accepted within tested scope; group/final rewards pending | Six-member DEV capacity and configurable random equipment, shards, BASIC sublimations and costumes are implemented. Hero reward ownership and terminal settlement fixes are included in the complete deployed checkout and covered by focused tests. Party/reconnect/final reward acceptance remains pending. Definitive rifts remain disabled until atomic key consumption is implemented. |
| 26 | No se pueden añadir merkagemas | [Abrir](26-insertar-y-retirar-merkagemas/README.md) |
| 27 | Clima | [Abrir](27-clima-por-zona/README.md) |
| 28 | Bonus de área | [Abrir](28-bonus-de-area/README.md) |
| 29 | Tofullero accepted; 26 validated native dungeon flows active | Runtime readback confirms 16 physical and 10 teleport flows active at version 3: 18 additions, eight preserved including accepted Tofullero. Isolated PostgreSQL gates cover 67 room victories and 201 reward receipts for three players; 12 focused activation tests pass. The eight new physical flows use explicit local room composition adaptations. Remaining definitions have per-entry blockers; boss spells/mechanics and ultimate-boss correctness remain incomplete. [Activation, blockers and manual priorities](../reports/dungeons/EXPANDED-ACTIVATION-20261010.md). No restart was needed; existing runs retain pinned versions. |
| 30 | Mesas de oficio ausentes o inoperantes | [Abrir](30-mesas-de-oficio-y-crafting/README.md) |
| 31 | Configuración repetida de celdas durante colocación | [Abrir](31-diversidad-de-celdas-de-colocacion/README.md) |
| 32 | Permiso `is_admin` para comandos `!` del chat | [Abrir](32-roles-admin-y-comandos/README.md) |
| 33 | Rendirse deja bloqueados nuevos combates y transporte | [Abrir](33-rendicion-y-retorno-al-mundo/README.md) |
| 34 | Builds personalizadas: desbloqueo tardío y hojas no seleccionables — prioridad alta | [Abrir](34-builds-personalizadas/README.md) |
| 35 | Zaap no seleccionable | [Abrir](35-zaap-no-seleccionable/README.md) |
| 36 | El botón de reciclado no hace nada | [Abrir](36-destruir-objetos/README.md) |
| 40 | Monster corpses after combat | [Abrir](40-cadaveres-de-monstruos/README.md) |
| 41 | Haven Bag chest | [Abrir](41-cofre-de-merkasaco/README.md) |
| 42 | Custom shop paid with kamas | [Abrir](42-tienda-personalizada-por-kamas/README.md) |
| E01 | Corrupción histórica de SQLite interrumpe crecimiento | [Abrir](E01-corrupcion-sqlite/README.md) |
| E02 | Recuperación de inventario 13713 serializa bolsas como entidad | [Abrir](E02-resincronizacion-inventario-invalida/README.md) |
| E03 | API de pruebas ejecuta antes de autenticar | [Abrir](E03-api-test-sin-autenticacion/README.md) |
| E04 | Activación 13776 sin handler | [Abrir](E04-activar-build-sin-handler/README.md) |
| E05 | Selección no persistida y deck 0 fijo | [Abrir](E05-seleccion-build-y-deck-cero/README.md) |
| E06 | Subida de nivel parcialmente confirmada con hoja fija inválida | [Abrir](E06-nivel-y-hojas-sin-atomicidad/README.md) |
| E07 | Borrado nativo de build sin handler | [Abrir](E07-borrado-de-build-sin-handler/README.md) |
| E08 | Capacidad 24 en interfaz versus índices 0–2 en validación | [Abrir](E08-limite-de-builds-inconsistente/README.md) |
| E09 | Hit Redis conserva lecturas SQL e inicializaciones repetidas | [Abrir](E09-sql-redundante-con-redis/README.md) |
| E10 | Actualización equipment_set no crea entradas nuevas | [Abrir](E10-equipment-set-omite-build-nueva/README.md) |
| E11 | Prueba de desplazamiento sin terreno exportado — reservada a otra sesión | [Abrir](E11-test-desplazamiento-sin-terreno-exportado/README.md) |
| E12 | Curación al alternar aptitudes | [Abrir](E12-curacion-al-alternar-aptitudes/README.md) |
| E13 | Canales de chat en general | [Abrir](E13-canales-de-chat/README.md) |
| E14 | Consumibles en barra rápida no persisten | [Abrir](E14-consumibles-barra-rapida-no-persisten/README.md) |
| E15 | Creación, permisos y persistencia de gremios | [Abrir](E15-gremios/README.md) |
| E16 | Nombres genéricos de monstruos | [Abrir](E16-nombres-genericos-monstruos/README.md) |
| E17 | Monturas y dragopavos | [Abrir](E17-monturas-y-dragopavos/README.md) |
| E18 | IA táctica de enemigos | [Abrir](E18-ia-tactica-enemigos/README.md) |
| E19 | Logros, objetivos y recompensas sin motor persistente | [Abrir](E19-logros/README.md) |
| E20 | Colocación no inicia el combate al agotarse el plazo | [Abrir](E20-colocacion-no-expira/README.md) |
| E21 | Accesos de Zurkalia a Astrub y arenas | [Abrir](E21-accesos-zurkalia/README.md) |
| E22 | Giro molesto del personaje al atacar | [Abrir](E22-giro-del-personaje-al-atacar/README.md) |
| E23 | Orientación invisible para otros jugadores | [Abrir](E23-orientacion-no-visible-otros-jugadores/README.md) |

## Cómo usar los planes

Leer DIAGNOSTICO y COTEJO antes de SOLUCION. Verificar hashes y reproducir el defecto en almacenamiento aislado; resolver FALTANTES y ejecutar PRUEBAS antes de cerrar. Las propuestas reutilizan piezas existentes, pero no afirman corrección integral de sistemas incompletos.

Priorizar E03/32 antes de exposición remota; E01 antes de ensayos sobre una base sospechosa; E02/23 para recuperación de inventario; E04–E08/E10 junto con 34 para builds; 0/E09 con 19/20 para rendimiento y persistencia. Esta prioridad es técnica y no autoriza despliegues ni reinicios.

[Reglas transversales](TRANSVERSALES.md) · [Validación](VALIDACION.md) · [Identidad de fuentes](manifest.json).

## Respuestas del usuario y alcance actualizado

[Decisiones incorporadas y responsabilidad de investigación](DECISIONES-Y-REVISION.md). Los hechizos quedan reservados a otra sesión. La auditoría continúa: generar carpetas no equivale a terminar el cotejo y las reproducciones.

## Nuevo defecto verificado

[E12 — Curación al alternar aptitudes](E12-curacion-al-alternar-aptitudes/README.md).

## Cobertura exhaustiva en curso

[Seguimiento de todos los issues](seguimiento-todos-los-issues.json). Ninguno se declara terminado por tener una carpeta o un plan. Las respuestas del usuario se conservan; los faltantes técnicos son trabajo de investigación, no decisiones que volver a solicitar. Toda interacción UI se delega a Luna con razonamiento low.

## Hallazgo adicional E13

[E13: canales de chat en general](E13-canales-de-chat/README.md). Alcance corregido por el usuario; el hallazgo específico de gremios se separa en E15.

## Nuevo reporte E14

[E14 — Consumibles en barra rápida no persisten](E14-consumibles-barra-rapida-no-persisten/README.md). El total actual es60, incluyendo los reportes35/36, E23 y E11 reservado a otra sesión; el estado vigente de E14 figura en la tabla.

## Priorización provisional de implementación

**Arquitectura:** se autorizan cambios incompatibles y una DB nueva; priorizar limpieza y escalabilidad. Sin backend legacy ni capas de retrocompatibilidad. [Criterio transversal](TRANSVERSALES.md).

Los estados conservan sus etiquetas y añaden indicadores visuales: ⏳ **Pendiente**, 🔍 **En revision**, 🧪 **Cambio hecho no confirmado**, ✅ **Solucionado totalmente**, 🟡 **Solucionado parcialmente** y ⛔ **Bloqueado**. La evidencia y el trabajo restante aparecen en una columna separada. Un cambio aplicado exige verificación del alcance completo antes de marcarlo como solucionado totalmente.

Esta clasificación usa el cotejo disponible. **No cierra la auditoría**: esfuerzo es relativo, sin estimaciones de horas; la prioridad final debe revisarse con reproducciones pendientes. La implementación y los reinicios están autorizados por el usuario; cada cierre requiere evidencia.

**Regla de prioridad del usuario (6 de octubre): trabajar primero todos los issues sin prefijo E. Un E solo se atiende si es una dependencia necesaria de un issue original, o después de terminar todos los originales.** Los números de bloques anteriores no autorizan adelantar un E independiente. Foco actual por nueva instrucción del usuario:9 (XP y subida de nivel) y10 (kamas), con máxima prioridad. La IA de monstruos corresponde al agente que asignará el usuario;15 es un issue original. Cualquier regresión causada por un despliegue se corrige antes de continuar. Los números conservan los bloques de prioridad anteriores: varias filas pueden compartir orden. Los issues antes mencionados fuera de la tabla se incluyen como transversales, por definir o reservados, sin asignarles una prioridad nueva.

| Orden | Issue | Nombre del issue | status | Impacto y esfuerzo relativo | Dependencias y criterio de avance | Evidencia y pendientes |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | [Retrasos al iniciar combates y lanzar hechizos](00-rendimiento-y-redis/README.md) | 🔍 En revision | Alto en rendimiento; medio–alto | Medir SQL/Redis, locks, serialización y latencia real; retirar trabajo redundante del camino caliente. Hechizos reservados. | Improved, open. Current complete deployment includes r72 performance changes. Automated focused checks pass; residual live latency, client UI delay and duplicate interactive publication remain under the other agent. |
| 1 | 32 | [Permiso `is_admin` para comandos `!` del chat](32-roles-admin-y-comandos/README.md) | ✅ Solucionado totalmente | Alto; acotado frente a sistemas nuevos | Autorizar comandos por is_admin; rechazar acciones sin permisos ni efectos. Antes de exposición remota. | Accepted. Preserve authorization boundaries. |
| 1 | E03 | [API de pruebas ejecuta antes de autenticar](E03-api-test-sin-autenticacion/README.md) | ✅ Solucionado totalmente | Alto; acotado frente a sistemas nuevos | Autenticar antes de ejecutar la API; comprobar rechazo sin efectos. Antes de exposición remota. | Previously accepted/resolved in their recorded scope. |
| 1 | E01 | [Corrupción histórica de SQLite interrumpe crecimiento](E01-corrupcion-sqlite/README.md) | ✅ Solucionado totalmente | Muy alto en persistencia; migración de esfuerzo alto | Base nueva, sin SQLite ni importación. Los fallos de combate no bloquean avanzar otros issues. [Evidencia](E01-corrupcion-sqlite/IMPLEMENTACION.md). | Previously accepted/resolved in their recorded scope. |
| 2 | 23 | [Bolso Sadida apilado rompe la interfaz hasta reiniciar](23-bolso-sadida-apilado/README.md) | ✅ Solucionado totalmente | Muy alto en persistencia; migración de esfuerzo alto | E02 conserva su aceptación independiente de recuperación explícita13713. | Accepted. Preserve split/equip/reconnect behavior. |
| 2 | E02 | [Recuperación de inventario 13713 serializa bolsas como entidad](E02-resincronizacion-inventario-invalida/README.md) | 🧪 Cambio hecho no confirmado | Muy alto en persistencia; migración de esfuerzo alto | Resincronización nativa válida para inventario y bolsas; cotejar consumidor y recuperación junto con 23. | Inventory recovery implemented; malformed-recovery UI acceptance pending. |
| 3 | 34 | [Builds personalizadas: desbloqueo tardío y hojas no seleccionables — prioridad alta](34-builds-personalizadas/README.md) | 🟡 Solucionado parcialmente | Muy alto para personajes; medio–alto | Resolver desbloqueo, selección y persistencia de builds junto con E04–E08/E10/E12; no modificar hechizos. | Core accepted, partial. Unlock thresholds, full capacity, modulation/health and selected combat deck. |
| 3 | 17 | [No se pueden subir características](17-aptitudes-y-calculo-de-estadisticas/README.md) | ✅ Solucionado totalmente | Muy alto para personajes; medio–alto | Persistir aptitudes y recalcular estadísticas de forma atómica con nivel, build, equipo y HP. | Core accepted. General runtime consumers and mount-related zero-stat regression are not certified. |
| 3 | E04 | [Activación 13776 sin handler](E04-activar-build-sin-handler/README.md) | ✅ Solucionado totalmente | Muy alto para personajes; medio–alto | Activación autoritativa y validación nativa de éxito/rechazo; coordinar con 34/E05. | Previously accepted/resolved in their recorded scope. |
| 3 | E05 | [Selección no persistida y deck 0 fijo](E05-seleccion-build-y-deck-cero/README.md) | 🟡 Solucionado parcialmente | Muy alto para personajes; medio–alto | Persistir selección y usar el deck de la build activa; coordinar con 34/E04 sin invadir hechizos de otra sesión. | Partial; combat still has build/deck0 accesses. |
| 3 | E06 | [Subida de nivel parcialmente confirmada con hoja fija inválida](E06-nivel-y-hojas-sin-atomicidad/README.md) | 🟡 Solucionado parcialmente | Muy alto para personajes; medio–alto | Recargar corrección de nivel del actor y reproducir el ciclo completo en cliente antes de cerrar. | Level atomicity implemented; full modulation/library scope remains partial. |
| 3 | E07 | [Borrado nativo de build sin handler](E07-borrado-de-build-sin-handler/README.md) | ✅ Solucionado totalmente | Muy alto para personajes; medio–alto | Autoridad única PostgreSQL tras E01; validar rechazo/éxito, fallback de activa e inventario intacto antes de cargar13169. | Previously accepted/resolved in their recorded scope. |
| 3 | E08 | [Capacidad 24 en interfaz versus índices 0–2 en validación](E08-limite-de-builds-inconsistente/README.md) | ✅ Solucionado totalmente | Muy alto para personajes; medio–alto | Unificar capacidad de interfaz y validación de índices; comprobar límites junto con 34. | Previously accepted/resolved in their recorded scope. |
| 3 | E10 | [Actualización equipment_set no crea entradas nuevas](E10-equipment-set-omite-build-nueva/README.md) | ✅ Solucionado totalmente | Muy alto para personajes; medio–alto | Crear entradas nuevas de equipment_set y mantenerlas al activar/reconectar; coordinar con 34. | Previously accepted/resolved in their recorded scope. |
| 3 | E12 | [Curación al alternar aptitudes](E12-curacion-al-alternar-aptitudes/README.md) | 🧪 Cambio hecho no confirmado | Muy alto para personajes; medio–alto | Evitar curación al alternar aptitudes; mantener coherencia de HP, nivel, hojas y equipo. | Wound preservation implemented; controlled regeneration acceptance pending. |
| 4 | 1 | [Las semillas solo disminuyen al reconectar](01-semillas-sin-refresco/README.md) | ✅ Solucionado totalmente | Mejoras visibles de alcance relativamente acotado | Acreditar cantidad visual inmediata tras consumo. El cooldown de extracción requiere validación independiente y configuración en DB. | Accepted. Immediate consumption/refresh. |
| 4 | 18 | [No se puede elegir hacia dónde mirar en colocación](18-orientacion-en-colocacion/README.md) | ✅ Solucionado totalmente | Mejoras visibles de alcance relativamente acotado | Validar orientación por fase y actor, y confirmar sincronización durante colocación. | Accepted. Peer visibility remains E23. |
| 4 | E22 | [Giro molesto del personaje al atacar](E22-giro-del-personaje-al-atacar/README.md) | 🔍 En revision | Molestia visible; esfuerzo por cotejar | Distinguir animación nativa y facing del servidor; preservar espalda/condiciones y hechizos. | Attack-facing behavior under investigation. |
| 4 | E14 | [Consumibles en barra rápida no persisten](E14-consumibles-barra-rapida-no-persisten/README.md) | ✅ Solucionado totalmente | Mejoras visibles de alcance relativamente acotado | Handler, persistencia y bootstrap de barra WORLD; confirmar asignación GUI y restauración al reconectar. | Previously accepted/resolved in their recorded scope. |
| 4 | E20 | [Colocación no termina cuando el contador llega a cero](E20-colocacion-no-expira/README.md) | ✅ Solucionado totalmente | Alto para combate; acotado en ciclo de fases | Deadline autoritativo y política PostgreSQL; reutilizar transición de Listo sin tocar hechizos. | Previously accepted/resolved in their recorded scope. |
| 4 | E17 | [Monturas equipadas que no permiten montarse](E17-monturas-y-dragopavos/README.md) | ✅ Solucionado totalmente | Mejoras visibles; ciclo persistente y movimiento amplían esfuerzo | Desbloqueo por defecto sin misión, PET/item persistidos y handlers de montar/desmontar; alimentación y ciclo completo amplían alcance. | Mounting/visibility accepted; broader equipment zero-stat regression tracked with39. |
| 4 | E16 | [Monstruos con nombre «Grupo local»](E16-nombres-genericos-monstruos/README.md) | ✅ Solucionado totalmente | Acotado; mejora visible | Cotejar nombres individuales y fallback nativo, variantes e idiomas; no depende de reproducción ni mazmorras. | Previously accepted/resolved in their recorded scope. |
| 5 | 19 | [Todos los monstruos se mueven a la vez](19-movimiento-aleatorio-eficiente/README.md) | ✅ Solucionado totalmente | Alto en rendimiento; medio–alto | Movimiento aleatorio con adyacencias indexadas, sin cálculo/envío bajo bloqueo global; intervalo y probabilidad en DB. | Accepted. Global performance is issue0. |
| 5 | 20 | [Pocos mobs iniciales, reproducción y pausa sin jugadores](20-poblacion-inicial-y-zonas-activas/README.md) | ✅ Solucionado totalmente | Alto en rendimiento; medio–alto | Siembra una vez por hábitat nativo; marcadores durables impiden reposición, simulación pausa sin presencia. | Accepted observed maps. Published runtime catalog scope must not be inferred from an absent checkout asset. |
| 5 | E09 | [Hit Redis conserva lecturas SQL e inicializaciones repetidas](E09-sql-redundante-con-redis/README.md) | 🟡 Solucionado parcialmente | Alto en rendimiento; medio–alto | Lectura Redis primero y eliminación de SQL/inicializaciones redundantes; diferenciar ausencia de caché de fallo con mutaciones pendientes. | Partial replay/cache optimization; complete latency/concurrency acceptance remains. |
| 6 | E18 | [Motor de IA táctica de enemigos](E18-ia-tactica-enemigos/README.md) | ⏳ Pendiente | Muy alto para PvE; alto, entregable por etapas | Autoridad NPC y preview del motor común; luego ranking, secuencias, espalda, alturas y coordinación. Depende de 0 y validación multijugador 14/15; antes de certificar dificultad 29/25. | Basic NPC movement accepted; complete tactical attack behavior not certified. |
| 7 | 5 | [Plantas y árboles (Cardo, fresnos y otros) aparecen como recursos ajenos](05-permisos-y-recoleccion-de-cardo/README.md) | ✅ Solucionado totalmente | Alto en ecosistema; alto | Validar propiedad y permisos para todas las plantas/árboles; incluir cooldown persistente y recolección autoritativa. | Accepted. Preserve public flora harvesting. |
| 7 | 6 | [Cardo no llega a su etapa final](06-etapas-completas-de-cardo/README.md) | 🟡 Solucionado parcialmente | Alto en ecosistema; alto | Cotejar etapas finales y transiciones para todas las plantas/árboles, con persistencia y crecimiento autoritativo. | Partial. Normal Cardo accepted; Fresno/general species coverage remains. |
| 7 | 2 | [Un bebé tofu nunca crece](02-maduracion-de-monstruos/README.md) | ✅ Solucionado totalmente | Alto en ecosistema; alto | Definir maduración y transiciones de referencia/edad de monstruos; coordinar con 3/20. | Accepted. Balance adjustments are separate. |
| 7 | 3 | [Los monstruos no se reproducen ni amplían grupos](03-reproduccion-sin-respawn/README.md) | 🟡 Solucionado parcialmente | Alto en ecosistema; alto | Reproducción persistente y límites por zona; coordinar con crecimiento, población y pausa sin jugadores. | Implemented, partial acceptance. Natural timing and recovery of offspring after restart. |
| 7 | 4 | [El porcentaje de plantación mostrado no es real](04-probabilidad-de-plantacion/README.md) | 🟡 Solucionado parcialmente | Alto en ecosistema; alto | Alinear porcentaje nativo y tirada autoritativa; resultados persistidos con consumo y XP correctos. | Partial. Wider terrain/climate/bonus coverage and effective configuration. |
| 7 | 7 | [No sube Wakfu ni Stasis](07-wakfu-y-stasis/README.md) | ✅ Solucionado totalmente | Alto en ecosistema; alto | Afinidad por acciones confirmadas, conteos por familia/región y recibos; conservar combate/hechizos. | Accepted. Preserve confirmed ecology progression. |
| 7 | 28 | [Bonus de área](28-bonus-de-area/README.md) | 🟡 Solucionado parcialmente | Alto en ecosistema; alto | Aplicar bonus desde estado autoritativo del ecosistema y condiciones de zona; depende de conteos y reglas de población. | Partial. Visual propagation and regional transition acceptance. |
| 8 | 8 | [No aumenta la experiencia de los oficios](08-experiencia-de-oficios/README.md) | ✅ Solucionado totalmente | Alto para progresión/economía; alto | Alcance correcto de XP de oficio y persistencia; integrar acciones, recetas y estaciones con 30. | Accepted. Gathering, planting and tested crafting. |
| 8 | 30 | [Mesas de oficio ausentes o inoperantes](30-mesas-de-oficio-y-crafting/README.md) | ✅ Solucionado totalmente | Alto para progresión/economía; alto | Fuentes de estaciones/mesas, recetas y acceso; validar fabricación y XP junto con 8. | Accepted by user. Guest bag workshop authorization is separate issue26. |
| 1 — máxima | 9 | [No hay experiencia ni subida de nivel por combate](09-experiencia-de-combate/README.md) | ✅ Solucionado totalmente | Máxima prioridad solicitada por el usuario | Aplicar fórmula Dofus con parámetros SQL y curva Wakfu; no copiar excepción artificial de nivel199. | Accepted. Preserve transactional rewards. |
| 1 — máxima | 10 | [No hay drops ni kamas](10-drops-y-kamas/README.md) | 🟡 Solucionado parcialmente | Máxima prioridad para drops y kamas, solicitada por el usuario | Drops con objetos, probabilidades y condiciones nativas Wakfu; kamas parametrizadas SQL; recibos durables y wallet visible. | Core accepted, partial catalog coverage. Complex criteria and roll limits remain. |
| 8 | E19 | [Logros, objetivos y recompensas sin motor persistente](E19-logros/README.md) | ⏳ Pendiente | Alto para progresión/economía; alto | Importar catálogo, formalizar eventos y dependencias, persistir objetivos/ciclos y conceder premios una sola vez. Depende de E01; logro 4228 entrega Gremialogema antes del flujo E15. | Full achievement progress/journal/rewards pending; minimal dungeon criterion authority exists. |
| 9 | 13 | [Mensajes privados y otros canales de chat](13-chat-privado-y-canales/README.md) | 🟡 Solucionado parcialmente | Alto para multijugador; alto | Completar permisos y recepción de las ramas restantes, preservando canales aceptados. | Accepted tested channels and contacts/ignored. DND and remaining specialized channels not accepted. |
| 9 | 35 | [Zaap no seleccionable](35-zaap-no-seleccionable/README.md) | 🧪 Cambio hecho no confirmado | Alto por regresión de transporte; acotado tras diagnóstico | Restablecer seleccionabilidad sin alterar rutas/dragopavos; no confundir con33. | Provisionally accepted interactives. Worktable confirmation alone does not close complete travel coverage. |
| 9 | 15 | [No hay grupos de jugadores](15-grupos-de-jugadores/README.md) | ✅ Solucionado totalmente | Alto para multijugador; alto | Party persistente/coherente y membresía compartida; precede joins, espectadores e instancias. | Accepted. Invitations, membership, leadership, dissolution and group chat. |
| 9 | 14 | [No se puede entrar al combate de otra persona](14-unirse-a-combates/README.md) | 🟡 Solucionado parcialmente | Alto para multijugador; alto | Registro compartido de combate y permisos de entrada; depende de 15 y ciclo de combate, incluidos 31/33. | Basic joining accepted. Full shared lifecycle owned by another agent. |
| 9 | 16 | [No se pueden ver los combates](16-espectadores-y-marcadores/README.md) | 🟡 Solucionado parcialmente | Alto para multijugador; alto | Registro compartido y publicación para espectadores; coordinar con 14/15 y retorno al mundo. | r63 deployed, live acceptance pending. r62 action streaming accepted; r63 repairs placement movement and existing summon entity/flush delivery. Mob cleanup/no spectator rewards accepted. |
| 9 | 12 | [No se puede pelear contra otros personajes](12-duelos-pvp/README.md) | 🧪 Cambio hecho no confirmado | Alto para multijugador; alto | Duelos con autorización y ciclo completo, sin premios; verificar retorno al mundo y varios personajes. | Expired-invitation retry regression corrected in r64; live acceptance pending. Finite quarantine and stale-reply protection covered by isolated PostgreSQL tests; challenge/return lifecycle must be reconfirmed. |
| 9 | 11 | [No se puede intercambiar con otros personajes](11-intercambio-entre-personajes/README.md) | ✅ Solucionado totalmente | Alto para multijugador; detalle restante bajo | Conservar transferencia atómica y persistencia; diferir el retiro parcial UI de baja prioridad. | Accepted by user. Historical partial-stack reports retained as historical evidence. |
| 9 | E13 | [Canales de chat en general](E13-canales-de-chat/README.md) | 🟡 Solucionado parcialmente | Alto para multijugador; alto | Auditar todos los canales con autorización y routing; coordinar con 13. El sistema completo de gremios corresponde a E15. | Overlaps13; old private-chat failure text is stale. Specialized channels remain open. |
| 10 | 22 | [Objetos sin identificar](22-identificacion-elementos-y-encantamiento/README.md) | 🟡 Solucionado parcialmente | Variable; medio–alto | Identificación, elementos y encantamiento con contratos propios; persistir resultados sin volver a sortear al reconectar. | Identification accepted; socket/equipment corrections deployed, acceptance pending. Socket costs, duplicate-equipment sacrifice, shard installation, rollback and native inventory refresh have automated coverage. Identified sword equipment refresh is corrected; Hector must still retry equipping it. Complete socket cost/effect/persistence and sublimation combat acceptance remain pending. |
| 10 | 26 | [No se pueden añadir merkagemas](26-insertar-y-retirar-merkagemas/README.md) | 🟡 Solucionado parcialmente | Variable; medio–alto | Inserción y retirada de merkagemas con validación y persistencia del merkasaco. | Owner journey provisionally accepted; guest access failed. Guest room permissions, configuration UI and bag zaap remain. Account chest41 manually accepted separately. |
| 10 | 24 | [Pasaporte de Amakna por defecto](24-nacion-y-pasaporte-neutral/README.md) | 🔍 En revision | Variable; medio–alto | Contrato de nación/pasaporte y estado inicial coherente; no extrapolar éxito de un paquete al sistema completo. | Failed visual acceptance. Still Amaknian; neutral packets alone do not validate the UI. |
| 10 | 27 | [Clima](27-clima-por-zona/README.md) | 🟡 Solucionado parcialmente | Variable; medio–alto | Estado de clima por zona, actualización y forecast coherentes, con reglas configurables. | Partial. Regional visual behavior; not a complete official weather simulation. |
| 11 | 29 | [Mazmorras](29-mazmorras-e-instancias/README.md) | 🟡 Solucionado parcialmente | Alto; estructural | Acreditar población por sala; party, sesiones, avance tras victoria/derrota, dificultad y premios. Depende de persistencia y ciclo de combate. | Tofullero accepted; 26 validated native dungeon flows active. Runtime readback confirms 16 physical and 10 teleport flows active at version 3: 18 additions, eight preserved including accepted Tofullero. Isolated PostgreSQL gates cover 67 room victories and 201 reward receipts for three players; 12 focused activation tests pass. The eight new physical flows use explicit local room composition adaptations. Remaining definitions have per-entry blockers; boss spells/mechanics and ultimate-boss correctness remain incomplete. [Activation, blockers and manual priorities](../reports/dungeons/EXPANDED-ACTIVATION-20261010.md). No restart was needed; existing runs retain pinned versions. |
| 11 | 25 | [Brechas dimensionales](25-brechas-dimensionales/README.md) | 🟡 Solucionado parcialmente | Alto; estructural | Ciclos/oleadas y recompensas propios; validar instancias y dificultad con IA básica disponible. | Solo play accepted within tested scope; group/final rewards pending. Six-member DEV capacity and configurable random equipment, shards, BASIC sublimations and costumes are implemented. Hero reward ownership and terminal settlement fixes are included in the complete deployed checkout and covered by focused tests. Party/reconnect/final reward acceptance remains pending. Definitive rifts remain disabled until atomic key consumption is implemented. |
| 11 | E15 | [Sistema completo de gremios](E15-gremios/README.md) | ⏳ Pendiente | Alto; estructural | Creación, membresía, permisos y durabilidad reales; depende de E01, social y flujo de Gremialogema de E19. | Full guild system pending. |
| Transversal | 21 | [Tools con configuración `.env` del servidor](21-conexion-remota-y-configuracion/README.md) | 🟡 Solucionado parcialmente | Sin clasificación individual previa | Infraestructura: separar host, puertos y secretos de reglas en DB; alcance exclusivo del servidor. | Partial. End-to-end connection from another device not certified. |
| Transversal | 31 | [Configuración repetida de celdas durante colocación](31-diversidad-de-celdas-de-colocacion/README.md) | 🧪 Cambio hecho no confirmado | Sin clasificación individual previa | Política SQL y layout persistente por encuentro. | Implemented, unaccepted. Complete visual variety/coherence acceptance; coordinate with other combat agent. |
| Transversal | 33 | [Rendirse deja bloqueados nuevos combates y transporte](33-rendicion-y-retorno-al-mundo/README.md) | 🟡 Solucionado parcialmente | Sin clasificación individual previa | Garantizar retorno tras rendición y desbloqueo de combate/transporte antes de certificar joins o instancias. | Individual accepted; shared review ongoing. Other agent owns complete shared lifecycle. |
| Reservado | E11 | [Prueba de desplazamiento sin terreno exportado — reservada a otra sesión](E11-test-desplazamiento-sin-terreno-exportado/README.md) | ⏳ Pendiente | Fuera de esta sesión | Reservado a otra sesión; no ejecutar ni modificar pruebas de hechizos/desplazamiento en este alcance. | Historical fixture/terrain issue, reserved to another session. |
| Por ordenar | E21 | [Accesos de Zurkalia a Astrub y arenas](E21-accesos-zurkalia/README.md) | ⏳ Pendiente | Alto para navegación; esfuerzo por determinar | Trazar interactivos, destinos y ciclo de instancias; verificar ambos accesos por separado. | Zurkalia access pending. |
| Por ordenar | E23 | [Orientación invisible para otros jugadores](E23-orientacion-no-visible-otros-jugadores/README.md) | 🧪 Cambio hecho no confirmado | Multijugador; esfuerzo por cotejar | Confirmar mensajes de exploración y difusión durante colocación, sin tocar hechizos. | Orientation persistence/publication implemented; peer visual acceptance pending. |
| Por ordenar | 36 | [El botón de reciclado no hace nada](36-destruir-objetos/README.md) | 🟡 Solucionado parcialmente | Inventario; esfuerzo por cotejar | Implementar petición12787 y producto/resultado12890 según contrato nativo. | General reward journey accepted. Historical individual README remains stale; do not infer all eligibility/options covered. |
| Por ordenar | 39 | [No se puede alimentar al dragopavo o mascotas](39-alimentacion-monturas-y-mascotas/README.md) | 🟡 Solucionado parcialmente | Tarea solicitada por el usuario | Revisar alimento compatible, acción nativa, consumo y persistencia. | Mounting/appearance accepted; equipment-stat regression not closed. Hector confirms Dragopavos work. Earlier intermittent zero characteristics on equip/unequip have no explicit full regression acceptance; feeding and multi-mount refresh coverage remain partial. |
| Prioridad original nueva | 38 | [No se pueden eliminar personajes](38-eliminar-personajes/README.md) | ✅ Solucionado totalmente | Impide liberar cupo | Handler nativo22870, baja lógica, nombre/cupo libres y monedero histórico conservado. | Accepted. User confirms the deletion journey works perfectly. |
| Prioridad original nueva | 40 | [Monster corpses after combat](40-cadaveres-de-monstruos/README.md) | 🟡 Solucionado parcialmente | Solicitado por el usuario | Cadáveres persistentes; duración configurable en PostgreSQL, 3600 segundos por defecto. | Corpse appearance and hand-resource harvesting accepted. Hector collected the molleja. Lifetime defaults to3600 seconds and is configurable in the database. Hourly expiry acceptance remains pending. Seed button remains visible and disabled after Hector restarted the client: manual acceptance failed. The attempted capture-agent menu patch has been withdrawn. A server/protocol solution remains under investigation; no client asset modifications are allowed. |
| Prioridad original nueva | 41 | [Haven Bag chest](41-cofre-de-merkasaco/README.md) | ✅ Solucionado totalmente | Solicitado por el usuario | Cofre compartido por cuenta, 100 espacios, transferencias atómicas, stacks parciales y metadatos persistentes. | Accepted by Hector. User confirms: Cofre funciona perfecto. Shared account storage and transfers; recorded automated verification remains valid. |
| Prioridad original nueva | 42 | [Custom shop paid with kamas](42-tienda-personalizada-por-kamas/README.md) | ⏳ Pendiente | Solicitado por el usuario | Revisar captura oficial y desarrollar solución general. | Pending. DB-configured products/prices and atomic purchase service. |
| Prioridad original nueva | 43 | [Secretos de exploración](43-secretos-de-exploracion/README.md) | ⏸ Diferido por el usuario | Solicitado por el usuario | Once artefactos de cuenta y cuatro capacidades nativas de movimiento, configurables en PostgreSQL. | Deferred by explicit user instruction. Existing artifacts and movement-power implementation retained; do not spend current acceptance time on secrets. |
| Prioridad original nueva | 44 | [Aprendizaje y apariencia de trajes](44-aprendizaje-y-apariencia-de-trajes/README.md) | ✅ Solucionado totalmente | Solicitado por el usuario | Aprender trajes, consumir un objeto y publicar la apariencia propia y de otros jugadores. | Titles, costumes, emotes, auras and mount appearances accepted. Hector confirms titles work after the owned-list publication correction. Emotes default unlocked with configurable locking policy. Sprint and other cosmetic categories remain separately unaccepted or unsupported. |
| Prioridad actual | Heroes | [Sistema de héroes](../reports/heroes/HEROES-RELEASE-20261010.md) | ✅ Flujo principal validado por el usuario | Máxima prioridad del usuario | Instanciar main + dos héroes y preservar selección, control, interfaz y ciclo de combate. | Hector confirma héroes y barras de vida correctos, combates PvM correctos, rendición correcta y retirada de un miembro correcta. Se conserva esta aceptación; ya no se pide repetir esas pruebas. Pendientes adicionales sin confirmación explícita: quitar ambos héroes, combate sólo con el principal y persistencia de la retirada tras reconectar. Motor de lanzamiento reservado a otro agente. |
| Solicitud adicional | Character capacity | Cupo de personajes | ✅ Solucionado totalmente | Configuración de cuenta | Predeterminado18, configurable1–127. | Desplegado y selección de personajes aceptada por Hector. |

### Incorporación de las últimas revisiones

- **PostgreSQL — prioridad 1, resuelto.** El Docker principal usa `wakemu_runtime`, con 33 tablas y nueve migraciones; SQLite queda como archivo histórico, sin fallback ni importación de personajes. Restauración poblada, retirada de módulos antiguos y gate de 77/77 pruebas acreditados. Creación de personaje, mapa e inventario tras reinicio comprobados con el cliente. La última suite completa terminó con código1: 1.737 pruebas, 12 fallos, 59 errores y una omitida (407,486s). Los fallos actuales se clasificaron en hechizos/efectos y fixtures de combate, incluida otra sesión; no se atribuyó un stack de fallo a PostgreSQL o Redis. La suite global sigue sin aprobar y no se confunde con los gates dirigidos de persistencia. [Evidencia de implementación](E01-corrupcion-sqlite/IMPLEMENTACION.md) · [Migración tabla por tabla](E01-corrupcion-sqlite/MIGRACION-POSTGRESQL-TABLAS.md).
- **XP visible — validación dentro de prioridad 8, sin fix para la captura aportada.** Los 59.929.868.921 XP persistidos coinciden con el inicio del nivel 200; el cálculo nativo muestra cero dentro del nivel. Con 123 XP adicionales devuelve 123. Sigue pendiente verificar el recorrido de una recompensa real, paquete y reconexión; también cotejar el límite 200 del servidor frente al 246 declarado por la curva nativa antes de ampliar niveles. Esta explicación no cierra el issue de XP por combate. [Diagnóstico y evidencia](09-experiencia-de-combate/XP-CERO-EN-VENTANA.md).

**33 y 31** deben revisarse junto al ciclo de combate antes de certificar joins o instancias: retorno tras rendición y diversidad de colocación no quedan cubiertos por desbloquear una puerta. **21** es configuración de infraestructura/conexión del servidor; separar host/puertos/secretos de parámetros de reglas en DB. [Parámetros del servidor](PARAMETROS-SERVIDOR-EN-DB.md).


## E15 — Sistema completo de gremios

[E15: creación, persistencia y funcionamiento de gremios](E15-gremios/README.md). Evidencia offline preservada; creación y prueba con un gremio real pendientes. El inventario actual tiene **60 issues**, incluido E11 reservado a otra sesión.


## E16 — Nombres genéricos de monstruos

[E16: «Grupo local» enviado como nombre individual](E16-nombres-genericos-monstruos/README.md). Causa reproducida en serialización del servidor; consumidor/fallback y variantes visuales pendientes. Cambio potencialmente acotado tras ese cotejo; no requiere resolver reproducción ni mazmorras.

## E17 — Monturas y dragopavos

[E17: monturas y dragopavos](E17-monturas-y-dragopavos/README.md). **Solucionado totalmente**: el usuario confirmó equipar, montar sin misión, caminar, reconectar, desmontar, quitar y reequipar, además de la visibilidad desde otro personaje. Alimentación y cosméticos son extensiones futuras. La orientación visible entre jugadores se sigue por separado en E23.

## E18 — IA táctica de enemigos

[E18: clasificación de hechizos, planes, espalda/elevaciones y coordinación](E18-ia-tactica-enemigos/README.md). Reutiliza la arquitectura de Dofus sin Laya mediante adaptadores Wakfu. **Prioridad 6: después de estabilizar la ejecución NPC del motor común de hechizos**, antes de certificar dificultad de mazmorras; implementar primero decisiones deterministas y luego coordinación. Alto impacto PvE, esfuerzo alto. El catálogo de habilidades existe; no implica soporte completo del motor.


## E19 — Sistema de logros

[E19: catálogo, progreso, recompensas y restauración del diario](E19-logros/README.md). El catálogo compartido contiene3.278 definiciones,6.029 objetivos y5.593 recompensas; el servidor envía un estado vacío. Consumidor nativo probado offline, incluyendo contador, finalización y seguimiento. **Prioridad8**, junto con progresión/recompensas; depende de E01 para durabilidad y alimenta E15 por la Gremialogema del logro4228. Reglas de escenarios y validación en partida siguen abiertas. Total: **60 issues**.

Verificación local adicional: World, sincronización estática, Registry compartido y marcadores75/75 aprobados en un entorno Python aislado. Docker sigue sin respuesta al último control; gates PostgreSQL/TLS finales pendientes. La salud actual no queda acreditada por el health histórico del último despliegue.

Recuperación de Docker: las dos candidatas antiguas de colocación/sublimación se detuvieron; `docker ps` vuelve a responder y el health del servidor activo devuelve200. La candidata de duelos r2 conserva un fallo ya corregido en fuente y no sirve como validación final; se reconstruye con los últimos marcadores, retorno y bonus territoriales. Se limita a un arranque de candidata a la vez.


Última validación del issue 14 — 🟠 Cambio hecho no confirmado: la imagen r18 aprobó 113 pruebas automáticas. La prueba TLS con tres cuentas ya confirma dos uniones sucesivas, colocación compartida, retirada del iniciador, victoria de los dos restantes y exactamente dos premios durables, sin premio para el retirado. Recorrido TLS completo aprobado (combate 46, siguiente combate 47): reconexión en exploración, premios/drops sin duplicados y nueva pelea. Retirada durante combate activo también aprobada por TLS (combate 49, siguiente combate 50), con idénticas comprobaciones de premios y reconexión. r18 instalada en world/base habitual y comprobada healthy; aceptación visual pendiente.

Conexión remota 21 — 🟡 Solucionado parcialmente: configuración directa y proxy de autenticación HTTPS preparados en fuente; cinco pruebas de configuración/login aprobadas; sintaxis y TLS interno comprobados. API real con Store aislado: login, renovación y token de juego aprobados; detectado token inválido con HTTP400. Corrección en fuente devuelve401 preservando solicitudes mal formadas400; ocho pruebas offline y contrato completo de API real con PostgreSQL aislado aprobados (login/renovación/token, rechazos401 y solicitudes mal formadas400). Imagen r19 preparada y contrato de autenticación PostgreSQL aprobado sobre la imagen real; sólo API cambia respecto a r18, combate idéntico. Gate adicional PostgreSQL aprobado: 41/41 sin omisiones. r19 instalada y healthy; 354 módulos idénticos a r18 y sólo API modificada. Conexión desde otro equipo todavía pendiente. Proxy probado contra upstream simulado: login, remember, bearer y rechazo de rutas no autorizadas. Falta autenticación contra world y conexión desde otro equipo con dirección y certificado reales.

Mazmorras 29 — 🔎 En revision: contexto y política por instancia preparados en fuente con 32 pruebas SQL. Hay mapas, conexiones, especies, estadísticas y drops; la composición de monstruos por sala no está acreditada. No se inventarán cantidades, niveles ni posiciones.

Mazmorras 29 — 🔍 En revision: archivo MethodWakfu descargado en paralelo y validado: 87 guías únicas (72 mazmorras, 4 eventos, 11 jefes supremos), 125 URLs con alias y 1.837 imágenes, sin errores. Índice canónico privado preparado para extracción a JSON con evidencia por sala; esquema y guía de extracción disponibles. Extracción completada posteriormente; encuentros todavía no activados en world.

Extracción de mazmorras: ocho agentes Luna procesaron las 87 guías archivadas. Tras la revisión independiente se registraron 221 salas; se corrigieron diferencias entre composición inicial, invocaciones y grupos aleatorios. Los JSON permanecen como evidencia privada, sin activar encuentros ni modificar combate.

Catálogo JSON privado consolidado: `.runtime/local/methodwakfu-dungeons/composition-catalog.json`. Las 87 guías pasan esquema, consistencia y procedencia; ocho pruebas del validador aprobadas. La revisión conserva los datos desconocidos y excluye invocaciones de la composición inicial.

Jalatós: revisión visual de las tres capturas de salas y retratos del bestiario acredita composiciones de 3, 5 y 6 enemigos. JSON completo y revisado; IDs de todas las especies resueltos por nombre francés e intersección con el catálogo nativo de esa mazmorra. Niveles y posiciones de aparición no acreditados todavía; no hay entrada jugable desplegada.

Mazmorras 29 — 🔍 En revision: recorrido de Jalatós derivado automáticamente de terreno y puertas nativos (tres salas). Aparición de grupos por JSON con recibo durable por instancia/sala en fuente; reentrada reutiliza el grupo. Salida, instancias, contexto y entrega: gate PostgreSQL aislado 48/48 (incluye duplicación de fixture de instancias), progresión 9/9. Configuración versionada desde JSON preparada y entrada conectada en fuente: roster y primer grupo se registran en la misma transacción. Coordinador validado con 7 pruebas; Entrada, puertas y salida conectadas en dispatcher en fuente. Gate PostgreSQL de configuración y entrada real de Jalatós: 5/5, incluido rollback del primer grupo y traslado. Enlace combate/sala conectado en fuente; Aborto durable 074 con callbacks conectado en fuente, sin avanzar sala; reconciliación de arranque y reconexión con contexto fijado incorporadas. Reconexión: 2/2 PostgreSQL; aborto/vinculación y regresión: pruebas aprobadas. Revisión de imagen e integración completa pendientes antes del despliegue. Todavía no desplegado. Primero aceptación manual de Jalatós, después importación en bloque.

Jalatós: imagen candidata r20 construida sobre r19 (`1145e8218c44`), sin cambiar world todavía. Comparación automática: 352 módulos existentes idénticos; cambios limitados a callbacks de fight_store, contexto de native_transports y acceso por instancia de teleporter_approach, más módulos nuevos de mazmorras y dispatcher filtrado. Copia de seguridad previa creada. Gates de imagen y recorrido TLS en preparación; aceptación manual completa y bulk siguen pendientes.

Gate inicial de imagen Jalatós: 231 pruebas, 0 skips; dos pruebas estáticas obsoletas de dispatcher actualizadas al flujo conectado (dispatch/delivery 11/11 host). Dos fallos de curación reproducidos idénticamente en r19 y r20, con módulos y tests iguales; no son regresión de mazmorras. Entrada detecta dependencia concreta: puerta26842 está en XY no caminable, y el acceso debe cotejar el punto nativo de interacción. Se investiga antes de desplegar, sin inventar radio de acceso.

Acceso a Jalatós: el cliente define las casillas de interacción con máscara QV por objeto y orientación nativa, no mediante un radio aproximado. Contrato localizado; exportación y regresión en curso. Prueba manual integral preparada en `29-mazmorras-e-instancias/MANUAL-ACCEPTANCE.md`, todavía no ejecutar. Harness TLS de entrada/reconexión preparado y driver real de combate multimonstruo en desarrollo para validar las tres salas.

Jalatós: acceso exterior corregido con máscara y orientación nativas; cuatro regresiones aprobadas, incluida altura y aislamiento de instancia. Las puertas interiores exportan máscara cero y el cliente puede omitir sus acciones: semántica en revisión antes de activar el recorrido. Harness completo de tres combates y salida preparado, aún sin ejecución TLS. World continúa en r19.

Jalatós: imagen candidata reconstruida (`ad0b160b0578`) con acceso nativo y validación estricta, dispatcher actualizado y reconciliación de abortos limitada a instancia. Gate host de los cinco módulos afectados: 29/29, sin skips; nuevo gate de imagen delegado. Sin despliegue ni reinicio de world.

Gate de imagen Jalatós (`ad0b160b0578`): 234 pruebas ejecutadas, sin skips, 232 correctas y los dos fallos de curación conocidos de r19; acceso estricto adicional 4/4. Revisión nativa distingue aceptación del paquete de puerta y disponibilidad del menú: máscara cero deja menú vacío, aunque existe callback por XY exacto. No se considera recorrido manual listo sin acreditar cómo activa el cliente las puertas.

Aceptación TLS de entrada ejecutada sobre world único con base aislada: falló al recibir bootstrap de mapa exterior 527 en lugar de 1086; se investiga rechazo real frente a respuesta pendiente del harness. Restauración automática de imagen r19 confirmada por docker inspect. No se considera entrada validada ni mazmorra desplegada.

Entrada TLS: base aislada confirma cero instancias y cero transiciones creadas, la entrada no llegó a confirmar transacción. Los logs no registran opcode 12296 y muestran desconexión durante movimiento: se revisan respuestas pendientes del harness antes de atribuir rechazo al servidor. Puertas interiores: revisión de bytecode y scripts no acredita productor alternativo del menú con máscara cero. Solicitada captura oficial mínima de primera puerta antes/después de victoria; se continúa validación independiente del servidor.

Jalatós: segunda aceptación TLS de entrada aprobada tras corregir consumo de bootstrap pendiente del harness. Dos clientes en instancia 144115188075855873, primera sala con tres monstruos, recuperación verificada por gate; recorrido completo aún no validado. World restaurado en r19. Captura oficial activa y separada; comparación de manifiestos detecta 22 archivos distintos, incluido wakfu-client.jar, pendiente revisar compatibilidad antes de aplicar estados de puertas.

Recorrido TLS completo: intento no alcanzó ejecución por plazo de arranque de 120 s del runner; world registró listener posteriormente y fue restaurado automáticamente. Plazo de readiness ampliado a 240 s para el siguiente intento, sin alterar combate. Comparación del cliente oficial confirma consumidores de puertas equivalentes con nombres ofuscados distintos; no usar clases antiguas para decodificar la captura nueva.

Captura oficial Jalatós: usuario confirma puerta inaccesible antes de victoria; después abre y dirige automáticamente al personaje, con movimiento interrumpible. Cadáveres quedan en el suelo (implementación pendiente). Opciones de dificultad accesibles dentro de mazmorra permiten bajarla; capturas acreditan niveles12–20 y modo competitivo máximo20. Referencias adicionales de identificación y tienda archivadas sin activar esos sistemas. Análisis de paquetes en curso.

Recorrido TLS completo alcanzó entrada compartida y prueba de puerta bloqueada; harness esperaba aviso674 pero el rechazo real entrega bootstrap13974. Corrección de aceptación del rechazo en curso; no se ha ejecutado todavía la primera victoria del recorrido. World restaurado r19. Captura oficial incorpora cadáveres visibles, Merkamundo y cofre como referencias futuras.

Evidencia oficial de primera puerta: tras victoria llegan dos actualizaciones12344 y el cruce emite12296 para objeto26845/destino2506, modo2. Estado inicial13984 distingue puerta bloqueada y salida habilitada. Decodificación precisa de estados en curso; aún no implementar máscaras supuestas. Harness de puerta bloqueada corregido con invariantes SQL de ubicaciones, progresión y grupos; dos regresiones aprobadas y nueva ejecución completa iniciada.

Nuevos issues originales del usuario: 40 cadáveres, 41 cofre de Merkasaco y 42 tienda personalizada pagada con kamas. Identificación22 y Merkasaco26 incorporan contexto de la captura oficial; apertura de Merkamundo se mantiene distinguida del Merkasaco.

Jalatós: causa concreta del rechazo al iniciar combate identificada: revalidación de NPC reconstruye instancia0 mientras el grupo de mazmorra pertenece a instancia privada. Corrección mínima con validación de pertenencia y regresiones en curso; no modificar estadísticas ni motor. Captura oficial acredita apertura mediante12344: visible primero, utilizable después, manteniendo máscara0; vectors comprobados en ambos clientes. Cambio de dificultad12223 y respuesta13339 decodificados, sin afirmar fórmula de escalado no observada.

Issue40: usuario aclara que cadáveres también existen fuera de mazmorras y no se eliminan por cambiar de sala.12304 acredita retirada de visibilidad del cliente, no desaparición persistente ni plazo. Alcance general del mundo actualizado; no implementar borrado al cambiar de sala como regla.

Jalatós candidata reconstruida (`37a36543ec29`): validación de instancia privada en bootstrap de combate con12/12 pruebas independientes; estados12344 de puertas derivados de progresión fijada incorporados a hidratación de entrada/retorno/reconexión. Helper de apertura en dos fases6/6; integración de bootstrap16/16. Nueva ejecución TLS completa y gate exacto de imagen en curso, no desplegado sobre base habitual.

Gate candidata37a365:251 pruebas sin skips, dos fallos baseline y seis errores por dependencia ajena arrastrada al copiar bootstrap de fuente. Overlay corregido sobre archivo exacto de r19, añadiendo solo pertenencia de instancia; no incorporar módulos de combate ajenos. TLS alcanzó petición de combate pero cerró conexión; no declarar primer combate validado. World restaurado r19.

Cambio de alcance autorizado por usuario: importación masiva antes de aceptación manual. Prioridad inmediata: traslado automático del grupo completo tras victoria, evitando esperar interacción de puertas. Importador y descubrimiento nativo general en paralelo; pruebas deben acreditar dos miembros en grupo y ambos como combatientes en cada sala. No declarar todas las composiciones completas cuando faltan datos. Pausar goal solo después de código, población, validación y caso manual entregados.

Dungeon integration update (2026-10-08): the exact `67aea608` candidate ran 279 automated tests with zero skips; two previously reproduced healing packet-order failures remain unchanged. Five strict teleporter-approach tests pass. The real two-player TLS acceptance remains unconfirmed: the second peer closed before joining the first room fight. The test runner restored the r19 world. Bulk preparation currently yields 24 validated configurations from 87 guides; remaining coverage reasons are explicit and do not count as populated dungeons. Dynamic route loading and automatic whole-party advancement are under integration. Status: **Cambio hecho no confirmado**.

Dungeon follow-up verification (2026-10-08): the packaged `a9d6a689` dispatcher, runtime route registry and harness regression subset passes 24 tests. Atomic bulk installer passes five isolated PostgreSQL tests including replay, immutable route conflict and complete rollback. Refined native discovery now resolves 80 guide identities and provides 68 topologies, with real native routes validated by asset/template destinations rather than assuming `raw_arM` is the physical entrance. Full two-player TLS still fails before joining after the deliberate in-dungeon owner reconnection; this is being isolated and is not acceptance. The manual acceptance document is a draft, not a handoff.

Two-owner dungeon TLS isolation (2026-10-08): removing the early reconnect from the full combat sequence allowed the second participant to join and both owners to enter the active room fight. Acceptance still fails while the harness waits for an NPC turn ACK checkpoint; the checkpoint is active with five actors and no pending ACK. This is new diagnostic evidence, not a passed fight or passed dungeon. The mandatory final exterior reconnection remains in the harness, and the separate in-dungeon reconnection boundary remains unconfirmed. Candidate `3e2f194a` was restored to r19 after the failed run. Safe typography normalization additionally resolves 527 monster-reference occurrences; unresolved references and unknown official rosters remain explicitly documented.

Dungeon bulk refinement (2026-10-08): 527 verified native references were applied with a fresh private backup; the regenerated 87-guide/221-room catalog yields 34 valid runtime configurations and 36 complete resolved rosters. Two-member entry-anchor relocation is now transactional and verified by four isolated PostgreSQL tests, with pinned progress and idempotent replay preserved. The AI-turn TLS harness diagnosis is proven: server-side AI packets are broadcast before the corresponding checkpoint is persisted. The driver now validates the native boundary against the persisted actor/action/turn before ACK; 12 helper regressions pass. Full TLS acceptance is running on candidate `c24d1485`; this is not yet a passed gate or a normal deployment.

Dungeon multi-player progression evidence (2026-10-08): real TLS fight 59 completed the first Jalató room with both owners; its acceptance checks verified exactly two reward receipts and automatic relocation/one next-room spawn. The next join failed because near-entry enemy seeds left only one player placement cell. The generic dungeon formation now separates enemy seeds from the entry anchor and reserves six reachable player slots; native-terrain tests cover all three 3/5/6-enemy rooms and parties of two/six. The protocol-derived NPC limit is 121 (127 total placement actors minus six party slots); migration 076 allocates disjoint 128-ID blocks, with 17 pure and seven PostgreSQL tests passing. Exact candidate `c24d1485` ran 293 tests without skips, with the same two baseline healing-order failures. Whole-dungeon acceptance remains **Cambio hecho no confirmado**; latest candidate `cf434649` is under TLS test.

### Dungeon acceptance progress — 2026-10-08

Status: En revision. Verified guide population now produces 35 native-route-validated configurations; optional generated rosters remain separate and explicitly nonofficial. The two-player TLS acceptance completed rooms one and two with two reward receipts and automatic party progression, but room three failed on an ordinary attack checkpoint timeout. This is not a passed full acceptance. The single world was restored to `wakemu-world:auth-status-20261007-r19`. Investigation continues in the test driver and recorded checkpoints before another complete run.

Automatic final party return passed six PostgreSQL regressions and seven dispatcher tests. Local materialization and same-world acceptance orchestration passed eleven isolated tests. The goal remains active until code, bulk population, full acceptance, and the complete manual case are ready; the user has requested a pause at that point.

Dungeon bulk progress: all 87 guide identities now have explicit roster drafts, including five legacy map registrations checked against native map localization and teleporter criteria. The 82 main catalog dungeons have validated native geometry for all 232 rooms and six-player formations. Legacy integration and its five geometry validations remain in progress; nothing has been bulk-activated in the normal database. Full TLS acceptance is still pending: one later run exposed a 60-second disposable session lease expiring during a 69-second NPC request; the next stopped before combat with a TLS test-peer record-layer error. These findings are being addressed in the test harness, not recorded as gameplay acceptance.

Dungeon return integration diagnosis (2026-10-08): the real two-player fight 67 committed victory, two-player progression, and the next room spawn, but both native return requests failed with `Unknown configured dungeon route`. Relative package imports created a second in-memory route registry that lacked the dynamically installed route. Dungeon runtime imports now share the canonical registry; 62 focused regressions pass, including module identity and dynamic context lookup. All 87 configurations and 246 room geometries are prepared and the isolated PostgreSQL bulk/replay/rollback checks pass. Exact rebuilt-image tests and the complete three-room TLS acceptance remain required before normal activation or the requested goal pause. Status: **En revision**.

Exact-image dungeon gate: `f2fecfad3b5b6255235b896e8c78a9717c9788f8f255a7b83bf17fc499204643` passes all 330 tests across 41 dungeon modules, with zero skips or errors. Ordinary combat files remain identical to the previously checked baseline; its two known healing-order failures are unchanged. Local automatic topology hydration disables unreviewed native teleporters, and private native travel requests are rejected while automatic party transport owns progression. The current full TLS run has verified a real two-player room-one victory and relocation of both characters to room two; later rooms and final exterior reconnection remain under test. The normal database is backed up and has not yet been bulk-activated.

### Dungeon deployment and manual handoff — 2026-10-08

Status: **Cambio hecho no confirmado**. Following Hector's explicit request to launch all configurations and perform manual acceptance himself, all 87 configurations (76 dungeon guides and 11 ultimate-boss guides), covering 246 rooms, were atomically installed into the normal `wakemu_runtime` database. Startup reload confirms 87 registered routes and 87 active context policies. The single healthy world runs `wakemu-world:dungeons-20261008-r20`, immutable image `d408f19d0301e1ac14a3bc4f66b0b78c46a3cebfcf799aabd9178fd26bede9a5`. The database was backed up before deployment. Automatic whole-party travel owns progression and final exterior return; unreviewed native teleporters are disabled for this local policy. Unknown room compositions remain explicitly generated from validated native species; unavailable authoritative access conditions and unsupported item costs are rejected.

Validation: 335 dungeon tests plus three fixture-heartbeat tests pass with zero skips/errors. Atomic all87 install, replay, rollback and 246-room/six-player geometry checks pass. Real two-player TLS runs verified the first two room victories, both rewards and both automatic transfers. Complete TLS acceptance is **not** approved: the final run exhausted a one-hour deadline, so final real victory/exterior reconnection remain for manual acceptance. The ordinary combat hashes are preserved; two pre-existing healing packet-order failures remain unchanged. [Complete manual case](29-mazmorras-e-instancias/MANUAL-ACCEPTANCE.md) and [all87 entry commands](29-mazmorras-e-instancias/INSTALLED-DUNGEONS.md) are ready. Work pauses at Hector's request; this is not completion of the broader goal.


### Heroes / character capacity release candidate (2026-10-10)

Prepared full shared image `wakemu-world:heroes-ready-20261010`; not deployed by this agent. Default character capacity is now **18**, configurable. Main + two owned heroes have real PostgreSQL/native packet/turn validation; native 12093 activation and hero removal flag are included. Gates passed: 73 core, 16 capacity, 7 activation delta, 4 owned-hero lifecycle. Actual native decoder accepted real entity/build/aptitude activation. Full graphical acceptance is pending; see [release and complete manual acceptance](../reports/heroes/HEROES-RELEASE-20261010.md). Tofullero solo boss-to-exit is accepted; group transport/reentry corrections are prepared. Secrets are deferred.

Deployment follow-up: Hector authorized the restart. `heroes-ready-20261010` is running with image `3f904524b08e`, migration applied, HTTP health OK, default capacity 18, and all 687 deployed files verified. Graphical main-plus-two-heroes acceptance is now ready; the earlier “not deployed” entries describe the preparation stage.

Combat deployment regression follow-up: the first heroes image caused missing placement UI in manual acceptance. Initial bootstrap regeneration now runs only for nonempty hero rosters and uses fresh-placement serializers. Empty rosters preserve the original fight and packet objects/bytes. Dispatcher regressions passed 2/2; dungeon recovery/delivery/hydration passed 16/16. Full shared image `heroes-combat-fix-20261010` (`6d3b8bbe24a5`) deployed after user authorization; all 687 deployed files verified and HTTP health OK. Graphical combat acceptance and hero nation/guild UI blocker remain open. An attempted r65 rollback did not start because migration checksums differ; no schema rollback was performed. Prueba Oficios was safely returned to the pinned native exterior and the general recovery fix is included.

Title publication follow-up: manual use consumed scrolls11431/7749 and durably granted title IDs137/68, but the client list was empty. Fixed category7 ownership publication from ft.zU/new flags to ft.zR/fC. Gate41/41 passed and native eST.E ownership, eSX selection, pq actor title passed. Full image `titles-ownership-fix-20261010` (`1b37a0fa9a26`) deployed; 687 files match. No replacement scrolls or new grants are needed. User explicitly accepted normal combat after the bootstrap fix, auras and mount appearances. Title graphical acceptance pending.

## Current heroes and character selection acceptance

Character selection default18 is deployed and accepted by Hector; configurable1–127. Ordinary combat, titles, auras and mount appearances are accepted. Heroes are the primary open task alongside dungeons. The nation replay fix is deployed. Manual testing exposed incomplete hero spell bars, undefined company slots, failed selection/removal, and an empty world after attempting a character change. Server records preserve all three participants across surrender and the second fight; captures show selection/removal failing before a client request is sent. Owned hero hydration now uses complete native format10 rather than remote appearance format11. Two-class native identity/name/book/deck replay and PostgreSQL surrender→return→remove/readd→second-fight regressions pass. Full shared image `heroes-owned-hydration-20261010` (`e788e511df10`) is deployed; all689 running source/migration hashes match. Graphical acceptance remains pending. Spell casting rejection investigation belongs to another agent and is outside this change.

Current priorities are heroes and dungeons. Rift solo play was reported satisfactory within the tested scope; group/final reward acceptance remains incomplete. Eight automated dungeon flows have placement, gates and exits validated; boss ability coverage remains incomplete and is explicitly separate from traversal acceptance.

Pending source verification follow-up: socket response construction now occurs inside the inventory transaction; failures roll back fee, shards and receipts. Native duplicate-equipment sacrifice and shard effect installation remain distinct actions. Combined sockets/equipment/rift/drop-delivery gate69/69 passed; ordinary owned-hero drops16/16 passed. These latest reward/socket changes are prepared, not deployed. Eight physical dungeon candidates passed an isolated PostgreSQL lifecycle with three players using authoritative finished-fight fixtures; this does not validate boss AI, spell mechanics or reward allocation. Heroes UI remains open despite coherent captured inputs; live predicate or complete native UI eligibility reproduction is still being investigated.


## Heroes and dungeon deployment follow-up (2026-10-10)

Current world image `heroes-settlement-fix-20261010` (`002af61cf485`) is healthy; all691 deployed source/migration hashes match. Hero-aware reward policy fixes a finished runtime remaining active in storage after another owned character or a registered summon kills the last enemy. The combined reward/drop gate passes56 tests; terminal heartbeat retry passes3 focused tests. Historical blocked fight155 was privately backed up and cancelled through normal interrupted-fight recovery; its historical rewards were not restored.

Hero company slots remain graphically unaccepted: native owned registry correctly contains main13 and heroes1/6 while the management panel shows empty slots. Native company refresh now follows all owned activations to avoid stale cached references. Same-group snapshots do not emit native ADD events for existing members; further UI listener diagnostics are in progress. Do not report heroes complete.

Eight physical dungeon configurations are active: seven native version3 configurations and accepted Tofullero preserved unchanged. Actual PostgreSQL flow/economy gates cover20 room victories and60 reward receipts; boss ability coverage is still incomplete. See [activated entrances and complete acceptance](../reports/dungeons/AUTOMATIC-PHYSICAL-ACTIVATION.md). Fifteen additional native teleporter sequences were extracted automatically; integration continues.

Client diagnostic follow-up: the old main client was explicitly closed for an instrumented relaunch; tool-launched replacement exits with native abort (exit250, child-6), including an isolated profile. The other account client was preserved. A private host-Terminal launch script is prepared for actual company-slot diagnostics. This is a client launch limitation, not evidence that the empty hero slots are repaired.


### Heroes manual rejection — 2026-10-10 morning

Hector rejected hero acceptance on the current r70 deployment: empty company slots reject additions as full, party portraits show duplicate visual classes, and accepted native12006 switches lose local world/character presentation and spell bars. Actual outgoing1184 bodies carry four distinct correct IDs/breeds (13,1,6,4); actual server12006 logs record successful switches. Native same-map switch handling is being corrected to preserve the existing scene and owned actor objects rather than resetting the original master with13256/13974 or reactivating existing owned actors. These corrections are source-only pending complete validation and deployment; company-slot rendering remains open. Concurrent client startup also overwrote inspector credentials; per-capture private inspector metadata now prevents that race on future launches. Do not count partial serializer proofs as graphical hero acceptance.

Native switch root cause found: the accepted12006 response omitted13440 (`>Bq`, result0 and actual target). Native13440 schedules the real bns/master swap; only after that does the client send12054 (`>q`, target). The corrected dispatcher waits for this matching completion before world/company/party/inventory publication, rejects wrong/stale completions, avoids map reset and repeated owned activation, and clears pending handoff on normal character selection. Saved companies also restore a real missing private party under the current main lease, preserving existing social parties; this supplies native group ADD events after reconnect/disband. Code and native codec/slot oracle are validated; deployment verification follows.


### Native hero handoff release — 2026-10-10 morning

Full shared image `heroes-native-switch-ack-current-20261010` (`2432f5aca5f9`) deploys the missing13440/12054 native switch handshake, deferred publication, scene/actor preservation, pending completion fencing, and legitimate private company-party restoration. Independent dispatcher handlers3/3, isolated PostgreSQL3/3 and hero wire8/8 passed; native ACK decoder/completion encoder and actual bns slot swap oracle passed. All692 image source/migration hashes match the complete checkout. A concurrent shared formatting pass was incorporated in the final image; all48 changed Python syntax trees were identical to the validated implementation. Graphical acceptance of adding/removing heroes, all3 control switches and follow-up combat is still required.

Deployment verification: running `heroes-native-switch-ack-current-20261010` is healthy, game startup completed, and all692 deployed source/migration hashes match. Manual acceptance remains pending; the next complete probe is company slots→three native control switches→remove/readd→three-character combat and return.

### Hero switch black fade follow-up — 2026-10-10

Hector reproduced a persistent black fade switching main19 to hero4. Both12006/13440 and12054 completed; the previous handshake release did not finish the native cinematic. Its actual `dbX` predicate also requires the selected actor's `GUILD_LOCAL_INFO` consumer, including for characters without a guild. Format10 does not contain that component. The completion handler now sends the existing adapted15548 format22 after validating target and session, before joining the world. It preserves owned actor identity and does not modify spell execution.

Full shared image `heroes-fade-guild-20261010` (`a4d98845aadc`) is deployed. All692 production source/migration files match the checkout and running container. Independent dispatcher/hero wire tests11/11 and wire tests30/30 pass. `VerifyHeroGuildFadeCompletion` executes the real client15548 consumer and confirms the actual fade predicate changes false→true while retaining the selected actor. Graphical acceptance remains pending: reconnect, add one hero, switch to it and back, verify scene/UI/control, then repeat with both hero slots. Previous handoff validation alone did not establish this visual behavior.

Hector subsequently confirmed switching improved substantially and combat could be played. New screenshot11:02:53 exposed incorrect current HP3084 and maximum2147483647 after switching. Actual stored actor19 health is70/70; actor4 is997/997. Owned format10 retained captured HP and lacks public characteristics, whose native defaults leave maximum HP at INT_MAX. The prepared correction replaces the HP scalar and follows hero admission/refresh with the existing authoritative exploration progression snapshot. Spell-bar visual ordering remains under investigation: actual actor19 and actor4 spellbook/deck consumers preserve their separate default/saved decks; no spell-execution change or speculative deck rewrite is included.

The health correction is deployed in full shared image `heroes-owned-stats-20261010` (`d66f191476c2`), with all692 running source/migration hashes verified. Automated focused gate41/41 passed. Real native HP/public-characteristic/XP consumers verify actor19 becomes70/70 at level2 and actor4 becomes997/997 at level60; only graphical notifications are suppressed in this headless component oracle. Reconnect and switch each way to verify current/max HP visually. Spell-bar native rendering/eligibility remains open despite correct persisted decks.
