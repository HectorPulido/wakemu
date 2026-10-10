# Steamer class inventory review — 2026-10-10

Inventory-only review of local runtime source and available class reports. No gameplay/catalog files were modified; no service, database or client was operated. Native breed ID: **16**.

## Authority and source freshness

PostgreSQL is the live native-catalog authority, read through [`native_catalog.py`](../../../../server/wakfu_server/storage/native_catalog.py); `server/protocol/` was deliberately removed after this migration, so its absence is not a catalog gap. In a direct `BEGIN READ ONLY` query against the active release, revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38` (complete; 7,483 documents), the published `Steamer roster` reconciles exactly with this report's local inventory: 41 spell IDs with matching kind, unlock level, and localized names. The current `breed-innate-definitions.json` entry also matches the innate IDs **7675, 4464** below. Relevant exact document hashes and the read-only verification method are recorded in the source audit. This proves catalog alignment for roster and innate seeds only; cast fields and broad dependency matrices below remain dated native-export snapshots.

Roster names/ownership/grant paths come from [`inventory.json`](../inventory.json), locally refreshed 2026-10-09. Native cast cost/range/root fields come from [`class-casting-gap-inventory-20261007.json`](../class-casting-gap-inventory-20261007.json), at level 200. Innate seeds, typed dependency counts, profiles and areas come from [`class-native-mechanic-components-20261007.json`](../class-native-mechanic-components-20261007.json) and [`class-native-mechanic-graph-20261007.json`](../class-native-mechanic-graph-20261007.json). State status counts come from [`class-state-gap-inventory.json`](../class-state-gap-inventory.json). These are pinned historical source reports, not live database reads.

Do **not** treat the Oct 8 `class-effect-route-inventory` overlay as a current source verdict: its source tree is missing here and regeneration needs the active catalog. The Oct 7 area contracts below are historical native structural evidence only.

## Owned spell denominator

The local catalog lists **21 actives, 20 passives and 4 extra/granted actions**. AP/MP/WP, range, LOS/line flags and roots are the reported native level-200 snapshot. `pending` means no individual game-verification flag in the local catalog. Spell structure, handler presence or a historical actor change is not complete acceptance.

### Active spells

| ID | Spell | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 6902 | Fuego Ardiente | 1 | 2/0/0 | 3–6 | LOS / modRange | 309827, 343680 | pending |
| 6903 | Escupellamas | 3 | 4/0/0 | 1–3 | LOS / line / modRange | 343111, 343689 | pending |
| 6904 | Calcinación | 9 | 4/0/0 | 3–6 | noLOS | 343120, 343700 | pending |
| 6905 | Flambeado | 15 | 3/0/0 | 1–5 | LOS / modRange | 343127, 343709 | pending |
| 6906 | Desfonde | 21 | 5/0/0 | 1–4 | LOS / modRange | 343135, 343717, 345917, 345921 | pending |
| 6907 | Corriente | 1 | 3/0/0 | 1–4 | LOS / line / modRange | 343179, 343182, 343185, 344924, 344925, 344932, 345157, 345158 | pending |
| 6908 | Evaporación | 7 | 4/0/0 | 2–3 | noLOS / line | 343223, 343736 | pending |
| 6909 | Espuma de Mar | 13 | 3/0/0 | 1–3 | LOS / line / modRange | 343275, 343759 | pending |
| 6910 | Piratería | 19 | 3/0/0 | 3–4 | noLOS / line / modRange | 343284, 343766 | pending |
| 6911 | Disolución | 25 | 4/0/0 | 1–3 | LOS / line | 343306, 343773 | pending |
| 6912 | Steamaza | 1 | 3/0/0 | 1–1 | LOS | 297420, 297422, 297740, 297741, 298461, 309897, 309911, 309913 | pending |
| 6913 | Pisoteo | 5 | 3/0/0 | 1–3 | LOS | 297424, 343780 | pending |
| 6914 | Machacado | 11 | 2/0/0 | 1–4 | LOS / modRange | 297430, 343373, 343788, 343796, 345141 | pending |
| 6915 | Martillo Imán | 17 | 4/0/0 | 1–4 | LOS / line / modRange | 297440, 343797 | pending |
| 6916 | Shock | 23 | 6/0/0 | 1–3 | LOS | 343380, 343806, 394992, 394998 | pending |
| 6917 | Blindaje | 3 | 0/0/2 | 1–5 | LOS / modRange | 343402 | pending |
| 6918 | Sobretensión | 15 | 3/0/0 | 1–5 | LOS / modRange | 343408, 343811 | pending |
| 6919 | Maquinaria | 30 | 0/0/2 | 1–3 | LOS / modRange | 343416 | pending |
| 6920 | Emboscada | 45 | 3/0/0 | 1–3 | LOS / modRange | 343426 | pending |
| 6921 | Transición | 60 | 1/0/1 | 1–3 | LOS / line / modRange | 350962 | pending |
| 6922 | Flujo de Stasis | 90 | 2/0/0 | 1–3 | LOS | 343449 | pending |

### Passives

| ID | Passive | Unlock | AP/MP/WP | Range @200 | Native flags | Selected roots @200 | Review |
|---:|---|---:|---|---:|---|---|---|
| 6925 | Moderador de Energía | 10 | 0/0/0 | 0–0 | LOS | 344474 | pending |
| 6926 | Caminos Tortuosos | 10 | 0/0/0 | 0–0 | LOS | 297815 | pending |
| 6927 | Versatilidad | 15 | 0/0/0 | 0–0 | LOS | 343946 | pending |
| 6928 | Blindaje Reforzado | 20 | 0/0/0 | 0–0 | LOS | 343974 | pending |
| 6929 | Estrategia Robótica | 25 | 0/0/0 | 0–0 | LOS | 346193, 351785 | pending |
| 6930 | Tecnología de Transportes | 30 | 0/0/0 | 0–0 | LOS | 298007 | pending |
| 6931 | Asistencia Telúrica | 35 | 0/0/0 | 0–0 | LOS | 344157, 344217, 344219 | pending |
| 6932 | Sustitución Mecánica | 40 | 0/0/0 | 0–0 | LOS | 297895 | pending |
| 6933 | Paciencia | 45 | 0/0/0 | 0–0 | LOS | 343859, 395986 | pending |
| 6934 | Aleación Ligera | 50 | 0/0/0 | 0–0 | LOS | 297884 | pending |
| 6935 | Inversión de Energía | 55 | 0/0/0 | 0–0 | LOS | 344043 | pending |
| 6936 | Revestimiento Absoluto | 60 | 0/0/0 | 0–0 | LOS | 344011, 344429 | pending |
| 6937 | Activación | 65 | 0/0/0 | 0–0 | LOS | 343999 | pending |
| 6938 | Ejecución Inmediata | 70 | 0/0/0 | 0–0 | LOS | 344024, 395182, 395184 | pending |
| 6939 | Protección Stasiada | 75 | 0/0/0 | 0–0 | LOS | 344040 | pending |
| 6940 | Ruedas Calientes | 80 | 0/0/0 | 0–0 | LOS | 343996, 395004 | pending |
| 6941 | Conquista Serena | 85 | 0/0/0 | 0–0 | LOS | 344026, 344140 | pending |
| 6942 | Chapuza | 90 | 0/0/0 | 0–0 | LOS | 344030 | pending |
| 6943 | Mecánica Avanzada | 95 | 0/0/0 | 0–0 | LOS | 344028 | pending |
| 7810 | Despliegue Táctico | 100 | 0/0/0 | 0–0 | LOS | 350970, 395005 | pending |

### Extra/granted actions

| ID | Action | Static grant path | Tree exported |
|---:|---|---|---|
| 6923 | Steamerator | innate_state 7675 → effect 347167 | yes |
| 6924 | Cañonero | innate_state 7675 → effect 347174 | yes |
| 7008 | Microbot | innate_state 7675 → effect 347165 | yes |
| 7700 | Torreta | innate_state 7675 → effect 347166 | yes |

A grant path is a dependency lead. It does not prove current grant timing, owner, client book delivery, level, duration, duplicate suppression, or removal.

## Innate states, secondary state closure, profiles, areas

Innate seed IDs: **7675, 4464** (7675: Maestro del Sabotaje; 4464: Golpe de gracia). The broad component matrix contains **45 distinct spell references, 1063 effects, 35 states, 2 native profiles and 4 area prototypes** across spell and innate roots. State overlay status is **3 partial / 32 pending**; a structurally referenced state need not be reachable or legally applied.

State IDs from the class status overlay (`*` marks innate seeds):

3309 Cegado; 3434 Estabilizado; 3495 Desestabilizado - Enemigo; 4464 Golpe de gracia **innate seed**; 6288 Bloque; 6527 Desestabilizado - Aliado; 7647 Steamerator; 7648 Cañonero; 7649 Torreta; 7650 label absent in local review catalog; 7651 Sobrepresión; 7654 Malus Golpe Crítico y Anticipación; 7655 Disolución; 7664 label absent in local review catalog; 7665 Bonus de Placaje; 7668 Bonus de Distancia; 7669 Malus de resistencia; 7672 Torreta; 7675 Maestro del Sabotaje **innate seed**; 7677 label absent in local review catalog; 7678 label absent in local review catalog; 7679 label absent in local review catalog; 7681 label absent in local review catalog; 7688 label absent in local review catalog; 7725 label absent in local review catalog; 7726 label absent in local review catalog; 7742 label absent in local review catalog; 7743 label absent in local review catalog; 7744 Sobretensión; 7745 label absent in local review catalog; 8906 label absent in local review catalog; 8930 label absent in local review catalog; 9197 label absent in local review catalog; 9315 Berserker; 9331 label absent in local review catalog

### Profile/book references

| Native profile | Native ability book in exported snapshot |
|---:|---|
| 2011 | empty ability list in exported profile |
| 3792 | empty ability list in exported profile |

### Area prototypes

| ID | Type | Native class | Historical creation route |
|---:|---|---|---|
| 781 | GLYPH | bcT | conditional audited type branch present |
| 978 | FAKE_FIGHTER | bcQ | conditional audited type branch present |
| 1473 | GLYPH | bcT | conditional audited type branch present |
| 1773 | GLYPH | bcT | conditional audited type branch present |

Area/profile rows are dependency references, not proof of creation, owner/controller identity, actor/book control, entry/exit activation, expiry, cleanup, or client presentation.

## Class resources and system inventory

Innate state 7675 (Maestro del Sabotaje) and shared state 4464 seed the class. Four extras are Steamerator 6923, Cañonero 6924, Microbot 7008 and Torreta 7700, linked from 7675 in the snapshot. The graph has profile rows 2011 and 3792; both show empty ability lists in the Oct 7 export (2011 maps to Jarabe de Pala in the spell-name report). Area refs include 781/1473/1773 GLYPH and 978 FAKE_FIGHTER. Current code has a native Microbot path projection, which covers path geometry only.

Roster AP/MP/WP values are spell costs only. Any distinct meter, capped stack, conditional resource conversion, passive modifier, timer and HUD encoding needs its own observed authority. Do not infer it from generic resource handling.

## Current runtime versus historical reports

Current shared entry points include [`combat_class_initialization.py`](../../../../server/wakfu_server/combat/combat_class_initialization.py), [`combat_spell_grant.py`](../../../../server/wakfu_server/combat/combat_spell_grant.py), [`combat_spell_grant_book.py`](../../../../server/wakfu_server/combat/combat_spell_grant_book.py), [`combat_state_handler.py`](../../../../server/wakfu_server/combat/combat_state_handler.py), [`combat_effect_area_events.py`](../../../../server/wakfu_server/combat/combat_effect_area_events.py), and the shared summon lifecycle code under `server/wakfu_server/combat/`. These implement shared machinery, not class-specific semantic acceptance.

Specific inspected runtime lead: `combat_microbot_path.py` projects rail/path geometry; this does not certify machine lifecycle.

The historical normal active matrix in [`current-review-20261007.md`](../current-review-20261007.md) records 96 scenarios, 78 actor-change observations, 2 rejections, 4 no-effect observations, and 8 packet-only observations for this class. Those are source-era execution observations; the report expressly does not revalidate them against current checkout or client. They are not a score or a count of finished spells.

Historical Steamer evidence: [`native-turn-hud-steamer-final.json`](../native-turn-hud-steamer-final.json) reports a bounded level-200 Ready/turn/HUD sequence with stable tracked sources. Its own scope specifies synthetic flat terrain and no GUI claim; 6923/state7647 and SP changes do not certify all class actions or current deployment.

## Lifecycle and client risks

Separate AP/MP/WP from Stasis points (SP) and HUD characteristic replication; test SP gain/spend/cap and do not invent WP regeneration. Validate machine placement/cap, ownership, rail and height/obstacle geometry, turret target/action/turn, duration/expiry, HUD snapshots, death/recall/end cleanup and reconnect. Existing Steamer HUD evidence is bounded and synthetic, with no GUI claim. Do not equate profile rows with a functioning turret ability book.

For this class, an integrated validation route should cover legal deck/passive ownership → Ready and innate state installation → resource/HUD snapshot → cast cost and selected cell/actor → triggered passive/state → actor or area lifecycle → turn ACK/reconnect → fight end. Assert numerical HP/armor/resource deltas, state levels/duration/removal, grant book ownership and client packets. Include prerequisite-negative, invalid-target, failed-child and replay cases, with rollback of resource, state, RNG and packets.

## Inventory outcome

This review gives the native roster and dependency denominator plus a source map; it does not claim class completion. Full condition coverage, passive semantics, state lifecycle, area/summon behavior and client presentation remain open; the roster and innate-seed equality check is established for the active release cited above. Join the root's machine-readable class enumeration when ready; do not regenerate or mutate catalogs as part of this inventory.

## Published authority reconciliation — 2026-10-10

PostgreSQL is the current catalog authority; the absence of `server/protocol/` is intentional and is not a missing-definition finding. Any earlier filesystem limitation in this review is superseded by this reconciliation. The route matrix was regenerated against the current runtime source and published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`: 161 registered families, 23 construction-gated families, no unregistered families in that matrix scope. See [current route evidence](../class-effect-route-inventory-20261010.json). Registration does not establish complete mechanics, delivery or gameplay behavior; historical class graph provenance remains separately dated.
