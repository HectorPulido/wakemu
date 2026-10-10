# Pandawa (native class 12) combat inventory — 2026-10-10

## Scope and evidence status

Inventory only. This review does not modify runtime code, catalog data, services or the database. PostgreSQL `native_catalog_active` and its immutable published documents are the current native-catalog authority; `server/protocol/` was intentionally removed after migration and its absence is not a catalog gap. The active published release is `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. See the [read-only source audit](../remaining-classes-source-audit-20261010.md) for release provenance and reconciliation boundaries.

The per-class spell rows are cross-checked against the installed-client [inventory.json](../inventory.json); detailed per-class typed dependency IDs and graph edges below come from the Oct. 7 native export and remain historical structure, not current evidence of a missing or present native definition. The Oct. 8 route overlay is historical; current route registration/gating is reported separately below from the Oct. 10 matrix. `reachability=unknown` in the old graph remains an unknown reachability claim. Catalog inclusion, route registration, handler existence and bounded fixtures are not functional class proof.

Sources: [class spell inventory](../clases/12.md); [historical typed component projection](../class-native-mechanic-components-20261007.json); [historical typed graph](../class-native-mechanic-graph-20261007.md) and [machine graph](../class-native-mechanic-graph-20261007.json); [historical requirements register](../class-mechanic-requirements-20261007.md); [Oct. 10 route inventory](../class-effect-route-inventory-20261010.md).

## Owned active and passive spells

The class inventory records **21 active and 17 passive IDs (38 total)**. Exact source names, kind, unlock level, family notes, individual review note and gameplay status are reproduced below. `Pendiente` is source catalog status, not a fresh live test. Family notes are copied from the class inventory and remain historical route hints, not current route claims. Per-root criteria/effects remain in the linked class Markdown.

| ID | Native label | Kind | Unlock | Historical family notes | Source review | In-game status |
|---:|---|---|---:|---|---|
| 4702 | Escupe Fuegos | Activo | 1 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4703 | Ronda General | Activo | 3 | 28 | Sin revisión individual | Pendiente |
| 4704 | Golpe Lechoso | Activo | 9 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4705 | Frasco Explosivo | Activo | 15 | 333 | Sin revisión individual | Pendiente |
| 4706 | Lactortazos | Activo | 21 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4707 | Escupe Leches | Activo | 1 | 305,333 | Sin revisión individual | Pendiente |
| 4708 | Nube de Leche | Activo | 5 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4709 | Tequileche | Activo | 11 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4710 | Tsunami | Activo | 17 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4711 | Fuente de Leches | Activo | 23 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4712 | Triple Karma Gnosborne | Activo | 1 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4713 | Six Roses | Activo | 7 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4714 | Golpe de Tonel | Activo | 13 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4715 | Lucha Cubalibre | Activo | 19 | 333 | Sin revisión individual | Pendiente |
| 4716 | Barriltzkrieg | Activo | 25 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4717 | Golpe de Bambú | Activo | 3 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4719 | Éter | Activo | 45 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4720 | Resaca | Activo | 60 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4721 | Happy Hour | Activo | 30 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6844 | Sed | Activo | 15 | 305 | Sin revisión individual | Pendiente |
| 6845 | Pandenkulo | Activo | 75 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4722 | Cóctel | Pasivo | 25 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4723 | Maestro de la Embriaguez | Pasivo | 30 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4724 | Tonel sin Fondo | Pasivo | 10 | 333,334,345 | Sin revisión individual | Pendiente |
| 4725 | Tonel Agresivo | Pasivo | 55 | 28 | Sin revisión individual | Pendiente |
| 4726 | Instinto Lechoso | Pasivo | 40 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5148 | Bambutella | Pasivo | 10 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5149 | Cianosis | Pasivo | 35 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5151 | Pandemia | Pasivo | 20 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5152 | Barrilisto | Pasivo | 15 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 6846 | Piripi | Pasivo | 100 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8595 | Paso Firme | Pasivo | 45 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8596 | Túnel Visión | Pasivo | 70 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8597 | Fermentación Láctica | Pasivo | 80 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8598 | La Gota que Colma el Vaso | Pasivo | 50 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8599 | Cianótico | Pasivo | 65 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8600 | Pandaperitivo | Pasivo | 60 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8601 | La Última | Pasivo | 90 | 345 | Sin revisión individual | Pendiente |

## Secondary/granted actions and books

These are listed by the source as extra granted actions, separate from ordinary owned spells. Acquisition routes, temporary/permanent book semantics, cost/conditions, UI/action-bar visibility, use, restoration and cleanup are separate acceptance criteria. This is not proof these are exhaustive grant paths.

| ID | Native label | Category | Source review | In-game status |
|---:|---|---|---|---|
| 4718 | Tonel | extra/granted | Sin revisión individual | Pendiente |
| 6847 | Karcham | extra/granted | Sin revisión individual | Pendiente |
| 6848 | Chamrak | extra/granted | Sin revisión individual | Pendiente |
| 8591 | Toneportación | extra/granted | Sin revisión individual | Pendiente |
| 8592 | Ebriedad | extra/granted | Sin revisión individual | Pendiente |

## Historical native typed spell closure

The Oct. 7 class projection’s owned-spell-plus-extra closure counted **area=1, area_mask=1, effect=772, hmi_trigger=7, native_condition_class=39, native_mask_bit=23, profile=1, spell=43, state=39** typed references. The exact direct state, area and profile references are retained below. These are historical native references and not assertions that definitions remain present in the current source snapshot, are dynamically reachable, have a registered current route, or execute correctly.

**Direct state IDs (39):** 1304, 3300, 3316, 3319, 3328, 3364, 3367, 3434, 3495, 3690, 4163, 6107, 6527, 6776, 7143, 751, 752, 9110, 9332, 9333, 9334, 9335, 9336, 9337, 9338, 9339, 9340, 9341, 9343, 9344, 9345, 9346, 9347, 9349, 9354, 9355, 9356, 9366, 9368.

**Direct area IDs (1):** 837.

**Innate seed states (2):** 4464, 7558. **Historical innate dependency state closure (16):** 1304, 3300, 3328, 3364, 3690, 4163, 4464, 6107, 6776, 7143, 7558, 9315, 9331, 9349, 9356, 9368. This closure is separate from spell dependencies; shared innate states do not prove per-spell lifecycle.

**Historical profile references (1):**

| Profile ID | Ability spell references in Oct. 7 graph | Reachability |
|---:|---|---|
| 3794 | none in historical projection | unknown |

## Current effect route coverage

The current Oct. 10 route matrix covers **54/64 registered** direct spell-closure family bindings and **10 construction-gated** bindings for this class. Gated family IDs: 300, 301, 302, 305, 307, 315, 421, 422, 843, 1013. No missing or unregistered family binding is listed for this class in the matrix. A construction-gated binding means its handler path requires the documented authority/factory at runtime; it is not an absent native definition or a gameplay failure. This remains route evidence, not functional coverage: class-specific source ownership, conditions, target behavior, transaction, client delivery and lifecycle still need acceptance. See the [current route matrix](../class-effect-route-inventory-20261010.json) generated against published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

## Class resource, secondary state and spatial lifecycle

The installed client contract maps breed 12 to characteristic 68 PANDAWA_RESOURCE and popup state3300. The current explicit server HUD synchronization does not include breed 12. A bounded Karcham/Chamrak regression covers carry/throw behavior offline, but does not prove the class counter’s current source or visible client value.

Direct area 837. Profile 3794 has an empty ability list in the historical typed graph. This is a profile reference, not evidence of an owned barrel summon book; resolve actual creation/grant data from current native source before enumerating summon abilities.

Pandawa class mechanics center on drunk/sober and barrel states, granted Tonel/Karcham/Chamrak/Toneportación/Ebriedad actions, carrier identity/follow/throw/release, and profile/book control if any actor is created. Check conditional costs and target restrictions, empty/occupied destinations, stabilized and uncarriable guards, rollback on rejection, owner death/disconnect, turn end, and next-fight cleanup.

Across the class, test the authoritative actor turn and legal native conditions, successful and rejected casts, exact AP/MP/WP and class-meter mutation, duplicate states and first-match semantics, and replay/reconnect. Summoned actors need owner/controller, book completeness, turn eligibility, and exact once-only death/retirement. Areas, traps, bombs, seeds or glyphs need identity, footprint, target rules, trigger timing, expiry/removal and cell reuse. State/resource/action-bar delivery and map objects need client verification. These lifecycle points remain **unverified** except for narrowly scoped evidence below; they are not all individually marked missing.

## Current shared runtime inspected

[carrying](../../../../server/wakfu_server/combat/combat_carrying.py), [carry handler](../../../../server/wakfu_server/combat/combat_carry_handler.py), [delivery](../../../../server/wakfu_server/combat/combat_carry_delivery.py), [release](../../../../server/wakfu_server/combat/combat_carry_release.py), [effect runtime](../../../../server/wakfu_server/combat/combat_effect_runtime.py), [conditions](../../../../server/wakfu_server/combat/combat_conditions.py), [HUD resource sync](../../../../server/wakfu_server/combat/combat_hud_resource.py).

These modules contain shared contract paths (conditions, effects, area/state lifecycle, summon/carry handling, or resource delivery); their existence is not proof that this class’s complete native spell closure selects them or passes class-specific guards. `combat_hud_resource.py` explicitly maps only breeds8 and11 at present; this establishes absence from that particular explicit mapping, not absence of every possible class resource producer.

## Bounded evidence and applicability of shared fixes

The [Oct. 8 four-class acceptance card](../manual-four-class-systems-20261008.md) documents Pandawa steps and cites [carry-6847-02.json](../../../../.runtime/combat-review-20261008/carry-6847-02.json) as actual owned6847→6848 regression, 3/3 PASS. This is specific carry-path evidence; it does not establish every extra grant, state/resource branch, barrel path, GUI behavior or whole fight lifecycle. The card itself prescribes further client acceptance.

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
