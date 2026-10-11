# Sadida implementation refresh — 2026-10-10

Inventory only: no gameplay edits, database writes, service operations or test executions. PostgreSQL immutable published release `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd` is authoritative. The [machine snapshot](sadida.json) preserves full current effect metadata, per-spell typed closure, all state/area definitions and eight summon books. The extraction reused `server/tools/audit_ecaflip_catalog.py` with `BREED=10` in process; it did not alter that tool. Transaction option was `default_transaction_read_only=on`.

## Result and readiness estimate

**Estimated reusable implementation: 70%, with ±10 points uncertainty. This is an implementation-planning estimate, not measured semantic or manual coverage.** Sadida is structurally present but not provisionally accepted from this refresh. No current missing definition was found in the traversed dependency scope; class-specific legal casts, doll/Voodoll interactions and complete lifecycle remain unqualified. Historical missing-family annotations cannot be treated as current defects.

| Implementation dimension | Weight | Estimated implemented | Evidence / remaining uncertainty |
|---|---:|---:|---|
| Shared foundation and published dependency availability |25|25|Definitions, numeric/resource/targeting routes and inherited shared gates exist; this scores availability, not Sadida acceptance.|
| Core active mechanics |30|22|Damage/healing/armor/displacement and summon/area routes exist; no complete Sadida legal-target matrix.|
| Passives and secondary class systems |30|15|Current20 passives, grants, doll books and chain trees exist; meaningful per-passive triggers and Voodoll delivery not qualified.|
| Lifecycle and recovery integration |15|8|General QI/retirement/replay recovery exists; eight-profile Sadida death/control/reconnect remains untested.|
| **Total** |**100**|**70**|Estimate of implementation reuse, not a test success rate.|

## Current catalog and historical reconciliation

Current counts: **21 actives +20 class passives**, **8 common passives**, **1,614 effects**, **73 states**, **9 areas**, **12 additional spell definitions**, **8 summon profiles**, and **91 effect families**. `missing=[]` means no absent definition among this extractor’s followed references. It does not assert every possible implicit native dependency is traversed.

The earlier `remaining-classes-20261010/10-review.md` names revision `a1f84e…` and labels Oct.7 graph references historical. Its direct historical projection counted1,416 effects/68 states; the broader earlier current-source audit counted1,572 effects/72 states. Those scopes differ from this refreshed own+common+innate+summon-book closure. Do not describe numerical differences alone as additions/removals or compare their percentages as test coverage. Current own41 roster agrees row-for-row with the earlier owned roster; primary extras911/926/8137 remain present, and current summon expansion makes nine further action definitions explicit.

Traversal covers every exported spell level plus level-zero roots, children, state304/321, effect421, area315/339, spell649/426 and307 summon-profile books recursively. Condition-only references, removal-only references, other parameter reference families and profile geometry/stats beyond the exported book are not claimed exhaustively reconciled. Full current parameter samples, selectors, criteria, event masks and flags are preserved in JSON for the next implementation pass.

## Every owned spell

All rows: **native definition present; gameplay not class-qualified**. “Families” is current structural dependency scope, including shared descendants, not a claim that every branch executes. Unlock levels are native metadata.

| ID | Name | Kind | Unlock | Current dependency families | Effects / states / areas |
|---:|---|---|---:|---|---|
|912|Sadida Solitario|passive|35|400|1 / 0 / 0|
|913|Guarda Plantas|passive|85|400|1 / 0 / 0|
|914|Toxinas|active|90|80, 90, 304, 321, 330, 400, 999, 1083, 1084|36 / 4 / 0|
|915|Árbol|active|3|25, 80, 304, 321, 330, 447|7 / 1 / 0|
|916|Enlace Muñequero|passive|45|400|1 / 0 / 0|
|917|Don Silvestre|passive|20|400|1 / 0 / 0|
|918|Lágrima de Sadida|active|3|1, 4, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 92, 93, 94, 95, 120, 126, 173, 174, 258, 304, 307, 315, 325, 330, 400, 430, 447, 560, 561, 562, 563, 843, 844, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|494 / 18 / 6|
|919|Viento Envenenado|active|7|5, 129, 304, 330, 1020|14 / 1 / 0|
|920|Sacrificio Muñequero|active|15|25, 28, 31, 400, 844|5 / 0 / 0|
|921|Vaporizar|active|1|1, 4, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 92, 93, 94, 95, 120, 173, 174, 304, 307, 315, 325, 330, 400, 430, 447, 560, 561, 562, 563, 843, 844, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|509 / 18 / 6|
|922|Drenaje|active|21|4, 258, 400|5 / 0 / 0|
|925|Zarza|active|1|1, 3, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 92, 93, 94, 95, 120, 173, 174, 304, 307, 315, 325, 330, 400, 430, 447, 560, 561, 562, 563, 843, 844, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|498 / 17 / 6|
|927|Hierbas Locas|active|11|1, 3, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 92, 93, 94, 95, 120, 173, 174, 304, 307, 315, 325, 330, 400, 430, 447, 560, 561, 562, 563, 843, 844, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|509 / 17 / 6|
|928|Resfriado|active|13|1, 5, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 90, 92, 93, 94, 95, 120, 173, 174, 304, 307, 315, 321, 325, 330, 400, 430, 447, 560, 561, 562, 563, 843, 844, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|494 / 18 / 6|
|929|Abono|active|5|1, 3, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 92, 93, 94, 95, 120, 173, 174, 304, 307, 315, 325, 330, 400, 430, 447, 560, 561, 562, 563, 843, 844, 865, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|507 / 17 / 6|
|930|Arcilla|active|9|1, 4, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 90, 92, 93, 94, 95, 120, 126, 161, 173, 174, 258, 304, 307, 315, 321, 325, 330, 400, 421, 430, 447, 560, 561, 562, 563, 843, 844, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|569 / 24 / 6|
|931|Herrumbre|active|15|4, 258|4 / 0 / 0|
|932|Hedor Boscoso|active|25|1, 5, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 92, 93, 94, 95, 120, 173, 174, 304, 307, 315, 321, 325, 330, 400, 430, 447, 560, 561, 562, 563, 843, 844, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|499 / 18 / 6|
|933|Explomuñeca|passive|15|400|1 / 0 / 0|
|934|Komhir|active|19|1, 5, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 92, 93, 94, 95, 120, 173, 174, 301, 304, 307, 315, 321, 325, 330, 400, 430, 447, 560, 561, 562, 563, 802, 843, 844, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|518 / 19 / 6|
|935|Terremoto|active|17|3, 330, 400, 402, 844|34 / 0 / 0|
|937|Zarzas Múltiples|active|23|3, 48|4 / 0 / 0|
|938|Borrasca|active|1|1, 5, 16, 20, 28, 31, 39, 41, 47, 48, 80, 82, 83, 84, 85, 92, 93, 94, 95, 120, 126, 173, 174, 300, 304, 307, 315, 325, 330, 400, 430, 447, 560, 561, 562, 563, 843, 844, 913, 951, 999, 1011, 1013, 1020, 1030, 1047, 1059, 1060, 1083, 1084|494 / 18 / 6|
|4959|Rezo Sadida|passive|10|999, 1084|2 / 0 / 0|
|5055|Terreno Infectado|passive|95|400|1 / 0 / 0|
|5057|Despertar Silvestre|active|30|25, 28, 40, 196, 304, 321, 330, 447, 913, 1013|20 / 3 / 0|
|5058|Murmullos Salvajes|passive|100|400|1 / 0 / 0|
|5234|Venenoso|passive|60|304, 321, 330, 400, 430, 999, 1020, 1083|26 / 2 / 0|
|7053|Terreno de Entendimiento|passive|65|400|1 / 0 / 0|
|7054|Fertilizante|active|45|20, 31, 41, 47, 80, 173, 304, 315, 330, 400, 447, 843, 999, 1047, 1093|81 / 13 / 4|
|8139|Fuerza de la Naturaleza|active|60|41, 126, 160, 304, 321, 330, 430, 1095|15 / 1 / 0|
|8149|Bendición Vudul|passive|90|400|1 / 0 / 0|
|8150|Empuje Silvestre|passive|75|48, 304, 315, 330, 349, 400, 843, 844, 949|11 / 1 / 2|
|8151|Terreno Fértil|passive|40|400|1 / 0 / 0|
|8152|Crecimiento Acelerado|passive|10|20, 31, 41, 47, 80, 173, 304, 330, 400, 999, 1047|39 / 6 / 0|
|8153|Devoción Muñequil|passive|30|400|1 / 0 / 0|
|8154|Mala Semilla|passive|25|400|1 / 0 / 0|
|8155|Ciclo Silvestre|passive|55|25, 28, 330, 843, 1047|7 / 0 / 0|
|8156|Comunicación Vegetal|passive|80|41, 57, 304, 913|4 / 1 / 0|
|8157|Conocimiento Sadida|passive|50|400|1 / 0 / 0|
|8158|Cadena de la Naturaleza|passive|70|48, 177, 330|3 / 0 / 0|

## Granted and summon action definitions

Primary grants: **911 La Superpoderosa**, **926 La Vudul**, **8137 Semilla**. Additional current book actions: **8140,5153,5023,5021,5026,5024,5025,5356,8138**. Native names are not populated for these in the extracted names document; IDs/book definitions remain authoritative. No name was fabricated. All twelve definitions and their roots are in JSON. Acquisition, casting UID ownership, disabled-level windows, cost, action-bar delivery, control and cleanup remain separate acceptance obligations.

| Profile | Exact current book references | Native level override | Status |
|---:|---|---|---|
|3745|8140|8140: override-1, max245|Definition present; actual creation/action/control/death cycle unverified.|
|3746|5153, 5023, 5021, 5026, 5024, 5025, 5356|5153: override-1, max245; 5023: override-1, max245; 5021: override-1, max245; 5026: override-1, max245; 5024: override-1, max245; 5025: override-1, max6; 5356: override-1, max245|Definition present; actual creation/action/control/death cycle unverified.|
|3747|5024, 8138|5024: override-1, max245; 8138: override-1, max245|Definition present; actual creation/action/control/death cycle unverified.|
|3748|5023, 8138|5023: override-1, max245; 8138: override-1, max245|Definition present; actual creation/action/control/death cycle unverified.|
|3749|5021, 8138|5021: override-1, max245; 8138: override-1, max245|Definition present; actual creation/action/control/death cycle unverified.|
|3750|5026, 8138|5026: override-1, max245; 8138: override-1, max245|Definition present; actual creation/action/control/death cycle unverified.|
|3751|5025, 5356, 8138|5025: override-1, max6; 5356: override-1, max245; 8138: override-1, max245|Definition present; actual creation/action/control/death cycle unverified.|
|5577|(empty)|none|Definition present; actual creation/action/control/death cycle unverified.|

**5577 has an authoritatively empty book.** That is not a missing spellbook defect. Do not give it ordinary attacks to make a scenario pass. Profile3746 has seven actions, while3747–3750 have two and3751 three. Action5025 has maximum native level6, distinct from245 for the other listed book actions; do not blindly inherit the owner level without the native evaluator.

## Resources, states and areas

Native breed resources are AP6/MP3/WP6/HP base50. Protected innates4464 and7561 are level1. No separate Sadida custom HUD meter is attested by this extraction; absence from the explicit breed8/11 HUD mapping is not a gameplay defect by itself. Actual AP/MP/WP payment/refund, armor97 and all referenced numeric characteristics still need class-specific qualification.

Key state contracts:7561 `Invocador Vegetal` roots378249/377795/377930/398466;3624 `Reacción en Cadena` maximum4 roots378028/378029/379726/379764;3616 `La vudul` maximum1;8217 `Árbol de Sadida` maximum1. All four are indefinite native states (`duration_base=-1`) with target clock; do not invent timed expiration. Other class carriers include8187–8209 doll/seed transformations,8210 Toxinas,8211–8216 grant/control carriers,8224–8229 buffs and8230 Comunicación Vegetal. Exact roots, caps and timing for **all73 states** are in JSON.

Current state IDs: `1144, 3309, 3434, 3495, 3587, 3590, 3591, 3595, 3596, 3597, 3598, 3599, 3600, 3615, 3616, 3617, 3624, 3640, 3645, 3681, 3682, 3827, 3837, 3856, 3857, 4097, 4464, 6505, 6506, 6527, 7561, 8187, 8188, 8189, 8190, 8191, 8192, 8193, 8194, 8195, 8196, 8197, 8198, 8199, 8200, 8201, 8202, 8204, 8205, 8206, 8207, 8208, 8209, 8210, 8211, 8212, 8213, 8214, 8215, 8216, 8217, 8224, 8225, 8226, 8227, 8228, 8229, 8230, 8257, 8258, 8259, 9315, 9331`.

| Area ID | Current roots | Shape | Timing/removal caution |
|---:|---|---|---|
|781|157651|point|Native masks/properties and raw duration fields retained in JSON; no assumed timed expiry.|
|1835|379521|point|Native masks/properties and raw duration fields retained in JSON; no assumed timed expiry.|
|1836|378645, 380036|rectangular or square ring-w:1-1 / h:1-1|Native masks/properties and raw duration fields retained in JSON; no assumed timed expiry.|
|1850|379712, 380035|crossRing-1-1|Native masks/properties and raw duration fields retained in JSON; no assumed timed expiry.|
|1851|379760|point|Native masks/properties and raw duration fields retained in JSON; no assumed timed expiry.|
|1852|379761|point|Native masks/properties and raw duration fields retained in JSON; no assumed timed expiry.|
|1853|379762|point|Native masks/properties and raw duration fields retained in JSON; no assumed timed expiry.|
|1854|379763|point|Native masks/properties and raw duration fields retained in JSON; no assumed timed expiry.|
|1855|379771|point|Native masks/properties and raw duration fields retained in JSON; no assumed timed expiry.|

Seed/tree/doll cap criteria use owned-team state counts, e.g.379583 requires8217 nearby and a count expression below6, while377776 checks individual doll counts and Voodoll subtraction. These are not interchangeable with a generic global summon count. Area ownership selectors are mixed deliberately: some use `IsSpecificArea(1853)` while neighbors use `IsOwnSpecificArea`; preserve exact native expressions rather than normalizing all to owner-only.

## Voodoll and shared damage: exact limits

Spell926 roots166082/378128/378133 include grouped creation and explicit kill28. State3616 roots156929/156930/341002/164943/378558/379563/379606/414067 include characteristic group913 and damage16 descendants.156930 has children379641 and156931;379641 is conditional on passive933, while156931 uses native damage parameters `[1,1,1,0]`. Native runner value, source/target/controller and effect context must be followed; a generic damage-link assumption is insufficient.

**Preserve disabled native branches.** State3616 root341002 criterion is `False`;164943 affiliation event1001 branch is `False`;378558 event2235 lethal/armor predicate ends in `and False`. Their descendants are structurally present but not active routes. Native affiliation1030 effects164944/164945 therefore do not prove a live Voodoll team switch. No missing share-damage mechanism is proven from those dormant branches. Actual Voodoll creation, target binding, received direct/AoE damage, ally/enemy healing, owner death, target death, dismissal, recast and no double-delivery must be investigated from the enabled graph.

## Reused advances and current route status

Old family hints28/47/325/349/430/560/561/562/563/1030 are now represented in shared code: kill28, disabled spell-level47, AI control325, authoritative QI cell group349, triggering-value430, fixed-characteristic eWX560–563, and affiliation1030. This establishes route existence, not Sadida runtime completion.349 metadata validates exact native criterion presence and actual QI/surface height; missing authority raises rather than silently selecting cells. Historical8150 “partial correction” is not a fresh proven blocker.

Applicable improvements since the early inventory include: state recursion identity by reference+state UID with criteria-before-cycle and bounded depth; fresh selector handling and exact cast anchors; validated retained-container cost authority and nested replay history; multiple matched normal/critical state pairs; corpse healing guard; full multiplayer character/deck context; actual QI registration/release and fresh summon-slot reuse; protected summon retirement; shared area ownership/removal and retained-manager cleanup. Each requires matching the Sadida native contract; prior-class passes do not certify dolls.

Concrete shared source anchors: `combat_effect_runtime.py`, `combat_effect_dispatch.py`, `combat_cell_group.py`, `combat_ai_control.py`, `combat_set_current_characteristic.py`, `combat_summon_creation.py`, `combat_summon_spellbook.py`, `combat_summon_retirement.py`, `combat_protected_kill.py`, `combat_state_variants.py`, `combat_event_replay.py` and area lifecycle modules. Source hashes for existing files are appended in JSON.

## Evidence versus gaps

| Finding | Classification | Next proof required |
|---|---|---|
| No missing record in followed current closure | Structural availability confirmed | Expand implicit/reference-family contracts before asserting universal closure.|
| Eight books present,5577 empty | Catalog contract confirmed | Legal creation, every actionable ability, native control/turn/cap and retirement.|
| Disabled Voodoll and disabled-level branches | Native intentional inactivity | Keep False/min/max gates; no fabricated activation.|
| Historical8150 cell-group warning | Unverified current behavior, not proven missing handler | Real legal seed/tree count and cell/QI scenario through379583.|
| Ordinary ally925 armor audit | Narrow historical evidence only | Actual ally/enemy/self/empty-cell normal+critical and armor consumption.|
| Full dolls/seed/tree/Voodoll pipeline | Unverified | Source-qualified real casts/events, positive/negative controls and rollback.|
| Shared damage/event context | High-risk unverified | Verify enabled Voodoll producer/recipient, exact once-only damage and bounded recursive reactions.|
| All20 passive mechanics | Unverified individually | Native trigger/threshold/control cases, not just successful initialization.|
| Reconnect/surrender/dungeon progression/client animation | Unverified | Full multiplayer manual battery after automated implementation qualification.|

No concrete missing gameplay implementation was reproduced in this inventory-only pass. That does **not** mean all mechanics work. The strongest current deficit is missing class-specific semantic evidence, with potential integration defects at controller/context, event timing, QI/area cleanup and simultaneous death boundaries.

## Existing test coverage and proposed complete qualification

No `test_*sadida*` or `test_*voodoll*` class pipeline module was found in `server/tests` during this refresh. Existing shared suites include cell-group/QI, AI control, fixed-characteristic assignment, summon relationships/count completeness/slot reuse/control wire turns, areas/removal/expiry, state variants, armor and value transfer. Their existence is not a new execution result. The historical925 ally audit reports `gameplay_verified=false` and only10 executed effect references; it cannot substitute for class acceptance.

Run a later implementation qualification in this order: all21 active legal contexts and all20 passive initialization; acquired911/926/8137 grants; all8 profiles and exact books; every ability under its actual owner/controller/turn; all9 areas and native reactions/removal; chain state3624 levels0→4 and negative/cap controls; precise doll count/replacement and foreign-owner isolation; Voodoll damage/healing plus multi-death ordering; actual NPC kill→QI release→cell reuse→resummon; owner/target death and no stuck turn; multiplayer Ready/reconnect/surrender and dungeon completion; Cra/Iop and accepted classes regression. Include resource receipts, immutable source snapshots and rejection rollback throughout. No test was run or delegated for this inventory-only request.

## Final inherited validation boundary

The parent workstream reports the latest deployed shared implementation/catalog548e1468… inherited a green182-test shared gate. A fresh Luna inventory-validation run passed36/36 tests across seven generic modules. These are shared foundation evidence only: no doll/Voodoll/Sadida class pipeline was found and neither result is counted as Sadida semantic acceptance. This refresh is frozen after read-only extraction and documentation; no services, gameplay code, DB data or catalog activation were changed.
