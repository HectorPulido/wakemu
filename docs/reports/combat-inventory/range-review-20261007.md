# Native casting range review — 2026-10-07

Current status: the findings below describe the original inventory checkpoint. Conditional ordinary/granted selection, modifiable-range flags, live RANGE11, category modifiers and the property2 cap have since been implemented and verified by the shared native range oracle. The old statements that runtime/protocol data remain unchanged are historical, not current blockers. See `native-range-contract-20261007.md` and `native-range-ui-parity-20261007.md` for current calculation and UI serialization evidence.

Scope: offline code/catalog and installed-client bytecode audit. No Docker, running-client interaction, shared-code modifications, or restarts were performed for this review.

## Confirmed general mismatch

`server/wakfu_server/combat/combat_cast.py:167-174` loads baseline class spell tables, and `:193-200` compares Manhattan distance directly against their minimum/maximum. It does not select conditional range, LOS, linear, or free-cell tables for ordinary class spells. Conditional cost handling alone does not select those casting properties. The native table selector in `combat_native_spell_casting.definition` currently applies to granted spells only.

The installed bulk catalog contains 4,143 spell definitions, including 369 with conditional tables. Existing `sniffer/java/ExportNativeSpellCasting.java` exports baseline and conditional ranges, but omits the range-modification boolean `fyP.guk()` from both. Therefore the current bulk catalog cannot faithfully apply actor RANGE bonuses by itself.

Examples from `server/protocol/native-spell-casting.json`, level 1:

| Ocra spell | Baseline | With passive 6949 |
|---|---|---|
| 4813 | 4–9 | 6–11 |
| 4820 | 2–5 | 4–7 |
| 4816 | 2–4 | 4–6 |

Spell 4813 also conditionally removes LOS when state 7757 exists and state 7792 is at least level 30. Spell 4807 conditionally removes LOS with passive 6961. These conditions are already present in the native bulk export but ordinary class cast validation does not use them.

## Native dynamic calculation, confirmed with javap

Offline command: `javap -classpath 'client/lib/*' -c -p fyF`, similarly `fcj`, `eHl`, `ffw`.

`fyF.i(fyG,eGj,Object,Object)` selects the native conditional fyP, evaluates maximum at spell level, and adds the sum of `eHl.b(fyU)` for each spell category. `fyF.j(...)` selects conditional minimum without adding those modifiers.

`fcj.a(PV,boolean,int,int)` reads `ffw.sgK`, characteristic 11 (RANGE). It adds one when the actor implements eHH and `buX()` is true. If maximum >= 1 and the supplied modifiable-range flag is true, it computes `max(minimum, maximum + rangeBonus)` using native integer arithmetic. Afterwards native property `ffe.sdz` caps maximum to 1 when it exceeds 1. Names of these native predicates/properties should be verified before assigning English gameplay labels; their bytecode behavior is explicit.

The flag comes from selected `fyP.guk()` via `fyF.d(...)`. It is not safe to add RANGE to every spell. Negative bonuses, zero-range spells, category modifiers, conditional flags, and the property cap matter.

Actor characteristic 11 already exists in `native-actor-characteristics.json`. Player snapshot initialization obtains equipment/aptitude bonuses and installs authoritative `effect_stats`; use the live snapshot, not character inventory or a separate recomputation during casts.

## Bulk sources and current limitations

- `ExportNativeSpellCasting.java`: all installed aNr casting definitions and conditional tables; extend once to include all casting booleans, then regenerate the full catalog.
- `ExportSpellEffectTrees.java` plus `server/tools/convert_spell_effect_trees.py`: class effect trees and baseline ranges. Preserve them as effect-tree evidence, not a replacement for full casting-table selection.
- `ExportEquipmentEffects.java`: all aLO equipment effects with passive/action split, stat IDs and evaluated values. Its exception handler prints “Skipping” and continues; bulk completeness must capture and account for stderr failures.
- `ExportActorCharacteristics.java`: native characteristic definitions, bounds/defaults and NPC profiles.
- `ExportAptitudeRules.java`, `ExportAptitudeEffects.java`, `ExportEquipmentRules.java`, `ExportItemEquipmentConditions.java`: existing offline sources for aptitude/equipment mechanics. Validate ownership and equipped-sheet activation separately from static native data.

## General correction proposal

Use one native casting-table selector for ordinary and granted spells. Select the complete conditional table against authoritative deck/state context, then calculate effective range from live characteristic 11, complete category range-modifier ownership, native actor predicates, and fight-property snapshot. Export modifiable-range flags in baseline and every conditional table. Preserve fail-closed behavior for unknown context and transaction rollback; do not special-case Ocra or spell IDs.

Tests should compare Python with an offline native Java oracle across every exported casting definition and representative levels. Include passive 6949 on/off, state-dependent LOS, positive/negative RANGE, modifiable/unmodifiable flags, maximum zero, the minimum clamp, category modifiers, carried predicate, property cap, and boundary distances. Existing cast fixtures do not supply this full native contract and need explicit authoritative snapshots for relevant tests. Passing static catalog checks alone does not establish client/server UI agreement or gameplay effect completion.

## Complete offline range-flag import (staging only)

`sniffer/java/ExportNativeCastingRangeFlags.java` was compiled and run after the other bulk exporters completed. It imported flags for all 4,143 native references, including all 369 spells with conditional tables (800 rules). There are 684 modifiable baseline tables and 280 modifiable conditional rules.

`server/tools/merge_casting_range_flags.py` joins exact spell references and exact conditional criteria. Missing references, missing flags and duplicate criteria are fatal; no defaults are inserted. The output is restricted to `.runtime` and cannot overwrite either input. Four pure unit tests passed.

Merged staging artifact: `.runtime/combat-review-20261007/range-flags/native-spell-casting-with-range-flags.json`. Every nonflag field was compared with the existing native casting catalog and remained identical. The runtime/protocol catalog remains unchanged. This completes the data import for this flag, not the server range-calculation implementation.

SHA256 evidence:

- `server/protocol/native-spell-casting.json`: `918c692952e5a0de89bca774795b431dac2a1c0476440c25c4ab1b05f183018d`
- `.runtime/combat-review-20261007/range-flags/native-casting-range-flags.json`: `da07b5c51ec9fa71392578706b48ce367ba7c03329ab441a3f738cd129c4e72e`
- `.runtime/combat-review-20261007/range-flags/native-spell-casting-with-range-flags.json`: `86aa881d5ed9231baf5000b7cdcc9326591193aca0bf31699e35c3af2a7072ff`
