# Eliotrope class inventory review — 2026-10-10

Inventory-only review of local runtime source and available class reports. No gameplay/catalog files were modified; no service, database or client was operated. Native breed ID: **18**.

## Authority and source freshness

PostgreSQL is the live native-catalog authority, read through [`native_catalog.py`](../../../../server/wakfu_server/storage/native_catalog.py); `server/protocol/` was deliberately removed after this migration, so its absence is not a catalog gap. In a direct `BEGIN READ ONLY` query against the active release, revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38` (complete; 7,483 documents), the published `Eliotrope roster` reconciles exactly with this report's local inventory: 41 spell IDs with matching kind, unlock level, and localized names. The current `breed-innate-definitions.json` entry also matches the innate IDs **3398, 4464** below. Relevant exact document hashes and the read-only verification method are recorded in the source audit. This proves catalog alignment for roster and innate seeds only; cast fields and broad dependency matrices below remain dated native-export snapshots.

Roster names/ownership/grant paths come from [`inventory.json`](../inventory.json), locally refreshed 2026-10-09. Native cast cost/range/root fields come from [`class-casting-gap-inventory-20261007.json`](../class-casting-gap-inventory-20261007.json), at level 200. Innate seeds, typed dependency counts, profiles and areas come from [`class-native-mechanic-components-20261007.json`](../class-native-mechanic-components-20261007.json) and [`class-native-mechanic-graph-20261007.json`](../class-native-mechanic-graph-20261007.json). State status counts come from [`class-state-gap-inventory.json`](../class-state-gap-inventory.json). These are pinned historical source reports, not live database reads.

Do **not** treat the Oct 8 `class-effect-route-inventory` overlay as a current source verdict: its source tree is missing here and regeneration needs the active catalog. The Oct 7 area contracts below are historical native structural evidence only.

## Owned spell denominator

The local catalog lists **21 actives, 20 passives and 3 extra/granted actions**. AP/MP/WP, range, LOS/line flags and roots are the reported native level-200 snapshot. `pending` means no individual game-verification flag in the local catalog. Spell structure, handler presence or a historical actor change is not complete acceptance.

### Active spells

| ID | Spell | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 4668 | Égida Ardiente | 5 | 3/0/1 | 2–5 | noLOS / line | 346308, 346326, 395851, 395852 | pending |
| 4669 | Escudo Quebrantador | 1 | 3/0/0 | 1–3 | LOS / line | 351020, 351024, 395837, 395844 | pending |
| 4670 | Seísmo | 11 | 4/0/0 | 1–4 | LOS | 316323, 316325, 351722, 351723 | pending |
| 4671 | Tunda | 23 | 3/0/0 | 1–4 | LOS | 352833, 352834 | pending |
| 4680 | Torbellino | 15 | 2/0/0 | 1–4 | LOS / line | 145100, 346292 | pending |
| 4683 | Brecha Temporal | 30 | 2/0/1 | 1–4 | noLOS | 179820 | pending |
| 4684 | Éxodo | 45 | 1/0/1 | 1–4 | LOS | 346243, 346281 | pending |
| 4685 | Incandescencia | 60 | 1/0/0 | 1–4 | LOS | 145361, 160487, 179824, 179831 | pending |
| 4691 | Wakmeha | 1 | 4/0/0 | 1–5 | LOS / line | 145280, 146580, 316104, 316270 | pending |
| 4692 | Pulsación | 3 | 2/0/0 | 1–4 | LOS | 350976, 350980 | pending |
| 4693 | Diluvio | 9 | 3/0/0 | 1–5 | noLOS / line | 149026, 149028, 179751, 179754, 179755, 179769, 349568, 349583 | pending |
| 4694 | Cataclismo | 21 | 5/0/0 | 1–4 | noLOS | 350993, 351015 | pending |
| 4695 | Colisión | 17 | 4/0/0 | 1–4 | LOS / line | 145284, 346365, 346367, 346369, 395990, 395993 | pending |
| 4697 | Flujo Torrencial | 1 | 4/0/0 | 1–3 | LOS / line | 351043, 351045, 395929, 395930, 397728, 397730 | pending |
| 4698 | Sifón | 7 | 2/0/0 | 1–4 | LOS / line | 145297, 316293, 317884, 346394, 346395, 346396, 346397, 346398, 346399, 346400, 395894, 395895 | pending |
| 4699 | Salva Etérea | 13 | 3/0/0 | 1–4 | noLOS / line | 145307, 145310, 346401, 346402, 346403, 346404 | pending |
| 4700 | Tormenta | 19 | 5/0/0 | 1–4 | LOS | 145311, 351051 | pending |
| 4701 | Hoja Desencadenada | 25 | 5/0/0 | 1–2 | LOS / line | 318737, 351660 | pending |
| 7198 | Huella de Wakfu | 15 | 0/0/2 | 1–4 | LOS | 346522 | pending |
| 7199 | Coalición | 3 | 2/0/0 | 1–4 | noLOS | 346260, 346261, 346263, 351616, 376980, 395949 | pending |
| 7200 | Parapeto | 90 | 2/0/1 | 1–3 | LOS | 316344 | pending |

### Passives

| ID | Passive | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 4686 | Rabia | 20 | 0/0/0 | 0–0 | noLOS | 351059, 395945 | pending |
| 4687 | Celada | 10 | 0/0/0 | 0–0 | noLOS | 351733 | pending |
| 4688 | Efervescencia | 30 | 0/0/0 | 0–0 | LOS | 316455 | pending |
| 4689 | Medio | 15 | 0/0/0 | 0–0 | noLOS | 351378, 395960 | pending |
| 4690 | Resiliencia | 10 | 0/0/0 | 0–0 | noLOS | 351727, 395941 | pending |
| 5056 | Discípulo del Portal | 40 | 0/0/0 | 0–0 | noLOS | 346504, 346507 | pending |
| 5131 | Transitorio | 25 | 0/0/0 | 0–0 | noLOS | 179730, 376989 | pending |
| 5132 | Reminiscencia | 45 | 0/0/0 | 0–0 | noLOS | 346468 | pending |
| 5143 | Portal Celestial | 35 | 0/0/0 | 0–0 | noLOS | 351392 | pending |
| 7202 | Interestelar | 50 | 0/0/0 | 0–0 | noLOS | 351440, 377000 | pending |
| 7203 | Dimensión Blanca | 55 | 0/0/0 | 0–0 | noLOS | 351391 | pending |
| 7204 | Quietud | 60 | 0/0/0 | 0–0 | noLOS | 346520 | pending |
| 7205 | Espaciotiempo | 65 | 0/0/0 | 0–0 | noLOS | 316359, 316467, 377027 | pending |
| 7206 | Portalivio | 70 | 0/0/0 | 0–0 | noLOS | 316512 | pending |
| 7207 | Escudo del Fin | 75 | 0/0/0 | 0–0 | noLOS | 351381, 377044 | pending |
| 7208 | Espada del Inicio | 80 | 0/0/0 | 0–0 | noLOS | 351757 | pending |
| 7209 | Cicatrización | 85 | 0/0/0 | 0–0 | noLOS | 346513 | pending |
| 7210 | Concentración | 90 | 0/0/0 | 0–0 | noLOS | 351756 | pending |
| 7720 | Meditación | 95 | 0/0/0 | 0–0 | noLOS | 346518, 395932 | pending |
| 7814 | Aliento de la Diosa | 100 | 0/0/0 | 0–0 | noLOS | 351726, 395955 | pending |

### Extra/granted actions

| ID | Action | Static grant path | Tree exported |
|---:|---|---|---|
| 4678 | Portal | innate_state 3398 → effect 316226 | yes |
| 4682 | Exaltación | innate_state 3398 → effect 316227 | yes |
| 7813 | Portal Celestial | innate_state 3398 → effect 351705 | yes |

A grant path is a dependency lead. It does not prove current grant timing, owner, client book delivery, level, duration, duplicate suppression, or removal.

## Innate states, secondary state closure, profiles, areas

Innate seed IDs: **3398, 4464** (3398: Guerrero ágil; 4464: Golpe de gracia). The broad component matrix contains **44 distinct spell references, 1039 effects, 37 states, 0 native profiles and 12 area prototypes** across spell and innate roots. State overlay status is **2 partial / 35 pending**; a structurally referenced state need not be reachable or legally applied.

State IDs from the class status overlay (`*` marks innate seeds):

756 Incurable; 3294 Teleportación de largo alcance; 3303 Exaltado; 3305 Transitorio; 3307 Seísmo; 3386 Sereno; 3394 Parapeto; 3398 Guerrero ágil **innate seed**; 3434 Estabilizado; 3495 Desestabilizado - Enemigo; 3671 Don Celestial; 4464 Golpe de gracia **innate seed**; 6527 Desestabilizado - Aliado; 6624 Frágil; 6857 Seísmo - Crítico; 6890 label absent in local review catalog; 7746 label absent in local review catalog; 7747 Sereno; 7748 label absent in local review catalog; 7749 Don Celestial - Bonus de PA; 7750 Conexión: Efervescencia; 7807 Escudo del Fin; 7808 label absent in local review catalog; 7813 Coalición; 7819 Portal Celestial; 7820 Portal Celestial - Contador; 7821 Portal Celestial; 7835 Exaltación; 8175 label absent in local review catalog; 8177 label absent in local review catalog; 8178 label absent in local review catalog; 8179 label absent in local review catalog; 8180 label absent in local review catalog; 8908 Sereno; 9196 label absent in local review catalog; 9315 Berserker; 9331 label absent in local review catalog

### Profile/book references

| Native profile | Native ability book in exported snapshot |
|---:|---|
| None in component snapshot | — |

### Area prototypes

| ID | Type | Native class | Historical creation route |
|---:|---|---|---|
| 781 | GLYPH | bcT | conditional audited type branch present |
| 823 | GATE | bcS | conditional audited type branch present |
| 825 | GLYPH | bcT | conditional audited type branch present |
| 826 | GLYPH | bcT | conditional audited type branch present |
| 1604 | GLYPH | bcT | conditional audited type branch present |
| 1605 | WALL | bcZ | no audited type branch observed |
| 1606 | GLYPH | bcT | conditional audited type branch present |
| 1607 | GLYPH | bcT | conditional audited type branch present |
| 1612 | GLYPH | bcT | conditional audited type branch present |
| 1790 | GLYPH | bcT | conditional audited type branch present |
| 1793 | GLYPH | bcT | conditional audited type branch present |
| 1856 | GLYPH | bcT | conditional audited type branch present |

Area/profile rows are dependency references, not proof of creation, owner/controller identity, actor/book control, entry/exit activation, expiry, cleanup, or client presentation.

## Class resources and system inventory

Innate state 3398 (Guerrero ágil) and shared state 4464 seed the class. Extras are Portal 4678, Exaltación 4682 and Portal Celestial 7813, linked from 3398. Twelve area prototypes are in the class dependency component: 781, 823, 825, 826, 1604, 1605, 1606, 1607, 1612, 1790, 1793 and 1856. Native area review classifies 823 as GATE, 1605 as WALL, and the other listed dependencies as GLYPH. Current code has a portal-cast evaluator for portal identity/visibility/range, but this audit did not find evidence of a complete portal-pair lifecycle acceptance.

Roster AP/MP/WP values are spell costs only. Any distinct meter, capped stack, conditional resource conversion, passive modifier, timer and HUD encoding needs its own observed authority. Do not infer it from generic resource handling.

## Current runtime versus historical reports

Current shared entry points include [`combat_class_initialization.py`](../../../../server/wakfu_server/combat/combat_class_initialization.py), [`combat_spell_grant.py`](../../../../server/wakfu_server/combat/combat_spell_grant.py), [`combat_spell_grant_book.py`](../../../../server/wakfu_server/combat/combat_spell_grant_book.py), [`combat_state_handler.py`](../../../../server/wakfu_server/combat/combat_state_handler.py), [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py), and the shared summon lifecycle code under `server/wakfu_server/combat/`. These implement shared machinery, not class-specific semantic acceptance.

Specific inspected runtime lead: `combat_portal_casting.py` evaluates casting eligibility/identity/range; it does not certify endpoint pairing or traversal.

The historical normal active matrix in [`current-review-20261007.md`](../current-review-20261007.md) records 92 scenarios, 45 actor-change observations, 17 rejections, 28 no-effect observations, and 2 packet-only observations for this class. Those are source-era execution observations; the report expressly does not revalidate them against current checkout or client. They are not a score or a count of finished spells.

## Lifecycle and client risks

Test endpoint pairing, owner/fight identity, cap, relinking/replacement, range/LOS/cell validity, crossing both directions, carried/summoned actors, portal damage modifiers, movement transitions, removal on death/end/reconnect and packet order. Static casting eligibility does not certify traversal. Historical area report has no audited WALL-1605 creation-type branch.

For this class, an integrated validation route should cover legal deck/passive ownership → Ready and innate state installation → resource/HUD snapshot → cast cost and selected cell/actor → triggered passive/state → actor or area lifecycle → turn ACK/reconnect → fight end. Assert numerical HP/armor/resource deltas, state levels/duration/removal, grant book ownership and client packets. Include prerequisite-negative, invalid-target, failed-child and replay cases, with rollback of resource, state, RNG and packets.

## Inventory outcome

This review gives the native roster and dependency denominator plus a source map; it does not claim class completion. Full condition coverage, passive semantics, state lifecycle, area/summon behavior and client presentation remain open; the roster and innate-seed equality check is established for the active release cited above. Join the root's machine-readable class enumeration when ready; do not regenerate or mutate catalogs as part of this inventory.

## Published authority reconciliation — 2026-10-10

PostgreSQL is the current catalog authority; the absence of `server/protocol/` is intentional and is not a missing-definition finding. Any earlier filesystem limitation in this review is superseded by this reconciliation. The route matrix was regenerated against the current runtime source and published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`: 161 registered families, 23 construction-gated families, no unregistered families in that matrix scope. See [current route evidence](../class-effect-route-inventory-20261010.json). Registration does not establish complete mechanics, delivery or gameplay behavior; historical class graph provenance remains separately dated.
