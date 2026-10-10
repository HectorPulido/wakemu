# Rogue (native class 13) combat inventory — 2026-10-10

## Scope and evidence status

Inventory only. This review does not modify runtime code, catalog data, services or the database. PostgreSQL `native_catalog_active` and its immutable published documents are the current native-catalog authority; `server/protocol/` was intentionally removed after migration and its absence is not a catalog gap. The active published release is `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. See the [read-only source audit](../remaining-classes-source-audit-20261010.md) for release provenance and reconciliation boundaries.

The per-class spell rows are cross-checked against the installed-client [inventory.json](../inventory.json); detailed per-class typed dependency IDs and graph edges below come from the Oct. 7 native export and remain historical structure, not current evidence of a missing or present native definition. The Oct. 8 route overlay is historical; current route registration/gating is reported separately below from the Oct. 10 matrix. `reachability=unknown` in the old graph remains an unknown reachability claim. Catalog inclusion, route registration, handler existence and bounded fixtures are not functional class proof.

Sources: [class spell inventory](../clases/13.md); [historical typed component projection](../class-native-mechanic-components-20261007.json); [historical typed graph](../class-native-mechanic-graph-20261007.md) and [machine graph](../class-native-mechanic-graph-20261007.json); [historical requirements register](../class-mechanic-requirements-20261007.md); [Oct. 10 route inventory](../class-effect-route-inventory-20261010.md).

## Owned active and passive spells

The class inventory records **21 active and 20 passive IDs (41 total)**. Exact source names, kind, unlock level, family notes, individual review note and gameplay status are reproduced below. `Pendiente` is source catalog status, not a fresh live test. Family notes are copied from the class inventory and remain historical route hints, not current route claims. Per-root criteria/effects remain in the linked class Markdown.

| ID | Native label | Kind | Unlock | Historical family notes | Source review | In-game status |
|---:|---|---|---:|---|---|
| 6463 | Llamambrada | Activo | 1 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6464 | Bomba Pegajosa | Activo | 3 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6465 | Ejecución | Activo | 9 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6466 | Cruce | Activo | 15 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6467 | Perforación | Activo | 21 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6468 | Metralla | Activo | 1 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6469 | Tromba | Activo | 5 | 28,345,430,1080,1099 | Entrada legal real validada: daño y desplazamiento en nivel5; daño y muerte en nivel200 | Pendiente |
| 6470 | Bala Emplomada | Activo | 11 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6471 | Daga Bumerán | Activo | 17 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6472 | Púlsar | Activo | 23 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6473 | Golpe Rápido | Activo | 1 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6474 | Trampa | Activo | 7 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6475 | Arcabuz | Activo | 13 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6476 | Obliteración | Activo | 25 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6478 | Larga Hoja | Activo | 19 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |
| 6489 | Descargador | Activo | 90 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6490 | Patada | Activo | 3 | 345 | Sin revisión individual | Pendiente |
| 6491 | Evanescencia | Activo | 45 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6492 | Gancho | Activo | 30 | 305 | Sin revisión individual | Pendiente |
| 6493 | Imán | Activo | 60 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6494 | Fumígenos | Activo | 15 | 430 | Sin revisión individual | Pendiente |
| 6479 | Tymobum | Pasivo | 10 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6480 | Gran Evasión | Pasivo | 55 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6481 | Bomber Fan | Pasivo | 45 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6482 | Artificiero | Pasivo | 20 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6483 | Túnica Reforzada | Pasivo | 40 | 430 | Sin revisión individual | Pendiente |
| 6484 | Desminador | Pasivo | 75 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6485 | Hoja Oxidada | Pasivo | 70 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6486 | Maestro de las Hojas | Pasivo | 30 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6487 | Pared de Pólvora | Pasivo | 80 | 345,1080 | Sin revisión individual | Pendiente |
| 6488 | Fugitivo | Pasivo | 25 | 345 | Sin revisión individual | Pendiente |
| 7062 | Tiro Sorpresa | Pasivo | 50 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7063 | Barril | Pasivo | 65 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7064 | Kabúm | Pasivo | 85 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7065 | Explobomba | Pasivo | 15 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7090 | Bombas Elementales | Pasivo | 35 | 430 | Sin revisión individual | Pendiente |
| 7091 | Maestro Tymador | Pasivo | 60 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7092 | Jackpot | Pasivo | 90 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7982 | Táctico | Pasivo | 95 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7983 | Rastro de Pólvora | Pasivo | 10 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7984 | Bombas de Efecto Retardado | Pasivo | 100 | 28,345,430,1080,1099 | Sin revisión individual | Pendiente |

## Secondary/granted actions and books

These are listed by the source as extra granted actions, separate from ordinary owned spells. Acquisition routes, temporary/permanent book semantics, cost/conditions, UI/action-bar visibility, use, restoration and cleanup are separate acceptance criteria. This is not proof these are exhaustive grant paths.

| ID | Native label | Category | Source review | In-game status |
|---:|---|---|---|---|
| 6495 | Detonación | extra/granted | Sin revisión individual | Pendiente |
| 7904 | Ardid | extra/granted | Sin revisión individual | Pendiente |
| 7905 | Tymobot | extra/granted | Sin revisión individual | Pendiente |
| 7906 | Dinamita | extra/granted | Sin revisión individual | Pendiente |

## Historical native typed spell closure

The Oct. 7 class projection’s owned-spell-plus-extra closure counted **area=7, area_mask=2, effect=2839, hmi_trigger=74, native_condition_class=54, native_mask_bit=43, profile=4, spell=49, state=64** typed references. The exact direct state, area and profile references are retained below. These are historical native references and not assertions that definitions remain present in the current source snapshot, are dynamically reachable, have a registered current route, or execute correctly.

**Direct state IDs (64):** 3434, 3495, 3656, 5563, 5564, 5627, 6527, 6620, 6876, 6877, 756, 7916, 7917, 7918, 7919, 7921, 7923, 7927, 7928, 7934, 7935, 7936, 7937, 7942, 7980, 7981, 7982, 7983, 7984, 7985, 7986, 8022, 8025, 8026, 8027, 8028, 8033, 8034, 8035, 8037, 8040, 8041, 8042, 8049, 8050, 8051, 8052, 8053, 8054, 8057, 8172, 8173, 8174, 8303, 8892, 8893, 8894, 8896, 8907, 9304, 9307, 9310, 9311, 9374.

**Direct area IDs (7):** 1333, 1335, 1809, 1810, 1811, 1818, 781.

**Innate seed states (2):** 4464, 7920. **Historical innate dependency state closure (47):** 4464, 5563, 5564, 756, 7916, 7917, 7918, 7919, 7920, 7923, 7927, 7928, 7935, 7936, 7937, 7942, 7980, 7981, 7982, 7983, 7984, 7985, 7986, 8022, 8028, 8037, 8041, 8049, 8050, 8052, 8053, 8054, 8057, 8093, 8172, 8173, 8174, 8414, 8415, 8433, 9305, 9307, 9310, 9311, 9315, 9331, 9367. This closure is separate from spell dependencies; shared innate states do not prove per-spell lifecycle.

**Historical profile references (4):**

| Profile ID | Ability spell references in Oct. 7 graph | Reachability |
|---:|---|---|
| 1236 | 6517, 6520, 7952, 7951 | unknown |
| 3795 | none in historical projection | unknown |
| 3796 | none in historical projection | unknown |
| 3797 | none in historical projection | unknown |

The historical component projection marks `state:7986` in `unknown_native_definitions`; that flag describes its Oct. 7 export only. Current source authority is the active PostgreSQL native catalog; this review does not infer current absence from that snapshot.

## Current effect route coverage

The current Oct. 10 route matrix covers **50/63 registered** direct spell-closure family bindings and **13 construction-gated** bindings for this class. Gated family IDs: 300, 301, 302, 305, 307, 315, 331, 340, 421, 422, 843, 935, 1013. No missing or unregistered family binding is listed for this class in the matrix. A construction-gated binding means its handler path requires the documented authority/factory at runtime; it is not an absent native definition or a gameplay failure. This remains route evidence, not functional coverage: class-specific source ownership, conditions, target behavior, transaction, client delivery and lifecycle still need acceptance. See the [current route matrix](../class-effect-route-inventory-20261010.json) generated against published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

## Class resource, secondary state and spatial lifecycle

The installed client contract maps breed 13 to characteristic 57 ROGUE_RESOURCE and popup state7919. The explicit current HUD synchronization only maps breeds8 and11; synchronization for breed13 is unverified. Bomb control/resource, detonator grants, and action-bar/event presentation must be traced as independent contracts.

Areas 1333,1335,1809,1810,1811,1818 and shared781. Profiles 1236,3795,3796,3797; profile1236 lists 6517,6520,7952,7951; the other three profiles have empty book arrays in the old graph. Their current semantic identities and creation paths must be verified from current native source.

Rogue coverage must include three bomb families/placements, bomb count and owner identity, combinations/wall geometry, detonations and granted actions6495/7904/7905/7906, class resource/initiative changes, areas/traps and any profile-based Tymobot actor. Verify creation ordering, delayed/turn triggers, replacement/cap rules, displacement/death, chain reactions exactly once, cleanup and client representations.

Across the class, test the authoritative actor turn and legal native conditions, successful and rejected casts, exact AP/MP/WP and class-meter mutation, duplicate states and first-match semantics, and replay/reconnect. Summoned actors need owner/controller, book completeness, turn eligibility, and exact once-only death/retirement. Areas, traps, bombs, seeds or glyphs need identity, footprint, target rules, trigger timing, expiry/removal and cell reuse. State/resource/action-bar delivery and map objects need client verification. These lifecycle points remain **unverified** except for narrowly scoped evidence below; they are not all individually marked missing.

## Current shared runtime inspected

[area lifecycle](../../../../server/wakfu_server/combat/combat_effect_area.py), [area events](../../../../server/wakfu_server/combat/combat_effect_area_events.py), [area catalog](../../../../server/wakfu_server/combat/combat_effect_area_catalog.py), [trap area contract](../../../../server/wakfu_server/combat/combat_trap_area.py), [summon creation](../../../../server/wakfu_server/combat/combat_summon_creation.py), [spellbook](../../../../server/wakfu_server/combat/combat_summon_spellbook.py), [retirement](../../../../server/wakfu_server/combat/combat_summon_retirement.py), [conditions](../../../../server/wakfu_server/combat/combat_conditions.py), [HUD resource sync](../../../../server/wakfu_server/combat/combat_hud_resource.py).

These modules contain shared contract paths (conditions, effects, area/state lifecycle, summon/carry handling, or resource delivery); their existence is not proof that this class’s complete native spell closure selects them or passes class-specific guards. `combat_hud_resource.py` explicitly maps only breeds8 and11 at present; this establishes absence from that particular explicit mapping, not absence of every possible class resource producer.

## Bounded evidence and applicability of shared fixes

No scoped Rogue full-cycle/bomb-chain client report was found in the reviewed materials. Historical typed graph marks `state:7986` unknown/missing for Rogue; this is an old export status, not a current gap claim. No dedicated bomb-named runtime module was found; bomb functionality may be modeled by shared area/state/effect paths, so lack of a module filename is not a missing behavior finding.

Earlier shared fixes for Cra, Iop, Sacrier, Eniripsa and Osamodas can apply where the exact native/runtime contract overlaps: criterion interpretation, effect-family dispatch, resource transaction/rollback, state ledger, area ownership and callback lifecycle, summon identity/book delivery, carried actor relations, event timing, or client notification. Reuse only after comparing the concrete native spell/effect/state/profile IDs and authoritative producer. A shared fix removes only its overlapping blocker; it does not certify another spell, passive, book grant, target branch, class counter, or complete fight cycle. No broad “other classes fixed” inference is made.

## Explicit gaps and next verification

- **Current source reconciliation:** the active PostgreSQL release is authoritative; this report’s typed closure remains Oct. 7 historical detail and has not been independently reconciled node-by-node to the active release. Do not infer current missing/present status from the folder layout.
- **Routes:** use the Oct. 10 route matrix linked above for current registration/gating. It reports route wiring only; per-effect runtime semantics and gameplay remain separate acceptance scope.
- **Per-spell acceptance:** every active, passive and extra row needs current-source reconciliation and legal cast/cost/target/effect/rejection/rollback checks. This short report does not enumerate every per-level native effect tree; the linked machine projection is historically exhaustive only for its export.
- **Books/actors:** complete grant timing, book IDs/abilities, actor creation, controller/turn transfer, summon cap/replacement, dismissal/death and next-fight cleanup are not exhaustively verified.
- **Resources/states:** characteristic reads/writes, class-specific meter caps and reset, all secondary state transitions, client HUD/popup and reconnect/fight cleanup remain unverified beyond the exact evidence stated above.
- **Spatial systems:** exact footprints, target selectors, activation ownership/timing, collision, chain/repeat behavior, retirement, reuse and client visibility need complete legal combat and follow-up fight proof.
- **Requirements denominator:** Oct. 7 report says 543 global unweighted units and zero global full-cycle verified units with a provisional denominator. This old global total cannot be converted to a current per-class percentage.

No 100% catalog/functionality claim is made.

## Related evidence

- [Native area lifecycle contracts (historical)](../class-native-area-contracts-20261007.csv) and [target selector contracts (historical)](../class-native-target-selector-contracts-20261007.csv).
- [Class dependency coverage (historical)](../class-dependency-coverage-20261007.md) and [class engine review (historical)](../class-engine-general-review-20261007.md).
- [Installed client breed HUD resource contract](../../../protocol/native-breed-hud-resources.md) (client source contract only, no GUI verification).

## Published authority reconciliation — 2026-10-10

PostgreSQL is the current catalog authority; the absence of `server/protocol/` is intentional and is not a missing-definition finding. The route matrix was regenerated against the current runtime source and published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`: 161 registered families, 23 construction-gated families, no unregistered families in that matrix scope. See [current route evidence](../class-effect-route-inventory-20261010.json) and the [read-only PostgreSQL source audit](../remaining-classes-source-audit-20261010.md). Registration does not establish complete mechanics, delivery or gameplay behavior; historical class graph provenance remains separately dated.
