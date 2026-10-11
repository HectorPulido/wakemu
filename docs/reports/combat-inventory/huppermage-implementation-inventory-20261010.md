# Huppermage implementation inventory — 2026-10-10

## Authority and denominator

Authority: complete published PostgreSQL revision `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`. The extraction uses `native_catalog_documents` for provenance and `native_catalog_records` for bounded source reads. No `server/protocol` fallback, writes, publication or service operations are used.

Native Huppermage is **breed19**, with **44 own spells** (26 active, 18 passive), eight common passives and three innate states4069/4464/7562. Conservative declared dependency closure contains **1549 effects, 50 states and 6 areas**. All exported spell-level arms are included; this is a source denominator, not an execution percentage. There are no missing records in the traversed dependency domains.

Machine evidence: `huppermage-catalog-inventory-20261010.json`. Reproduction tool: `server/tools/audit_huppermage_catalog.py`. Reference traversal includes group children, state applications304, grants649, nested casts426 and area creation315/339. Condition-only references and state removal references remain expressions rather than executable seeds. Additional reference families need explicit qualification before calling the closure exhaustive.

## Own spell inventory

| ID | Native localized name | Kind | Unlock | Declared effect families |
|---|---|---|---:|---|
| 5561 | Resonancia | active | 13 | 330, 1083 |
| 5562 | Flujo de Energía | active | 1 | 2, 150, 304, 330, 400, 876 |
| 5563 | Luz del Alba | active | 21 | 2, 304, 321, 330, 400, 1085, 1093 |
| 5564 | Aguacero | active | 1 | 4, 258, 330, 400 |
| 5565 | Deshielo | active | 7 | 4, 258, 304, 321, 330, 400, 447, 1085, 1093 |
| 5566 | Vestigio | active | 23 | 4, 126, 129, 258, 304, 330 |
| 5567 | Desprendimiento | active | 1 | 3, 48, 55, 330 |
| 5568 | Ranura | active | 25 | 3, 48, 177, 330 |
| 5569 | Falla | active | 9 | 3, 304, 321, 330, 400, 1013, 1085, 1093 |
| 5570 | Mariposas Diurnas | active | 3 | 5, 300, 301, 330 |
| 5571 | Disco Luminiscente | active | 5 | 2, 304, 321, 330, 400, 1085, 1093 |
| 5572 | Sombras Danzantes | active | 11 | 5, 304, 321, 330, 340, 400, 1085, 1093 |
| 5575 | Fortaleza Solar | active | 3 | 2, 3, 4, 5, 31, 39, 40, 48, 55, 80, 126, 129, 150, 177, 258, 300, 301, 304, 321, 330, 340, 400, 422, 447, 649, 876, 1013, 1085, 1086, 1093 |
| 5576 | Pared de Energía | active | 30 | 48, 330, 339, 400 |
| 5577 | Principio Valere | active | 60 | 302, 315, 330, 340, 345, 400, 422, 843 |
| 5579 | Dinamo | passive | 10 | 321, 330 |
| 5580 | Iniciativa del Alma | passive | 80 | 31, 330, 421 |
| 5581 | Distensión Elemental | passive | 15 | 400 |
| 5582 | Conexión Luminosa | passive | 20 | 400 |
| 5583 | Universalidad | passive | 30 | 80, 126, 160, 330, 400, 1086, 1095 |
| 5584 | Sobrecarga Rúnica | passive | 75 | 400 |
| 5585 | Plenitud | passive | 25 | 400 |
| 5586 | Profusión Rúnica | passive | 40 | 304, 321, 330, 400, 430, 1093 |
| 5587 | Absorción Cuadramental | passive | 45 | 177, 330, 1085, 1093 |
| 5588 | Refracción Elemental | passive | 50 | 2, 3, 4, 5, 31, 39, 40, 48, 55, 82, 83, 84, 85, 96, 97, 98, 99, 126, 129, 132, 133, 134, 135, 150, 177, 258, 300, 301, 304, 321, 330, 340, 400, 421, 422, 447, 560, 561, 562, 563, 649, 844, 876, 912, 913, 1013, 1085, 1093, 1095 |
| 5590 | Orbes Relucientes | active | 19 | 304, 321, 330, 400, 402, 1083, 1084, 1093 |
| 5591 | Rayo Crepuscular | active | 29 | 304, 321, 330, 400, 913, 1083, 1085, 1093 |
| 5592 | Halo Tornasolado | active | 35 | 304, 321, 330, 400, 1083, 1085, 1093 |
| 5593 | Lágrimas Centelleantes | active | 31 | 304, 321, 330, 400, 1083, 1084, 1085, 1093 |
| 5594 | Flecha de Luz | active | 15 | 300, 304, 321, 330, 402, 421, 430, 913, 1083 |
| 5595 | Espada de Luz | active | 33 | 24, 330, 865, 1083 |
| 5596 | Espejismo | active | 27 | 5, 304, 321, 330, 400, 422, 1085, 1093 |
| 5597 | Resplandor de Luna | active | 17 | 304, 321, 330, 400, 402, 865, 1013, 1083, 1085, 1093 |
| 7754 | Visio Imperum | active | 45 | 39, 160, 161, 304, 330, 400, 430, 447, 1093 |
| 7755 | Sobrecarga Rúnica | active | 15 | 31, 41, 80, 304, 321, 330, 400, 1084, 1085, 1093 |
| 7797 | Extensión de los Sentidos | passive | 35 | 400 |
| 7798 | Trascendencia Rúnica | passive | 90 | 330, 430 |
| 7800 | Combinación Elemental | passive | 85 | 304, 321, 330, 400, 1093 |
| 7801 | Pulsación | passive | 70 | 400 |
| 7802 | Antítesis | passive | 10 | 400 |
| 7803 | Vuelo del Alma | passive | 65 | 400 |
| 7804 | Altruismo del Alma | passive | 55 | 330, 400, 912, 1085 |
| 7805 | Aire Nuevo | passive | 60 | 400 |
| 7809 | Runificación | active | 90 | 126, 304, 321, 330, 400, 1085, 1093, 1095 |

## Additional native actions

Innate4069 grants three actions outside the44 own deck entries:5573,5574 and5578. The source effects254521/347912/349779 place them in native bar2 slots0/1/2 on opening1028, excluding action933 forms and instance862. They must be resolved through actual granted UIDs; manually constructing an own-deck UID is invalid. Their roots and casting flags are recorded under `derived_spells` in the JSON.

## Mechanism map and risks

| Mechanism | Native evidence | Current shared implementation | Remaining acceptance |
|---|---|---|---|
| Four elemental runes | Innate4069: root175866 global1024, children175867–175870 test IsActivatedByElement(1–4), then apply4064–4067 | combat_cast_events.py / combat_runtime_adapter.py / combat_state_handler.py | Actual four-element casts/runes passed; broader combinations remain separate |
| Quadramental Breeze | Characteristic111; families1085 gain and1086 loss; native intrinsic events2244/2245 | combat_current_stat_consumer.py merges native-current-stat-events with actual source mask6 | Native initial500/max-WP link,5594 expenditure200 and end-turn recovery200 passed; Heart inversion remains separate |
| WP/Breeze coupling | Innate175857 listens67,175859 listens68; class1020 transmits actual source value; children adjust111 | combat_trigger_level_group.py; current-stat193/194 publish67/68 from native registry | WP changes must alter Breeze using actual value, without confusing AP/MP or raw maximum with current |
| Natural end boundary | Innate175304 subscribes1037;175306 gains200 unless4121 | combat_turn_events.py explicit documented Wakemu end-regeneration policy | Test ordinary end then Heart mode end; no fabricated event injection |
| Opening/start boundary |175861 listens1003;254520 listens1028;4121 has start/end rules | combat_start_events.py and combat_turn_events.py | Existing Heart test directly applies native source effect416488; this does not prove a user-accessible passive path |
| LIGHT |1083 damage /1084 healing; strongest mastery with native tie order | combat_damage_healing.py light_damage_element; generic damage/heal handlers | Unequal mastery and ties; inspect actual resulting damage element, not icon alone |
| Rune inversion/removal |321 decurse plus304 states and400 markers; packet/removal state ownership matters | combat_state_decurse.py / combat_state_child_removal.py / combat_effect_dispatch.py | Inverse lifecycle, marker persistence and no duplicated reactions after repeated casts |
| Temporary abilities |649 grants in innate4069 and Fortress/Refraction closures | combat_spell_grant.py / combat_spell_grant_book.py | Actual current UID, granted action availability, removal and reconnect |
| Areas |GLYPH781/1049/1791, FAKE_FIGHTER1035/1052, WALL1605; native point shapes | combat_effect_area.py / combat_wall_area.py / combat_fake_fighter.py | Constructor, blocked placement, collision/LOS and retirement; source shape alone does not prove callbacks |
| Incoming modifiers/healing |1093 triggering final modifier,1094/1095 FINAL_HEAL_IN_PERCENT114 changes, actual state criteria | combat_final_modifier.py / combat_effect_dispatch.py | Friendly/self/enemy distinctions and immediate vs retained client delivery |

No Hupper-only production patch has been justified at this checkpoint. Most behavior is expressed by source data on shared mechanisms. Missing behavior must be repaired in its shared owner after a concrete failing path is established, rather than adding spell-ID branches. The apparent family171 absence in the broad static report belongs to common passive4956. PostgreSQL effect-characteristic-registry confirms its eWQ/INIT35 binding, which the factory registers generically; it is not an actual missing Hupper route.

## Automated verification

New `test_combat_huppermage_runtime.HuppermageRuntimeTests.test_four_elemental_casts_create_matching_native_rune` uses actual native initialization and ordinary owned spell transactions at level200. Four independent source fixtures use fixed variation seed17 and cast5562/5564/5567/5570 into a native enemy at distance2. Assertions cover matching rune4064/4065/4066/4067, damage, AP consumption and source snapshot immutability. No states or resources are injected. Luna verified all four subcases: 1 test passed in 94.064 seconds. This proves the four ordinary rune/damage branches, not the complete resource or grant system.

Extraction command (credentials stay in the existing private file):

```sh
PYTHONPATH=server WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' WAKFU_DATABASE_PASSWORD_FILE=.runtime/local/secrets/postgres-password /tmp/wakemu-combat-review-venv/bin/python3 server/tools/audit_huppermage_catalog.py --output docs/reports/combat-inventory/huppermage-catalog-inventory-20261010.json
```

## Complete manual battery

Use a legitimately leveled Huppermage and a durable sparring target. The full battery needs level200 to expose every own spell and passive; do not bypass deck availability with invented commands. Save the original deck before changing it. Run the following groups as one system acceptance, recording spell names/IDs, current runes, Breeze, AP/WP, target health and any rejection.

1. Start with elemental spells5562,5564,5567,5570 and no optional passive. Cast each element on a legal target cell. Expect the matching rune4064/4065/4066/4067, legal damage/AP cost and no unrelated elemental rune from the same single-element cast. Repeat an element and check the native condition prevents unintended duplicate rune acquisition.
2. Add light spells5590–5597 in valid deck slots, in batches if necessary. Acquire their stated prerequisites normally; cast at legal ranges. Expect Breeze expenditure and actual damage/healing. Test differing elemental masteries and a tie; strongest-mastery LIGHT selection must follow FIRE/WATER/EARTH/AIR tie order. Compare target resistance-sensitive outcomes rather than using the spell icon as proof.
3. Advance turns normally with and without Heart of Fire4121. Record Breeze before/end/next start. Verify ordinary regeneration and the passive inversion/removal stated by the current tooltip; no manual state injection. Equip5588 and7797 separately and together in later runs to distinguish their source criteria.
4. Exercise utility5575/5576/5577/7754/7755/7809 after normal prerequisites. Check created area placement, occupied-cell rejection without partial AP loss, wall movement/LOS behavior, temporary spell UID availability and removal. End/reconnect once and confirm no phantom areas or stale granted actions.
5. Repeat damage and healing against enemy, ally and self where casting permits. Check self-exclusions, target/controller ownership and modifier removal. Complete one victory and one surrender; return to the world with the original character appearance, no combat-only actions and no stuck resources.
6. Repeat with each optional passive in legal slots, grouping compatible passives. The44-row table is the denominator: mark each spell/passive as exercised, blocked by a known prerequisite, or failed with an exact observable result. A successful four-element test alone must never be reported as complete Huppermage verification.

## Concrete shared blocker: omitted native resource-cost map

Read-only original bytecode identifies a real data/payment gap beyond handler
registration. `.runtime/local/fyF-casting.txt`, method
`fyF.g(fyG,eGj,Object,Object)` (lines585–678), iterates **all** entries in
`fyP.guh()`, evaluates each native `fyI.Qi(level)` and category modifier, and
stores them in a `fyQ`. For `ffw.sid` (HUPPERMAGE_RESOURCE111), offsets160–180
call `fyQ.h(byte,int)` without the ordinary zero clamp. Other characteristics
call `fyQ.g` after `max(0,cost)`. Original `/tmp/wakemu-fyQ-cost-review.txt`
confirms `h` preserves signed and zero values, whereas `g` discards nonpositive
values.

The initial audit found that `sniffer/java/ExportNativeSpellCasting.java` lines19/25 exported only AP/MP/WP. The following paragraph describes that pre-correction baseline.
The PostgreSQL `native-spell-casting.json` row5594 likewise has only a three-value
cost table. `combat_conditional_costs.py` selects/modifies three-key tuples, and
`combat_spell_transaction.py` lines77–95 pays only AP/MP/WP. The declared LIGHT
spell5594 effect closure contains no class1086 Breeze-loss applicator to supply
that missing payment elsewhere. Thus the native full cost-map source cannot be
represented by the current cast-cost schema. Actual per-spell111 values still
require a source export; no cost amount or sign is guessed here.

Proposed general correction sent to the coordinating agent: export/import the
entire baseline and conditional native resource-cost maps, preserve signed111
semantics, validate current resource eligibility and pay atomically through the
actual class characteristic authority. Native category modifiers and emitted
cost context must use the same selected table. The complete correction is implemented below. Catalog activation remains owned by the coordinating agent; the four rune casts alone do not certify the remaining class mechanics.


## Full resource-cost correction (implemented; deployment pending)

The new original-Java export reads all 4,143 spell `fyP.guh` maps, baseline and conditional, at levels0 through the declared maximum. Observed resource keys are2/AP,3/MP,4/WP,111/Breeze and123. The three-resource public fields remain available; extra resources are additive.

Original `fyM.a` and `fcN.b` prove that resource111 is a signed **current delta**: negative consumes Breeze and requires its absolute amount to be available; positive recovers Breeze. `fyM` applies consumption modifier112 or generation modifier113, including Java overflow and float rounding. For example, native5594 has delta−200, not a positive200 cost magnitude. `eWf`'s fourth packed resource is `shk`, not Breeze, and is not reused.

The shared correction selects the complete table, rejects unknown criteria changing extra resources, verifies legacy AP/MP/WP against the existing casting table, approves extra deltas once, and applies them inside the atomic cast preview. Paid nested426 casts share the payment; explicitly cost-ignored casts remain free by their native request policy. Current values use authoritative bounds/frozen membership; no missing characteristic defaults to free payment. Existing commit delivery sends actual actor stats with12873.

The payment caller is an explicit Wakemu server policy based on native cost/eligibility data. Original `fad.b(PN,int,PV)` constructs family1089 with a null caster, null PK/PL, UID−1, the signed requested delta and target bearer. Its `bbx` adds2246. The explicit paid-cast policy then binds the actual payer as caster through the source-proven `Qe.e(PV)` setter before replaying native post-phases3/4 before roots, for both normal and paid nested casts. This caller binding is Wakemu policy, not a recovered original caller. It is necessary for the real state4069 listener309165, whose authoritative metadata declares reversed subscription: Qe routes caster channel30, whereas the fresh null-caster constructor can only emit target channel3. The source descriptor includes the payer and policy identity; validation rejects cross-actor binding. It never mutates PA twice or packs Breeze as an eWf fourth resource. Original server call placement remains unavailable. When actual change is zero, native `mu(true)` suppresses only PR notification: `eZR.a` still calls `Qe.a`, which emits phases3/4. The helper preserves those events and emits no standalone PR notification. Source: `.runtime/combat-review-20261010/fad-breeze-events.txt`, original `eZR.a`/`Qe.a` bytecode.

### Deployment prerequisite

`native-spell-resource-costs.json` is a **required PostgreSQL catalog document** and is prewarmed. The implementation must not be deployed with an older active release lacking it. Export with `javac -proc:none -cp 'client/lib/*' -d .runtime/java sniffer/java/ExportNativeSpellResourceCosts.java`, then `java -Xmx384m -cp '.runtime/java:client/lib/*' ExportNativeSpellResourceCosts client OUTPUT_DIRECTORY/native-spell-resource-costs.json`. Use `server/tools/stage_spell_resource_cost_catalog.py` to clone an explicitly complete base revision, fencing the current active revision. It preserves every base document and adds only this document. Staging never activates the revision; activation and a complete checkout build must be coordinated by the main agent.

The fresh focused gate passed10 tests in18.938 seconds: four complete-cost selection/delta/payment tests, four native WP/Breeze dependency tests, and two actual Hupper runtime tests (four elemental subcases plus LIGHT5594). Actual5594 starts at source-derived Breeze500, pays200, damages its target, preserves the original source snapshot, rolls back source/RNG on a post-payment factory exception, and recovers200 through the real end-turn provider. Prior-class regression validation remains pending.

### Native WP/Breeze dependency

Original `eGj` registers `ffu(ffh)` on the WP4 PA. On maximum notification `ffg.sfY`, `ffu.a` calls Breeze111 `PA.or(50 + 75 * WP.effectiveMaximum)`. The former snapshot installed WP maximum6 without executing this native dependency, leaving Breeze maximum50 and making genuine200-cost spells unreachable. The new constructor binding applies to every snapshot containing both native characteristics, with no breed gate. Actual WP maximum setters refresh the same dependency; current setters preserve its hidden expandable raw current, frozen behavior, hard cap and preview/checkpoint primitives. Native proof is preserved in `.runtime/combat-review-20261010/eGj-resource-binding.txt` and `hupper-resource-constructors.txt`.

The complete inactive revision `3472243858e1e2fc715342a7ba70396d077344847570b2109a4f37326b7dcee5` preserves all7,483 documents from copied-flags base `879c0fcabd8e195869bff59f451605017b52666970643af8e1a912cb73ad6a51` and adds only the full resource-cost document (SHA256 `fb10cfe102215efac81153552aa112a3a92d95d91dff76e53fb036d754f827b0`). Staging completed successfully; the published revision remains unchanged. The actual5594 test now derives initial Breeze500 from the native WP maximum6 and exercises cost200, source/RNG rollback and actual end-turn recovery200. The focused10-test gate passed; coordinated prior-class regression validation and deployment remain pending.


## Consolidated acceptance status

| Surface | Evidence | Status |
|---|---|---|
| Full class data and dependency inventory | Published PG revision;44 own spells,3 derived grants,1,549 effects,50 states,6 areas; no missing referenced dependency in the declared traversal | Inventoried, not a functional percentage |
| Four elemental attacks and matching runes | Actual5562/5564/5567/5570 transactions | Automated pass |
| Breeze capacity follows WP maximum | Native `eGj`/`ffu`; constructor, maximum writers, raw/frozen/bounds/preview tests | Automated pass |
| Signed full resource payment |4,143 original spell tables; actual5594, atomic failure and native end-turn recovery | Automated pass |
| Grant bar, Heart of Fire, strongest-mastery LIGHT behavior, remaining utility/passive combinations | Source paths recorded above | Manual battery pending; not certified by the focused tests |
| Breeze-special trigger2246 | Original fad source and Qe.e payer-binding policy; strict source admission, normal/nested boundary; actual5594 activates state4069 listener309165 | Automated pass (4-test Hupper/Breeze gate) |
| Prior Cra/Iop/shared resource regressions | Existing suites, new full-cost PG scope required | Pending main-agent gate |
| Deployment | Full inactive347224… release staged, no activation performed by this agent | Pending coordinated complete build |

The isolated shared casting API fixtures now supply complete resource-cost authority: the same55-test gate passed with no failures, errors or skips. This repairs test data without weakening missing-authority production guards.

The post-binding Hupper/Breeze gate passed4/4 in16.332 seconds against inactive complete347224…: both helper tests and both actual Hupper runtime tests, including real309165 activation during5594. Log: `.runtime/three-class-review-20261010/hupper-breeze-rev3472-caster-bound.log`. Failed payment/source-RNG rollback remains covered by the existing resource-cost and actual5594 tests; a broad updated prior-class gate is still required before deployment.

## Bounded full active/passive runtime matrix

`server/tools/audit_huppermage_normal_casts.py` reuses `NormalCastAudit` and the production Ready/owned-turn/transaction/commit path. At level200, it equips all26 own active spells in legal12-slot chunks, first with no optional passive and then separately with each of18 own legal passives:57 initialized decks and494 normal active observations. Current owned Ready grants are also discovered by actual UID and attempted; they are not inserted into the deck manually. Every cast uses an independent actual-turn preview, bounded64-candidate native eligibility search, one eligible target and unchanged native resource budgets. No target found in this bounded context is distinguished from an actual transaction failure; neither proves a spell can never run.

The process pins complete PostgreSQL revision347224… without activation, disables cyclic GC for this bounded catalog process and exits after writing its report. The audit LOS callback now reads the provided owned character map source rather than a nonexistent Fight.map_id. This is an audit fixture repair, with no production eligibility relaxation.

Temporary abilities5573/5574/5578 originate in actual649 definitions254521/347912/349779 and are guarded by absence of933 and instance!=862. The report records actual Ready-grant attempts and post-commit grant/state ledgers. Availability or one successful cast alone does not certify every conditional removal/reconnect branch. The full bounded matrix completed; results and qualifications follow. No complete-class success claim is made.

### Matrix outcome and source qualification

All57 decks reached native Ready. Of494 ordinary active observations,418 prepared and committed (22 active spells across all19 baseline/passive variants);76 had no eligible nominal context (four active spells across19 variants). There were **zero actual effect-transaction failures**. All18 own optional passives initialized legally. This does not certify every passive reaction, combination or combat state.

| Nominal context not reached | Source requirement | Interpretation |
|---|---|---|
|5566 Vestigio|`not IsTargetCellFree() or IsOwnSpecificArea(1049)` plus native range/target rules|The nominal actor/area layout supplied no legal target; not a failed effect execution.|
|5577 Principio Valere|Rune5371/5372/5373/5374; rune-specific occupied/free/area-distance/carry branches|Needs an actual acquired rune and matching target context.|
|7754 Visio Imperum|Rune5371/5372/5373/5374 with target-state exclusions|Needs an actual acquired rune.|
|7809|`GetStateLevel(4064)+...+GetStateLevel(4067) >= -2`|Native absent-state levels make the fresh no-rune baseline ineligible.|
|5573/5574/5578 Ready grants|Runic marker5371–5374, corresponding rune and/or own area1049 criteria|All171 fresh-baseline grant attempts correctly remained context-gated.|

A subsequent **actual source sequence passed1/1 with three grant subcases**: ordinary5562 creates rune4064 and marker5371, then each actual Ready-granted UID executes independently.5573 enters Heart4121,5574 creates glyph1049,5578 applies7774. No state/resource/UID is fabricated. Log: `.runtime/three-class-review-20261010/hupper-rune-unlocks-grants-rev3472.log` (33.627 seconds).

The raw matrix report retains `source_stable=false`, `ready_gate_passed=false` and `deployment_gate_passed=false`: admin_domain.py/admin_http.py changed and admin_actions.py/admin_map_catalog.py/admin_profiler.py appeared during the run. All391 recorded combat paths have identical before/after hashes. The audited combat/domain/tool/fixture paths contain no references to those admin modules. These results are scoped combat evidence, **not a relabeled whole-checkout readiness gate**. No global freeze or redundant matrix rerun is requested solely for unrelated admin edits.

Machine summary: `huppermage-runtime-matrix-20261010.json`; raw report `.runtime/three-class-review-20261010/hupper-normal-passive-matrix-rev3472.json`, SHA256 `c925ffe20ee48e0c0c1a5fd1aced6b23f9ccbdd8a5b03b5aa000f635db1ad3d6`.

### Highest remaining mechanic risks

1. Heart4121 entry is now proved through actual5573. Its later natural-regeneration suppression, stored Breeze7791, inverse/removal and repeated-turn behavior need a complete sequence; entry alone does not prove the tooltip's full lifecycle.
2. Light strongest-mastery damage/healing, resistance selection and equal-mastery tie behavior need numeric multi-element acceptance beyond ordinary successful casts.
3. Area1049 creation is proved through a real rune/grant. Repeated creation, area-assisted target branches, movement/collision/LOS, timer removal and reconnect must be qualified as one lifecycle.
4. Every own passive initialized and the22 nominal active routes executed with each passive individually. Conditional incoming damage/healing, multi-passive combinations, rune conversion and boundary reactions remain distinct from that matrix.
5. The four no-context active spells now have legal source-backed rune follow-up transactions (below). Their alternative rune/target branches remain distinct from that evidence.

The final source-backed nominal-context follow-up passed1/1 with four subcases in23.719 seconds: a legal deck contains5562 plus5566/5577/7754/7809; an actual5562 cast acquires marker5371, then each remaining spell independently passes native eligibility and executes through its actual deck UID. Tests preserve the source snapshot and native costs (7809 is genuinely zero AP). Together with the bounded matrix, **all26 own active spell IDs now have legal transaction evidence** and all18 own passives have legal initialization/matrix evidence. This is not proof of every conditional effect, passive trigger or client visual. Log: `.runtime/three-class-review-20261010/hupper-nominal-active-contexts-rev3472.log`.
