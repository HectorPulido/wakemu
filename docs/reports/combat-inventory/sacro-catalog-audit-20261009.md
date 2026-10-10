# Sacrier complete catalog inventory — 2026-10-09

## Scope and authority

This is an audit of native breed 11 (SACRIER), not a completion certificate. No production code, gameplay database state, service, or container was modified. Current effect definitions were read through the published PostgreSQL catalog authority, revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. The initial dependency seed/ownership graph is the explicitly historical `class-native-mechanic-graph-20261007.json`; it was then reconciled and expanded from current published runtime children, roots and native reference producers at every integer parameter level 0 through 250. False and unreachable branches remain in structural closure.

Inventory: **21 normal active spells, 20 passives, 5 native granted actions, 3 additional morphology actions, and 2 innate states**. The historical union contains 46 spells/934 effects/46 states; the **current reconciled union contains 49 spells, 1029 effect definitions, 52 states, 1 area (1605), 1 morph profile (5900), 65 historical native condition classes, 51 mask bits, and 23 HMI triggers**. All 1029 referenced effects exist and every family has a current factory/dispatch binding. **One historical innate dependency, state 759, is absent from the current merged state catalog.**

Machine-readable evidence: [full scoped runtime definitions](sacro-catalog-audit-20261009.json), [current exact family bindings](sacro-current-family-routes-20261009.json). The snapshot includes per-root ownership, all levels/critical roots, costs and casting metadata, target masks, criteria, native event metadata and state records. Presence does not prove publishers, selector roles, lifecycle, packet delivery, or rollback correctness.

## Exhaustive action and passive register

“Historical evidence” refers to prior records, not fresh execution in this audit. Gated families have handlers but depend on authority/providers. “No structural gap” means no absent effect/family binding; it does not mean the action is fully working.

| ID | Name | Kind | Unlock level | Effects/states in historical closure | Current construction-gated families | Historical evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 5028 | Sangre a Sangre | Activo | 1 | 94/16 | None | Lanzamiento real en cliente de prueba: daño propio y de fuego al Wonejo, victoria. No acredita todos los estados, niveles ni variantes. |
| 5029 | Jaula de Sangre | Activo | 15 | 17/1 | 1013 | Sin revisión individual |
| 5030 | Atracción | Activo | 3 | 12/0 | 301, 1013 | Prueba GUI estricta aprobada: tirón con desnivel y coste de 1 PA y 1 PW |
| 5031 | Sangre Ardiente | Activo | 9 | 87/15 | None | Corregido y confirmado en el juego por el usuario: Sangre Ardiente funciona. Prueba de servidor adicional con tres enemigos adyacentes a niveles 20 y 200. |
| 5032 | Punición | Activo | 21 | 91/15 | None | Sin revisión individual |
| 5033 | Pie de Roca | Activo | 1 | 16/0 | 1013 | Daño, aplicación de 7 de armadura y absorción comprobados en cliente: dos golpes de 5 consumen los 7 de armadura y restan solamente 3 PdV. |
| 5034 | Tormenta Espiritual | Activo | 20 | 113/15 | 340, 421 | Sin revisión individual |
| 5035 | Demencia | Activo | 11 | 11/0 | 301, 339 | Sin revisión individual |
| 5036 | Fatal Furiarga | Activo | 23 | 36/1 | 1013 | Sin revisión individual |
| 5037 | Columnata | Activo | 17 | 28/0 | 302, 1013 | Sin revisión individual |
| 5038 | Aversión | Activo | 1 | 6/0 | None | Usuario confirma daño; otros efectos pendientes |
| 5039 | Puño Tatuabalanzante | Activo | 6 | 101/15 | 305 | Sin revisión individual |
| 5040 | Asalto | Activo | 13 | 10/0 | 422, 1013 | Sin revisión individual |
| 5041 | Cinetosis | Activo | 7 | 27/1 | 300, 302 | Reacciones normales, Berserker, críticas, intercambio y caso letal aprobados internamente; sincronización gráfica no validada en esta revisión |
| 5042 | Fulgor | Activo | 25 | 45/0 | 302, 1013 | Flags5 corregidos; pruebas internas pasan, despliegue y GUI pendientes |
| 5043 | Transposición | Activo | 3 | 2/0 | 422 | Sin revisión individual |
| 5044 | Sacrificio | Activo | 30 | 22/3 | 422 | Sin revisión individual |
| 5045 | Armadura Sanguínea | Activo | 15 | 10/3 | 1013 | Sin revisión individual |
| 5047 | Baño de Sangre | Activo | 45 | 6/1 | None | Sin revisión individual |
| 5049 | Rastro de Sangre | Pasivo | 40 | 4/0 | None | Sin revisión individual |
| 5050 | Placidez | Pasivo | 20 | 6/0 | 421 | Sin revisión individual |
| 5051 | Sangre Tatuada | Pasivo | 10 | 4/1 | None | Bonus de vida verificado en cliente nivel20: 250→410 PV al iniciar combate. Falta comprobar intervalo de Corazón Sanguíneo; pasiva completa pendiente. |
| 5052 | Rechazo a la Muerte | Pasivo | 50 | 13/1 | 1013 | Sin revisión individual |
| 5053 | Pacto de Sangre | Pasivo | 25 | 11/0 | 421, 1013 | Sin revisión individual |
| 5054 | Trascendencia | Pasivo | 35 | 3/0 | None | Sin revisión individual |
| 5192 | Movilidad | Pasivo | 10 | 8/1 | None | Sin revisión individual |
| 5193 | Libación | Pasivo | 30 | 6/1 | None | Sin revisión individual |
| 5194 | Venas de Wakfu | Pasivo | 15 | 95/15 | 421 | Sin revisión individual |
| 5195 | Quebrantador | Pasivo | 45 | 21/0 | 421, 1013 | Sin revisión individual |
| 7211 | Coagulación | Activo | 60 | 7/1 | 1013 | Sin revisión individual |
| 7212 | Transferencia Sanguínea | Activo | 90 | 3/1 | None | Sin revisión individual |
| 7213 | Circulación Sanguínea | Pasivo | 55 | 6/0 | 421 | Sin revisión individual |
| 7214 | Juego Peligroso | Pasivo | 60 | 3/0 | None | Sin revisión individual |
| 7215 | Visión | Pasivo | 65 | 5/0 | None | Sin revisión individual |
| 7216 | Armadura Ardiente | Pasivo | 70 | 4/0 | 421 | Sin revisión individual |
| 7217 | Pacto de Wakfu | Pasivo | 75 | 88/16 | None | Bloqueo detectado; corrección parcial en trabajo |
| 7218 | Corazón de Sacrógrito | Pasivo | 100 | 1/0 | None | Sin revisión individual |
| 7219 | Agita Viajes | Pasivo | 85 | 16/0 | 421 | Sin revisión individual |
| 7220 | Pilar | Pasivo | 90 | 17/0 | None | Sin revisión individual |
| 7224 | Inmolación | Pasivo | 95 | 105/17 | 421 | Sin revisión individual |
| 7830 | Ejecutor | Pasivo | 80 | 6/0 | None | Sin revisión individual |
| 5046 | Mártir | Granted | Native state grant | 26/1 | 1013 | See granted-action section in historical class register; manual coverage pending. |
| 6065 | Corazón Sanguíneo | Granted | Native state grant | 32/1 | 1013 | See granted-action section in historical class register; manual coverage pending. |
| 8586 | Corte | Granted | Native state grant | 104/17 | 421, 422 | See granted-action section in historical class register; manual coverage pending. |
| 8587 | Venganza | Granted | Native state grant | 21/4 | None | See granted-action section in historical class register; manual coverage pending. |
| 8593 | Armadura Ardiente | Granted | Native state grant | 19/1 | 1013 | See granted-action section in historical class register; manual coverage pending. |

## Innate dependencies and concrete missing data

- Innate **4464**, and innate **3702 (Berserker)**, must install through the general owning-class initialization path; they must not be inserted into the active/passive deck. Both current state records exist.
- **State 759 missing:** current native effects 316596, 316608 and 316615 (family 304) reference state 759, while effect 316760 (family 321) removes it. Ownership appears only under innate 3702 in the historical graph. The record is `null` in the snapshot.
- 316596 is a child of 197716 with criterion `GetTeamId("triggeringCaster") <> GetTeamId("target")`; 316608 is a child of 316606 with criterion `(GetCharacMax("HP", "caster") * 0.02) <= GetStateLevel(6872, "target")`; 316615 is a child of 316613 with the analogous `0.2` threshold. Removal 316760 is under 316594 guarded by `HasState(759, "caster")`. These immediate parents are not literal `False` branches. Full event/dynamic reachability requires a dedicated oracle/runtime probe before calling the gap player-visible. Do not fabricate a replacement state.

## Old gap claims reconciled with current source

The older class page reports families 430, 339, 305 and 1000 as absent. That is stale:

- **430**: `NativeTriggerValueHandler` is bound by the common factory; it mutates the actual triggering runner and requires authoritative actors, timing and triggering-runner context. This is now an event/semantics test risk, not an absent handler.
- **1000**: `NativeRedirectRunnerHandler` is bound; redirects an actual triggering Qe with native event masks and target rebinding. Sacrifice 5044 requires runtime probes for chained target roles and death/rollback.
- **305**: general displacement `approach_cell` binding exists. Tatuabalanzante 5039 still needs approach distance, occupied/blocked cells, physics, height, resource and packet checks.
- **339**: area handler exists within retention-gated initialization. Demencia 5035 still requires a real authoritative area lifecycle and grid probe.
- Other Sacrier construction-gated families: **300, 301, 302, 340, 421, 422, 1013**. These are not declared absent; missing authority at a callsite can still reject a cast.

## Most failure-prone interactions

1. **HP-dependent damage and self-damage:** Sangre a Sangre 5028, Sangre Ardiente 5031, Punición 5032, Baño de Sangre 5047, innates and Libación 5193/Pacto de Wakfu 7217/Inmolación 7224. Verify self versus enemy target, armor absorption, HP thresholds, retained stack changes, reactive recursion, critical roots, lethal self-damage, and single payment.
2. **Damage interception and death:** Sacrificio 5044, Rechazo a la Muerte 5052, Pactos 5053/7217, Pilar 7220. Verify redirected runner identity, pre/post-damage event phases, invulnerability, allies dying/disconnecting, multiple protectors, cleanup, and no wrongly attributed death animation.
3. **Forced movement with reactions:** Atracción 5030, Tormenta Espiritual 5034, Demencia 5035, Tatuabalanzante 5039, Asalto 5040, Cinetosis 5041, Fulgor 5042, Transposición 5043. Probe adjacency, swaps, null/freed targets, large radius, obstacles, occupied destination, height, arena edge, deaths on route, and nested Cinetosis damage.
4. **Armor and HP conversion:** Pie de Roca 5033, Fatal Furiarga 5036, Columnata 5037, Armadura Sanguínea 5045, Coagulación 7211, Corazón Sanguíneo 6065, Armadura Ardiente 7216/8593. Probe zero/positive armor, percentage HP caps, give/receive modifiers, turn expiration, resource reimbursement, and state consumption after the exact damage event.
5. **Granted-action lifecycle:** Mártir 5046, Corazón Sanguíneo 6065, Corte 8586, Venganza 8587, Armadura Ardiente 8593. Actions must derive from actual native ownership/retained state and disappear when it expires; reconnect/turn changes must preserve owner and bar identity.
6. **Turn and event scope:** Cinetosis, Berserker, Vision 7215, Executioner 7830 and all retained passives depend on correct publishers and actor-local events. Source registration alone cannot establish this. Multiplayer first turn, reconnect, surrender, victory and dungeon transition require common acceptance with Cra and Iop.

## Existing concrete automated evidence to reuse

- `server/tests/test_combat_heart_blood.py`: innate native grant, self-cast, armor consumption, turn usage, state-granted 8586 cast and stored-damage healing/consumption. The test names and assertions cover those cases; they are not a certificate for all five extras.
- `server/tests/test_combat_server_initialization.py::test_real_sacro_start_passive_applies_state_3231_without_forcing_child`: native passive installation rather than ad hoc state insertion.
- `server/tests/test_combat_turn_events.py::test_sacro_actual_berserker_recalculates_at_start_without_mutating_original`: real innate Berserker start behavior.
- Historical user confirmation: Sangre Ardiente 5031 works; Sangre a Sangre 5028 actual GUI self/enemy damage; Pie de Roca 5033 armor and absorption; Atracción 5030 height/cost GUI harness. These are narrow observations.
- Historical Cinetosis normal/Berserker/critical/swap/lethal internal tests and Fulgor flags5 tests are recorded in `clases/11.md`; fresh current execution and visual synchronization are still required.

## General Cra/Iop work that should carry over

- Native explicit target propagation fixes in common effect dispatch: retain correct caster, target, ally and triggering actor through group recalculation. Essential for self-harm, armor, heals and Sacrifice. Re-test Sangre Ardiente area anchor after any adjustment.
- Common retained delivery manager, native runner mutation/redirect, precise owner UID and conditional roots: do not solve this with Sacrier-only bypasses.
- Preparation consumption policy is a generic bounded native-structure policy: only apply to a Sacrier state if its actual native damage/marker/removal structure matches. Never copy Iop state IDs or presume every Sacrier stack consumes on attack.
- General summoning ownership/counters, spell grants and removal: useful for all granted actions; no summoned entity is observed in this classified Sacrier closure, so beacon-specific patches are not a Sacrier feature. Area1605 still needs its native lifecycle.
- General damage/heal/armor aptitude consumers, selected-build caps, Barrier renewal and tackle/dodge apply to Sacrier initialization and combat. Armor/healing/berserk interactions need class-specific runtime evidence.
- Map cells, LOS, dead actor occupancy, actor identity, death event delivery, movement animation finalization, turn guard/retry serialization and cleanup are shared. They must remain covered with Cra/Iop to prevent regressions.


## Current-definition reconciliation beyond the historical graph

The JSON `dynamic_reconciliation` block records exact current edges, per-seed added/removed nodes, complete additional definitions, profile/area metadata and zero-level morphology casting. It evaluates raw reference parameters with the actual production `parameter_value` at every integer level **0..250**, including current selected roots and the explicit native zero-level profile catalog. This is structural inspection; it does not claim that every sampled level is an equip/cast level.

Compared with the historical union: **95 additional effects, 6 additional states, 3 additional spells, 1 profile and 2 mask bits; no old dependency node was removed from any root closure.** The new states are 6009, 6012, 6018, 6024, 6361 and 6500. Some are literal criterion/removal dependencies; including them does not mean the Sacrier owns those effects or can equip another class action.

- **Profile 5900** is reached by native family933 effect416860. Its native temporary book contains **8588, 8589, 8590**, maximum245, raw-reference casting UIDs, minimum0, descriptorHP1, world property7, no initial state triples or fight properties. The native zero-level casting/roots are included, which matters because the profile constructor can select level0.
- **Area1605** is native `WALL`, type7/container3, levelmax1, pointshape, root316463, properties3/8, no entry/exit masks. This must be audited as an authoritative area owner, not as a summoned monster.
- **Family865** newly appears through the expanded roots. It is implemented in `combat_effect_dispatch.py:315` via native two-child value-transfer execution; it needs final-runner callback and exact target checks rather than a made-up scalar heal/damage shortcut.
- **Finisher1099** already lies in Sacrier dependencies. Its parameter is a death presentation script assignment, not another executable spell/effect reference. The shared producer/death manager and wrong-actor animation regression remain acceptance concerns.

| Original seed | Added current dependency nodes | Removed nodes |
| --- | ---: | ---: |
| spell:5028 | 94 | 0 |
| spell:5030 | 81 | 0 |
| spell:5031 | 94 | 0 |
| spell:5032 | 94 | 0 |
| spell:5034 | 96 | 0 |
| spell:5039 | 94 | 0 |
| spell:5040 | 81 | 0 |
| spell:5041 | 78 | 0 |
| spell:5042 | 79 | 0 |
| spell:5044 | 4 | 0 |
| spell:5047 | 19 | 0 |
| spell:5050 | 3 | 0 |
| spell:5054 | 74 | 0 |
| spell:5192 | 3 | 0 |
| spell:5194 | 93 | 0 |
| spell:7215 | 19 | 0 |
| spell:7217 | 94 | 0 |
| spell:7224 | 90 | 0 |
| spell:7830 | 19 | 0 |
| spell:6065 | 42 | 0 |
| spell:8586 | 109 | 0 |
| spell:8587 | 187 | 0 |
| state:4464 | 39 | 0 |
| state:3702 | 110 | 0 |

## Requested event-provider classification

`native-current-stat-events.json` was read from the same current catalog and included in the JSON. Its actual source is the original eVi prototypes/eWQ/eWR.bbx then Qe.bbw, before dynamic PC extras.

| Event ID | Current-stat intrinsic provider | Audit conclusion |
| --- | --- | --- |
| 2235 | Family1010/eWQ,1012/eXi,1013/eWx; fixed stat97 (armor) | Intrinsic current-stat event publisher exists; Sacrier listener/phase/ownership still require a runtime test. |
| 4 | No catalog row | Requires another native publisher/cost-runner audit; do not infer it from movement channel4. |
| 60 | No catalog row | Requires another native publisher audit; `channel=60` in cast/turn/death code is not `event_id=60`. |
| 74 | No catalog row | Requires independent source-runner publisher audit. |
| 1041 | No catalog row | Requires independent publisher audit. |
| 2263 | No catalog row | Requires independent publisher/characteristic audit. |

No scoped Sacrier effect advertises these requested IDs in target_masks[6]. Source events can still come from other classes/runners, so their absence from a Sacrier source list does not establish a global missing implementation. In particular, direct spell cost AP/MP/WP mutation in `combat_spell_transaction.py` is not proof of a native current-stat payment-runner event.

## Audit limitations and next verification

No gameplay test was run by this catalog-only subtask. The parent audit/test agents are responsible for fresh execution. This audit deliberately distinguishes absent data (759), current registered but unverified behavior, gated providers, historical manual observations, and full client acceptance. Current-definition reconciliation now covers children, selected/raw roots, state apply/remove, native grant parameter2, morph profile books, area owners, linked effect421 and literal criterion references. Triggered-spell families not present in this closure, dynamic strings/nonliteral criteria and original native server publishers still require their own authority; this structural audit is not runtime coverage.
