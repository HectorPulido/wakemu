# Ouginak class inventory review — 2026-10-10

Inventory-only review of local runtime source and available class reports. No gameplay/catalog files were modified; no service, database or client was operated. Native breed ID: **15**.

## Authority and source freshness

PostgreSQL is the live native-catalog authority, read through [`native_catalog.py`](../../../../server/wakfu_server/storage/native_catalog.py); `server/protocol/` was deliberately removed after this migration, so its absence is not a catalog gap. In a direct `BEGIN READ ONLY` query against the active release, revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38` (complete; 7,483 documents), the published `Ouginak roster` reconciles exactly with this report's local inventory: 40 spell IDs with matching kind, unlock level, and localized names. The current `breed-innate-definitions.json` entry also matches the innate IDs **4464, 7521** below. Relevant exact document hashes and the read-only verification method are recorded in the source audit. This proves catalog alignment for roster and innate seeds only; cast fields and broad dependency matrices below remain dated native-export snapshots.

Roster names/ownership/grant paths come from [`inventory.json`](../inventory.json), locally refreshed 2026-10-09. Native cast cost/range/root fields come from [`class-casting-gap-inventory-20261007.json`](../class-casting-gap-inventory-20261007.json), at level 200. Innate seeds, typed dependency counts, profiles and areas come from [`class-native-mechanic-components-20261007.json`](../class-native-mechanic-components-20261007.json) and [`class-native-mechanic-graph-20261007.json`](../class-native-mechanic-graph-20261007.json). State status counts come from [`class-state-gap-inventory.json`](../class-state-gap-inventory.json). These are pinned historical source reports, not live database reads.

Do **not** treat the Oct 8 `class-effect-route-inventory` overlay as a current source verdict: its source tree is missing here and regeneration needs the active catalog. The Oct 7 area contracts below are historical native structural evidence only.

## Owned spell denominator

The local catalog lists **21 actives, 19 passives and 4 extra/granted actions**. AP/MP/WP, range, LOS/line flags and roots are the reported native level-200 snapshot. `pending` means no individual game-verification flag in the local catalog. Spell structure, handler presence or a historical actor change is not complete acceptance.

### Active spells

| ID | Spell | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 6256 | Emplomado | 15 | 3/0/0 | 1–1 | LOS | 341005, 341008, 341161, 341171, 341508, 341509 | pending |
| 6257 | Plaga | 3 | 4/0/1 | 1–3 | LOS / line / modRange | 242646, 340548, 340549, 340552, 341122, 341129, 341514, 341517 | pending |
| 6258 | Ruptura | 9 | 2/0/0 | 1–2 | LOS / line | 339469, 340451, 341136, 341150 | pending |
| 6259 | Cuchillada | 21 | 5/0/0 | 1–4 | LOS / line / modRange | 340002, 340458, 341178, 341188 | pending |
| 6260 | Disturbio | 1 | 3/0/0 | 1–3 | LOS / line / modRange | 340001, 341103, 341544, 341552 | pending |
| 6261 | Zascadilla | 1 | 2/0/0 | 1–1 | LOS | 340013, 340491, 341200, 341211 | pending |
| 6262 | Rayadura | 17 | 3/0/0 | 1–2 | LOS / line | 341011, 341015, 341269, 341276 | pending |
| 6263 | Apaleamiento | 5 | 3/0/1 | 1–1 | LOS | 339517, 340385, 340481, 340490, 341219, 341241 | pending |
| 6264 | Tirón | 23 | 4/0/0 | 1–2 | LOS | 340003, 340465, 341283, 341296 | pending |
| 6265 | Moloso | 11 | 4/0/0 | 1–2 | LOS | 241526, 291382, 291480, 340031, 340494, 340502, 340504, 340649, 341255, 341262 | pending |
| 6266 | Barrido | 1 | 4/0/0 | 1–3 | LOS / line / modRange | 339522, 340505 | pending |
| 6267 | Contusión | 7 | 3/0/0 | 2–3 | LOS / modRange | 291545, 340509 | pending |
| 6268 | Gran Can | 13 | 3/0/1 | 3–5 | LOS / line | 243795, 340512, 341374, 341394 | pending |
| 6269 | Fracturahuesos | 19 | 2/0/0 | 1–3 | LOS / modRange | 291555, 339527, 340527, 340528, 341414, 341421 | pending |
| 6270 | Bulla | 25 | 6/0/1 | 1–3 | LOS / modRange | 340033, 341095, 341428, 341441 | pending |
| 6284 | Cazador | 3 | 2/0/0 | 2–4 | LOS / line | 240989 | pending |
| 6285 | Persecución | 60 | 3/0/1 | 0–6 | LOS | 240988, 291429 | pending |
| 6287 | Colmillo | 30 | 3/0/0 | 2–4 | noLOS / line / modRange | 243399 | pending |
| 6288 | Amaine | 45 | 2/0/1 | 1–3 | LOS | 243435, 341590 | pending |
| 7551 | Manada | 90 | 0/0/1 | 0–2 | noLOS | 395645 | pending |
| 7552 | Bote | 15 | 1/0/0 | 1–4 | LOS / line | 340034, 340037 | pending |

### Passives

| ID | Passive | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 6271 | Cubil | 75 | 0/0/0 | 1–1 | LOS | 340145 | pending |
| 6272 | Arte Canino | 70 | 0/0/0 | 1–1 | LOS | 340136, 340142, 340244, 397236, 397239 | pending |
| 6273 | Maestro Perrero | 95 | 0/0/0 | 1–1 | LOS | 341489 | pending |
| 6274 | Compañero | 10 | 0/0/0 | 1–1 | LOS | 242504 | pending |
| 6275 | Ardor | 40 | 0/0/0 | 1–1 | LOS | 340104, 340105, 340113 | pending |
| 6276 | Agotamiento | 55 | 0/0/0 | 1–1 | LOS | 242686, 340122 | pending |
| 6277 | Pillaje | 45 | 0/0/0 | 1–1 | LOS | 242627, 293058, 293061, 342261 | pending |
| 6278 | Colmillos Agudos | 80 | 0/0/0 | 1–1 | LOS | 340154, 340155 | pending |
| 6279 | Olfacción | 65 | 0/0/0 | 1–1 | LOS | 341038 | pending |
| 6280 | Regateo | 10 | 0/0/0 | 1–1 | LOS | 341023 | pending |
| 6281 | Busca | 60 | 0/0/0 | 1–1 | LOS | 340123, 341037 | pending |
| 6282 | Fuerza Sabia | 90 | 0/0/0 | 1–1 | LOS | 341041 | pending |
| 7553 | Acérrimo | 20 | 0/0/0 | 1–1 | LOS | 340085, 340088, 340091 | pending |
| 7554 | Veda Abierta | 25 | 0/0/0 | 1–1 | LOS | 341032, 345698 | pending |
| 7555 | Digestión | 30 | 0/0/0 | 1–1 | LOS | 340098, 340099 | pending |
| 7556 | Energía Canina | 35 | 0/0/0 | 1–1 | LOS | 340101, 340112 | pending |
| 7557 | Furor | 50 | 0/0/0 | 1–1 | LOS | 340116, 340117, 345699 | pending |
| 7558 | Rastreador Canino | 85 | 0/0/0 | 1–1 | LOS | 340158, 340176 | pending |
| 7596 | Sa Hueso | 15 | 0/0/0 | 1–1 | LOS | 341024 | pending |

### Extra/granted actions

| ID | Action | Static grant path | Tree exported |
|---:|---|---|---|
| 6283 | Presa | innate_state 7521 → effect 339679 | yes |
| 6286 | Wauwau | innate_state 7521 → effect 339893 | yes |
| 6855 | Uginikántropo | innate_state 7521 → effect 339892 | yes |
| 6856 | Perseguidor | spell 6285 → effect 291430; innate_state 7521 → effect 339680 | yes |

A grant path is a dependency lead. It does not prove current grant timing, owner, client book delivery, level, duration, duplicate suppression, or removal.

## Innate states, secondary state closure, profiles, areas

Innate seed IDs: **4464, 7521** (4464: Golpe de gracia; 7521: Uginak). The broad component matrix contains **48 distinct spell references, 1130 effects, 36 states, 1 native profiles and 3 area prototypes** across spell and innate roots. State overlay status is **1 partial / 35 pending**; a structurally referenced state need not be reachable or legally applied.

State IDs from the class status overlay (`*` marks innate seeds):

756 Incurable; 1304 Incurable; 3434 Estabilizado; 3495 Desestabilizado - Enemigo; 4464 Golpe de gracia **innate seed**; 6527 Desestabilizado - Aliado; 6624 Frágil; 7514 Picado; 7515 Rayadura; 7516 Apaleado; 7517 Apaleamiento; 7521 Uginak **innate seed**; 7522 Bulla; 7523 Fractura; 7524 Perseguidor; 7525 Presa; 7526 Uginikántropo; 7527 Perseguido; 7528 label absent in local review catalog; 7529 Wauwau; 7530 Pillaje; 7531 Rastreador; 7534 label absent in local review catalog; 7535 label absent in local review catalog; 7537 Manada; 7538 Huesito; 7539 Ardor; 7540 Regateo; 7554 Bonus de Esquiva; 7555 Malus de Esquiva; 7577 Olfacción; 7579 Fuerza Sabia; 8438 label absent in local review catalog; 8902 label absent in local review catalog; 9315 Berserker; 9331 label absent in local review catalog

### Profile/book references

| Native profile | Native ability book in exported snapshot |
|---:|---|
| 4559 | 6291 (UID 6291, override -1, max 245), 6292 (UID 6292, override -1, max 245), 6293 (UID 6293, override -1, max 245), 6294 (UID 6294, override -1, max 245) |

### Area prototypes

| ID | Type | Native class | Historical creation route |
|---:|---|---|---|
| 781 | GLYPH | bcT | conditional audited type branch present |
| 1267 | GLYPH | bcT | conditional audited type branch present |
| 1268 | GLYPH | bcT | conditional audited type branch present |

Area/profile rows are dependency references, not proof of creation, owner/controller identity, actor/book control, entry/exit activation, expiry, cleanup, or client presentation.

## Class resources and system inventory

Innate state 7521 (Uginak) and shared state 4464 seed the class. Four extras are Presa 6283, Wauwau 6286, Uginikántropo 6855, and Perseguidor 6856. The native dependency graph contains profile 4559 with ability entries 6291–6294 (override level −1); its runtime role and availability are not established by the profile node. Area prototypes 781, 1267 and 1268 are GLYPHs.

Roster AP/MP/WP values are spell costs only. Any distinct meter, capped stack, conditional resource conversion, passive modifier, timer and HUD encoding needs its own observed authority. Do not infer it from generic resource handling.

## Current runtime versus historical reports

Current shared entry points include [`combat_class_initialization.py`](../../../../server/wakfu_server/combat/combat_class_initialization.py), [`combat_spell_grant.py`](../../../../server/wakfu_server/combat/combat_spell_grant.py), [`combat_spell_grant_book.py`](../../../../server/wakfu_server/combat/combat_spell_grant_book.py), [`combat_state_handler.py`](../../../../server/wakfu_server/combat/combat_state_handler.py), [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py), and the shared summon lifecycle code under `server/wakfu_server/combat/`. These implement shared machinery, not class-specific semantic acceptance.

Specific inspected runtime lead: No dedicated class-named module was found in the inspected combat source paths; current behavior is expected to flow through shared native effect/state/grant systems and needs exact-root review.

The historical normal active matrix in [`current-review-20261007.md`](../current-review-20261007.md) records 96 scenarios, 80 actor-change observations, 6 rejections, 10 no-effect observations, and 0 packet-only observations for this class. Those are source-era execution observations; the report expressly does not revalidate them against current checkout or client. They are not a score or a count of finished spells.

## Lifecycle and client risks

Track prey mark ownership, legal target replacement, expiry/death, consumption, resource values, conditional grant eligibility and temporary-book replacement separately. Check Persecución 6285's spell-derived Perseguidor grant against the innate 7521 grant for duplicate/wrong-owner behavior. Validate profile4559 creation/control/turn/book/removal only if an actual root reaches it; profile presence does not prove summon creation. Test pursuit/retreat and map-boundary movement plus glyph expiry.

For this class, an integrated validation route should cover legal deck/passive ownership → Ready and innate state installation → resource/HUD snapshot → cast cost and selected cell/actor → triggered passive/state → actor or area lifecycle → turn ACK/reconnect → fight end. Assert numerical HP/armor/resource deltas, state levels/duration/removal, grant book ownership and client packets. Include prerequisite-negative, invalid-target, failed-child and replay cases, with rollback of resource, state, RNG and packets.

## Inventory outcome

This review gives the native roster and dependency denominator plus a source map; it does not claim class completion. Full condition coverage, passive semantics, state lifecycle, area/summon behavior and client presentation remain open; the roster and innate-seed equality check is established for the active release cited above. Join the root's machine-readable class enumeration when ready; do not regenerate or mutate catalogs as part of this inventory.

## Published authority reconciliation — 2026-10-10

PostgreSQL is the current catalog authority; the absence of `server/protocol/` is intentional and is not a missing-definition finding. Any earlier filesystem limitation in this review is superseded by this reconciliation. The route matrix was regenerated against the current runtime source and published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`: 161 registered families, 23 construction-gated families, no unregistered families in that matrix scope. See [current route evidence](../class-effect-route-inventory-20261010.json). Registration does not establish complete mechanics, delivery or gameplay behavior; historical class graph provenance remains separately dated.
