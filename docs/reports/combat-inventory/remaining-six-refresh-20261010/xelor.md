# Xelor refresh — 2026-10-10

Inventory only. Current PostgreSQL release: `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd`. No tests, gameplay modifications, catalog activation or service operations were performed. Exact read-only document hashes and current owned roster are in [PG source](xelor-pg-source.json); the full dependency/criterion roster and current code hashes are in [machine inventory](xelor.json). Historical dependency edges remain dated evidence, not re-exported current reachability.

## Implementation estimate and evidence readiness

**Practical implementation estimate:65% (provisional, low confidence; prior estimate60%).** The modest increase credits reusable current shared casting/resource/area/turn/recovery fixes, not newly demonstrated Xelor gameplay. It is an engineering estimate of available implementation, distinct from the explicit29% evidence-readiness score below. **Current complete manual acceptance:0%**; no whole-class manual acceptance has been recorded. These figures must not be combined or interpreted as65% of spells proven working.

Common implementation rubric (manual acceptance excluded):

| Implementation dimension | Weight | Estimated earned | Basis |
|---|---:|---:|---|
| Shared foundation |25|23|Current casting, resources, targeting, typed PV, area/summon ownership, turn and recovery machinery; class-specific producer gaps remain possible.|
| Core class mechanics |30|20|Native owned roster and general cast routes, actual sphere grant/initial twelve hours; full temporal/position/AP chains are not qualified.|
| Passives and secondary mechanics |30|15|Innate/passive/extra definitions and shared reactive execution exist, but twenty-passive semantic matrix and all secondary conditions lack complete acceptance.|
| Lifecycle |15|7|Shared construction, registration, timeline and retention/removal exist; sphere center, all four profiles and complete clock/reconnect cycles remain unverified.|
| **Total** |**100**|**65**|Provisional implementation estimate, not demonstrated gameplay coverage.|

**29% under the explicit weighted rubric below; not a measured proportion of functioning spells.** Xelor is not qualified for complete manual acceptance. There is no demonstrated missing native definition or absent shared handler in this review; there are substantial unverified class semantics and one unresolved sphere fixture.

| Evidence dimension | Weight | Earned | Basis |
|---|---:|---:|---|
| Catalog roster/source |15|15|Current PG confirms21active,20passive, native resources/innates and four explicit empty ability books.|
| Shared runtime routes |15|10|Current source has shared constructors/events/retention/targeting; historical route matrix58bindings,10authority-gated. Full current per-root instantiation not rerun.|
| Active behavior |25|1|754 legacy primitive proves narrow damage/AP/rollback only; sphere actual grant/creation is partial.|
| Passive behavior |20|0|No complete per-passive numeric positive/negative acceptance in reviewed evidence.|
| Lifecycle |15|3|Actual initial12hours and owned summon creation, plus reusable shared timeline/area code; center/removal chain incomplete.|
| Client acceptance |10|0|No current complete Xelor client acceptance.|

## Exhaustive owned and granted roster

Each row preserves its native roots, states, families and criterion strings in the machine inventory. “Unverified” is not a missing-handler finding. Legacy754 assertions are not the general production transaction or conditional Hora Actual acceptance.

| ID | Label | Kind | Evidence |
|---:|---|---|---|
|749|Martillhora|active|class-specific acceptance unverified|
|750|Perturbación|active|class-specific acceptance unverified|
|751|Suspensión|active|class-specific acceptance unverified|
|752|Rayoscuro|active|class-specific acceptance unverified|
|753|Polvo|active|class-specific acceptance unverified|
|754|Aguja|active|partial legacy754 primitive|
|757|Premonición|active|class-specific acceptance unverified|
|763|Reloj|active|class-specific acceptance unverified|
|765|Tempus Fugit|active|class-specific acceptance unverified|
|766|Rueda Dentada|active|class-specific acceptance unverified|
|767|Hora Punta|active|class-specific acceptance unverified|
|771|Regreso Espontáneo|active|class-specific acceptance unverified|
|772|Simetría|active|class-specific acceptance unverified|
|775|Ralentización|active|class-specific acceptance unverified|
|776|Contrarreloj|active|class-specific acceptance unverified|
|777|Sinistro|active|class-specific acceptance unverified|
|783|Reloj de Arena|active|class-specific acceptance unverified|
|1417|Desincronización|active|class-specific acceptance unverified|
|1418|Paradoja|active|class-specific acceptance unverified|
|2839|Devoción|active|class-specific acceptance unverified|
|5344|Regulador|active|class-specific acceptance unverified|
|756|Memoria|passive|class-specific acceptance unverified|
|758|Maestro de la Esfera|passive|class-specific acceptance unverified|
|761|Relojería|passive|class-specific acceptance unverified|
|764|Tac Tic|passive|class-specific acceptance unverified|
|785|Curso del Tiempo|passive|class-specific acceptance unverified|
|5351|Presagio|passive|class-specific acceptance unverified|
|5352|Prontitud|passive|class-specific acceptance unverified|
|5353|Tic Tac|passive|class-specific acceptance unverified|
|7184|Contrahorario|passive|class-specific acceptance unverified|
|7185|Deja Vu|passive|class-specific acceptance unverified|
|7186|Conocimiento del Pasado|passive|class-specific acceptance unverified|
|7187|Presagios Violentos|passive|class-specific acceptance unverified|
|7188|Dimensión Oscura|passive|class-specific acceptance unverified|
|7189|Ralentización del Tiempo|passive|class-specific acceptance unverified|
|7190|Remanencia|passive|class-specific acceptance unverified|
|7191|Mecanismos Especializados|passive|class-specific acceptance unverified|
|7192|Permutación Momentánea|passive|class-specific acceptance unverified|
|7193|Mago de Combate|passive|class-specific acceptance unverified|
|7195|Marchitación|passive|class-specific acceptance unverified|
|7196|Asimilación|passive|class-specific acceptance unverified|
|3909|Robo de Tiempo|None|class-specific acceptance unverified|
|5345|Esfera|None|partial actual grant/creation; center unresolved|
|7794|Distorsión|None|class-specific acceptance unverified|

## Resources, states and dependencies

Current PG innate authority specifies **AP6, MP3, WP12, HP base50**; protected innate states6755 and4464 use native level parameter1. WP12 must not be replaced with another class's default6. Actor level/gear/conditional modifiers remain separate actual PA inputs. The model must preserve resource loss/gain, AP payment events, resistance-to-loss, negative/zero outcomes, refresh clocks and atomic rejected casts.

The historical complete spell-plus-innate union contains **46 states**, not just the40 direct spell states:
4464,6743,6744,6745,6746,6747,6749,6750,6751,6752,6754,6755,6756,6759,6760,6761,6771,6772,6773,6774,6779,6780,6856,6858,6859,6860,6861,6862,6863,6864,6865,7545,7784,7785,7786,7787,7788,7789,7790,7814,7815,7818,7887,9245,9315,9331.

Critical class contracts include Distorsión6744, Hora Actual6759, Tic/Tac6771/6772, Reloj de Arena6745, Devoción6749/7545, Contrarreloj6760/6780, Puntualidad7814 and sphere-return states6779/7818/7887. Their presence does not establish correct state levels, alternating phases, per-target limits, AP reaction recursion, duration clock or removal. The JSON retains each spell's actual exported condition strings and related state/family lists; no condition is classified as supported merely because its name is parsed.

### All25 area dependencies

Direct spell scope has24; adding innate-only574 gives the full25:
**574,781,969,1537–1544,1546–1558,1792**. There is no inferred153? range beyond the explicit list.1537–1544,574,781,969,1792 are GLYPH;1546–1558 are HOUR in the historical typed projection. A template reference is not proof of legal creation, exact footprint, registered PV/Qf ownership, actor entry/exit selection, duration, position change, disappearance or client rendering. The current PG area document hash is recorded; this report does not claim the historical class-to-area edges were regenerated.

### Four native profiles and books

Current PostgreSQL `native-class-summon-abilities.json` explicitly returns an empty `abilities` array for **1422,3790,3791,5444**. These are four verified profile/book records, **not four missing books** and not four playable AI actors. No invented ability is required to make an empty native book “complete.” Their class-owned constructor descriptors, stats, owner/controller, off-timeline behavior, insertion/removal and triggered effects still require individual legal production acceptance. Generic owned creation has progressed for the sphere; it does not qualify all four profiles.

## Exact unresolved sphere contract

`test_combat_summon_entry.NativeSummonEntryTests.test_native_granted_sphere_common_entry_and_registered_roster` uses the actual granted5345 creation path. Original compact terrain clipped three directional points, yielding nine hours plus two environment areas (11 total). A source-derived15×15 compact fixture now places all twelve initial hours1546–1557 plus faP46 and environment910: **14 total**.

Center1558 is a separate state/event branch:
313305→313306 (`IsOwnSpecificArea(1557)`)→313307→313308 (family315, reference1558).
Native eOF tests selected areaPV, or its explicit null-PV cell form; ordinary actor7 standing on an hour is not automatically an areaPV. The observed actor-target313306 false therefore does not demonstrate a broken criterion. A later test dispatches actual native400 producer352198 to registered hour1557 so2251 traverses real area replay; **the terminal run still has14 rather than the original15 assertion**. The expected center is not proven, and its subsequent removal assertions are not reached. No direct center insertion, criterion override or relaxed area-count assertion was used.

This is an unresolved fixture/producer/replay boundary, **not a demonstrated production defect**. Source evidence does not yet distinguish whether this attempted event carries the correct original parent context and state-manager subscription. Bounded next qualification: capture real2251 subscription recipient/criteria/source and require actual313308 execution under a native legal owner action. Do not repeat arbitrary center/standing changes or certify the whole dial from initial hour presence. The failed focused source SHA was `0ebee8d68dd3c05083e8cd88eaa602e26d1c2c6f75608b3b6d8cab14993578dd`.

## Reusable current shared advances

| Contract | Current route/evidence | Xelor-specific remainder |
|---|---|---|
| Conditional cost/range/LOS | `combat_native_spell_casting.py`, shared casting context/diagnostics preserve selected criteria, native free-cell/path distinctions and current modifiers. Cra conditional-wall and general casting tests are reusable kernel evidence. | Prove Hora Actual/Tic/Tac/dial/PB conditions at their real producer levels; compare selected table and reject atomicity. |
| Null/nonactor PV and group context | State managers support registered areas including nullable Qf; group level/current-trigger fixes and narrowly bounded fresh-target reconstruction preserve explicit PV identity. | Actual temporal group descendants, area targets and source level propagation must match Xelor roots. |
| AP/resources and paid events | `combat_resource_loss.py`/handler, current-stat consumers and actual positive AP-payment2234 policy are shared. Retained sources removed during L3 are not recreated. | Ralentización/Devoción/Distorsión gain/loss/refresh and once-only reactions on real targets, including immune/zero/kill cases. |
| Turns and temporal controls | `combat_additional_turn.py`, `combat_turn_suppression.py`, `combat_turn_duration.py`, table-turn source and recovery separate timeline from roster. Additional-turn tests include45-case Java differential; suppression tests assert literal native clearing rather than invented reference counting. | Exact class callers, Tic/Tac, delayed returns, duplicate/extra turns, suppression expiry and AP refresh under player/end/ACK lifecycle. |
| Position and native terrain | Shared displacement uses selected-surface provenance, actual QI obstacles and conditional LOS; native map surface publication/compact connected terrain eliminates known missing-authority paths. | Hora Punta/Tempus Fugit/Simetría/Paradoja/return actions on actual dial/glyph and actor targets, blocked cells, z changes and rollback. |
| Summon/area retention | Shared creator snapshots, QI slot registration, ownership and removal preserve effectUID versus areaUID; current recovery supports non-timeline beacons/roster separation. | Four Xelor profiles and all25 areas still need source-qualified class lifecycle/reconnect acceptance; sphere center remains unresolved. |
| Lethal and healing | Proven corpse guard false becomes a nonexecuting heal without weakening missing authority; KO policy uses actual lethal source. | Do not extrapolate to Xelor-specific lethal/AP/clock chains without their exact roots. |

## Existing tests and evidence limits

- `test_combat_xelor_cast`: three legacy754 primitive tests (fire damage/AP4, insufficient AP/unknown historical state, LOS/encoding rollback). This is a specialized old path with supplied callbacks, not21 normal class casts.
- `test_combat_xelor_passive`: native unlock-payload bytes and conditional extra grant records5345/3909/7794. These do not prove all20 passive reactive effects or client action-bar lifecycle.
- `test_combat_summon_entry`: actual granted sphere creation and initial hours; latest focused run fails14-versus15 before full center/removal acceptance.
- Shared `test_combat_additional_turn`, `test_combat_turn_suppression`, `test_combat_table_turn`, turn-duration/guard/events, area/state-manager and resource-loss tests qualify reusable kernels. Their existence is not a newly executed green batch: **no tests were run by this inventory author**. A later delegated current-source batch passed36/36 existing tests across seven modules, including `test_combat_xelor_cast` and `test_combat_xelor_passive`, against active release548e1468. That refreshes their bounded primitive/unlock evidence; it did not execute the full sphere test or qualify all class spells.
- Historical73 Ready profiles/635 ordinary pairs and the earlier route matrix are useful bounded diagnostics, not a current complete Xelor semantic gate. Current catalog revision differs from those executions. They are not silently relabeled current-pass evidence.

## Missing versus unverified and risk

**Proven missing in this scoped refresh: none.** Current owned catalog41 definitions, innate records and four empty native books are present. The previous route review listed no absent family binding; ten bindings were authority-construction-gated, not missing. This refresh does not assert every runtime provider is available for every class branch, because no new complete instantiation audit was run.

**Unresolved:** center1558 branch in the current full sphere fixture. **Unverified:** whole21-active normal transactions; whole20-passive numeric positive/negative effects; acquisition/use/cleanup for all three extras; complete46-state temporal/resource behavior; four profile lifecycles; all25 area footprints/entry/exit/removal; time-control/carry/corpse edge cases; client tooltip/action bar and reconnect/full-fight cleanup.

Highest risks are event-source/selected-area identity, effect-level propagation, timeline-versus-roster insertion, AP reaction reentry, conditional Hora Actual tables, and duration clocks across added/suppressed turns. None should be “fixed” with spell-ID exceptions, fake AP/state setup, guessed zero snapshots or invented native abilities.

The next general gate should cover real Ready/grants → normal owned casts → source-qualified temporal events and positional branches → actual end/ACK/additional/suppressed turns → dial/profile removal/reconnect → subsequent fight. Preserve full source/PG hashes and report legal guards separately from missing-authority errors. Manual client acceptance remains a later explicit gate, not the result of this inventory.


## Current delegated regression refresh

Luna reports **36/36 PASS** across seven existing modules, including Xelor cast/passive suites, on active PostgreSQL release `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd`. This is a combined batch total, not36 Xelor-specific cases. The full sphere creation/center test was not run in that batch; its historical14-versus15 failure remains unresolved. The practical65% estimate and separate29% evidence-readiness rubric retain their explicit limits; manual acceptance remains excluded from implementation scoring.
