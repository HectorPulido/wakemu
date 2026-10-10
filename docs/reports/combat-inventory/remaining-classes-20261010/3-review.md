# Enutrof (native class 3) combat review — 2026-10-10

## Scope and evidence rule

This review covers the owned active/passive spell catalog, extra/granted spell rows, native spell dependency closure, class innate closure, profile/book and area dependencies, runtime route status, class-specific resource/state lifecycle concerns and current verification. Catalog inclusion, graph reachability, handler registration and isolated primitive tests are inventory evidence only; they do not establish a functional spell or class mechanic. “Unverified” means the reviewed material has not demonstrated the behavior; “missing” is reserved for an explicitly absent native/runtime definition or route.

Primary class catalog and effect/state/criterion detail: [existing class inventory](../clases/3.md). Native typed source: [18-class component projection](../class-native-mechanic-components-20261007.json), [native typed graph and provenance](../class-native-mechanic-graph-20261007.md) and [native graph JSON](../class-native-mechanic-graph-20261007.json). Class mechanic requirements register: [requirements](../class-mechanic-requirements-20261007.md) and [machine records](../class-mechanic-requirements-20261007.json). Route source: [class effect route inventory](../class-effect-route-inventory-20261010.md) and [machine data](../class-effect-route-inventory-20261010.json).

The active PostgreSQL native catalog is authoritative for current native records; `server/protocol/` was intentionally removed and its absence is not a gap. The detailed spell/state/profile/area projections and requirements register cited below are Oct. 7 historical exports; current route wiring is instead covered by the Oct. 10 route matrix. See the [read-only PostgreSQL source audit](../remaining-classes-source-audit-20261010.md) for published-release provenance and limits.

## Owned active and passive roster

The class source lists **21 active** and **17 passive** definitions (38 class-spell IDs total). Every row below is included so future verification can be tracked without mistaking catalog presence for success. Detailed roots, native families, related states and textual conditions are preserved in the linked class inventory.

| ID | Native label | Kind | Review status in source inventory |
|---:|---|---|---|
| 2008 | Pala del Juicio | Activo | Sin revisión individual; in-game: Pendiente |
| 2010 | Pala Asesina | Activo | Sin revisión individual; in-game: Pendiente |
| 2011 | Jarabe de Pala | Activo | Sin revisión individual; in-game: Pendiente |
| 2012 | Pala Drona | Activo | Sin revisión individual; in-game: Pendiente |
| 2013 | Pala Sísmica | Activo | Sin revisión individual; in-game: Pendiente |
| 2014 | Cortes | Activo | Sin revisión individual; in-game: Pendiente |
| 2015 | Timo | Activo | Sin revisión individual; in-game: Pendiente |
| 2016 | Impuesto | Activo | Sin revisión individual; in-game: Pendiente |
| 2017 | Depuración | Activo | Sin revisión individual; in-game: Pendiente |
| 2018 | Fusión | Activo | Sin revisión individual; in-game: Pendiente |
| 2019 | Meteoro | Activo | Sin revisión individual; in-game: Pendiente |
| 2021 | Brasas | Activo | Sin revisión individual; in-game: Pendiente |
| 2022 | Río de Lava | Activo | Sin revisión individual; in-game: Pendiente |
| 2026 | Riqueza Sísmica | Activo | Sin revisión individual; in-game: Pendiente |
| 2032 | Purga | Activo | Sin revisión individual; in-game: Pendiente |
| 2037 | Explosión de Grisú | Activo | Sin revisión individual; in-game: Pendiente |
| 2064 | Fuerza de la Edad | Activo | Sin revisión individual; in-game: Pendiente |
| 6324 | Aceleración | Activo | Sin revisión individual; in-game: Pendiente |
| 6337 | Torpeza | Activo | Sin revisión individual; in-game: Pendiente |
| 8240 | Avaricia | Activo | Sin revisión individual; in-game: Pendiente |
| 8242 | Corrupción | Activo | Sin revisión individual; in-game: Pendiente |
| 2009 | Geología Avanzada | Pasivo | Sin revisión individual; in-game: Pendiente |
| 2028 | Arte de los Caminantes | Pasivo | Sin revisión individual; in-game: Pendiente |
| 2039 | Bendición Anutrof | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5059 | Colocaciones Bursátiles | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5071 | Codicia | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5075 | Perfórtanker | Pasivo | Sin revisión individual; in-game: Pendiente |
| 5076 | Cotización en Bolsa | Pasivo | Sin revisión individual; in-game: Pendiente |
| 6326 | Intereses Acreedores | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8272 | Intercambio Asíncrono | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8273 | Estribo | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8274 | Provectrato | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8275 | La Binocular | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8276 | Seguro a Todo Riesgo | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8277 | Protección Mineral | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8278 | Optimización Focal | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8279 | Tuneladora | Pasivo | Sin revisión individual; in-game: Pendiente |
| 8280 | Herencia | Pasivo | Sin revisión individual; in-game: Pendiente |

## Extra and granted actions

These spell IDs are catalogued separately from the ordinary class roster. The source explicitly says its routes are not necessarily an exhaustive transformation list. Unlock, grant timing, casting eligibility, effects, costs, UI/action-bar presentation and cleanup remain distinct acceptance points.

| ID | Native label | Kind | Review status |
|---:|---|---|---|
| 2027 | Llamada del Compañero | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 2038 | Perfórserker | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 2063 | Excavación | Extra/granted action | listed; acquisition and runtime remain separately unverified |
| 6405 | Deuda | Extra/granted action | listed; acquisition and runtime remain separately unverified |

## Native typed closure

The class-specific direct spell dependency projection contains **area=8, area_mask=7, effect=762, hmi_trigger=22, native_condition_class=47, native_mask_bit=22, profile=5, spell=49, state=39** nodes by typed kind. These are unioned native class spell/extras dependencies, not a count of mechanics proven to execute. Direct state IDs (39): 3309, 3462, 3614, 3643, 5203, 5204, 5205, 5237, 5395, 5398, 5399, 5400, 5401, 5402, 702, 842, 8552, 8553, 8554, 8559, 8560, 8561, 8562, 8563, 8564, 8566, 8567, 8572, 8581, 8582, 8583, 8586, 8587, 8588, 8589, 8590, 8591, 8607, 8895.

Direct area IDs (8): 1925, 202, 203, 204, 205, 207, 209, 781.

Innate seed states (3): 3652, 4464, 5197. Innate dependency state closure (41): 3462, 3614, 3643, 3652, 4464, 5197, 5203, 5204, 5205, 5395, 5398, 5399, 5400, 5401, 5402, 702, 842, 8552, 8553, 8554, 8559, 8560, 8561, 8562, 8563, 8566, 8567, 8572, 8573, 8583, 8586, 8587, 8588, 8589, 8590, 8591, 8607, 8873, 8895, 9315, 9331. Innates may carry shared branches; a shared state, family or condition does not imply each dependent spell is broken. The class-only graph counts spell dependencies separately from common innates.

Native profile references (5):

| Profile ID | Native ability spell IDs in typed node | Evidence status |
|---:|---|---|
| 1380 | 2058, 2077, 3541, 3542, 8257, 8258, 8259 | Native profile/book record present; complete acquisition/control/ability use unverified |
| 1381 | 2058, 2077, 3541, 3542, 8257, 8258, 8259 | Native profile/book record present; complete acquisition/control/ability use unverified |
| 1382 | 2058, 2077, 3541, 3542, 8257, 8258, 8259 | Native profile/book record present; complete acquisition/control/ability use unverified |
| 1383 | 2058, 2077, 3541, 3542, 8257, 8258, 8259 | Native profile/book record present; complete acquisition/control/ability use unverified |
| 1384 | 2058, 2077, 3541, 3542, 8257, 8258, 8259 | Native profile/book record present; complete acquisition/control/ability use unverified |

The graph's profile nodes have reachability `unknown`. Profile contents describe native definitions only; they do not attest that class effects create these actors, add their books, transfer a turn, permit casts or remove them correctly.

## Class resources and secondary states

The class has ordinary AP/MP/WP pools plus prospecting/treasure and deposit/mining state chains in the native closure: `Cazatesoros` 3652, `Tesoros` 8552, `Colocaciones Bursátiles` 8553–8554, ore-vein states 5203–5205 and 8559–8567, and debt/beserker-related states 5395 and 702 (`Perfórserker`). Four native deposit prototypes (202–205) carry grade/ownership/lifecycle data. State names/IDs establish the records exist; they do not prove actual gain/loss amount, branch progression, reset timing, loot/prospecting application or client HUD updates. State 8873 is an explicit missing native definition with guarded/unknown reachability.

## Runtime routes and class mechanic review

The current Oct. 10 route matrix covers **60/72 registered** direct spell-closure family bindings and **12 construction-gated** bindings for this class. Gated family IDs: 300, 301, 302, 305, 307, 315, 339, 421, 422, 813, 843, 1013. No missing or unregistered family binding is listed for this class in the matrix. A construction-gated binding means its handler path requires the documented authority/factory at runtime; it is not an absent native definition or a gameplay failure. This remains route evidence, not functional coverage: class-specific source ownership, conditions, target behavior, transaction, client delivery and lifecycle still need acceptance. See the [current route matrix](../class-effect-route-inventory-20261010.json) generated against published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

The historical typed projection includes prospecting/loot-oriented passives, five native ability profiles (1380–1384), eight class areas, and a historical unresolved state reference 8873. The captured profile definitions each contain the same seven book ability IDs (2058, 2077, 3541, 3542, 8257, 8258, 8259); this is structural book content, not proof each profile/book can be obtained or cast.

**Lifecycle, cleanup and client risk.** Validate cast rejection atomicity (AP/MP/WP/resource and state unchanged), created area/summon identity and owner/controller, entry/exit or turn-start timing, charge/timer expiration, death/removal, reconnect/checkpoint, next-fight cleanup, visible client actor/area/action-bar state and actual combat outcome. The shared runtime has implementations for many underlying boundaries, but the class inventories do not certify every native producer or lifecycle path. Whole-class manual client proof remains unverified; bounded offline cases below have narrower evidence and are not client certification.

The class graph includes deposit prototypes 202–205, glyph prototypes 207/209/781/1925, and profiles 1380–1384. The 2026-10-07 area matrix says no audited creation-type branch for ENUTROF_DEPOSIT, while the current `combat_effect_area.py` has a grade capture branch and the later native deposit contract records construction/cloning checks for all four prototypes. Treat the older matrix row as stale for constructor recognition; the runtime does have shared type12/deposit-grade handling. Entry-event source, full callback/lifecycle, state delivery and client domains remain unknown, so this newer primitive support still does not establish full gameplay delivery.

## Runtime handlers inspected

The current deposit creation/grade branch is in [`combat_effect_area.py`](../../../../server/wakfu_server/combat/combat_effect_area.py), type12 predicates and ownership queries in [`combat_area_predicates.py`](../../../../server/wakfu_server/combat/combat_area_predicates.py) and [`combat_effect_area_queries.py`](../../../../server/wakfu_server/combat/combat_effect_area_queries.py), with callback dispatch in [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py). The native primitive evidence is [deposit contract](../native-enutrof-deposit-contract-20261007.md).

## Current evidence and application of shared fixes

The Oct. 7 projection reported state 8873 as missing from its exported definition set and retained an original guarded reference. This is a historical export result only; current published-catalog presence/absence is not concluded from that old record. Deposit lifecycle report proves subtype primitives only; it explicitly does not prove a complete class gameplay sequence.

Prior shared work for Cra, Iop, Sacrier, Eniripsa and Osamodas can apply only where a dependency/contract overlaps: e.g. family dispatcher semantics, conditions, actor-state application, area ownership/removal, event producers, client state delivery or summon control. It can eliminate a shared blocker for these spells when the same native contract is present, but it does not prove an individual spell, passive, class-specific target rule or turn-cycle. Verify the exact root/child IDs and native condition before marking any row complete. The broad route, handler, scenario and dependency counts must not be converted into a class completion percentage.

## Explicit gaps and next acceptance coverage

- Each listed active, passive and extra remains individually unverified except for the exact scoped sequence explicitly cited above. The per-spell native conditions in the source inventory remain to be checked against live behavior.
- The full class-owned secondary/granted-book acquisition matrix, every spell/state/area branch at its legal levels, client presentation and complete fight-cycle cleanup are not exhaustively included in these short reports; the linked JSON/graph are the canonical exhaustive machine inventories for the exported projection. No 100% functionality claim is made.
- Class-specific resource/secondary-state reads, gains/losses, caps and reset points need a complete legal-turn acceptance across a new fight. State presence in the graph or original effects alone is not lifecycle proof.
- Shared fixes from other classes should be inherited only after comparing source signatures and runtime authorities. No blanket cross-class pass is inferred.

**Historical native export note:** `state:8873` was listed as missing in the Oct. 7 typed projection and has `reachability=unknown`. Do not carry that as a current source gap without reconciling the active PostgreSQL release.

## Related evidence

- [Class mechanic gap index](../class-mechanic-gap-index-20261007.md) and [dependency coverage report](../class-dependency-coverage-20261007.md).
- [Native area prototype/lifecycle matrix](../class-native-area-contracts-20261007.csv); area IDs above can be looked up by prototype type, class ownership, creation, activation, removal and client contract.
- [Class engine active review](../class-engine-general-review-20261007.md): global active-scenario observations are path diagnostics and do not certify full class functionality.
- [Requirements register](../class-mechanic-requirements-20261007.md): unweighted shared contract units, not per-spell completion.

## Published authority reconciliation — 2026-10-10

PostgreSQL is the current catalog authority; the absence of `server/protocol/` is intentional and is not a missing-definition finding. The route matrix was regenerated against the current runtime source and published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`: 161 registered families, 23 construction-gated families, no unregistered families in that matrix scope. See [current route evidence](../class-effect-route-inventory-20261010.json) and the [read-only PostgreSQL source audit](../remaining-classes-source-audit-20261010.md). Registration does not establish complete mechanics, delivery or gameplay behavior; historical class graph provenance remains separately dated.
