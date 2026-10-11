> 2026-10-11: static spell preparation now reuses validated native LOS data for all 934 maps (158 MiB, 9,632,196 ordered columns exactly equivalent); existing geometry and valid LOS artifacts are preserved. Bounded deck-validation reuse passes 12 tests; LOS fixtures pass 7 tests; combined gate 24/24 passes. Code and data await coordinated world publication. [Scope, measurements and acceptance](../reports/health/SPELL-STATIC-PREPARATION-20261011.md).

> 2026-10-11: prepared geometry is ready for all 934 available native maps (681 MiB), with exhaustive equivalence and 55 passing regressions. Map527 load plus unchanged arena selection measured 3.07s→0.90s locally. Runtime deployment awaits shared-owner coordination; current live image is not claimed updated. [Evidence and acceptance](../reports/health/PREPARED-GEOMETRY-20261011.md).

> 2026-10-10 19:22: the 18:25 combat pause matches a 22.9-second generation-2 collection. World now prepares and freezes its static startup heap before creating live gameplay state; GC remains enabled for future sessions and fights. Ecology rejects obsolete proposals terminally and caps delivery at five attempts, including HTTP failures; exhausted proposals remain archived. The formerly saturated queue has zero pending rows and ecology is healthy. Automated checks and residual 4–7-second AI search latency are recorded in [incident investigation](../reports/health/LIVE-SLOW-COMBAT-20261010-1825.md). Fresh combat and planting acceptance remain pending.

> 2026-10-10: ecology extraction is deployed in external mode in the shared world/ecology images; services and stop/restart/query smoke checks pass, manual gameplay acceptance pending. World records durable events without an ecology HTTP wait, while the separate worker prepares ecological changes and world retains final gameplay checks. [Architecture and acceptance](../reports/health/ECOLOGY-EXTRACTION-ACCEPTANCE-20261010.md), [service contracts](../reports/health/ECOLOGY-SERVICE-INFRASTRUCTURE-20261010.md).

> 2026-10-10: cautious optimization batch limits profiler downloads to 64 KiB reads; 21 service and 15 acceptance tests passed. No gameplay changes or world restart. [Implementation, rejected candidates and acceptance](../reports/health/CAUTIOUS-OPTIMIZATION-20261010.md).

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

Read the closed and open tables first. User decisions updated on 2026-10-11 supersede historical acceptance notes below. Current source and deployed image must be verified separately; older image tags are release history.
Source and deployed code are compared per investigation, not assumed globally
identical. Focused checks do not constitute a passing full suite. Shared combat
and performance behavior must be preserved throughout this review.

Complete staged-system acceptance: [exact commands, steps and expected results](../reports/SYSTEMS-ACCEPTANCE-20261011.md). Run after a coordinated complete deployment; the document distinguishes unimplemented contracts and pending graphical checks.

## Closed issues

Only closed and accepted scopes appear here. Accepted limitations remain explicit.

| Issue | Current status | Evidence / remaining scope |
| --- | --- | --- |
| 1 — [Las semillas solo disminuyen al reconectar](01-semillas-sin-refresco/README.md) | ✅ Closed — Accepted | Immediate consumption/refresh. |
| 2 — [Un bebé tofu nunca crece](02-maduracion-de-monstruos/README.md) | ✅ Closed — Accepted | Balance adjustments are separate. |
| 3 — [Los monstruos no se reproducen ni amplían grupos](03-reproduccion-sin-respawn/README.md) | ✅ Closed — Closed by Hector | Current reproduction accepted and closed by explicit instruction on 2026-10-11. New reproduction/growth changes belong to a new issue. |
| 4 — [El porcentaje de plantación mostrado no es real](04-probabilidad-de-plantacion/README.md) | ✅ Closed — Closed with accepted limitation | Hector accepts the ordinary profile’s fixed visual1% as the final limitation. This does not describe the actual server roll. Optional native mode remains inactive and is not a closure requirement. [Evidence](../reports/PLANTING-PROBABILITY-20261011.md). |
| 5 — [Plantas y árboles (Cardo, fresnos y otros) aparecen como recursos ajenos](05-permisos-y-recoleccion-de-cardo/README.md) | ✅ Closed — Accepted | Preserve public flora harvesting. |
| 6 — [Cardo no llega a su etapa final](06-etapas-completas-de-cardo/README.md) | ✅ Closed — Closed by Hector | All146 plantable trees, cereals and plants reviewed:401 growth edges and88 optional variants. Durable seed-harvest regrowth correction verified. New graphical defects belong in a new issue. |
| 7 — [No sube Wakfu ni Stasis](07-wakfu-y-stasis/README.md) | ✅ Closed — Accepted | Preserve confirmed ecology progression. |
| 8 — [No aumenta la experiencia de los oficios](08-experiencia-de-oficios/README.md) | ✅ Closed — Accepted | Gathering, planting and tested crafting. |
| 9 — [No hay experiencia ni subida de nivel por combate](09-experiencia-de-combate/README.md) | ✅ Closed — Accepted | Preserve transactional rewards. |
| 11 — [No se puede intercambiar con otros personajes](11-intercambio-entre-personajes/README.md) | ✅ Closed — Accepted by user | Historical partial-stack reports retained as historical evidence. |
| 14 — [No se puede entrar al combate de otra persona](14-unirse-a-combates/README.md) | ✅ Closed — Closed by Hector | Joining combat works generally; explicitly accepted and closed on 2026-10-11. |
| 15 — [No hay grupos de jugadores](15-grupos-de-jugadores/README.md) | ✅ Closed — Accepted | Invitations, membership, leadership, dissolution and group chat. |
| 16 — [No se pueden ver los combates](16-espectadores-y-marcadores/README.md) | ✅ Closed — Closed by Hector | Spectating works generally; explicitly accepted and closed on 2026-10-11. |
| 18 — [No se puede elegir hacia dónde mirar en colocación](18-orientacion-en-colocacion/README.md) | ✅ Closed — Accepted | Peer visibility remains E23. |
| 19 — [Todos los monstruos se mueven a la vez](19-movimiento-aleatorio-eficiente/README.md) | ✅ Closed — Accepted | Global performance is issue0. |
| 20 — [Pocos mobs iniciales, reproducción y pausa sin jugadores](20-poblacion-inicial-y-zonas-activas/README.md) | ✅ Closed — Accepted observed maps | Published runtime catalog scope must not be inferred from an absent checkout asset. |
| 23 — [Bolso Sadida apilado rompe la interfaz hasta reiniciar](23-bolso-sadida-apilado/README.md) | ✅ Closed — Accepted | Preserve split/equip/reconnect behavior. |
| 27 — [Clima](27-clima-por-zona/README.md) | ✅ Closed — Closed; accepted by Hector | Regional weather and forecast deployed and automatically verified (109-test gate and native oracle). Hector confirms "Clima ok" on2026-10-11. [Report](../reports/REGIONAL-WEATHER-20261011.md). |
| 30 — [Mesas de oficio ausentes o inoperantes](30-mesas-de-oficio-y-crafting/README.md) | ✅ Closed — Accepted by user | Guest bag workshop authorization is separate issue26. |
| 32 — [Permiso `is_admin` para comandos `!` del chat](32-roles-admin-y-comandos/README.md) | ✅ Closed — Accepted | Preserve authorization boundaries. |
| 36 — [El botón de reciclado no hace nada](36-destruir-objetos/README.md) | ✅ Closed — Closed by Hector | Recycling works; accepted and closed on 2026-10-11. Any optional catalog expansion is separate. |
| 38 — [No se pueden eliminar personajes](38-eliminar-personajes/README.md) | ✅ Closed — Accepted | User confirms the deletion journey works perfectly. |
| 39 — [No se puede alimentar al dragopavo o mascotas](39-alimentacion-monturas-y-mascotas/README.md) | ✅ Closed — Closed by Hector | Feeding/mount issue explicitly closed on 2026-10-11. |
| 40 — [Monster corpses after combat](40-cadaveres-de-monstruos/README.md) | ✅ Closed — Closed; accepted by Hector | Hector confirms seed extraction works on2026-10-11; one-hour expiry was already accepted. Server-only harvesting consumes the corpse atomically;59-test gate and native menu oracle passed. [Evidence](../reports/corpse-server-menu-visibility-20261011.md). |
| 41 — [Haven Bag chest](41-cofre-de-merkasaco/README.md) | ✅ Closed — Accepted by Hector | User confirms: Cofre funciona perfecto. Shared account storage and transfers; recorded automated verification remains valid. |
| 44 — [Aprendizaje y apariencia de trajes](44-aprendizaje-y-apariencia-de-trajes/README.md) | ✅ Closed — Titles, costumes, emotes, auras and mount appearances accepted | Hector confirms titles work after the owned-list publication correction. Emotes default unlocked with configurable locking policy. Sprint and other cosmetic categories remain separately unaccepted or unsupported. |
| Character capacity (additional request) | ✅ Closed — Accepted | Default18, configurable1–127; character selection accepted by Hector. |
| Mining veins (additional review) | ✅ Closed — Accepted by Hector | 2,881 available fixed veins on 46 maps cover all 51 mineral references. World/ecology restarted with complete current source; 70 focused PostgreSQL/navigation tests and 5 startup tests pass. Mining navigation uses a separately pinned SQL release, leaving the global gameplay catalog and AI configuration unchanged. Default respawn: 300 seconds. Manual command and deployment evidence: [installed veins](../reports/mining/DEPLOYED-VEINS-20261010.md). |
| E01 — [Corrupción histórica de SQLite interrumpe crecimiento](E01-corrupcion-sqlite/README.md) | ✅ Closed — Closed in recorded scope | Previously accepted/resolved in their recorded scope. |
| E03 — [API de pruebas ejecuta antes de autenticar](E03-api-test-sin-autenticacion/README.md) | ✅ Closed — Closed in recorded scope | Previously accepted/resolved in their recorded scope. |
| E04 — [Activación 13776 sin handler](E04-activar-build-sin-handler/README.md) | ✅ Closed — Closed in recorded scope | Previously accepted/resolved in their recorded scope. |
| E07 — [Borrado nativo de build sin handler](E07-borrado-de-build-sin-handler/README.md) | ✅ Closed — Closed in recorded scope | Previously accepted/resolved in their recorded scope. |
| E08 — [Capacidad 24 en interfaz versus índices 0–2 en validación](E08-limite-de-builds-inconsistente/README.md) | ✅ Closed — Closed in recorded scope | Previously accepted/resolved in their recorded scope. |
| E10 — [Actualización equipment_set no crea entradas nuevas](E10-equipment-set-omite-build-nueva/README.md) | ✅ Closed — Closed in recorded scope | Previously accepted/resolved in their recorded scope. |
| E14 — [Consumibles en barra rápida no persisten](E14-consumibles-barra-rapida-no-persisten/README.md) | ✅ Closed — Closed in recorded scope | Previously accepted/resolved in their recorded scope. |
| E16 — [Monstruos con nombre «Grupo local»](E16-nombres-genericos-monstruos/README.md) | ✅ Closed — Closed in recorded scope | Previously accepted/resolved in their recorded scope. |
| E20 — [Colocación no termina cuando el contador llega a cero](E20-colocacion-no-expira/README.md) | ✅ Closed — Closed in recorded scope | Previously accepted/resolved in their recorded scope. |
| E05 — [Selección no persistida y deck 0 fijo](E05-seleccion-build-y-deck-cero/README.md) | ✅ Closed — Closed after final source verification: 26 build tests passed, including distinct active decks in real combat after reopen and inactive-build edits | Closed after final source verification: 26 build tests passed, including distinct active decks in real combat after reopen and inactive-build edits. Active selection and modulated fallback decks are preserved; deployed2026-10-11. |
| E09 — [Hit Redis conserva lecturas SQL e inicializaciones repetidas](E09-sql-redundante-con-redis/README.md) | ✅ Closed — Closed by Hector | Closed by Hector. Explicitly closed on 2026-10-11; obsolete cache architecture diagnosis retired. |
| E13 — [Canales de chat en general](E13-canales-de-chat/README.md) | ✅ Closed — Closed; merged into 13 | Closed; merged into 13. Explicitly closed in favor of issue13; all remaining chat scope tracked there. |

## Open issues and additional requests

Runtime recovered2026-10-11 21:24UTC: all nine existing services are running; every configured healthcheck passes. Recovery preserved the last published images/catalog. Systems completion remains prepared but unpublished while shared monster recovery is unqualified. [Prepared publication scope](../reports/SYSTEMS-COMPLETION-HANDOFF-20261011.md); [single complete manual journey](../reports/SYSTEMS-ACCEPTANCE-20261011.md).

These issues remain open until the stated implementation and acceptance work is complete. Deployment status is tracked per feature.

| Issue | Current status | Evidence / remaining scope |
| --- | --- | --- |
| 0 — [Retrasos al iniciar combates y lanzar hechizos](00-rendimiento-y-redis/README.md) | 🟡 Improved, open | Current complete deployment includes r72 performance changes. Automated focused checks pass; residual live latency, client UI delay and duplicate interactive publication remain under the other agent. |
| 10 — [No hay drops ni kamas](10-drops-y-kamas/README.md) | 🟡 Open — Steles and dungeon difficulty deployed; score and rarity caps verified; deployment pending | Steles, Stasis/competitive modulation and existing drop-context modules are present in the complete deployed image, confirmed by source hashes. Damage-score lifecycle integration and configurable local rarity caps are complete after that build. All268 score-conditioned rows now have local profiles: Ogrest/Rushu/Neoogrest20 rounds, Love Royal Gobball3 rounds or a legitimate early boss defeat. Final profile/runtime/dispatcher/checkpoint gate18/18 passed through migration141. Separate monster playability remains unqualified for Ogrest/Rushu/Neoogrest; score coverage does not enable them. Independent integrated gate61/61, actual readiness dispatcher3/3 and terminal-reward/checkpoint1/1 passed; the configured survival encounter finishes after its complete round budget. Local caps per item/recipient/fight default to unlimited common/unusual, rare6, mythic3, legendary2, relic/PvP/epic1, admin0; scope and values are configurable; the686 opaque-complex rows remain disabled. Full dungeon/drop acceptance remains pending. [Deployment check](../reports/SYSTEMS-DEPLOYMENT-CHECK-20261011.md); [steles](../reports/NATIVE-DUNGEON-STELES-20261011.md); [coverage](../reports/DROP-CRITERIA-COVERAGE-20261011.md); [score rules and acceptance](../reports/BOSS-SCORE-AUTHORITY-20261011.md); [configurable rarity limits](../reports/LOCAL-DROP-RARITY-ALLOCATION-20261011.md). |
| 12 — [No se puede pelear contra otros personajes](12-duelos-pvp/README.md) | 🟡 Expired-invitation retry regression corrected in r64; live acceptance pending | Finite quarantine and stale-reply protection covered by isolated PostgreSQL tests; challenge/return lifecycle must be reconfirmed. |
| 13 — [Mensajes privados y otros canales de chat](13-chat-privado-y-canales/README.md) | 🟡 Nation routing deployed; admin rights and intergame verified; deployment pending | Canonical nations/enrollment and native World recipient routing remain authoritative. Native /a rights derive only from trusted accounts.is_admin; ordinary accounts have ADMIN_CHAT cleared (historical39-test gate). The same trusted role now projects native ACCESS_ADMIN_DATA115 for Ranch visibility; both permissions are granted/revoked together while preserving all other bits and native fields (new5/5 focused tests). Next deployment pending. Native /d requires a separate authenticated TLS/Spin/protobuf service: backend, genuine HAAPI token endpoint and same-World listener are complete and verified (20 protocol/auth/HTTP tests and4 lifecycle tests), not deployed. Original native decoders and recipient directory also pass. Graphical acceptance remains pending. /b is BLOCKED at Hector's request: eligibility is fixed in the installed client world catalog to7 battleground maps (1161,1203,1217,1218,1219,1277,1279); enabling it on ordinary maps cannot be achieved with World routing alone under the no-client-change rule. /f is also BLOCKED at Hector's request: the native client additionally requires government office; citizenship alone does not unlock sending. The original physical nation board20158/map527 now opens the existing chooser through native READ28;10 helper/actual-dispatcher/PostgreSQL tests and original producer/consumer oracles pass, deployment pending. [Board and walkable approach](../reports/NATIVE-NATION-BOARD-20261011.md). No replacement !politica/!jcj commands. [Native eligibility](../reports/NATION-CHAT-NATIVE-ELIGIBILITY-20261011.md). |
| 17 — [No se pueden subir características](17-aptitudes-y-calculo-de-estadisticas/README.md) | 🟡 Core accepted; equipment identity/publication review open | Mount level0→0 and level2→1 mastery were accepted by Hector and match native floor(level×0.8); that rounding is not an open zero-stat defect. Actual Store/PostgreSQL same-reference two-UID test passes: feed A only, reject B deletion while an inactive build owns it, remove the saved reference, delete B only and reopen with A/food intact. Independent original-JAR replay and the original13078 handler pass for separate UID/XP/level records. New actual server-packet replay through the original BAGS/12470/12471 physical inventory handlers also passes independent Luna verification: A0/B0→A100/B0 preserves UID, then deletingB leavesA100. [Physical publication proof and GUI boundary](../reports/BUILDS-PHYSICAL-MOUNT-PUBLICATION-20261011.md). A pre-opened native panel retains its old pet object in this bounded replay; the full graphical rebind/physical-item path remains unverified, so no live panel fix or closure is claimed. New confirmed server publication defect: actual equipment-removal format3 omits zero rows, and the original native consumer retains the previous stat (9 instead of0); the canonical full payload resets it correctly. Server correction is verified: the same original consumer now receives9→0 after equipment removal; native baseline, resource overrides and equipment-return regressions pass5/5. The correction is not deployed. [World build-stat reset proof](../reports/SELECTED-BUILD-RUNTIME-CONSUMERS-20261011.md). [Current source and native observer audit](../reports/BUILD-STAT-SOURCE-AUDIT-20261011.md); [accepted scaling](../reports/health/MOUNT-IDENTITY-REVIEW-20261009.md). |
| 21 — [Tools con configuración `.env` del servidor](21-conexion-remota-y-configuracion/README.md) | 🟡 Manual acceptance pending | Connection from another device remains to be tested by Hector. |
| 22 — [Objetos sin identificar](22-identificacion-elementos-y-encantamiento/README.md) | 🟡 Open; assigned to another agent | Implementation and validation owned by the other agent. [Complete effects inventory](../reports/sublimation-combat-inventory/README.md); [source review](22-identificacion-elementos-y-encantamiento/SOURCE-REVIEW-20261011.md). |
| 24 — [Pasaporte de Amakna por defecto](24-nacion-y-pasaporte-neutral/README.md) | 🟡 Entry-packet correction deployed; new graphical acceptance pending | The older visual failure predates the format22 NATION_ID correction. Direct installed-World execution passes3 targeted neutral/enrolled/roster regressions; original passport consumer has no zero-to-Amakna fallback. This does not prove the historical session root cause or current rendered UI. [Current deployed-source/native consumer review](24-nacion-y-pasaporte-neutral/STATUS-REVIEW-20261011.md). |
| 25 — [Brechas dimensionales](25-brechas-dimensionales/README.md) | 🟡 Gameplay accepted;50× rewards deployed; final acceptance pending | The active image contains the verified50× ordinary XP/kamas implementation for actually killed original rift monsters, including partial waves; living monsters and summons excluded. Immutable receipts prevent replay.55-test gate passed; final graphical rewards acceptance pending. [Reward evidence](../reports/RIFT-CURRENCY-REWARDS-20261011.md); [deployment check](../reports/SYSTEMS-DEPLOYMENT-CHECK-20261011.md). |
| 26 — [No se pueden añadir merkagemas](26-insertar-y-retirar-merkagemas/README.md) | 🟡 Public guest access deployed; acceptance pending | All room types publicly accessible; guest garden/worktable uses own inventory and rewards. Owner-only gem/furniture/chest/configuration guards retained. Full eight-module guest/persistence gate passed:60 tests. |
| Haven Bag zaap (new request) | 🟡 Portal integration written; current repair not yet deployed | Visible blue portal is native RanchEntrance36028, not an ordinary Zaap. Native scene hydration, source/action/lease checks, separate Ranch session, movement/refresh and parent return are now integrated in current server code; historical actual-source Ranch/bag/static and chest regression gates passed80 tests. Fresh selected-character SQL inventory/administrator authorization now protects entry and biome switching: real item32864 or trusted administrator required, without consumption; returning remains allowed after access is lost. New affected gate26/26 passed, including4 isolated PostgreSQL cases and actual dispatcher execution; native administrator-data projection separately passed5/5. These corrections are not deployed. Six native biome choices inventoried; action35/map1440 has qualified terrain. The other five are original developer/admin-gated placeholders: zero dynamic slots, no world declarations and no map assets in the installed manifest; rejected safely. Raw catalog has7 biomes, but the portal references only6; biome7/map1034 is not a portal choice. [Original source/criteria inventory](../reports/HAVEN-RANCH-SOURCE-DISCOVERY-20261011.md). All45 ordinary Zaap destinations are inventoried. [Implemented portal and complete acceptance](../reports/HAVEN-RANCH-PORTAL-20261011.md); [audit](../reports/HAVEN-BAG-ZAAP-AUDIT-20261011.md); [ordinary destinations](../reports/HAVEN-BAG-ZAAP-DESTINATIONS-20261011.md). |
| Random native combat borders (new request) | 🟡 Implemented and automatically verified; deployed; graphical acceptance pending | Default native pool46/48 selects once per durable fight (50/50 MP/AP) and persists with its placement layout. Dispatcher and duels consume the same pinned reference. Native handler/proof/AST checks passed; corrected SQL placement/duel gate9/9 passed with131 migrations and unchanged sources. Original native branches remain unchanged; full graphical session acceptance pending. [Native inventory and acceptance](../reports/NATIVE-RANDOM-COMBAT-BORDERS-20261011.md). Complete inventory:103 native borders,142 root references and307 recursive effects, independently matched to the active catalog. Other101 remain uncertified. [Complete inventory](../reports/combat-inventory/native-border-complete-inventory-20261011.md). |
| Combat cell pointing / tactical markers (new request) | 🟡 Implemented and deployed; graphical acceptance pending | Native cell ping and8 icons, own-team visibility, lease/geometry validation,5-second ping cooldown and late-join replay integrated. Selected automated gates and native five-opcode oracle pass. Complete combat visual acceptance pending; separate from personal world-map notes. Sender and allies explicitly verified for all8icons and ping/removal; enemies/spectators excluded. Independent gate8/8 passed. [Protocol, recipients and acceptance](../reports/COMBAT-TACTICAL-MARKERS-20261011.md). |
| 28 — [Bonus de área](28-bonus-de-area/README.md) | 🟡 Deployed and automatically verified; graphical acceptance pending | Native world13046 refresh updates regional Wisdom/Prospection and explicitly clears zero values. Bounded worker snapshots now refresh stationary players through their owner session, preserving HP/build and fencing stale epochs, revisions, leases and location. No weather repetition or unchanged stat spam. Integrated80-test gate and updated module15-test gate passed. Deployed2026-10-11 with coherent World/worker images; graphical acceptance pending. |
| 29 — [Mazmorras](29-mazmorras-e-instancias/README.md) | 🟡 Stasis/competitive implementation deployed; acceptance pending | Persisted native1–10 selection, competitive level bands, frozen reward curves and custom automatic modulation are in the active complete image. Qualified HP/damage initialization and entry/exit/recovery gates passed; Hector still needs to test the complete dungeon system. [Difficulty authority](../reports/DUNGEON-DIFFICULTY-AUTHORITY-20261011.md); [deployment check](../reports/SYSTEMS-DEPLOYMENT-CHECK-20261011.md). |
| 31 — [Configuración repetida de celdas durante colocación](31-diversidad-de-celdas-de-colocacion/README.md) | 🟡 Implemented, unaccepted | Complete visual variety/coherence acceptance; coordinate with other combat agent. |
| 33 — [Rendirse deja bloqueados nuevos combates y transporte](33-rendicion-y-retorno-al-mundo/README.md) | 🟡 Open; Hector testing pending | Complete surrender acceptance remains for Hector; preserve previously accepted individual behavior. |
| 34 — [Builds personalizadas: desbloqueo tardío y hojas no seleccionables — prioridad alta](34-builds-personalizadas/README.md) | 🟡 Modulation corrections deployed; graphical acceptance pending | Default decks now use each sheet effective level; authoritative selection/health reviewed. Level-up owned spellbook and roster refresh integrated; selected level/mount publication gate9/9 passed, with explicit mock/native coverage limits. The newly confirmed world-publication stale-stat defect is corrected and verified5/5 plus original-JAR9→0 replay; this correction is not deployed. [Selected-build runtime proof](../reports/SELECTED-BUILD-RUNTIME-CONSUMERS-20261011.md). Full visual49/50/51 and modulated build acceptance pending. [Current source and publication audit](../reports/BUILD-STAT-SOURCE-AUDIT-20261011.md). Current-source competitive modulation and dependent instance lifecycle gate49/49 passed with unchanged production hashes: world/combat profile parity, owned selection/wounds restoration, hero reconnect, temporary-sheet immutability and transactional entry rollback. This does not certify the unresolved physical equipment panel refresh. [Current verification receipt](../reports/SYSTEMS-COMPLETION-HANDOFF-20261011.md). |
| 35 — [Zaap no seleccionable](35-zaap-no-seleccionable/README.md) | 🟡 Provisionally accepted interactives | Worktable confirmation alone does not close complete travel coverage. |
| 42 — [Custom shop paid with kamas](42-tienda-personalizada-por-kamas/README.md) | 🟡 Basic purchase manually confirmed; expanded catalog pending | Jalamartillo 2027, DB-configured 1,000 OG/kamas shared wallet, atomic purchase microservice. |
| 43 — [Secretos de exploración](43-secretos-de-exploracion/README.md) | 🟡 Deferred by explicit user instruction | Existing artifacts and movement-power implementation retained; do not spend current acceptance time on secrets. |
| Heroes — [Sistema de héroes](../reports/heroes/HEROES-RELEASE-20261010.md) | 🟡 Switch fix deployed; manual acceptance pending | The active complete image includes transactional hero health initialization and migration136. Missing baselines are initialized without resetting existing clocks, wounds or death. Actual-source23-test gate and original-source/database4-test gate passed. Reconnect and switch existing/newly selected heroes for final acceptance. The disconnect interrupted the compass test; no causal connection to the compass defect was found. [Deployment check](../reports/SYSTEMS-DEPLOYMENT-CHECK-20261011.md). |
| Personal map destination / minimap / compass (new request) | 🟡 Blocked — Hector requested deferral; no server-only repair demonstrated | Hector confirms both ? and downward-arrow markers persist on the big map and appear on the minimap after returning from character selection, but not immediately after creation. Neither requires text. Original arrow34 and silver?30 both create personal notes, without invoking the compass. Native palette drag saves notes.dat and refreshes only the full-map registry; the separate minimap registry reloads on world-context assignment. No packet sends note coordinates; the server cannot publish or convert that note into a compass target. Native chat-name Mostrar independently creates a compass target for another visible actor. Offline native lifecycle verified; graphical Mostrar acceptance pending. No client changes authorized. [Complete lifecycle audit](../reports/minimap/NATIVE-NOTE-LIFECYCLE-AUDIT-20261011.md). |
| Ecosystem species list (new request) | 🟡 Server correction deployed; graphical acceptance pending | Active image contains regional named/unique family publication within the native three-slot contract. Removed107 global seed families from every regional list.39 tests cover274 regions and four locales. [Evidence and acceptance](../reports/ECOSYSTEM-LIST-20261011.md); [deployment check](../reports/SYSTEMS-DEPLOYMENT-CHECK-20261011.md). |
| Wells, candles and other interactives (new request) | 🟡 Wells/lights deployed; seats staged; remaining contracts inventoried | Full961-archive/31,238-chunk audit:11,987 known objects in48types,3 raw unknown type53 and81 separate legacy candidates. Two ordinary wells grant100 water;446 ordinary lights supported. Additional water pickup1337 is a30% lottery; quest well2307 is an Ogrest cinematic, not free water. Stool dispatcher is now integrated;7 PostgreSQL regressions verify occupancy, same-generation actor changes and certified animations.2,504 common placements qualify;37 restricted/missing-template placements stay denied. Actual-source environment/Ranch/static compatibility gate43/43 passed, including SQL cleanup retry and allied scene updates. Additional seat definitions use additive migration141; deployment remains pending. Physical nation board is also qualified (10 tests), not deployed. Native boats are integrated with13 pure/dispatcher and5 PostgreSQL tests passed: original393 bidirectional links, supported ordinary/level criteria, no guessed arrivals. [Boat/Cannon contracts and round trip](../reports/NATIVE-BOAT-AND-CANNON-20261011.md). 33 ordinary doors are also integrated:13 unit/source checks,3 executed dispatcher/movement/scene checks and a real PostgreSQL state/collision test pass. [Door scope and acceptance](../reports/NATIVE-ORDINARY-DOORS-20261011.md). These additions are not deployed. [48-type semantics and remaining work](../reports/ENVIRONMENT-INTERACTIONS-20261011.md), [exact water sources](../reports/ENVIRONMENT-WATER-SOURCES-20261011.json), [per-object CSV](../reports/ENVIRONMENT-OBJECTS-20261011.csv). |
| Account bans (new request) | 🟡 Deployed; real HTTP sanction journey passed; visual acceptance pending | Permanent/timed bans, audited English dashboard actions, atomic token/session revocation and login/world enforcement. Focused37-test aggregate passed. Real authenticated HTTP journey passed on disposable account: CSRF/reason guards, permanent/timed bans, expiry, token/session revocation, unban and logout. Account left clean. Real TLS world session closed0.719s after dashboard ban. Authenticated visual editor acceptance remains pending. Additional live-session/account-FK lock-order correction passed32/32 bans/auth/admin regressions and is staged, not deployed. |
| NPC placement, dialogue and quests (new request) | 🟡 ALL recoverable original placements now prioritized; bulk import in progress | Hector prioritizes placing every recoverable NPC before further dialogue work. General position-only import in migration144 and actual scene/replay hooks is verified:5/5 pure/source tests,1/1 isolated PostgreSQL test through144 and10/10 original native packet/action-mask decodes. Deployment remains pending. All684 captured records/33breeds were classified:10 accredited noncombat NPC identities,670 non-NPC records and4 duplicates. Existing dialogue actors are excluded dynamically, adding5 physical actors without guessing roots; all unproven native actions are disabled. The101 exact protector locations lack sufficient physical-actor bindings for additional spawns;1,143 Lua coordinate occurrences were also reviewed without inventing map authority. [Complete placement inventory and limits](../reports/npc-dialogue/BULK-POSITION-RECOVERY-20261011.md). Deployed image contains Grugal original map1387(-12,0,2), action1238→root5764, quarantine of4 incorrect trial placements and captured foreign-map replay filtering;27 tests passed. Broader source recovery now inventories422 conversational identities, with genuine captured B.Tóven4069/map527 and Mod’Ulo4399/map9 positions also recovered; their initial roots remain unproven. Three more original initial scenes (Huly, Kheperalia, Airyna) and verified objective criteria are integrated and passed31 tests, including3 PostgreSQL cases; these post-build changes are not deployed. A fifth accredited initial binding, Otomaï5459/map1385(20,17,1)→root5772, is integrated separately in migration142 with its original PROTECTOR424 identity and native actor registration; Offline domain/native-oracle checks and24 actual-bootstrap/dispatcher integration tests pass; six isolated PostgreSQL tests through142 also pass. Deployment and graphical acceptance remain pending. A new protector-identity cross-check confirms B.Tóven303 and native placements/dialogue portraits for Suricasso442 and Arlemia414; their initial-root edges remain unproven, so no speculative scenes are enabled. [Protector frontier](../reports/npc-dialogue/NATIVE-PROTECTOR-DIALOGUE-FRONTIER-20261011.md). Complete protector/action/dialogue schema review confirms B.Tóven action798 requests the root from the original server; the missing edge is its12969 response, not an omitted client export field. [Initial-binding schema evidence](../reports/npc-dialogue/NATIVE-PROTECTOR-INITIAL-BINDING-SCHEMA-20261011.md). New original capture recovery identifies29 exact choice→node transitions across these5 speakers/7 observed roots, with zero conflicting targets. Current continuation integration is in progress: the previous adapter closed initial choices and rejected later nodes. Only source-qualified current roots and native criteria may authorize continuation; later story roots and quest/reward side effects remain unimplemented. [Observed dialogue branches](../reports/npc-dialogue/ORIGINAL-OBSERVED-DIALOGUE-EDGES-20261011.md). Extracted4,599 dialogue nodes and3,278 quest definitions are not all playable. [Original recovery](../reports/npc-dialogue/ORIGINAL-CAPTURE-DIALOGUE-RECOVERY-20261011.md); [all422 NPC coverage and3 new initial bindings](../reports/npc-dialogue/NATIVE-NPC-COMPLETE-COVERAGE-20261011.md); [script source ledger](../reports/npc-dialogue/NATIVE-LUA-ACTOR-SOURCE-LEDGER-20261011.md). |
| Fishing spots (additional review) | 🟡 Installed; graphical acceptance pending | 3,377 installed fixed spots cover 51 supported references on 40 maps. World/ecology are healthy; 144 focused tests pass and both exhaustion forms restore through the live worker. Native fishing range is three tiles, with both deletion and empty-stage exhaustion restored after 300 seconds. Opaque encounter reference 306 remains excluded. Independent compact navigation catalog preserves the global gameplay catalog. [Behavior and complete manual acceptance](../reports/fishing/DEPLOYED-FISHING-20261010.md). |
| Default professions (additional request) | 🟡 Deployed and automatically tested; entry acceptance pending | All15 catalog professions learned at level0 on world entry for new and existing accounts; existing progress preserved. Profession suite10/10 passed. |
| Forced combat outcomes (additional request) | 🟡 Implemented and automatically tested; not deployed | Authorized `!winfight` and `!losefight` end an active fight through normal settlement for the complete team. Combat command and lifecycle regression gate59/59 passed. See [manual acceptance](../reports/COMBAT-OUTCOME-COMMANDS.md). |
| Nearby group combat invitation (additional request) | 🟡 Implemented and automatically tested; not deployed | Native join modal for nearby online party members on the same map and instance; native acceptance12197 and manual join13241 share the authoritative join handler. Ten focused tests and the62-test shared combat regression gate passed; refusal/timeout do not join. Graphical acceptance remains pending. Client assets unchanged. See [complete acceptance](../reports/GROUP-COMBAT-JOIN-PROMPT-20261010.md). |
| E02 — [Recuperación de inventario 13713 serializa bolsas como entidad](E02-resincronizacion-inventario-invalida/README.md) | 🟡 Inventory recovery implemented; malformed-recovery UI acceptance pending | Inventory recovery implemented; malformed-recovery UI acceptance pending. |
| E06 — [Subida de nivel parcialmente confirmada con hoja fija inválida](E06-nivel-y-hojas-sin-atomicidad/README.md) | 🟡 Level/library refresh deployed; graphical acceptance pending | Level/library refresh deployed; graphical acceptance pending. Native15548 owned spellbook and23548 real-level roster refresh integrated after !nivel; no activation/map reset. Modulation fallback corrected; nine selected publication/scaling tests passed. The former format3-only source gap is superseded;49/50/51 graphical acceptance pending. [Current source review](../reports/BUILD-STAT-SOURCE-AUDIT-20261011.md). |
| E11 — [Prueba de desplazamiento sin terreno exportado — reservada a otra sesión](E11-test-desplazamiento-sin-terreno-exportado/README.md) | 🟡 Historical fixture/terrain issue, reserved to another session | Historical fixture/terrain issue, reserved to another session. |
| E12 — [Curación al alternar aptitudes](E12-curacion-al-alternar-aptitudes/README.md) | 🟡 Wound preservation implemented; controlled regeneration acceptance pending | Wound preservation implemented; controlled regeneration acceptance pending. |
| E15 — [Sistema completo de gremios](E15-gremios/README.md) | 🟡 Full guild system pending | Full guild system pending. |
| E17 — [Monturas equipadas que no permiten montarse](E17-monturas-y-dragopavos/README.md) | 🟡 Mounting/visibility accepted; broader equipment zero-stat regression tracked with17 | Mounting/visibility accepted; broader equipment zero-stat regression tracked with17. |
| E18 — [Motor de IA táctica de enemigos](E18-ia-tactica-enemigos/README.md) | 🟡 Basic NPC movement accepted; complete tactical attack behavior not certified | Basic NPC movement accepted; complete tactical attack behavior not certified. |
| E19 — [Logros, objetivos y recompensas sin motor persistente](E19-logros/README.md) | 🟡 Complete inventory in progress; monster/dungeon achievements prioritized | Hector authorizes enabling achievements based on monster kills and dungeon completion. Mission-dependent achievements are BLOCKED for now. Complete inventory:1,837 definitions outside the mission tree;1,389 have literal/transitive mission dependencies and19 additional textual dependencies need review. There are162 kill/dungeon candidates;8 simple dungeon completion definitions are identified for the general engine, not activated yet. Arbitrary custom IDs/text are ignored by the accredited native journal protocol. [Complete inventory, rules, rewards and custom feasibility](../reports/achievements/INSTALLED-INVENTORY-20261011.md). Existing minimal dungeon criterion authority is not a complete achievement engine. |
| Daily and recurring missions (new request) | 🟡 Inventory and server-only feasibility review in progress | Review installed Almanax/daily missions and recurring destructive-monster events, including original objectives, scheduling/reset rules, rewards, native UI and durable replay protection. No new daily/event implementation or activation claimed yet. |
| E21 — [Accesos de Zurkalia a Astrub y arenas](E21-accesos-zurkalia/README.md) | 🟡 Zurkalia access pending | Zurkalia access pending. |
| E22 — [Giro molesto del personaje al atacar](E22-giro-del-personaje-al-atacar/README.md) | 🟡 Attack-facing behavior under investigation | Attack-facing behavior under investigation. |
| E23 — [Orientación invisible para otros jugadores](E23-orientacion-no-visible-otros-jugadores/README.md) | 🟡 Orientation persistence/publication implemented; peer visual acceptance pending | Orientation persistence/publication implemented; peer visual acceptance pending. |

Earlier complete World/AI/ecology/admin release deployed and verified2026-10-11; [deployment evidence](../reports/SYSTEMS-DEPLOYMENT-20261011.md). Run the [complete systems manual journey](../reports/SYSTEMS-ACCEPTANCE-20261011.md); graphical acceptance remains pending.

Prepared complete world image and title/emote acceptance: [release instructions](../reports/cosmetics/TITLES-EMOTES-RELEASE-20261010.md).

Focused investigations: [late spectators](16-espectadores-y-marcadores/STATUS-REVIEW-20261009.md),
[sockets](22-identificacion-elementos-y-encantamiento/STATUS-REVIEW-20261009.md),
[passport](24-nacion-y-pasaporte-neutral/STATUS-REVIEW-20261009.md),
[guest room permissions](26-insertar-y-retirar-merkagemas/STATUS-REVIEW-20261009.md).
These reviews have not applied gameplay corrections.

There is no issue37 directory in this inventory:44 original issues including0,
plus23 E issues =67 tracked issues.



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
| 22 | Identificación, elementos y encantamiento | [Abrir](22-identificacion-elementos-y-encantamiento/README.md) |
| 23 | Bolso Sadida apilado rompe la interfaz hasta reiniciar | [Abrir](23-bolso-sadida-apilado/README.md) |
| 24 | Pasaporte de Amakna por defecto | [Abrir](24-nacion-y-pasaporte-neutral/README.md) |
| 25 | Fallas dimensionales y recompensas | [Abrir](25-brechas-dimensionales/README.md) |
| 26 | No se pueden añadir merkagemas | [Abrir](26-insertar-y-retirar-merkagemas/README.md) |
| 27 | Clima | [Abrir](27-clima-por-zona/README.md) |
| 28 | Bonus de área | [Abrir](28-bonus-de-area/README.md) |
| 29 | 107/107 ordinary main routes prepared in source; deployment and graphical acceptance pending | The 109 level-specific definitions represent 107 distinct ordinary routes. Individual review resolved the final eleven structural blockers; isolated lifecycle evidence and remaining mechanic limits are recorded in the [current per-dungeon review](../reports/dungeons/FINAL-ELEVEN-INDIVIDUAL-REVIEW-20261010.md). The last previously inspected runtime baseline was 37 ordinary native flows plus 10 ultimate-boss arenas; no fresh deployment audit, activation or restart is implied. Original boss scripts and optional annexes are not certified. [Complete manual acceptance](../reports/dungeons/FINAL-ELEVEN-MANUAL-ACCEPTANCE-20261010.md). |
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

## Historical priority reference

The previous priority matrix is preserved in [the historical snapshot](HISTORICAL-PRIORITY-MATRIX-20261011.md). The closed and open tables above are the authoritative current status. Original issues without E retain priority; E issues are addressed as dependencies or after originals.

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
