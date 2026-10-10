# Xelor (native class 5) combat review — 2026-10-10

## Scope and evidence rule

This review covers the owned active/passive spell catalog, extra/granted spell rows, native spell dependency closure, class innate closure, profile/book and area dependencies, runtime route status, class-specific resource/state lifecycle concerns and current verification. Catalog inclusion, graph reachability, handler registration and isolated primitive tests are inventory evidence only; they do not establish a functional spell or class mechanic. “Unverified” means the reviewed material has not demonstrated the behavior; “missing” is reserved for an explicitly absent native/runtime definition or route.

Primary class catalog and effect/state/criterion detail: [existing class inventory](../clases/5.md). Native typed source: [18-class component projection](../class-native-mechanic-components-20261007.json), [native typed graph and provenance](../class-native-mechanic-graph-20261007.md) and [native graph JSON](../class-native-mechanic-graph-20261007.json). Class mechanic requirements register: [requirements](../class-mechanic-requirements-20261007.md) and [machine records](../class-mechanic-requirements-20261007.json). Route source: [class effect route inventory](../class-effect-route-inventory-20261010.md) and [machine data](../class-effect-route-inventory-20261010.json).

The active PostgreSQL native catalog is authoritative for current native records; `server/protocol/` was intentionally removed and its absence is not a gap. The detailed spell/state/profile/area projections and requirements register cited below are Oct. 7 historical exports; current route wiring is instead covered by the Oct. 10 route matrix. See the [read-only PostgreSQL source audit](../remaining-classes-source-audit-20261010.md) for published-release provenance and limits.

## Owned active and passive roster

The class source lists **21 active** and **20 passive** definitions (41 class-spell IDs total). Every row below is included so future verification can be tracked without mistaking catalog presence for success. Detailed roots, native families, related states and textual conditions are preserved in the linked class inventory.

| ID | Native label | Kind | Review status in source inventory |
|---:|---|---|---|
| 749 | Martillhora | Activo | Sin revisión individual; in-game: Pendiente |
| 750 | Perturbación | Activo | Sin revisión individual; in-game: Pendiente |
| 751 | Suspensión | Activo | Sin revisión individual; in-game: Pendiente |
| 752 | Rayoscuro | Activo | Sin revisión individual; in-game: Pendiente |
| 753 | Polvo | Activo | Sin revisión individual; in-game: Pendiente |
| 754 | Aguja | Activo | Sin revisión individual; in-game: Pendiente |
| 757 | Premonición | Activo | Sin revisión individual; in-game: Pendiente |
| 763 | Reloj | Activo | Sin revisión individual; in-game: Pendiente |
| 765 | Tempus Fugit | Activo | Sin revisión individual; in-game: Pendiente |
| 766 | Rueda Dentada | Activo | Sin revisión individual; in-game: Pendiente |
| 767 | Hora Punta | Activo | Sin revisión individual; in-game: Pendiente |
| 771 | Regreso Espontáneo | Activo | Sin revisión individual; in-game: Pendiente |
| 772 | Simetría | Activo | Sin revisión individual; in-game: Pendiente |
| 775 | Ralentización | Activo | Sin revisión individual; in-game: Pendiente |
| 776 | Contrarreloj | Activo | Sin revisión individual; in-game: Pendiente |
| 777 | Sinistro | Activo | Sin revisión individual; in-game: Pendiente |
| 783 | Reloj de Arena | Activo | Sin revisión individual; in-game: Pendiente |
| 1417 | Desincronización | Activo | Sin revisión individual; in-game: Pendiente |
| 1418 | Paradoja | Activo | Sin revisión individual; in-game: Pendiente |
| 2839 | Devoción | Activo | Sin revisión individual; in-game: Pendiente |
| 5344 | Regulador | Activo | Sin revisión individual; in-game: Pendiente |
| 756 | Memoria | Pasivo | Sin revisión individual; in-game: Pendiente |
| 758 | Maestro de la Esfera | Pasivo | Sin revisión individual; in-game: Pendiente |
| 761 | Relojería | Pasivo | Sin revisión individual; in-game: Pendiente |
| 764 | Tac Tic | Pasivo | Sin revisión individual; in-game: Pendiente |
| 785 | Curso del Tiempo | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5351 | Presagio | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5352 | Prontitud | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5353 | Tic Tac | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7184 | Contrahorario | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7185 | Deja Vu | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7186 | Conocimiento del Pasado | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7187 | Presagios Violentos | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7188 | Dimensión Oscura | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7189 | Ralentización del Tiempo | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7190 | Remanencia | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7191 | Mecanismos Especializados | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7192 | Permutación Momentánea | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7193 | Mago de Combate | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7195 | Marchitación | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7196 | Asimilación | Pasivo | Sin revisión individual; in-game: Pendiente |

## Extra and granted actions

These spell IDs are catalogued separately from the ordinary class roster. The source explicitly says its routes are not necessarily an exhaustive transformation list. Unlock, grant timing, casting eligibility, effects, costs, UI/action-bar presentation and cleanup remain distinct acceptance points.

| ID | Native label | Kind | Review status |
|---:|---|---|---|
| 3909 | Robo de Tiempo | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 5345 | Esfera | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 7794 | Distorsión | Extra/granted action | listed; acquisition and runtime remain separately unverified |

## Native typed closure

The class-specific direct spell dependency projection contains **area=24, area_mask=6, effect=1190, hmi_trigger=20, native_condition_class=57, native_mask_bit=36, profile=4, spell=44, state=40** nodes by typed kind. These are unioned native class spell/extras dependencies, not a count of mechanics proven to execute. Direct state IDs (40): 6743, 6744, 6745, 6746, 6749, 6750, 6751, 6752, 6754, 6756, 6759, 6760, 6761, 6771, 6772, 6773, 6774, 6779, 6780, 6856, 6858, 6859, 6860, 6861, 6862, 6863, 6864, 6865, 7545, 7784, 7785, 7787, 7788, 7789, 7790, 7814, 7815, 7818, 7887, 9245.

Direct area IDs (24): 1537, 1538, 1539, 1540, 1541, 1542, 1543, 1544, 1546, 1547, 1548, 1549, 1550, 1551, 1552, 1553, 1554, 1555, 1556, 1557, 1558, 1792, 781, 969.

Innate seed states (2): 6755, 4464. Innate dependency state closure (17): 4464, 6744, 6747, 6752, 6755, 6759, 6761, 6779, 7786, 7787, 7788, 7814, 7818, 7887, 9245, 9315, 9331. Innates may carry shared branches; a shared state, family or condition does not imply each dependent spell is broken. The class-only graph counts spell dependencies separately from common innates.

Native profile references (4):

| Profile ID | Native ability spell IDs in typed node | Evidence status |
|---:|---|---|
| 1422 | none | Native profile/book record present; complete acquisition/control/ability use unverified |
| 3790 | none | Native profile/book record present; complete acquisition/control/ability use unverified |
| 3791 | none | Native profile/book record present; complete acquisition/control/ability use unverified |
| 5444 | none | Native profile/book record present; complete acquisition/control/ability use unverified |

The graph's profile nodes have reachability `unknown`. Profile contents describe native definitions only; they do not attest that class effects create these actors, add their books, transfer a turn, permit casts or remove them correctly.

## Class resources and secondary states

The temporal state chains include `Distorsión` 6744, `Hora Actual` 6759, alternating `Tic`/`Tac` 6771–6772, `Reloj de Arena` 6745, `Devoción` 6749/7545, `Contrarreloj` 6760/6780, `Puntualidad` 7814 and the sphere-return states 6779/7818/7887. Areas 1537–1558 are among the native class-owned placements; profile refs 1422/3790/3791/5444 are in the same class closure. AP/MP/WP and any turn-derived resource state must be measured across legal turns. State presence does not verify alternation, generated/consumed values, turn reset, client display or cleanup after summon/dial removal. No separate Xelor-only numeric pool is asserted here absent direct runtime proof.

## Runtime routes and class mechanic review

The current Oct. 10 route matrix covers **48/58 registered** direct spell-closure family bindings and **10 construction-gated** bindings for this class. Gated family IDs: 302, 307, 315, 340, 421, 422, 843, 911, 1008, 1013. No missing or unregistered family binding is listed for this class in the matrix. A construction-gated binding means its handler path requires the documented authority/factory at runtime; it is not an absent native definition or a gameplay failure. This remains route evidence, not functional coverage: class-specific source ownership, conditions, target behavior, transaction, client delivery and lifecycle still need acceptance. See the [current route matrix](../class-effect-route-inventory-20261010.json) generated against published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

Class dependencies include temporal state stacks, 24 class areas, and four native ability profiles (1422, 3790, 3791, 5444). Profile nodes 1422/3790/3791/5444 have empty native ability lists in this export; they are summon/profile references, not books with enumerated abilities here. The inventory tracks temporal resources/turn alternation and dial area relationships through exact state and area IDs below.

**Lifecycle, cleanup and client risk.** Validate cast rejection atomicity (AP/MP/WP/resource and state unchanged), created area/summon identity and owner/controller, entry/exit or turn-start timing, charge/timer expiration, death/removal, reconnect/checkpoint, next-fight cleanup, visible client actor/area/action-bar state and actual combat outcome. The shared runtime has implementations for many underlying boundaries, but the class inventories do not certify every native producer or lifecycle path. Whole-class manual client proof remains unverified; bounded offline cases below have narrower evidence and are not client certification.

A shared summon constructor/cast pipeline exists; the Xelor profile refs need per-profile owned creation, control, ability, turn, death and cleanup coverage. Areas 1537–1558 include the temporal/dial set. General area registration, movement and cleanup routes are shared, but existence of those handlers/families is not a complete temporal area lifecycle proof.

## Runtime handlers inspected

Temporal placements use the shared area handler modules [`combat_effect_area.py`](../../../../server/wakfu_server/combat/combat_effect_area.py), [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py), and [`combat_state_managers.py`](../../../../server/wakfu_server/combat/combat_state_managers.py). Profile/actor creation and turn/book delivery route through [`combat_summon_creation.py`](../../../../server/wakfu_server/combat/combat_summon_creation.py), [`combat_summon_initialization.py`](../../../../server/wakfu_server/combat/combat_summon_initialization.py), and [`combat_summon_spellbook.py`](../../../../server/wakfu_server/combat/combat_summon_spellbook.py). These are shared code routes; no report reviewed here closes all Xelor-specific transaction and client lifecycle branches.

## Current evidence and application of shared fixes

No scoped full Xelor summon/profile book or whole-class temporal sequence evidence was found in the reviewed sources. Do not treat the graph closure or generic summon tests as class-level proof.

Prior shared work for Cra, Iop, Sacrier, Eniripsa and Osamodas can apply only where a dependency/contract overlaps: e.g. family dispatcher semantics, conditions, actor-state application, area ownership/removal, event producers, client state delivery or summon control. It can eliminate a shared blocker for these spells when the same native contract is present, but it does not prove an individual spell, passive, class-specific target rule or turn-cycle. Verify the exact root/child IDs and native condition before marking any row complete. The broad route, handler, scenario and dependency counts must not be converted into a class completion percentage.

## Explicit gaps and next acceptance coverage

- Each listed active, passive and extra remains individually unverified except for the exact scoped sequence explicitly cited above. The per-spell native conditions in the source inventory remain to be checked against live behavior.
- The full class-owned secondary/granted-book acquisition matrix, every spell/state/area branch at its legal levels, client presentation and complete fight-cycle cleanup are not exhaustively included in these short reports; the linked JSON/graph are the canonical exhaustive machine inventories for the exported projection. No 100% functionality claim is made.
- Class-specific resource/secondary-state reads, gains/losses, caps and reset points need a complete legal-turn acceptance across a new fight. State presence in the graph or original effects alone is not lifecycle proof.
- Shared fixes from other classes should be inherited only after comparing source signatures and runtime authorities. No blanket cross-class pass is inferred.

## Related evidence

- [Class mechanic gap index](../class-mechanic-gap-index-20261007.md) and [dependency coverage report](../class-dependency-coverage-20261007.md).
- [Native area prototype/lifecycle matrix](../class-native-area-contracts-20261007.csv); area IDs above can be looked up by prototype type, class ownership, creation, activation, removal and client contract.
- [Class engine active review](../class-engine-general-review-20261007.md): global active-scenario observations are path diagnostics and do not certify full class functionality.
- [Requirements register](../class-mechanic-requirements-20261007.md): unweighted shared contract units, not per-spell completion.

## Published authority reconciliation — 2026-10-10

PostgreSQL is the current catalog authority; the absence of `server/protocol/` is intentional and is not a missing-definition finding. The route matrix was regenerated against the current runtime source and published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`: 161 registered families, 23 construction-gated families, no unregistered families in that matrix scope. See [current route evidence](../class-effect-route-inventory-20261010.json) and the [read-only PostgreSQL source audit](../remaining-classes-source-audit-20261010.md). Registration does not establish complete mechanics, delivery or gameplay behavior; historical class graph provenance remains separately dated.
