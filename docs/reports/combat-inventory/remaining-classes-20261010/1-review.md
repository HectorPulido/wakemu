# Feca (native class 1) combat review — 2026-10-10

## Scope and evidence rule

This review covers the owned active/passive spell catalog, extra/granted spell rows, native spell dependency closure, class innate closure, profile/book and area dependencies, runtime route status, class-specific resource/state lifecycle concerns and current verification. Catalog inclusion, graph reachability, handler registration and isolated primitive tests are inventory evidence only; they do not establish a functional spell or class mechanic. “Unverified” means the reviewed material has not demonstrated the behavior; “missing” is reserved for an explicitly absent native/runtime definition or route.

Primary class catalog and effect/state/criterion detail: [existing class inventory](../clases/1.md). Native typed source: [18-class component projection](../class-native-mechanic-components-20261007.json), [native typed graph and provenance](../class-native-mechanic-graph-20261007.md) and [native graph JSON](../class-native-mechanic-graph-20261007.json). Class mechanic requirements register: [requirements](../class-mechanic-requirements-20261007.md) and [machine records](../class-mechanic-requirements-20261007.json). Route source: [class effect route inventory](../class-effect-route-inventory-20261010.md) and [machine data](../class-effect-route-inventory-20261010.json).

The active PostgreSQL native catalog is authoritative for current native records; `server/protocol/` was intentionally removed and its absence is not a gap. The detailed spell/state/profile/area projections and requirements register cited below are Oct. 7 historical exports; current route wiring is instead covered by the Oct. 10 route matrix. See the [read-only PostgreSQL source audit](../remaining-classes-source-audit-20261010.md) for published-release provenance and limits.

## Owned active and passive roster

The class source lists **21 active** and **18 passive** definitions (39 class-spell IDs total). Every row below is included so future verification can be tracked without mistaking catalog presence for success. Detailed roots, native families, related states and textual conditions are preserved in the linked class inventory.

| ID | Native label | Kind | Review status in source inventory |
|---:|---|---|---|
| 6967 | Fecalistófedes | Activo | Sin revisión individual; in-game: Pendiente |
| 6968 | Meteorito | Activo | Sin revisión individual; in-game: Pendiente |
| 6969 | Ataque Natural | Activo | Sin revisión individual; in-game: Pendiente |
| 6970 | Magma | Activo | Sin revisión individual; in-game: Pendiente |
| 6971 | Volcán | Activo | Sin revisión individual; in-game: Pendiente |
| 6972 | Gota | Activo | Sin revisión individual; in-game: Pendiente |
| 6973 | Onda | Activo | Sin revisión individual; in-game: Pendiente |
| 6974 | Avalancha | Activo | Sin revisión individual; in-game: Pendiente |
| 6975 | Tormenta | Activo | Sin revisión individual; in-game: Pendiente |
| 6976 | Filo Abisal | Activo | Sin revisión individual; in-game: Pendiente |
| 6977 | Golpe Telúrico | Activo | Sin revisión individual; in-game: Pendiente |
| 6978 | Orbe Defensivo | Activo | Sin revisión individual; in-game: Pendiente |
| 6979 | Bastión | Activo | Sin revisión individual; in-game: Pendiente |
| 6980 | Muralla | Activo | Sin revisión individual; in-game: Pendiente |
| 6981 | Bastón | Activo | Sin revisión individual; in-game: Pendiente |
| 6982 | Inmune | Activo | Sin revisión individual; in-game: Pendiente |
| 6983 | Tregua | Activo | Sin revisión individual; in-game: Pendiente |
| 6984 | Pacificación | Activo | Sin revisión individual; in-game: Pendiente |
| 6985 | Provocación | Activo | Sin revisión individual; in-game: Pendiente |
| 6986 | Égida | Activo | Sin revisión individual; in-game: Pendiente |
| 6987 | Magnetismo | Activo | Sin revisión individual; in-game: Pendiente |
| 6988 | Glifo Aumentado | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6989 | Línea | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6990 | Uno para Todos | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6991 | Maestro de los Escudos | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6992 | Quien Quiere la Paz Prepara la Guerra | Pasivo | Inicialización de servidor con evento de inicio completa: estado 9315 presente; pendiente cliente.; in-game: Pendiente |
| 6993 | Trato Pacifista | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6994 | Conocimiento del Mapa | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6995 | La Mejor Defensa es el Ataque | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6996 | Armadura de Combate | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6997 | Piel Rocosa | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6998 | Ojo por Ojo | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6999 | Glifos Persistentes | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7000 | Pastor | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7001 | Experiencia del Terreno | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7002 | Escudos Elementales | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7003 | Caparazón de Espinas | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7004 | Comprensión del Wakfu | Pasivo | Sin revisión individual; in-game: Pendiente |
| 7005 | Protector del Rebaño | Pasivo | Sin revisión individual; in-game: Pendiente |

## Extra and granted actions

These spell IDs are catalogued separately from the ordinary class roster. The source explicitly says its routes are not necessarily an exhaustive transformation list. Unlock, grant timing, casting eligibility, effects, costs, UI/action-bar presentation and cleanup remain distinct acceptance points.

| ID | Native label | Kind | Review status |
|---:|---|---|---|
| 7009 | Armadura de la Paz | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 7052 | Teletransportación | Extra/granted action | listed; acquisition and runtime remain separately unverified |

## Native typed closure

The class-specific direct spell dependency projection contains **area=9, area_mask=1, effect=1470, hmi_trigger=17, native_condition_class=48, native_mask_bit=46, spell=41, state=61** nodes by typed kind. These are unioned native class spell/extras dependencies, not a count of mechanics proven to execute. Direct state IDs (61): 3434, 3495, 6316, 6318, 6319, 6320, 6321, 6323, 6324, 6325, 6327, 6332, 6333, 6334, 6335, 6336, 6337, 6338, 6339, 6340, 6341, 6345, 6346, 6347, 6348, 6349, 6350, 6351, 6352, 6354, 6355, 6356, 6357, 6359, 6360, 6361, 6362, 6364, 6365, 6378, 6389, 6408, 6409, 6432, 6433, 6473, 6474, 6484, 6485, 6499, 6500, 6501, 6527, 6540, 6541, 6545, 6546, 6547, 6672, 6925, 751.

Direct area IDs (9): 1474, 1475, 1476, 1477, 1478, 1479, 1480, 1501, 1502.

Innate seed states (3): 6381, 4464, 7560. Innate dependency state closure (7): 4464, 6345, 6364, 6381, 7560, 9315, 9331. Innates may carry shared branches; a shared state, family or condition does not imply each dependent spell is broken. The class-only graph counts spell dependencies separately from common innates.

Native profile references (0):

| Profile ID | Native ability spell IDs in typed node | Evidence status |
|---:|---|---|
| — | — | No class-owned profile dependency in the typed component projection |

The graph's profile nodes have reachability `unknown`. Profile contents describe native definitions only; they do not attest that class effects create these actors, add their books, transfer a turn, permit casts or remove them correctly.

## Class resources and secondary states

The spell rows use ordinary AP/MP/WP pools, and the native conditions also inspect armor/shield and state predicates. The typed state inventory gives concrete Feca state families such as meteorite/magma/volcano shields (6319/6321/6323 and 6347/6349/6350), immunity/pacification (6361/6500), and shared armor state 6364; shield and armor changes, caps, turn duration, ally targeting and removal are still per-state runtime/client checks. Glyph placement also consumes map cells and retained area identity; 1474–1480 and 1501–1502 are exact linked area dependencies. The inventory does not show a separate Feca-only numeric resource meter beyond ordinary combat pools and shield/armor state.

## Runtime routes and class mechanic review

The current Oct. 10 route matrix covers **48/57 registered** direct spell-closure family bindings and **9 construction-gated** bindings for this class. Gated family IDs: 300, 301, 302, 315, 340, 421, 422, 843, 1013. No missing or unregistered family binding is listed for this class in the matrix. A construction-gated binding means its handler path requires the documented authority/factory at runtime; it is not an absent native definition or a gameplay failure. This remains route evidence, not functional coverage: class-specific source ownership, conditions, target behavior, transaction, client delivery and lifecycle still need acceptance. See the [current route matrix](../class-effect-route-inventory-20261010.json) generated against published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

Shielding, elemental attacks and glyph placement/turn activation are represented by the owned spell rows and area/state closure. The inventory identifies no class-owned summon profile. The level-200 glyph proof for Fecalistófedes (6967) below is one scoped path only.

**Lifecycle, cleanup and client risk.** Validate cast rejection atomicity (AP/MP/WP/resource and state unchanged), created area/summon identity and owner/controller, entry/exit or turn-start timing, charge/timer expiration, death/removal, reconnect/checkpoint, next-fight cleanup, visible client actor/area/action-bar state and actual combat outcome. The shared runtime has implementations for many underlying boundaries, but the class inventories do not certify every native producer or lifecycle path. Whole-class manual client proof remains unverified; bounded offline cases below have narrower evidence and are not client certification.

Glyphs use shared area creation, callbacks, retention, turn events, bootstrap and cleanup. The class graph includes nine areas (1474–1480, 1501–1502). The manual card validates one owned five-cell cross lifecycle for 6967; it does not cover other glyph variants, all passives, books, combat conditions, reconnect or every expiry path.

## Runtime handlers inspected

Glyph creation, registration, turn-start/movement/exit callbacks and queries are in [`combat_effect_area.py`](../../../../server/wakfu_server/combat/combat_effect_area.py), [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py), and [`combat_effect_area_queries.py`](../../../../server/wakfu_server/combat/combat_effect_area_queries.py); state manager identity and cleanup paths are in [`combat_state_managers.py`](../../../../server/wakfu_server/combat/combat_state_managers.py). [Four-class acceptance card](../manual-four-class-systems-20261008.md) and [glyph lifecycle evidence](../../../../.runtime/combat-review-20261008/feca-glyph-manual-03.json) show the bounded path and explicitly set full client verification to false.

## Current evidence and application of shared fixes

Fecalistófedes (6967) has an end-to-end offline glyph lifecycle report and a prepared live acceptance card. The class table still records the rest as not individually reviewed; this one case cannot be generalized.

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
