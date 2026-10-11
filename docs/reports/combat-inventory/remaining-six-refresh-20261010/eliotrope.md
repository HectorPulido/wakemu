# Eliotrope (breed 18) current combat inventory

Read-only refresh of the existing Eliotrope review against the current shared combat runtime and published native catalog. No gameplay code, catalog data, services, or database records were changed. No tests or live-client probes were run by this review. The parent reports a fresh Luna run of 36/36 tests passing, including `test_combat_portal_casting`; that result is recorded as supplied evidence, not as an independently run test.

## Authority, denominator, and score

The active PostgreSQL catalog release is `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd` (7,484 documents; activated 2026-10-11 03:50:43 UTC). I queried PostgreSQL directly under `BEGIN READ ONLY`, read no Redis keys, and rolled back. The refreshed evidence is [`eliotrope-current-pg-reconciliation.json`](eliotrope-current-pg-reconciliation.json). It independently reconciles all 41 Eliotrope-owned spell IDs, kinds, unlock levels, and localized names; checks innate seeds **3398** and **4464**; confirms all 112 class-owned spell-root references are present in the current published casting-root document; and confirms all three granted action trees and closure references. The older shared reconciliation cited by the original class report names the prior `a1f84…` release and must not be described as the active release.

The latest release changed the document hashes for `native-class-casting-roots.json` and the two summon-profile documents compared with that earlier reconciliation. The current casting-root file was read and its 112 Eliotrope roster-root references were checked directly; the roster/innate/granted-tree hashes remain identical to the prior checked copies. The profile export now contains 45 global profiles; no Eliotrope-owned summon profile is linked by the dated Eliotrope graph. The local structural export [`18-inventory.json`](../remaining-classes-20261010/18-inventory.json) still provides the 1,302-node, 2,888-edge, 203-requirement-unit class graph; it remains a dated graph export rather than a current PG behavioral proof.

The roster is **21 active spells, 20 passives, and 3 extra/granted actions**, or 44 action entries total. The common six-class implementation rubric excludes manual acceptance and weights the same four areas for each class:

| Category | Weight | Eliotrope estimate | Basis |
|---|---:|---:|---|
| Shared combat foundation | 25% | 90% (22.5 points) | Shared cast, actor, resource, area registration, and movement systems are present; portal eligibility and gate construction/ownership are implemented. |
| Core class mechanics | 30% | 70% (21 points) | Portal placement/eligibility and several class routes exist, but no reviewed combat movement caller joins a gate crossing to a paired exit and actor relocation. |
| Passives and secondary mechanics | 30% | 50% (15 points) | The class graph and roots are present, but no comprehensive current branch/trigger validation was established for the passive and granted-action set. |
| Lifecycle | 15% | 43.3% (6.5 points) | Generic area ownership, activation, removal, and movement-event plumbing exist; portal pair replacement, traversal, death/fight/reconnect cleanup semantics remain unverified or unimplemented in the reviewed combat path. |
| **Estimated implementation** | **100%** | **65%** | Approximate source-review estimate: `22.5 + 21 + 15 + 6.5`. |

These are judgment-based estimates for implemented source coverage, not test or semantic-certification percentages. In the typed dependency export, spell-only roots cover 48 distinct effect families: 37 have registered routes and 11 are construction-gated; those roots contain 718 registered and 157 gated effect nodes. Innate dependencies cover 40/46 families with registered routes and 309/336 registered nodes. A construction-gated route is an implementation path with a runtime construction guard; it is not counted as missing implementation. Route registration alone does not prove correct spell semantics.

- **Individual manual acceptance:** 0/44 directly accepted actions in this review; manual acceptance is excluded from the 65% implementation estimate. The parent-reported automated run passed 36/36 tests, including portal-casting coverage; it does not represent a full traversal or all-action manual acceptance run.

Catalog and roster coverage is 100%; class gameplay and client acceptance remain unverified.

## Owned actions and status

Every row below has published roster alignment. `Inventory only` means the ID and ownership/grant path are sourced, while no current end-to-end class acceptance is recorded. Individual level-200 roots, costs, ranges, flags, and native export provenance are in the prior [class review](../remaining-classes-20261010/18-review.md); its older active-release statement is superseded by the direct current-PG reconciliation linked above.

### Active spells — 21

| ID | Name | Current evidence |
|---:|---|---|
| 4668 | Égida Ardiente | Inventory only |
| 4669 | Escudo Quebrantador | Inventory only |
| 4670 | Seísmo | Inventory only |
| 4671 | Tunda | Inventory only |
| 4680 | Torbellino | Inventory only |
| 4683 | Brecha Temporal | Inventory only |
| 4684 | Éxodo | Inventory only |
| 4685 | Incandescencia | Inventory only |
| 4691 | Wakmeha | Inventory only |
| 4692 | Pulsación | Inventory only |
| 4693 | Diluvio | Inventory only |
| 4694 | Cataclismo | Inventory only |
| 4695 | Colisión | Inventory only |
| 4697 | Flujo Torrencial | Inventory only |
| 4698 | Sifón | Inventory only |
| 4699 | Salva Etérea | Inventory only |
| 4700 | Tormenta | Inventory only |
| 4701 | Hoja Desencadenada | Inventory only |
| 7198 | Huella de Wakfu | Inventory only |
| 7199 | Coalición | Inventory only |
| 7200 | Parapeto | Inventory only |

### Passives — 20

| ID | Name | Current evidence |
|---:|---|---|
| 4686 | Rabia | Inventory only |
| 4687 | Celada | Inventory only |
| 4688 | Efervescencia | Inventory only |
| 4689 | Medio | Inventory only |
| 4690 | Resiliencia | Inventory only |
| 5056 | Discípulo del Portal | Inventory only |
| 5131 | Transitorio | Inventory only |
| 5132 | Reminiscencia | Inventory only |
| 5143 | Portal Celestial | Inventory only |
| 7202 | Interestelar | Inventory only |
| 7203 | Dimensión Blanca | Inventory only |
| 7204 | Quietud | Inventory only |
| 7205 | Espaciotiempo | Inventory only |
| 7206 | Portalivio | Inventory only |
| 7207 | Escudo del Fin | Inventory only |
| 7208 | Espada del Inicio | Inventory only |
| 7209 | Cicatrización | Inventory only |
| 7210 | Concentración | Inventory only |
| 7720 | Meditación | Inventory only |
| 7814 | Aliento de la Diosa | Inventory only |

### Extra/granted actions — 3

| ID | Name | Published grant source | Current evidence |
|---:|---|---|---|
| 4678 | Portal | Innate state 3398, grant effect 316226 | Grant tree and cast record present; delivery/lifecycle unverified |
| 4682 | Exaltación | Innate state 3398, grant effect 316227 | Grant tree and cast record present; delivery/lifecycle unverified |
| 7813 | Portal Celestial | Innate state 3398, grant effect 351705 | Grant tree and cast record present; delivery/lifecycle unverified |

Innate state seeds are **3398 (Guerrero ágil)** and **4464 (Golpe de gracia)**. The native innate book arrays and class roster are reconciled as source records; current installation timing, resource/HUD snapshot, action delivery, duplicate suppression, and cleanup are not accepted by that reconciliation.

## Current shared-runtime coverage

- **Portal cast eligibility:** [`combat_portal_casting.py`](../../../../server/wakfu_server/combat/combat_portal_casting.py) evaluates an entry gate and possible exit gates using actual native gate type, fight affiliation, QI occupancy, range, linear/LOS condition callbacks, and visibility callbacks. [`combat_casting_context.py`](../../../../server/wakfu_server/combat/combat_casting_context.py) integrates that evaluation with cast alignment and gate-related conditions. This is a concrete shared subsystem, not proof that the Eliotrope spell roots invoke it correctly in every case.
- **Gate presence/count and conditions:** [`combat_gate_conditions.py`](../../../../server/wakfu_server/combat/combat_gate_conditions.py) scans the complete effect-area population for native type 19 and uses captured affiliation and occupancy. Missing authority raises rather than guessing.
- **Area construction/container:** [`combat_effect_area.py`](../../../../server/wakfu_server/combat/combat_effect_area.py) recognizes GATE areas only with native class `bcS`, type 19, and empty effect/entry/exit masks. It creates a unique Qs manager with fixed cell, creator owner, captured `faV.bcM` fight affiliation, `faX` container contract, and the native remaining-activation value. [`combat_area_contracts.py`](../../../../server/wakfu_server/combat/combat_area_contracts.py) maps GATE to native `faX`. It does not store a portal-pair key in the row.
- **Cast selection details:** `evaluate_portal_casting()` uses the actual complete area set. It excludes the selected entry UID when there is exactly one entry, but when multiple own gates qualify it leaves the other gates in the exit set. It derives independent range (`twI`), alignment (`twU`), and LOS (`twG`) failures and preserves the native special same-cell category. The function returns eligibility facts only; it does not choose a destination actor position or move a fighter.
- **Generic area event and owner lifecycle:** [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py), QI/global-PV collection code, and `remove_owned_hour_area()` provide generic registration, event ordering, exact-manager child cleanup, and removal. Its `movement()` snapshots area records and routes entry/exit only through each definition's masks. The audited gate prototypes require empty entry/exit masks. Gate prototypes in [`test_combat_gate_area_lifecycle.py`](../../../../server/tests/test_combat_gate_area_lifecycle.py) assert fixed PV identity, null state manager, captured affiliation despite later owner movement/team change, explicit occupancy, and rejection before UID/packet on missing affiliation. These tests do not exercise portal passage.
- **Movement caller scope:** I inspected [`combat_state.py`](../../../../server/wakfu_server/combat/combat_state.py) `move()`, `server_move()`, and `_move_actor()`, plus the client/AI entry points in [`combat_movement_runtime.py`](../../../../server/wakfu_server/combat/combat_movement_runtime.py), and the step callbacks in [`combat_area_transaction.py`](../../../../server/wakfu_server/combat/combat_area_transaction.py) / [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py). These paths validate and commit ordinary movement cells, update movement costs/resources, then dispatch voluntary and native area movement events. I found no type-19-specific branch in these reviewed combat movement callers that redirects a fighter from a gate endpoint to a paired endpoint. This is a scoped source finding, not proof that no related behavior exists elsewhere in the repository or client.
- **Current test scope:** [`test_combat_portal_casting.py`](../../../../server/tests/test_combat_portal_casting.py) covers single-entry versus multiple-entry sets, independent range/line/LOS failures, same-cell rules, captured affiliation and occupancy, entry/exit conditional coordinates, Java integer overflow, and missing authority. [`test_combat_gate_conditions.py`](../../../../server/tests/test_combat_gate_conditions.py) covers owner/team distinction, all-candidate validation, occupancy, and unknown authority. [`test_combat_use_gate_conditions.py`](../../../../server/tests/test_combat_use_gate_conditions.py) covers native gate condition evaluation from fighter/QI/root context. The parent reports Luna's 36/36 suite pass including portal casting. None of the cited portal-casting checks is a full paired traversal test asserting destination position, movement cost, trigger order, lifecycle, or client packet sequence.
- **Recent shared fixes:** generic area-event tests now require an explicit retained-container snapshot and actual target-mask data; movement callbacks use a frozen Qs registration order/snapshot before dispatch, and gate cast tests consume the actual native root selector. These corrections strengthen shared area/cast plumbing, but the reviewed movement path still has no gate-specific endpoint redirection.
- **Route inventory:** the current [`class-effect-route-inventory-20261010.json`](../class-effect-route-inventory-20261010.json) covers the declared typed class component and summarizes 161 registered and 23 gated family routes across its inventory scope. Those route counts are not a per-spell pass or behavior score. The previous 2026-10-07 report's 92 scenario counts are historical and are not current acceptance evidence.

## Mechanic closure and unresolved behavior

The dated native component export lists 44 distinct spell references, 1,039 effects, 37 states, 12 area prototypes, and no native summon profiles for this class. It marks two state rows partial and 35 pending in the historical status overlay. Those are dependency/status counts, not assertions of reachability. The 12 area references are **781, 823, 825, 826, 1604, 1605, 1606, 1607, 1612, 1790, 1793, 1856**; 823 is typed GATE, 1605 WALL, and the remaining listed dependencies GLYPH. No Eliotrope summon profile is identified in the dated class graph; this should be treated as “none found in that export,” not proof that no runtime-created profile can occur.

The central implementation gap is portal passage, beyond just missing acceptance. Current gate rows are independent area records, while the evaluator can reason about candidate entry/exit gates for a cast. In the current type-19 path reviewed here, no function consumes an actor crossing an endpoint, resolves its counterpart, computes an exit coordinate, applies movement/cost/trigger ordering, and emits the resulting movement packets. The generic area runtime can unregister an area and remove owned children, but it does not encode a paired-gate deletion/relink policy. Still-open behavior includes owner/fight-scoped pair identity; first/second placement and replacement/cap rules; occupied/blocked exit selection; bidirectional passage; movement cost and trigger ordering; portal modifiers; carry/summon/passenger cases; removal on death/fight end/reconnect; and client visuals/packet sequence.

The rest of the action set also needs branch-level behavior evidence: passive condition/stack/trigger semantics, innates and extras delivery, conditional resource/state changes, effect-child ordering, state duration/removal and turn boundaries, area ownership/activation/expiry, failure rollback, and client action/telemetry consistency. Resource spell costs are in the cast inventory; no separate Eliotrope meter has been asserted here.

## Practical review outcome

The class has a current-release reconciled roster, all 112 current published cast-root references, all extra grant trees, and substantial shared gate construction/eligibility code. Under the common six-class rubric, the rough implementation estimate is **65%**; the parent-reported **36/36 automated test pass** is separate, and direct manual acceptance remains **0/44 actions**. The next useful acceptance target is a general gate-crossing lifecycle test covering deck/passive ownership → Ready and innate/extras delivery → portal placement A/B → travel both directions → invalid/blocked destination and passive branches → movement/HUD/packet checks → removal/death/reconnect/fight end, asserting gate identities, cells, affiliation, resource deltas, actor positions, retained states, and client-visible transitions.
