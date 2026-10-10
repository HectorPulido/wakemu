# Zobal (native Masqueraider) class inventory review — 2026-10-10

Inventory-only review of local runtime source and available class reports. No gameplay/catalog files were modified; no service, database or client was operated. Native breed ID: **14**.

## Authority and source freshness

PostgreSQL is the live native-catalog authority, read through [`native_catalog.py`](../../../../server/wakfu_server/storage/native_catalog.py); `server/protocol/` was deliberately removed after this migration, so its absence is not a catalog gap. In a direct `BEGIN READ ONLY` query against the active release, revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38` (complete; 7,483 documents), the published `Zobal roster` reconciles exactly with this report's local inventory: 40 spell IDs with matching kind, unlock level, and localized names. The current `breed-innate-definitions.json` entry also matches the innate IDs **3769, 4464** below. Relevant exact document hashes and the read-only verification method are recorded in the source audit. This proves catalog alignment for roster and innate seeds only; cast fields and broad dependency matrices below remain dated native-export snapshots.

Roster names/ownership/grant paths come from [`inventory.json`](../inventory.json), locally refreshed 2026-10-09. Native cast cost/range/root fields come from [`class-casting-gap-inventory-20261007.json`](../class-casting-gap-inventory-20261007.json), at level 200. Innate seeds, typed dependency counts, profiles and areas come from [`class-native-mechanic-components-20261007.json`](../class-native-mechanic-components-20261007.json) and [`class-native-mechanic-graph-20261007.json`](../class-native-mechanic-graph-20261007.json). State status counts come from [`class-state-gap-inventory.json`](../class-state-gap-inventory.json). These are pinned historical source reports, not live database reads.

Do **not** treat the Oct 8 `class-effect-route-inventory` overlay as a current source verdict: its source tree is missing here and regeneration needs the active catalog. The Oct 7 area contracts below are historical native structural evidence only.

## Owned spell denominator

The local catalog lists **21 actives, 19 passives and 5 extra/granted actions**. AP/MP/WP, range, LOS/line flags and roots are the reported native level-200 snapshot. `pending` means no individual game-verification flag in the local catalog. Spell structure, handler presence or a historical actor change is not complete acceptance.

### Active spells

| ID | Spell | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 7066 | Patada Azotada | 1 | 3/0/0 | 1–3 | LOS / line | 307464, 307467, 308835, 308838, 311650, 311652 | pending |
| 7067 | Hendidura | 3 | 3/0/0 | 1–1 | LOS | 307478, 307479, 307481, 307482, 308191, 308192, 308867, 308870, 308949, 308950 | pending |
| 7068 | Perturbación | 9 | 3/0/0 | 0–0 | LOS / line | 307497, 307498, 307499, 307500, 308873, 308882 | pending |
| 7069 | Neurosis | 15 | 4/0/1 | 1–4 | LOS / modRange | 308570, 308576, 308876, 308879 | pending |
| 7070 | Cabriola | 21 | 6/0/0 | 3–5 | noLOS / line | 307506, 307513, 307514, 307521 | pending |
| 7071 | Señales | 1 | 2/0/0 | 1–4 | noLOS / modRange | 308885, 308888, 330080, 330081 | pending |
| 7072 | Armazón | 5 | 4/0/0 | 1–5 | LOS / modRange | 307529, 307533, 307534, 307535, 308891, 308894 | pending |
| 7073 | Salvamento | 11 | 3/0/0 | 1–5 | LOS / modRange | 308559, 308565, 308897, 308901 | pending |
| 7074 | Ensañamiento | 17 | 5/0/0 | 1–5 | LOS | 307554, 307560, 308905, 308908 | pending |
| 7075 | Zarabanda | 23 | 5/0/1 | 1–3 | LOS / line / modRange | 308911, 308914, 330029, 330030 | pending |
| 7076 | Fuga | 1 | 3/0/0 | 1–3 | LOS / line | 307579, 307582 | pending |
| 7077 | Persecución | 7 | 0/2/0 | 1–1 | LOS | 307585, 307589, 308923, 308924, 308926, 308927 | pending |
| 7078 | Brinco | 13 | 2/0/0 | 1–4 | noLOS / line | 308929, 413711, 413732, 413734 | pending |
| 7079 | Cabalgata | 19 | 2/0/0 | 1–1 | LOS / line | 307621, 307627, 308808, 308813, 308935, 308938 | pending |
| 7080 | Disyunción | 25 | 4/0/1 | 1–5 | LOS | 307633, 307637, 308941, 308944 | pending |
| 7084 | Entrechoque | 3 | 0/0/1 | 1–2 | LOS | 413127, 413374 | pending |
| 7085 | Danza Motivadora | 15 | 3/0/0 | 1–3 | LOS / modRange | 307680 | pending |
| 7086 | Danza Macabra | 30 | 2/0/1 | 1–5 | LOS / line | 307711 | pending |
| 7087 | Acrobatismo | 45 | 3/0/0 | 6–6 | noLOS / line | 307724, 307845, 313007 | pending |
| 7088 | Aura de Brutalidad | 60 | 2/0/0 | 0–0 | noLOS | 308017 | pending |
| 7089 | Solidez | 75 | 1/0/1 | 0–5 | LOS / line / modRange | 308019, 308023, 412891 | pending |

### Passives

| ID | Passive | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 7093 | Juego de Piernas | 10 | 0/0/0 | 0–0 | noLOS | 308163, 308167, 308257, 308259 | pending |
| 7094 | Fuera Máscaras | 10 | 0/0/0 | 0–0 | noLOS | 308038 | pending |
| 7095 | Empujes Violentos | 15 | 0/0/0 | 0–0 | noLOS | 308039, 308062, 413133 | pending |
| 7096 | Arte de la Venganza | 20 | 0/0/0 | 0–0 | noLOS | 308161 | pending |
| 7097 | Máscara de Vida | 25 | 0/0/0 | 0–0 | noLOS | 308066, 308068 | pending |
| 7098 | Carnaval | 30 | 0/0/0 | 0–0 | noLOS | 308073, 308515 | pending |
| 7099 | Armadura Única | 35 | 0/0/0 | 0–0 | noLOS | 308173 | pending |
| 7100 | Ancla | 40 | 0/0/0 | 0–0 | noLOS | 308081, 308083 | pending |
| 7101 | Bruto | 45 | 0/0/0 | 0–0 | noLOS | 308084, 308085, 308086 | pending |
| 7102 | Protector Apartado | 50 | 0/0/0 | 0–0 | noLOS | 308264 | pending |
| 7103 | Colisiones de Apoyo | 55 | 0/0/0 | 0–0 | noLOS | 308128, 308136, 413134 | pending |
| 7104 | Erosión | 60 | 0/0/0 | 0–0 | noLOS | 308246, 311665 | pending |
| 7105 | Giro | 65 | 0/0/0 | 0–0 | noLOS | 308093 | pending |
| 7106 | Colisiones Regenerativas | 70 | 0/0/0 | 0–0 | noLOS | 308144, 308157, 413136, 413137 | pending |
| 7107 | Espejos | 75 | 0/0/0 | 0–0 | noLOS | 308238 | pending |
| 7108 | En Contacto | 80 | 0/0/0 | 0–0 | noLOS | 308096 | pending |
| 7111 | Arte de la Huida | 85 | 0/0/0 | 0–0 | noLOS | 308171 | pending |
| 7112 | Mirada Enmascarada | 90 | 0/0/0 | 0–0 | noLOS | 308115 | pending |
| 7113 | Empujes de Traba | 95 | 0/0/0 | 0–0 | noLOS | 308117, 308125, 309413, 413138 | pending |

### Extra/granted actions

| ID | Action | Static grant path | Tree exported |
|---:|---|---|---|
| 7081 | Máscara Sáikopat | innate_state 3769 → effect 308275 | yes |
| 7082 | Máscara Eskérdikat | innate_state 3769 → effect 308276 | yes |
| 7083 | Máscara Zobal | innate_state 3769 → effect 308277 | yes |
| 7226 | Máscara Sáikopat II | innate_state 3769 → effect 316972 | yes |
| 8559 | Espíritu Enmascarado | innate_state 3769 → effect 413347 | yes |

A grant path is a dependency lead. It does not prove current grant timing, owner, client book delivery, level, duration, duplicate suppression, or removal.

## Innate states, secondary state closure, profiles, areas

Innate seed IDs: **3769, 4464** (3769: Guerrero Lunático; 4464: Golpe de gracia). The broad component matrix contains **45 distinct spell references, 862 effects, 44 states, 0 native profiles and 2 area prototypes** across spell and innate roots. State overlay status is **1 partial / 43 pending**; a structurally referenced state need not be reachable or legally applied.

State IDs from the class status overlay (`*` marks innate seeds):

751 Ardiente; 752 Escaldado; 756 Incurable; 1144 Convaleciente; 3434 Estabilizado; 3495 Desestabilizado - Enemigo; 3769 Guerrero Lunático **innate seed**; 3770 Cabalgata; 3771 Cabalgata; 3789 label absent in local review catalog; 3813 label absent in local review catalog; 4464 Golpe de gracia **innate seed**; 6527 Desestabilizado - Aliado; 6610 Danza Motivadora; 6611 Máscara Sáikopat; 6612 Máscara Eskérdikat; 6613 Máscara Zobal; 6614 Máscara Sáikopat; 6615 Máscara Eskérdikat; 6616 Máscara Zobal; 6618 Aura de Brutalidad; 6619 Acrobatismo; 6622 En Contacto - Bonus; 6623 En Contacto - Malus; 6624 Frágil; 6626 Protector Apartado - Bonus; 6627 Protector Apartado - Malus; 6637 Retirada de PW; 6648 label absent in local review catalog; 6661 label absent in local review catalog; 6662 Zarabanda; 6703 Bonus Crítico; 6704 Erosión; 6888 Máscara Sáikopat II; 9128 Perturbación; 9244 Bonus de Esquiva; 9246 Entrechoque; 9247 Saikocarga; 9248 Eskerdicarga; 9249 Clasicarga; 9270 label absent in local review catalog; 9271 label absent in local review catalog; 9315 Berserker; 9331 label absent in local review catalog

### Profile/book references

| Native profile | Native ability book in exported snapshot |
|---:|---|
| None in fixed summon-profile component | — |

The current published `native-class-copy-profiles.json` separately contains constructor profile **2382**, whose `seed_identity.effect_descriptor_edges` links effect **413075** to that profile. This is a copy/actor-constructor dependency, not a fixed class summon ability-book entry, so it does not change the component matrix's zero summon-profile count. Its profile row has an empty ability book, fight properties `[15, 108]`, and world property `[7]`; no creation or copied-actor lifecycle is established by this definition.

### Area prototypes

| ID | Type | Native class | Historical creation route |
|---:|---|---|---|
| 1204 | GLYPH | bcT | conditional audited type branch present |
| 1527 | AURA | bcD | conditional audited type branch present |

Area/profile rows are dependency references, not proof of creation, owner/controller identity, actor/book control, entry/exit activation, expiry, cleanup, or client presentation.

## Class resources and system inventory

Innate state 3769 (Guerrero Lunático) and shared state 4464 seed the class. Five extras are three masks (7081–7083), Máscara Sáikopat II (7226) and Espíritu Enmascarado (8559), all linked from state 3769 in the snapshot. Area prototypes are 1204 GLYPH and 1527 AURA. The published copy-profile row is documented above separately from the fixed summon-profile count.

Roster AP/MP/WP values are spell costs only. Any distinct meter, capped stack, conditional resource conversion, passive modifier, timer and HUD encoding needs its own observed authority. Do not infer it from generic resource handling.

## Current runtime versus historical reports

Current shared entry points include [`combat_class_initialization.py`](../../../../server/wakfu_server/combat/combat_class_initialization.py), [`combat_spell_grant.py`](../../../../server/wakfu_server/combat/combat_spell_grant.py), [`combat_spell_grant_book.py`](../../../../server/wakfu_server/combat/combat_spell_grant_book.py), [`combat_state_handler.py`](../../../../server/wakfu_server/combat/combat_state_handler.py), [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py), and the shared summon lifecycle code under `server/wakfu_server/combat/`. These implement shared machinery, not class-specific semantic acceptance.

Specific inspected runtime lead: No dedicated class-named module was found in the inspected combat source paths; current behavior is expected to flow through shared native effect/state/grant systems and needs exact-root review.

The historical normal active matrix in [`current-review-20261007.md`](../current-review-20261007.md) records 94 scenarios, 72 actor-change observations, 2 rejections, 18 no-effect observations, and 0 packet-only observations for this class. Those are source-era execution observations; the report expressly does not revalidate them against current checkout or client. They are not a score or a count of finished spells.

## Lifecycle and client risks

Verify mask grant owner and availability, exactly intended active mask, state replacement/removal, passive changes, appearance packet, resource/stat changes, death/reconnect/fight-end reset, and interactions with the five extras. For collision/push spells assert both actor and cell outcome. Do not treat a granted mask action as an owned deck spell.

For this class, an integrated validation route should cover legal deck/passive ownership → Ready and innate state installation → resource/HUD snapshot → cast cost and selected cell/actor → triggered passive/state → actor or area lifecycle → turn ACK/reconnect → fight end. Assert numerical HP/armor/resource deltas, state levels/duration/removal, grant book ownership and client packets. Include prerequisite-negative, invalid-target, failed-child and replay cases, with rollback of resource, state, RNG and packets.

## Inventory outcome

This review gives the native roster and dependency denominator plus a source map; it does not claim class completion. Full condition coverage, passive semantics, state lifecycle, area/summon behavior and client presentation remain open; the roster and innate-seed equality check is established for the active release cited above. Join the root's machine-readable class enumeration when ready; do not regenerate or mutate catalogs as part of this inventory.

## Published authority reconciliation — 2026-10-10

PostgreSQL is the current catalog authority; the absence of `server/protocol/` is intentional and is not a missing-definition finding. Any earlier filesystem limitation in this review is superseded by this reconciliation. The route matrix was regenerated against the current runtime source and published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`: 161 registered families, 23 construction-gated families, no unregistered families in that matrix scope. See [current route evidence](../class-effect-route-inventory-20261010.json). Registration does not establish complete mechanics, delivery or gameplay behavior; historical class graph provenance remains separately dated.

## Local implementation update — 2026-10-10

The [implementation report](../zobal-implementation-20261010.md) records a passing 170-test staged-catalog gate, including prior-class regressions, mask grants/bonus switching, real-corpse Danza Macabra resurrection, exact-range Acrobatismo and copied-book dependencies. Row-level pending labels above are manual/mechanic acceptance status, not missing handler counts. The [manual battery](../zobal-manual-acceptance-20261010.md) covers all 21 owned actives and 19 class passives. Initialization success alone does not validate every passive event or amount.

Native-source exclusions are specific: push/collision event roots308039/308062/413133 (7095),308128/308136 (7103),308144/308157 (7106),308117/308125/309413 (7113) contain literal `False` or `and False`. Other independent roots, including413134/413136/413137/413138, are not disabled by that observation. Preserve those published distinctions rather than inventing active collision behavior.

No deployment, service restart or active-catalog switch by this workstream. User acceptance remains pending; project count remains6/18.
