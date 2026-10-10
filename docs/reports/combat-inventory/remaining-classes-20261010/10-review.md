# Sadida (native class 10) combat inventory — 2026-10-10

## Scope and evidence status

Inventory only. This review does not modify runtime code, catalog data, services or the database. PostgreSQL `native_catalog_active` and its immutable published documents are the current native-catalog authority; `server/protocol/` was intentionally removed after migration and its absence is not a catalog gap. The active published release is `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. See the [read-only source audit](../remaining-classes-source-audit-20261010.md) for release provenance and reconciliation boundaries.

The per-class spell rows are cross-checked against the installed-client [inventory.json](../inventory.json); detailed per-class typed dependency IDs and graph edges below come from the Oct. 7 native export and remain historical structure, not current evidence of a missing or present native definition. The Oct. 8 route overlay is historical; current route registration/gating is reported separately below from the Oct. 10 matrix. `reachability=unknown` in the old graph remains an unknown reachability claim. Catalog inclusion, route registration, handler existence and bounded fixtures are not functional class proof.

Sources: [class spell inventory](../clases/10.md); [historical typed component projection](../class-native-mechanic-components-20261007.json); [historical typed graph](../class-native-mechanic-graph-20261007.md) and [machine graph](../class-native-mechanic-graph-20261007.json); [historical requirements register](../class-mechanic-requirements-20261007.md); [Oct. 10 route inventory](../class-effect-route-inventory-20261010.md).

## Owned active and passive spells

The class inventory records **21 active and 20 passive IDs (41 total)**. Exact source names, kind, unlock level, family notes, individual review note and gameplay status are reproduced below. `Pendiente` is source catalog status, not a fresh live test. Family notes are copied from the class inventory and remain historical route hints, not current route claims. Per-root criteria/effects remain in the linked class Markdown.

| ID | Native label | Kind | Unlock | Historical family notes | Source review | In-game status |
|---:|---|---|---:|---|---|
| 914 | Toxinas | Activo | 90 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 915 | Árbol | Activo | 3 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 918 | Lágrima de Sadida | Activo | 3 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 919 | Viento Envenenado | Activo | 7 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 920 | Sacrificio Muñequero | Activo | 15 | 28 | Sin revisión individual | Pendiente |
| 921 | Vaporizar | Activo | 1 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 922 | Drenaje | Activo | 21 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 925 | Zarza | Activo | 1 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 927 | Hierbas Locas | Activo | 11 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 928 | Resfriado | Activo | 13 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 929 | Abono | Activo | 5 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 930 | Arcilla | Activo | 9 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 931 | Herrumbre | Activo | 15 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 932 | Hedor Boscoso | Activo | 25 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 934 | Komhir | Activo | 19 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 935 | Terremoto | Activo | 17 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 937 | Zarzas Múltiples | Activo | 23 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 938 | Borrasca | Activo | 1 | 28,47,325,430,560,561,562,563,1030 | Sin revisión individual | Pendiente |
| 5057 | Despertar Silvestre | Activo | 30 | 28,196 | Sin revisión individual | Pendiente |
| 7054 | Fertilizante | Activo | 45 | 47 | Sin revisión individual | Pendiente |
| 8139 | Fuerza de la Naturaleza | Activo | 60 | 430 | Sin revisión individual | Pendiente |
| 912 | Sadida Solitario | Pasivo | 35 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 913 | Guarda Plantas | Pasivo | 85 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 916 | Enlace Muñequero | Pasivo | 45 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 917 | Don Silvestre | Pasivo | 20 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 933 | Explomuñeca | Pasivo | 15 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 4959 | Rezo Sadida | Pasivo | 10 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5055 | Terreno Infectado | Pasivo | 95 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5058 | Murmullos Salvajes | Pasivo | 100 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5234 | Venenoso | Pasivo | 60 | 430 | Sin revisión individual | Pendiente |
| 7053 | Terreno de Entendimiento | Pasivo | 65 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8149 | Bendición Vudul | Pasivo | 90 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8150 | Empuje Silvestre | Pasivo | 75 | 349 | Bloqueo detectado; corrección parcial en trabajo | Pendiente |
| 8151 | Terreno Fértil | Pasivo | 40 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8152 | Crecimiento Acelerado | Pasivo | 10 | 47 | Sin revisión individual | Pendiente |
| 8153 | Devoción Muñequil | Pasivo | 30 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8154 | Mala Semilla | Pasivo | 25 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8155 | Ciclo Silvestre | Pasivo | 55 | 28 | Sin revisión individual | Pendiente |
| 8156 | Comunicación Vegetal | Pasivo | 80 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8157 | Conocimiento Sadida | Pasivo | 50 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8158 | Cadena de la Naturaleza | Pasivo | 70 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |

## Secondary/granted actions and books

These are listed by the source as extra granted actions, separate from ordinary owned spells. Acquisition routes, temporary/permanent book semantics, cost/conditions, UI/action-bar visibility, use, restoration and cleanup are separate acceptance criteria. This is not proof these are exhaustive grant paths.

| ID | Native label | Category | Source review | In-game status |
|---:|---|---|---|---|
| 911 | La Superpoderosa | extra/granted | Sin revisión individual | Pendiente |
| 926 | La Vudul | extra/granted | Sin revisión individual | Pendiente |
| 8137 | Semilla | extra/granted | Sin revisión individual | Pendiente |

## Historical native typed spell closure

The Oct. 7 class projection’s owned-spell-plus-extra closure counted **area=9, area_mask=7, effect=1416, hmi_trigger=72, native_condition_class=48, native_mask_bit=36, profile=8, spell=53, state=68** typed references. The exact direct state, area and profile references are retained below. These are historical native references and not assertions that definitions remain present in the current source snapshot, are dynamically reachable, have a registered current route, or execute correctly.

**Direct state IDs (68):** 1144, 3309, 3434, 3495, 3587, 3590, 3591, 3595, 3596, 3597, 3598, 3599, 3600, 3615, 3616, 3617, 3624, 3640, 3645, 3681, 3682, 3827, 3837, 3856, 3857, 6505, 6506, 6527, 8187, 8188, 8189, 8190, 8191, 8192, 8193, 8194, 8195, 8196, 8197, 8198, 8199, 8200, 8201, 8202, 8204, 8205, 8206, 8207, 8208, 8209, 8210, 8211, 8212, 8213, 8214, 8215, 8216, 8217, 8224, 8225, 8226, 8227, 8228, 8229, 8230, 8257, 8258, 8259.

**Direct area IDs (9):** 1835, 1836, 1850, 1851, 1852, 1853, 1854, 1855, 781.

**Innate seed states (2):** 4464, 7561. **Historical innate dependency state closure (53):** 3309, 3591, 3595, 3596, 3597, 3598, 3599, 3600, 3616, 3617, 3624, 3681, 3682, 3856, 3857, 4464, 7561, 8187, 8188, 8189, 8190, 8191, 8192, 8193, 8194, 8195, 8196, 8197, 8198, 8199, 8200, 8202, 8204, 8205, 8206, 8207, 8208, 8209, 8211, 8212, 8213, 8214, 8215, 8216, 8217, 8225, 8226, 8229, 8257, 8258, 8259, 9315, 9331. This closure is separate from spell dependencies; shared innate states do not prove per-spell lifecycle.

**Historical profile references (8):**

| Profile ID | Ability spell references in Oct. 7 graph | Reachability |
|---:|---|---|
| 3745 | 8140 | unknown |
| 3746 | 5153, 5023, 5021, 5026, 5024, 5025, 5356 | unknown |
| 3747 | 5024, 8138 | unknown |
| 3748 | 5023, 8138 | unknown |
| 3749 | 5021, 8138 | unknown |
| 3750 | 5026, 8138 | unknown |
| 3751 | 5025, 5356, 8138 | unknown |
| 5577 | none in historical projection | unknown |

The source class inventory marks passive **8150** “Bloqueo detectado; corrección parcial en trabajo.” This is a historical work note, not a current confirmed defect or a confirmed fix. Its current disposition is **unverified**.

## Current effect route coverage

The current Oct. 10 route matrix covers **69/77 registered** direct spell-closure family bindings and **8 construction-gated** bindings for this class. Gated family IDs: 300, 301, 307, 315, 421, 422, 843, 1013. No missing or unregistered family binding is listed for this class in the matrix. A construction-gated binding means its handler path requires the documented authority/factory at runtime; it is not an absent native definition or a gameplay failure. This remains route evidence, not functional coverage: class-specific source ownership, conditions, target behavior, transaction, client delivery and lifecycle still need acceptance. See the [current route matrix](../class-effect-route-inventory-20261010.json) generated against published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

## Class resource, secondary state and spatial lifecycle

The installed client contract lists characteristic 61 SADIDA_RESOURCE and no popup state. The current `combat_hud_resource.py` projection does not include breed 10, so value synchronization through that explicit path is missing; any alternative writer/initialization path remains unverified. Do not infer that the class has no resource mechanic from a blank popup.

Areas 1835, 1836, 1850–1855 and shared area 781. Profiles 3745–3751 and 5577; historical ability refs are 8140; 5153,5023,5021,5026,5024,5025,5356; pairs 5024/5023/5021/5026/5025 with 8138; and empty book 5577. Their association to dolls/trees must follow native definitions; profile presence alone is not summon creation/control proof.

Sadida-specific coverage must include every doll profile/book and owned-versus-extra acquisition (911,926,8137), tree transformation/return, seed placement/activation, doll count/ownership, state transfer and passive-trigger timing. Area and summon identity must survive movement, KO/removal, controller changes, reconnect and fight end. Resource value, dolls, seeds and states need clean reset and client presentation.

Across the class, test the authoritative actor turn and legal native conditions, successful and rejected casts, exact AP/MP/WP and class-meter mutation, duplicate states and first-match semantics, and replay/reconnect. Summoned actors need owner/controller, book completeness, turn eligibility, and exact once-only death/retirement. Areas, traps, bombs, seeds or glyphs need identity, footprint, target rules, trigger timing, expiry/removal and cell reuse. State/resource/action-bar delivery and map objects need client verification. These lifecycle points remain **unverified** except for narrowly scoped evidence below; they are not all individually marked missing.

## Current shared runtime inspected

[summon creation](../../../../server/wakfu_server/combat/combat_summon_creation.py), [initialization](../../../../server/wakfu_server/combat/combat_summon_initialization.py), [spellbooks](../../../../server/wakfu_server/combat/combat_summon_spellbook.py), [retirement](../../../../server/wakfu_server/combat/combat_summon_retirement.py), [area lifecycle](../../../../server/wakfu_server/combat/combat_effect_area.py), [area events](../../../../server/wakfu_server/combat/combat_effect_area_events.py), [state managers](../../../../server/wakfu_server/combat/combat_state_managers.py), [HUD resource sync](../../../../server/wakfu_server/combat/combat_hud_resource.py).

These modules contain shared contract paths (conditions, effects, area/state lifecycle, summon/carry handling, or resource delivery); their existence is not proof that this class’s complete native spell closure selects them or passes class-specific guards. `combat_hud_resource.py` explicitly maps only breeds8 and11 at present; this establishes absence from that particular explicit mapping, not absence of every possible class resource producer.

## Bounded evidence and applicability of shared fixes

[armor1013-sadida-ally-audit.json](../armor1013-sadida-ally-audit.json) is a historical single common-entry case for spell925 on an ordinary ally: state changed, rollback preserved, 10 effect references executed, but `gameplay_verified=false`, one first-false IsTargetCellFree branch, and no actual game client verification. This does not prove the spell’s enemy/ally/empty-cell matrix or the class lifecycle. Class source row8150 retains “partial correction in progress”; because its source note predates this review, its current fix state is unverified.

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
