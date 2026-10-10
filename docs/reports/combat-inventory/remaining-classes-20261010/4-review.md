# Sram (native class 4) combat review — 2026-10-10

## Scope and evidence rule

This review covers the owned active/passive spell catalog, extra/granted spell rows, native spell dependency closure, class innate closure, profile/book and area dependencies, runtime route status, class-specific resource/state lifecycle concerns and current verification. Catalog inclusion, graph reachability, handler registration and isolated primitive tests are inventory evidence only; they do not establish a functional spell or class mechanic. “Unverified” means the reviewed material has not demonstrated the behavior; “missing” is reserved for an explicitly absent native/runtime definition or route.

Primary class catalog and effect/state/criterion detail: [existing class inventory](../clases/4.md). Native typed source: [18-class component projection](../class-native-mechanic-components-20261007.json), [native typed graph and provenance](../class-native-mechanic-graph-20261007.md) and [native graph JSON](../class-native-mechanic-graph-20261007.json). Class mechanic requirements register: [requirements](../class-mechanic-requirements-20261007.md) and [machine records](../class-mechanic-requirements-20261007.json). Route source: [class effect route inventory](../class-effect-route-inventory-20261010.md) and [machine data](../class-effect-route-inventory-20261010.json).

The active PostgreSQL native catalog is authoritative for current native records; `server/protocol/` was intentionally removed and its absence is not a gap. The detailed spell/state/profile/area projections and requirements register cited below are Oct. 7 historical exports; current route wiring is instead covered by the Oct. 10 route matrix. See the [read-only PostgreSQL source audit](../remaining-classes-source-audit-20261010.md) for published-release provenance and limits.

## Owned active and passive roster

The class source lists **21 active** and **15 passive** definitions (36 class-spell IDs total). Every row below is included so future verification can be tracked without mistaking catalog presence for success. Detailed roots, native families, related states and textual conditions are preserved in the linked class inventory.

| ID | Native label | Kind | Review status in source inventory |
|---:|---|---|---|
| 4579 | Estafa | Activo | Sin revisión individual; in-game: Pendiente |
| 4581 | Ataque Mortal | Activo | Sin revisión individual; in-game: Pendiente |
| 4583 | Ataque Letal | Activo | Sin revisión individual; in-game: Pendiente |
| 4584 | Cleptosram | Activo | Sin revisión individual; in-game: Pendiente |
| 4585 | Ataque Pérfido | Activo | Sin revisión individual; in-game: Pendiente |
| 4586 | Ejecución | Activo | Sin revisión individual; in-game: Pendiente |
| 4587 | Sangría Mortal | Activo | Sin revisión individual; in-game: Pendiente |
| 4588 | Primer Sangrado | Activo | Sin revisión individual; in-game: Pendiente |
| 4589 | Castigo | Activo | Sin revisión individual; in-game: Pendiente |
| 4590 | Abrir las Venas | Activo | Sin revisión individual; in-game: Pendiente |
| 4592 | Traumatismo | Activo | Sin revisión individual; in-game: Pendiente |
| 4593 | Golpe Solapado | Activo | Sin revisión individual; in-game: Pendiente |
| 4594 | Golpe Penetrante | Activo | Sin revisión individual; in-game: Pendiente |
| 4595 | Estratagema | Activo | Sin revisión individual; in-game: Pendiente |
| 4596 | Pavor | Activo | Sin revisión individual; in-game: Pendiente |
| 4597 | Engaño | Activo | Sin revisión individual; in-game: Pendiente |
| 4601 | Galopada | Activo | Sin revisión individual; in-game: Pendiente |
| 4602 | Destripador | Activo | Sin revisión individual; in-game: Pendiente |
| 6850 | Asesinato | Activo | Sin revisión individual; in-game: Pendiente |
| 8479 | Miedo | Activo | Sin revisión individual; in-game: Pendiente |
| 8481 | Jugarreta | Activo | Sin revisión individual; in-game: Pendiente |
| 4606 | Asalto Brutal | Pasivo | Sin revisión individual; in-game: Pendiente |
| 4607 | Juego de Manos | Pasivo | Sin revisión individual; in-game: Pendiente |
| 4608 | Asesino | Pasivo | Sin revisión individual; in-game: Pendiente |
| 4609 | Trampa de repulsión II | Pasivo | Sin revisión individual; in-game: Pendiente |
| 4610 | Hemofilia | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5122 | Emboscada | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5124 | Contención | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5126 | Treta | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8503 | Trampa de atracción II | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8504 | Trampa de teletransportación II | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8508 | Señuelo | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8510 | Miedo Alternativo | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8511 | Asalto Letal | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8512 | Distracción Alternativa | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8513 | Localización Cuántica | Pasivo | Sin revisión individual; in-game: Pendiente |

## Extra and granted actions

These spell IDs are catalogued separately from the ordinary class roster. The source explicitly says its routes are not necessarily an exhaustive transformation list. Unlock, grant timing, casting eligibility, effects, costs, UI/action-bar presentation and cleanup remain distinct acceptance points.

| ID | Native label | Kind | Review status |
|---:|---|---|---|
| 4603 | Doble | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 4604 | Invisibilidad | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 5182 | Trampa de Repulsión | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 5183 | Trampa de Atracción | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 5184 | Trampa de Teletransportación | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 5186 | Quitar una Trampa | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 8505 | Trampa de repulsión II | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 8506 | Trampa de atracción II | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 8507 | Trampa de teletransportación II | Extra/granted action | listed; acquisition and runtime remain separately unverified |

## Native typed closure

The class-specific direct spell dependency projection contains **area=3, area_mask=1, effect=898, hmi_trigger=31, native_condition_class=43, native_mask_bit=24, profile=1, spell=49, state=24** nodes by typed kind. These are unioned native class spell/extras dependencies, not a count of mechanics proven to execute. Direct state IDs (24): 1304, 3114, 3125, 3129, 3136, 3137, 3667, 5218, 6118, 8899, 9131, 9133, 9141, 9142, 9143, 9160, 9166, 9171, 9172, 9173, 9179, 9180, 9184, 9357.

Direct area IDs (3): 2128, 2136, 781.

Innate seed states (2): 4464, 7556. Innate dependency state closure (18): 1304, 3114, 3125, 3129, 3136, 3137, 3667, 4464, 7556, 9141, 9159, 9160, 9166, 9173, 9179, 9184, 9315, 9331. Innates may carry shared branches; a shared state, family or condition does not imply each dependent spell is broken. The class-only graph counts spell dependencies separately from common innates.

Native profile references (1):

| Profile ID | Native ability spell IDs in typed node | Evidence status |
|---:|---|---|
| 3251 | 4611, 4612, 8480, 8502 | Native profile/book record present; complete acquisition/control/ability use unverified |

The graph's profile nodes have reachability `unknown`. Profile contents describe native definitions only; they do not attest that class effects create these actors, add their books, transfer a turn, permit casts or remove them correctly.

## Class resources and secondary states

The observed class mechanics use ordinary AP/MP/WP pools, stealth/clone/mark state chains and finite trap charges. The native state inventory names `Invisible` 3129, `Punto Débil` 3114, `Hemorragia` 3125, `Aparente` 3136, `Maestro de las Sombras` 3137, `Doble` 3667, `Marca Letal` 9160 and `Sangría Mortal` 9172; trap charges, trigger turn ownership, one-shot removal and movement consequence need separate tests. No independent Sram-only numeric resource bar is established by the reviewed class sources. This report does not treat the generic WP/AP/MP payment path as class mechanic completion.

## Runtime routes and class mechanic review

The current Oct. 10 route matrix covers **60/72 registered** direct spell-closure family bindings and **12 construction-gated** bindings for this class. Gated family IDs: 300, 301, 302, 307, 308, 315, 331, 421, 422, 843, 935, 1013. No missing or unregistered family binding is listed for this class in the matrix. A construction-gated binding means its handler path requires the documented authority/factory at runtime; it is not an absent native definition or a gameplay failure. This remains route evidence, not functional coverage: class-specific source ownership, conditions, target behavior, transaction, client delivery and lifecycle still need acceptance. See the [current route matrix](../class-effect-route-inventory-20261010.json) generated against published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

Class dependencies include one profile (3251) whose original ability book lists 4612, 8480, 4611 and 8502, plus areas 2128/2136 and shared glyph area 781. Additional extra actions include Double/Invisibility and trap actions (table below). The exact owner, turn and trap charge behavior needs full sequence validation.

**Lifecycle, cleanup and client risk.** Validate cast rejection atomicity (AP/MP/WP/resource and state unchanged), created area/summon identity and owner/controller, entry/exit or turn-start timing, charge/timer expiration, death/removal, reconnect/checkpoint, next-fight cleanup, visible client actor/area/action-bar state and actual combat outcome. The shared runtime has implementations for many underlying boundaries, but the class inventories do not certify every native producer or lifecycle path. Manual client proof is pending for the bounded offline cases referenced below; none is full client verification.

Trap placement uses shared area/characteristic installation, area event and movement handling, charge exhaustion and removal code in combat_trap_area.py/combat_effect_area_events.py. Class area prototypes 2128 and 2136 are typed GLYPH in the native area inventory; do not relabel them TRAP based on their use. The dedicated Sram acceptance report verifies the original trap placement/activation/cleanup path for extra action 5182 in offline evidence, with an exact manual acceptance card; all other trap variants and passives remain unverified.

## Runtime handlers inspected

Area creation and activation use [`combat_effect_area.py`](../../../../server/wakfu_server/combat/combat_effect_area.py) and [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py); trap constructor characteristics, owner movement guard and exhausted cleanup are in [`combat_trap_area.py`](../../../../server/wakfu_server/combat/combat_trap_area.py). [Four-class acceptance card](../manual-four-class-systems-20261008.md), offline [trap owner case](../../../../.runtime/combat-review-20261008/sram-trap-manual-02.json) and [enemy-entry case](../../../../.runtime/combat-review-20261008/sram-trap-enemy-01.json) are bounded runtime evidence, not full client proof.

## Current evidence and application of shared fixes

Bounded offline evidence exercises the 5182 trap activation/cleanup path; its manual acceptance card still awaits client behavior and does not verify other Sram attacks, alternate trap books, concealment, clone control, every owner/enemy activation branch, reconnect persistence or all fight cleanup.

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
