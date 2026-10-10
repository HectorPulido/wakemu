# Ecaflip (native class 6) combat inventory — 2026-10-10

## Scope and evidence status

Inventory only. This review does not modify runtime code, catalog data, services or the database. PostgreSQL `native_catalog_active` and its immutable published documents are the current native-catalog authority; `server/protocol/` was intentionally removed after migration and its absence is not a catalog gap. The active published release is `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. See the [read-only source audit](../remaining-classes-source-audit-20261010.md) for release provenance and reconciliation boundaries.

The per-class spell rows are cross-checked against the installed-client [inventory.json](../inventory.json); detailed per-class typed dependency IDs and graph edges below come from the Oct. 7 native export and remain historical structure, not current evidence of a missing or present native definition. The Oct. 8 route overlay is historical; current route registration/gating is reported separately below from the Oct. 10 matrix. `reachability=unknown` in the old graph remains an unknown reachability claim. Catalog inclusion, route registration, handler existence and bounded fixtures are not functional class proof.

Sources: [class spell inventory](../clases/6.md); [historical typed component projection](../class-native-mechanic-components-20261007.json); [historical typed graph](../class-native-mechanic-graph-20261007.md) and [machine graph](../class-native-mechanic-graph-20261007.json); [historical requirements register](../class-mechanic-requirements-20261007.md); [Oct. 10 route inventory](../class-effect-route-inventory-20261010.md).

## Owned active and passive spells

The class inventory records **21 active and 20 passive IDs (41 total)**. Exact source names, kind, unlock level, family notes, individual review note and gameplay status are reproduced below. `Pendiente` is source catalog status, not a fresh live test. Family notes are copied from the class inventory and remain historical route hints, not current route claims. Per-root criteria/effects remain in the linked class Markdown.

| ID | Native label | Kind | Unlock | Historical family notes | Source review | In-game status |
|---:|---|---|---:|---|---|
| 2041 | Cara o Cruz | Activo | 1 | 345 | Sin revisión individual | Pendiente |
| 2042 | Dado Seis | Activo | 9 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2043 | Todo o Nada | Activo | 19 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2044 | Tres Cartas | Activo | 25 | 345 | Sin revisión individual | Pendiente |
| 2045 | Craps | Activo | 1 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2046 | Bufido | Activo | 21 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2047 | All In | Activo | 7 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2048 | Ruleta de Dados | Activo | 15 | 345 | Sin revisión individual | Pendiente |
| 2049 | Batalla | Activo | 13 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2050 | Dado Gatuno | Activo | 3 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2060 | Doble o Nada | Activo | 3 | 426 | Sin revisión individual | Pendiente |
| 2061 | Felintuición | Activo | 30 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2065 | Lengua Raspadora | Activo | 1 | 345 | Sin revisión individual | Pendiente |
| 2066 | Laceraciones | Activo | 5 | 345 | Sin revisión individual | Pendiente |
| 2067 | Pulga Arcito | Activo | 11 | 345 | Curación real en motor común: nivel11cura10/nivel200cura50,4PA,estado7931,paquetes/rollback verificados. Pendiente cargar últimas condiciones y probar cliente. | Pendiente |
| 2072 | ¡Zarpas Quietas! | Activo | 17 | 345 | Sin revisión individual | Pendiente |
| 2073 | Pulguita | Activo | 23 | 345 | Sin revisión individual | Pendiente |
| 2075 | Topkaj | Activo | 15 | 28,196 | Sin revisión individual | Pendiente |
| 2078 | Ficha de Vida | Activo | 45 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2079 | Mala Suerte | Activo | 60 | 426 | Sin revisión individual | Pendiente |
| 7225 | Trébol | Activo | 90 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2059 | Tarot Suertudo | Pasivo | 25 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2062 | Pulgación | Pasivo | 10 | 345 | Sin revisión individual | Pendiente |
| 2068 | Desventura | Pasivo | 10 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2076 | En Racha | Pasivo | 15 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 2080 | Desdicha | Pasivo | 20 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5246 | Tarot Profético | Pasivo | 30 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5249 | Impacto Felino | Pasivo | 40 | Sin ausencia detectada; validar límites | Registro, ejecución por evento y retirada aprobados en pruebas internas; falta productor automático | Pendiente |
| 5250 | Destino de Zurcarák | Pasivo | 35 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 5251 | Trampas | Pasivo | 45 | 426 | Sin revisión individual | Pendiente |
| 7954 | Racha Sanadora | Pasivo | 50 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7955 | Tarot Felino | Pasivo | 55 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7956 | La Fortuna Sonríe a los Audaces | Pasivo | 60 | 430 | Sin revisión individual | Pendiente |
| 7957 | Cruz, Gano | Pasivo | 65 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7958 | Dados Generosos | Pasivo | 70 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7959 | Felino Supremo | Pasivo | 75 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7960 | Black Jack | Pasivo | 80 | 430 | Sin revisión individual | Pendiente |
| 7961 | Triunfos Periódicos | Pasivo | 85 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 7999 | Siete Fetiche | Pasivo | 95 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8000 | El Universo | Pasivo | 100 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |
| 8001 | Racha de Cartas | Pasivo | 90 | Sin ausencia detectada; validar límites | Sin revisión individual | Pendiente |

## Secondary/granted actions and books

These are listed by the source as extra granted actions, separate from ordinary owned spells. Acquisition routes, temporary/permanent book semantics, cost/conditions, UI/action-bar visibility, use, restoration and cleanup are separate acceptance criteria. This is not proof these are exhaustive grant paths.

| ID | Native label | Category | Source review | In-game status |
|---:|---|---|---|---|
| 7227 | Re-tirada | extra/granted | Sin revisión individual | Pendiente |
| 7938 | El Gatallón | extra/granted | Sin revisión individual | Pendiente |
| 7939 | El Dios Uginak | extra/granted | Sin revisión individual | Pendiente |
| 7940 | Los Bebestias de Zurcarák | extra/granted | Sin revisión individual | Pendiente |
| 7941 | El Ermitaño Peludo | extra/granted | Sin revisión individual | Pendiente |
| 7942 | La Luna Peluda | extra/granted | Sin revisión individual | Pendiente |
| 7943 | Los Dados Caprichosos | extra/granted | Sin revisión individual | Pendiente |
| 7944 | El Miaumiau Negro | extra/granted | Sin revisión individual | Pendiente |
| 7945 | La Rueda de la Fortuna | extra/granted | Sin revisión individual | Pendiente |
| 7946 | El Miaucrificio | extra/granted | Sin revisión individual | Pendiente |
| 7947 | El Dios Zurcarák | extra/granted | Sin revisión individual | Pendiente |
| 7948 | Desventura | extra/granted | Sin revisión individual | Pendiente |
| 7949 | Desdicha | extra/granted | Sin revisión individual | Pendiente |
| 7950 | Destino de Zurcarák | extra/granted | Sin revisión individual | Pendiente |
| 7953 | Salto del Felino | extra/granted | Sin revisión individual | Pendiente |
| 7989 | El Universo | extra/granted | Sin revisión individual | Pendiente |

## Historical native typed spell closure

The Oct. 7 class projection’s owned-spell-plus-extra closure counted **area=1, area_mask=1, effect=1497, hmi_trigger=58, native_condition_class=56, native_mask_bit=46, profile=3, spell=59, state=70** typed references. The exact direct state, area and profile references are retained below. These are historical native references and not assertions that definitions remain present in the current source snapshot, are dynamically reachable, have a registered current route, or execute correctly.

**Direct state IDs (70):** 1144, 3309, 3462, 3683, 3697, 3709, 3710, 3711, 3712, 3713, 3714, 3715, 3716, 3717, 3718, 3730, 3738, 3740, 3741, 3747, 6624, 6637, 756, 7929, 7930, 7931, 7933, 7940, 7941, 7944, 7945, 7946, 7947, 7948, 7951, 7952, 7953, 7954, 7955, 7956, 7957, 7959, 7960, 7961, 7962, 7963, 7964, 7965, 7966, 7967, 7968, 7969, 7970, 7971, 7972, 7973, 7974, 7975, 7978, 7979, 7987, 8002, 8010, 8036, 8043, 8044, 8045, 8046, 8047, 8432.

**Direct area IDs (1):** 1798.

**Innate seed states (2):** 6892, 4464. **Historical innate dependency state closure (53):** 3309, 3683, 3699, 3709, 3710, 3711, 3712, 3713, 3714, 3715, 3716, 3717, 3718, 3730, 3738, 3740, 3741, 4464, 6637, 6892, 7932, 7940, 7941, 7950, 7957, 7959, 7961, 7962, 7963, 7964, 7965, 7966, 7967, 7968, 7969, 7970, 7971, 7972, 7973, 7974, 7975, 7978, 7979, 7987, 7999, 8036, 8043, 8044, 8045, 8046, 8148, 9315, 9331. This closure is separate from spell dependencies; shared innate states do not prove per-spell lifecycle.

**Historical profile references (3):**

| Profile ID | Ability spell references in Oct. 7 graph | Reachability |
|---:|---|---|
| 1482 | 5231 | unknown |
| 3789 | none in historical projection | unknown |
| 5535 | 7986 | unknown |

## Current effect route coverage

The current Oct. 10 route matrix covers **81/90 registered** direct spell-closure family bindings and **9 construction-gated** bindings for this class. Gated family IDs: 300, 301, 302, 307, 315, 421, 422, 843, 1013. No missing or unregistered family binding is listed for this class in the matrix. A construction-gated binding means its handler path requires the documented authority/factory at runtime; it is not an absent native definition or a gameplay failure. This remains route evidence, not functional coverage: class-specific source ownership, conditions, target behavior, transaction, client delivery and lifecycle still need acceptance. See the [current route matrix](../class-effect-route-inventory-20261010.json) generated against published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

## Class resource, secondary state and spatial lifecycle

The installed client contract maps breed 6 to characteristic 60 ECAFLIP_RESOURCE and popup state 3683. The historical source does not establish the resource writer or GUI display; the current explicit server HUD projection only handles breeds 8 and 11 (`combat_hud_resource.py`), so breed-6 value synchronization is unverified, not assumed absent from all other producers.

Area 1798; inspect historical area contract row before making semantic claims. The profile references are 1482, 3789 and 5535, with native ability references 5231, none, and 7986 respectively.

Ecaflip-specific concerns are card/random outcome selection, tarot/fortune state chains, temporary granted actions, roulette/area placement, cat summon/profile books and resource counter synchronization. Random groups and action grants require source-preserving transaction and deterministic rollback; catalog closure cannot prove odds, event order, action-bar restoration, or cleanup.

Across the class, test the authoritative actor turn and legal native conditions, successful and rejected casts, exact AP/MP/WP and class-meter mutation, duplicate states and first-match semantics, and replay/reconnect. Summoned actors need owner/controller, book completeness, turn eligibility, and exact once-only death/retirement. Areas, traps, bombs, seeds or glyphs need identity, footprint, target rules, trigger timing, expiry/removal and cell reuse. State/resource/action-bar delivery and map objects need client verification. These lifecycle points remain **unverified** except for narrowly scoped evidence below; they are not all individually marked missing.

## Current shared runtime inspected

[random groups](../../../../server/wakfu_server/combat/combat_random_group.py), [conditions](../../../../server/wakfu_server/combat/combat_conditions.py), [effect runtime](../../../../server/wakfu_server/combat/combat_effect_runtime.py), [summon creation](../../../../server/wakfu_server/combat/combat_summon_creation.py), [summon books](../../../../server/wakfu_server/combat/combat_summon_spellbook.py), [summon retirement](../../../../server/wakfu_server/combat/combat_summon_retirement.py), [HUD resource sync](../../../../server/wakfu_server/combat/combat_hud_resource.py).

These modules contain shared contract paths (conditions, effects, area/state lifecycle, summon/carry handling, or resource delivery); their existence is not proof that this class’s complete native spell closure selects them or passes class-specific guards. `combat_hud_resource.py` explicitly maps only breeds8 and11 at present; this establishes absence from that particular explicit mapping, not absence of every possible class resource producer.

## Bounded evidence and applicability of shared fixes

The historical [ready-eca-carrying-focal.json](../ready-eca-carrying-focal.json) records 26/26 Ready-entry cases, but the scope is a no-equipment fixture, no graphical validation, and the the old source hash manifest refers to the pre-migration filesystem export and is not current-catalog evidence. Treat it as historical start-path evidence only. The old [random-group-native.txt](../../random-group-native.txt) report also records a focal blockage at family649; its route source is historical and is not current readiness evidence.

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
