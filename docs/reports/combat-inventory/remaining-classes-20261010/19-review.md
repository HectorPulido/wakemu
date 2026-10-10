# Huppermage class inventory review — 2026-10-10

Inventory-only review of local runtime source and available class reports. No gameplay/catalog files were modified; no service, database or client was operated. Native breed ID: **19**.

## Authority and source freshness

PostgreSQL is the live native-catalog authority, read through [`native_catalog.py`](../../../../server/wakfu_server/storage/native_catalog.py); `server/protocol/` was deliberately removed after this migration, so its absence is not a catalog gap. In a direct `BEGIN READ ONLY` query against the active release, revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38` (complete; 7,483 documents), the published `Huppermage roster` reconciles exactly with this report's local inventory: 44 spell IDs with matching kind, unlock level, and localized names. The current `breed-innate-definitions.json` entry also matches the innate IDs **4069, 4464, 7562** below. Relevant exact document hashes and the read-only verification method are recorded in the source audit. This proves catalog alignment for roster and innate seeds only; cast fields and broad dependency matrices below remain dated native-export snapshots.

Roster names/ownership/grant paths come from [`inventory.json`](../inventory.json), locally refreshed 2026-10-09. Native cast cost/range/root fields come from [`class-casting-gap-inventory-20261007.json`](../class-casting-gap-inventory-20261007.json), at level 200. Innate seeds, typed dependency counts, profiles and areas come from [`class-native-mechanic-components-20261007.json`](../class-native-mechanic-components-20261007.json) and [`class-native-mechanic-graph-20261007.json`](../class-native-mechanic-graph-20261007.json). State status counts come from [`class-state-gap-inventory.json`](../class-state-gap-inventory.json). These are pinned historical source reports, not live database reads.

Do **not** treat the Oct 8 `class-effect-route-inventory` overlay as a current source verdict: its source tree is missing here and regeneration needs the active catalog. The Oct 7 area contracts below are historical native structural evidence only.

## Owned spell denominator

The local catalog lists **26 actives, 18 passives and 3 extra/granted actions**. AP/MP/WP, range, LOS/line flags and roots are the reported native level-200 snapshot. `pending` means no individual game-verification flag in the local catalog. Spell structure, handler presence or a historical actor change is not complete acceptance.

### Active spells

| ID | Spell | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 5561 | Resonancia | 13 | 4/0/0 | 1–3 | LOS / line / modRange | 173470, 348627 | pending |
| 5562 | Flujo de Energía | 1 | 2/0/0 | 1–4 | LOS / line | 348256, 350261, 350266, 350270, 351500, 351501 | pending |
| 5563 | Luz del Alba | 21 | 2/0/0 | 1–4 | LOS / modRange | 348320, 348567 | pending |
| 5564 | Aguacero | 1 | 2/0/0 | 1–5 | LOS / line / modRange | 348319, 348584 | pending |
| 5565 | Deshielo | 7 | 2/0/0 | 1–3 | LOS / line | 348318, 348590 | pending |
| 5566 | Vestigio | 23 | 2/0/0 | 2–4 | LOS / modRange | 348296, 348596 | pending |
| 5567 | Desprendimiento | 1 | 2/0/0 | 1–3 | noLOS / line / modRange | 348379, 348605 | pending |
| 5568 | Ranura | 25 | 2/0/0 | 1–1 | LOS | 254539, 348613, 395273, 395278 | pending |
| 5569 | Falla | 9 | 2/0/0 | 1–3 | LOS / modRange | 175203, 348388, 349432, 349433, 350210, 350222 | pending |
| 5570 | Mariposas Diurnas | 3 | 2/0/0 | 1–4 | noLOS / line | 173482, 175703, 254526, 254529 | pending |
| 5571 | Disco Luminiscente | 5 | 2/0/0 | 1–5 | LOS | 348400, 348558 | pending |
| 5572 | Sombras Danzantes | 11 | 2/0/0 | 1–4 | LOS | 175244, 175583, 350398, 350413, 350459, 350469, 350479, 350482, 350490, 350493 | pending |
| 5575 | Fortaleza Solar | 3 | 3/0/0 | 1–2 | LOS | 175251 | pending |
| 5576 | Pared de Energía | 30 | 0/0/0 | 1–3 | noLOS / line | 175760 | pending |
| 5577 | Principio Valere | 60 | 2/0/0 | 0–6 | noLOS | 175262 | pending |
| 5590 | Orbes Relucientes | 19 | 3/0/0 | 1–4 | LOS / modRange | 175541, 175542, 350311, 350316 | pending |
| 5591 | Rayo Crepuscular | 29 | 4/0/0 | 1–5 | LOS / modRange | 348410, 348634, 350323, 350325 | pending |
| 5592 | Halo Tornasolado | 35 | 2/0/0 | 1–4 | LOS / modRange | 348430, 350346, 352748 | pending |
| 5593 | Lágrimas Centelleantes | 31 | 3/0/0 | 1–4 | noLOS / line / modRange | 175229, 348121, 348122, 348123, 350327, 350328, 409369, 409371 | pending |
| 5594 | Flecha de Luz | 15 | 6/0/0 | 2–5 | LOS / line / modRange | 348411, 348635 | pending |
| 5595 | Espada de Luz | 33 | 2/0/0 | 1–1 | LOS | 175232, 175688, 414011, 414012, 414058, 414059 | pending |
| 5596 | Espejismo | 27 | 2/0/0 | 1–3 | noLOS / line | 175236, 348621, 409386, 409388 | pending |
| 5597 | Resplandor de Luna | 17 | 4/0/0 | 1–1 | LOS | 348420, 348642 | pending |
| 7754 | Visio Imperum | 45 | 2/0/0 | 0–4 | noLOS | 348501 | pending |
| 7755 | Sobrecarga Rúnica | 15 | 2/0/0 | 1–4 | LOS / modRange | 348116, 348660, 351724, 351725 | pending |
| 7809 | Runificación | 90 | 0/0/0 | 1–3 | LOS / modRange | 350196, 350201 | pending |

### Passives

| ID | Passive | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 5579 | Dinamo | 10 | 0/0/0 | 0–0 | LOS | 349503 | pending |
| 5580 | Iniciativa del Alma | 80 | 0/0/0 | 0–0 | LOS | 350551 | pending |
| 5581 | Distensión Elemental | 15 | 0/0/0 | 0–0 | LOS | 350525 | pending |
| 5582 | Conexión Luminosa | 20 | 0/0/0 | 0–0 | LOS | 350527 | pending |
| 5583 | Universalidad | 30 | 0/0/0 | 0–0 | LOS | 349448, 349785 | pending |
| 5584 | Sobrecarga Rúnica | 75 | 0/0/0 | 0–0 | LOS | 350536 | pending |
| 5585 | Plenitud | 25 | 0/0/0 | 0–0 | LOS | 349344 | pending |
| 5586 | Profusión Rúnica | 40 | 0/0/0 | 0–0 | LOS | 350667, 350670 | pending |
| 5587 | Absorción Cuadramental | 45 | 0/0/0 | 0–0 | LOS | 350528, 350529, 350638 | pending |
| 5588 | Refracción Elemental | 50 | 0/0/0 | 0–0 | LOS | 350534, 416480 | pending |
| 7797 | Extensión de los Sentidos | 35 | 0/0/0 | 0–0 | LOS | 349309 | pending |
| 7798 | Trascendencia Rúnica | 90 | 0/0/0 | 0–0 | LOS | 350653 | pending |
| 7800 | Combinación Elemental | 85 | 0/0/0 | 0–0 | LOS | 350654 | pending |
| 7801 | Pulsación | 70 | 0/0/0 | 0–0 | LOS | 349340 | pending |
| 7802 | Antítesis | 10 | 0/0/0 | 0–0 | LOS | 349287 | pending |
| 7803 | Vuelo del Alma | 65 | 0/0/0 | 0–0 | LOS | 349315 | pending |
| 7804 | Altruismo del Alma | 55 | 0/0/0 | 0–0 | LOS | 350535, 395267 | pending |
| 7805 | Aire Nuevo | 60 | 0/0/0 | 0–0 | LOS | 349131 | pending |

### Extra/granted actions

| ID | Action | Static grant path | Tree exported |
|---:|---|---|---|
| 5573 | Corazón de Luz | innate_state 4069 → effect 254521 | yes |
| 5574 | Fuego Fatuo | innate_state 4069 → effect 347912 | yes |
| 5578 | Ciclo Elemental | innate_state 4069 → effect 349779 | yes |

A grant path is a dependency lead. It does not prove current grant timing, owner, client book delivery, level, duration, duplicate suppression, or removal.

## Innate states, secondary state closure, profiles, areas

Innate seed IDs: **4069, 4464, 7562** (4069: label absent in local review catalog; 4464: Golpe de gracia; 7562: Guerrero Elemental). The broad component matrix contains **47 distinct spell references, 1508 effects, 49 states, 0 native profiles and 6 area prototypes** across spell and innate roots. State overlay status is **4 partial / 45 pending**; a structurally referenced state need not be reachable or legally applied.

State IDs from the class status overlay (`*` marks innate seeds):

756 Incurable; 3434 Estabilizado; 3495 Desestabilizado - Enemigo; 3587 Transparente; 4064 Incan'runa; 4065 Acua'runa; 4066 Telu'runa; 4067 Aer'runa; 4069 label absent in local review catalog **innate seed**; 4120 Halo Tornasolado; 4121 Corazón de Fuego; 4122 Fortaleza Solar; 4126 Abundancia; 4131 label absent in local review catalog; 4132 label absent in local review catalog; 4133 label absent in local review catalog; 4134 label absent in local review catalog; 4464 Golpe de gracia **innate seed**; 5371 Última runa generada - Incan'runa; 5372 Última runa generada - Acua'runa; 5373 Última runa generada - Telu'runa; 5374 Última runa generada - Aer'runa; 6527 Desestabilizado - Aliado; 6624 Frágil; 7562 Guerrero Elemental **innate seed**; 7768 Corazón Incandescente; 7769 Corazón Acuático; 7770 Corazón Telúrico; 7771 Corazón Aéreo; 7772 label absent in local review catalog; 7774 label absent in local review catalog; 7791 Brisa Cuadramental Almacenada; 7797 label absent in local review catalog; 7798 label absent in local review catalog; 7799 label absent in local review catalog; 7800 label absent in local review catalog; 7825 Energía Positiva; 7826 Energía Negativa; 9236 Luminiscencia; 9237 Debilidad Incandescente; 9238 Debilidad Acuática; 9239 Debilidad Telúrica; 9240 Debilidad Aérea; 9241 Vestigio; 9242 Obsesión; 9243 label absent in local review catalog; 9309 label absent in local review catalog; 9315 Berserker; 9331 label absent in local review catalog

### Profile/book references

| Native profile | Native ability book in exported snapshot |
|---:|---|
| None in component snapshot | — |

### Area prototypes

| ID | Type | Native class | Historical creation route |
|---:|---|---|---|
| 781 | GLYPH | bcT | conditional audited type branch present |
| 1035 | FAKE_FIGHTER | bcQ | conditional audited type branch present |
| 1049 | GLYPH | bcT | conditional audited type branch present |
| 1052 | FAKE_FIGHTER | bcQ | conditional audited type branch present |
| 1605 | WALL | bcZ | no audited type branch observed |
| 1791 | GLYPH | bcT | conditional audited type branch present |

Area/profile rows are dependency references, not proof of creation, owner/controller identity, actor/book control, entry/exit activation, expiry, cleanup, or client presentation.

## Class resources and system inventory

Native innate seeds are 4069 (label absent from local review state names), shared 4464, and 7562 (Guerrero Elemental). Extras are Corazón de Luz 5573, Fuego Fatuo 5574 and Ciclo Elemental 5578, linked from 4069. Six area dependencies are 781, 1035, 1049, 1052, 1605 and 1791: the historical area report marks 1035/1052 FAKE_FIGHTER, 1605 WALL, and the rest GLYPH. No native profile node appears in the class component projection. Shared elemental/healing/stasis code does not prove Hupper-specific light/rune lifecycle.

Roster AP/MP/WP values are spell costs only. Any distinct meter, capped stack, conditional resource conversion, passive modifier, timer and HUD encoding needs its own observed authority. Do not infer it from generic resource handling.

## Current runtime versus historical reports

Current shared entry points include [`combat_class_initialization.py`](../../../../server/wakfu_server/combat/combat_class_initialization.py), [`combat_spell_grant.py`](../../../../server/wakfu_server/combat/combat_spell_grant.py), [`combat_spell_grant_book.py`](../../../../server/wakfu_server/combat/combat_spell_grant_book.py), [`combat_state_handler.py`](../../../../server/wakfu_server/combat/combat_state_handler.py), [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py), and the shared summon lifecycle code under `server/wakfu_server/combat/`. These implement shared machinery, not class-specific semantic acceptance.

Specific inspected runtime lead: No dedicated class-named module was found in the inspected combat source paths; current behavior is expected to flow through shared native effect/state/grant systems and needs exact-root review.

The historical normal active matrix in [`current-review-20261007.md`](../current-review-20261007.md) records 118 scenarios, 93 actor-change observations, 19 rejections, 0 no-effect observations, and 4 packet-only observations for this class. Those are source-era execution observations; the report expressly does not revalidate them against current checkout or client. They are not a score or a count of finished spells.

Historical Hupper evidence: [`healing-flags-hupper-31.json`](../healing-flags-hupper-31.json) and [`healing-flags-hupper-200.json`](../healing-flags-hupper-200.json) are bounded ordinary ally/opponent fixtures without equipped passives or illegal resource inflation; they do not cover injured-target conditions, all state/rune combinations, critical branches, or full semantics.

## Lifecycle and client risks

Verify rune identity/order, acquire/replace/consume transitions, level/duration, distinct active/passive effects, light gauge and HUD, granted spell lifecycle, and fire-wisp creation/control/expiry only where source roots actually produce an actor. Check ally/enemy/self healing and critical conversions. The two Hupper healing audits are bounded level31/200 scenarios without equipped passives, not full semantics. Historical area report has no audited WALL-1605 creation-type branch.

For this class, an integrated validation route should cover legal deck/passive ownership → Ready and innate state installation → resource/HUD snapshot → cast cost and selected cell/actor → triggered passive/state → actor or area lifecycle → turn ACK/reconnect → fight end. Assert numerical HP/armor/resource deltas, state levels/duration/removal, grant book ownership and client packets. Include prerequisite-negative, invalid-target, failed-child and replay cases, with rollback of resource, state, RNG and packets.

## Inventory outcome

This review gives the native roster and dependency denominator plus a source map; it does not claim class completion. Full condition coverage, passive semantics, state lifecycle, area/summon behavior and client presentation remain open; the roster and innate-seed equality check is established for the active release cited above. Join the root's machine-readable class enumeration when ready; do not regenerate or mutate catalogs as part of this inventory.

## Published authority reconciliation — 2026-10-10

PostgreSQL is the current catalog authority; the absence of `server/protocol/` is intentional and is not a missing-definition finding. Any earlier filesystem limitation in this review is superseded by this reconciliation. The route matrix was regenerated against the current runtime source and published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`: 161 registered families, 23 construction-gated families, no unregistered families in that matrix scope. See [current route evidence](../class-effect-route-inventory-20261010.json). Registration does not establish complete mechanics, delivery or gameplay behavior; historical class graph provenance remains separately dated.
