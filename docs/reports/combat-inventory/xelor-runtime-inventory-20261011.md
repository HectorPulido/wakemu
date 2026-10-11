# Xelor current runtime inventory and acceptance plan — 2026-10-11

## Authority and conclusion

Read-only PostgreSQL snapshot of the active complete revision `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`. Companion evidence: `xelor-current-catalog-20261011.json`, generated with the shared published-catalog traversal with BREED=5. No database writes, combat execution, service operations, or engine changes were performed for this inventory.

The published roster contains 21 Xelor active spells, 20 Xelor passives, eight shared passives and three referenced granted spells. Conservative recursive closure contains 1,405 effects, 47 states, 25 areas and four summon profiles, with no missing definitions found by this traversal. These numbers include shared passives and referenced states/areas across all exported levels; they are not 1,405 enabled Xelor branches or evidence of functional coverage.

The concrete gap is acceptance evidence: the existing class-specific tests exercise a restricted Aguja branch and initialization/grants, not every active/passive reaction. No new Xelor gameplay defect is proven by this read-only inventory. The historical sphere-center issue must be rechecked against current code, which already expects the center to be created. No percentage of working behavior is asserted.

## Complete owned roster

| Kind | ID | Published name | Unlock level |
|---|---:|---|---:|
| active | 749 | Martillhora | 1 |
| active | 750 | Perturbación | 1 |
| active | 751 | Suspensión | 7 |
| active | 752 | Rayoscuro | 13 |
| active | 753 | Polvo | 25 |
| active | 754 | Aguja | 19 |
| passive | 756 | Memoria | 35 |
| active | 757 | Premonición | 60 |
| passive | 758 | Maestro de la Esfera | 10 |
| passive | 761 | Relojería | 30 |
| active | 763 | Reloj | 9 |
| passive | 764 | Tac Tic | 25 |
| active | 765 | Tempus Fugit | 5 |
| active | 766 | Rueda Dentada | 45 |
| active | 767 | Hora Punta | 1 |
| active | 771 | Regreso Espontáneo | 25 |
| active | 772 | Simetría | 17 |
| active | 775 | Ralentización | 3 |
| active | 776 | Contrarreloj | 15 |
| active | 777 | Sinistro | 30 |
| active | 783 | Reloj de Arena | 15 |
| passive | 785 | Curso del Tiempo | 40 |
| active | 1417 | Desincronización | 21 |
| active | 1418 | Paradoja | 11 |
| active | 2839 | Devoción | 3 |
| active | 5344 | Regulador | 90 |
| passive | 5351 | Presagio | 15 |
| passive | 5352 | Prontitud | 10 |
| passive | 5353 | Tic Tac | 20 |
| passive | 7184 | Contrahorario | 45 |
| passive | 7185 | Deja Vu | 50 |
| passive | 7186 | Conocimiento del Pasado | 55 |
| passive | 7187 | Presagios Violentos | 60 |
| passive | 7188 | Dimensión Oscura | 65 |
| passive | 7189 | Ralentización del Tiempo | 70 |
| passive | 7190 | Remanencia | 75 |
| passive | 7191 | Mecanismos Especializados | 80 |
| passive | 7192 | Permutación Momentánea | 85 |
| passive | 7193 | Mago de Combate | 90 |
| passive | 7195 | Marchitación | 95 |
| passive | 7196 | Asimilación | 100 |


Referenced grants: `3909` , `5345` , `7794` .

## Resources, ownership and clock contracts

Native innate resources are AP6, MP3, WP12 and HP_base50. Initial protected states are6755 and4464 at level1. Tests must initialize the published breed snapshot instead of borrowing another class’s WP6 fixture. Native innate grants and their conditional casting tables must be used; a visible shortcut alone does not attest legal casting or server ownership.

Current state closure: `4097`, `4464`, `6743`, `6744`, `6745`, `6746`, `6747`, `6749`, `6750`, `6751`, `6752`, `6754`, `6755`, `6756`, `6759`, `6760`, `6761`, `6771`, `6772`, `6773`, `6774`, `6779`, `6780`, `6856`, `6858`, `6859`, `6860`, `6861`, `6862`, `6863`, `6864`, `6865`, `7545`, `7784`, `7785`, `7786`, `7787`, `7788`, `7789`, `7790`, `7814`, `7815`, `7818`, `7887`, `9245`, `9315`, `9331`.

High-value state chains include6744 Distorsión;6759 Hora Actual;6771/6772 Tic/Tac;6745 Reloj de Arena;6749/7545 Devoción;6760/6780 Contrarreloj;7814 Puntualidad; and6779/7818/7887 sphere-return. Their exact criteria, target/removal masks and durations are preserved in the JSON. State presence must be tested separately from triggering, consumption and expiry.

Areas: `574`, `781`, `969`, `1537`, `1538`, `1539`, `1540`, `1541`, `1542`, `1543`, `1544`, `1546`, `1547`, `1548`, `1549`, `1550`, `1551`, `1552`, `1553`, `1554`, `1555`, `1556`, `1557`, `1558`, `1792`. Native sphere hours are1546–1557;1558 is a separate center reaction rather than an unconditional thirteenth hour. Area receivers must remain registered native Qq objects: an actor standing on an hour is not the same recipient.

Summon profiles1422,3790,3791,5444 all explicitly publish empty ability books. This is evidence of empty books, not a missing ability export and not permission to invent autonomous attacks. Test their actual birth effects, owned areas, destruction, replacement and duration contracts.

Mask indices matter: index6 is intrinsic producer metadata, not a subscriber channel. For example352198 declares2251 in index6, and many2285/2286 rows also use index6. Do not label those events absent by literal searching for a publisher. Conditions containing False are preserved but are not evidence of an enabled failure.

## Existing executable evidence and its limits

| Module | Existing scope | Limitation |
|---|---|---|
| `server/tests/test_combat_xelor_cast.py` | Three restricted execute_xelor754 tests: fire damage/AP4; conditional/unknown-state rejection; LOS and encoding rollback | Direct restricted adapter, not current full21-spell pipeline |
| `server/tests/test_combat_xelor_passive.py` | Two payload/grant tests, including5345/3909/7794 and required6755 | Initialization is not20-passive semantic activation |
| `server/tests/test_combat_summon_entry.py` | Actual granted5345, registered summon,12hours then explicit352198/2251 center reaction; source now asserts15total areas | Existing fixture usesWP6; needs fresh run and actual ordinary gameplay center activation, not only explicit effect invocation |
| `server/tests/test_combat_additional_turn.py` | Seven insertion/cursor/removal tests including45-case original Java differential | General timeline semantics, not proof each Xelor spell invokes the correct branch |
| `server/tests/test_combat_turn_suppression.py` | Six native parameter/wire/removal/boundary tests | General suppression contract, not full class combinations |

No tests were run for this inventory. Previous reports and their source hashes are historical evidence only. In particular the Oct10 report’s unresolved14-vs15 sphere result is superseded as a description of current test source: current source has the15-area assertion, but a fresh passing result has not been established here.

## Prioritized actual-context verification

| Priority | Context | Required positive/negative evidence |
|---|---|---|
| P0 | Published Ready initialization and complete casting roster at representative low/high levels | Every owned active gets native-eligible targets; grants are obtained through6755; correct AP/MP/WP debit once; native rejection leaves fight/RNG unchanged. A target-search miss is a fixture gap, not a failed spell. |
| P0 | Full sphere lifecycle5345 and current-hour selection | Twelve correctly positioned hours, center1558 through lawful producer, correct owner/type/cell, clipping and occupied cells, own/foreign spheres, replacement/destruction, disconnect/reconnect snapshot parity. |
| P0 | First turn, end/ACK/start, multi-character PVM/PVP | Exact current owner, no dead/summon phantom timeline entries, all parties see the same roster and usable own spells, terminal fight settles once, dungeon progression and surrender do not disconnect either participant. |
| P1 | Tic/Tac, Tac Tic and7184 Contrahorario | Different current native states change the relevant enabled effect branches; check following turn and removal, not merely initial state icons. |
| P1 | AP removal/gain, Ralentización/Robo de Tiempo and reactive passives | Numerical delta, source/target and triggering amount; zero removal, resisted removal, ally/enemy context, double turn, once-only reaction and transactional failure. |
| P1 | Distorsión, Aguja low-AP/current-hour variants and other conditional casts | Compare native conditional metadata before/after actual state changes; verify damage, extra cost and resource recovery, with/without source state. |
| P1 | Contrarreloj/Regreso Espontáneo/Tempus Fugit/Hora Punta/Simetría/Paradoja | Actual saved/live positions and owner, occupied destination, blocker/LOS/height boundaries, death of recipient, replay without stale selected PV. |
| P1 | Devoción, Premonición, Reloj de Arena delayed chains | Actual enabled event and correct target clock, turn-start/end order, expiry, nested callbacks, killed target before delayed delivery, no duplicated listeners on successive casts. |
| P1 | Rueda Dentada/Sinistro/Regulador and7191 Mecanismos Especializados | Native-profile birth, owner routing, actual area/state reactions, multiple mechanisms, death cleanup; empty ability books remain empty. |
| P1 | Every20 passive | Equip one passive with lawful unlocked level, activate its actual native consumer; compare baseline/no-passive and unmet criterion; assert numerical or lifecycle outcome and expiry. Marker-only roots must be tested via their consuming spells. |
| P2 | Visual and client acceptance | Clock orientation/hour indicators, actual resource display and shortcut grants, death animation identity, movement ending idle, reconnect full actor/area population; server smoke cannot attest these. |

## Shared paths to reuse without class-specific patches

- `combat_server_spell.py`: native casting validation, conditional costs/range, prepare/commit rollback and source event delivery.
- `combat_effect_dispatch.py` and `combat_effect_resolver.py`: typed explicit recipients versus fresh selection, live selected-target coordinates and own-Qq bit43 selection; directly relevant to clock-area criteria and delayed groups.
- `combat_state_decurse.py`: deferred criteria before invalid state preparation, and native removal lifecycle; do not treat state321 as flags421 dispel.
- `combat_additional_turn.py`: original eWl/SQ/Tc insertion, duplicated owner turns and cursor preservation. Do not equate two turns with a new round.
- `combat_turn_suppression.py`, `combat_runtime_messages.py` and native duration handlers: suppression, end/ACK/start, terminal reaction guards and clock-owner expiry.
- Shared paid-ability receipt and cast-event cleanup: one payment and rollback, intrinsic versus special event channels, successful1025 removal delivery to prevent one-cast listener accumulation.
- Summon initialization/global PV/QI/area registry/checkpoint paths: registered ownership, empty native books, death/destruction, resurrected occupancy and recovery snapshots.
- Cra/Iop/Sacrier/Aniripsa/Enutrof regressions already address selected-population lifetime, point-vs-area selection, own-area recognition, killed-target handling, delayed delivery, terminal callbacks and state expiry; run them alongside Xelor changes.

## Safe next implementation boundary

First refresh actual gameplay baselines and20-passive contexts against this PG snapshot, then isolate a reproducible native discrepancy before changing the shared engine. Keep existing Cra/Iop/Sacrier/Aniripsa/Enutrof checks in the same frozen validation batch. No class-specific bypasses for LOS, AP legality, empty summons, area ownership or timeline assertions. Manual acceptance should cover one complete clock/resource/movement fight plus multi-character ending/reconnect rather than scattered icons.
