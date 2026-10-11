# Generalizing pending monster blockers — 2026-10-10

This investigation evaluates reusable causes behind the 29 pending under-level-10 references. Two general corrections are implemented and validated offline. The active release remains `13c8122abba26ca40757c48df137540a5f0e6defdc6676cde6fd19ac6b84b33d`, with 40 enabled references. No catalog activation or service restart was performed for this investigation.

## Findings across the complete inventory

| Shared cause | References with the dependency | Statically covered references | Implementation status |
|---|---:|---:|---|
| Native spell maximum-level clamp omitted | 330 | 241 | Corrected in ordinary NPC ownership |
| NPC states outside the class resistance seed domain | 1,797 | 1,271 | Automatic authoritative export integrated into candidate preparation |
| Missing native cell-group/eYk metadata | 233 | 173 | Native import path identified; implementation pending |
| Missing effective summon ability profiles | 156 | 117 | Native profile dependency identified; implementation pending |

These populations overlap. They are dependency impact counts, not predicted activations. The resistance count includes every typed state dependency, including states that might not use chance/resistance in the encountered branch, and 264 references without owned spells. Summon counts sample original parameters at levels 1–200 and compare base, capture and copy catalogs; they do not certify runtime reachability or complete initialization.

## Case 1: Rata de Astrub and state resistance

Reference 1710 owns Mordisco Enfermizo (1013), applying state 283. Native execution rejected it with `Native state resistance mode outside proven class domain`. The implementation of the effect already existed: the missing element was the original `fyW.elk` value. The class-only seed inventory did not contain this NPC dependency. References 2199, 2203, 2204 and 2227 share this primary blocker.

[export_monster_state_resistance.py](../../../server/tools/export_monster_state_resistance.py) reuses `ExportNativeClassStateResistance.java` and the existing sealing helper. It checks the installed client and all 113 original binary archives against extraction provenance, checks unchanged inputs/exporter before and after execution, and validates six native level samples per state. Existing enum identity, class rows, explicit absences, provenance and seed metadata are preserved. Conflicting values or absence claims reject the import.

The complete inventory export found 2,600 additional state definitions and 190 explicit original null lookups outside the existing 945-ID domain. These are evidence, not globally published metadata. Candidate preparation automatically exports only the selected references' missing state dependencies; the six-reference experiment added four definitions with 24 native level checks. Validator and staging enforce append-only preservation of the shared document.

Rata de Astrub now passes every owned spell and real AI commit: the target loses HP, receives its native state, and the actor spends AP. Rol duende feliz (2204) also passes all four spell cases and real commit. Rol duende gruñón, tímido and astuto still require native target/scene conditions for spells 3117/3141. The resistance failure is resolved without bypassing those independent guards.

## Case 2: Shrederches and spell level normalization

The previous classification for 2603 was incorrect: spell 3799 has a casting table, but its native maximum is 1. Our ordinary NPC ownership resolved descriptor-relative `-1` to actor level 5 without the next native constructor step.

Native `bPD.a(ArrayList, short, eGj)` resolves `-1`; `bPO(bPK, short, long, eGj)` then assigns `(short)Math.min(requested, bPK.Fq())` at offsets 29–39. This matches the formula already used by class summons in `combat_summon_spellbook.fresh_action_book`.

`maps/monsters.native_abilities` now performs that clamp using the authoritative casting catalog before action ownership, costs and root selection. Explicit levels below the maximum, zero and other negative values are not raised or replaced with invented positive levels. Missing definitions and invalid maxima fail closed. Across the current inventory, 330 references and 647 distinct spells can request a level beyond their maximum. None of the 40 currently enabled references is in that population.

Shrederches now correctly requests spell level 1 and proceeds beyond casting selection. Its next failure is `Missing scoped native class summon ability profile`: effects 96363/96364/96365 summon profile 2612, absent from the effective base/capture/copy ability catalogs. This is a separate metadata dependency, not evidence that the clamp failed.

## Next reusable imports

The two remaining cell-group examples are Larva nutricia (2819) and Arakna menor hambrienta (5698). The native class graph exporter already preserves `effect.fKT()` null presence, `area_class` and `raw_parameters`; `import_class_cell_group_metadata.extract` produces the runtime format. Extend the exact NPC dependency closure and merge by effect reference, retaining all class entries. Do not infer criterion presence from empty criterion text. There are 275 missing definitions used by 233 references.

The summon example should reuse the existing native profile/book, initialization and dependency exporters for the exact profiles referenced by `eZl.C` parameter 0 (family 307). Import ability books together with their initial-state and effect dependencies; importing only a profile name or allowing an empty action book would not establish functional summons. Effective profile gaps affect 156 references and 176 distinct profiles; four references are strictly below level 10.

Scene/target failures require legitimate state-producing native actions and original encounter conditions. Resource failures require checking native costs and legitimate resource producers. Neither group is suitable for blanket condition disabling or resource inflation.

## Validation and deliverable

The six-reference experiment covers 24 actor-level/spell combinations. Effectful preview passes increased from 12 to 19. Rata de Astrub (1710) and Rol duende feliz (2204) pass every case and the real AI commit, including unchanged forecast source, injected serializer-failure rollback and preserved actor identities. Four references remain pending for the independent reasons above.

**250 selected class, shared-combat, activation and monster regressions pass**, with zero failures, errors or skips and native opt-in enabled. Complete runtime, test dependency and validator hashes remained stable between previews and commits. This investigation created two new test files and did not edit existing tests. The existing transaction test already differed from the previous release when this investigation captured its inputs; that external difference was retained and tested.

Finalization and staging dry-run both pass. The private inactive candidate contains 42 enabled policy entries: the existing 40 plus the two validated additions. It has not been staged for activation or deployed. Live inventory therefore continues to report 40 active and 29 pending.

Private evidence: `.runtime/monster-blocker-generalization-20261010/` contains `dependency-impact.json`, `resistance-impact.json`, `bPD-proof.txt`, `bPO-proof.txt`, `sealed-all/`, `candidate/`, `previews.json`, `validation.json`, `test-preservation.json`, `validated/` and `staging-dry-run.json`.

After a complete validated deployment of the matching candidate, the additional manual probes are `!mob 1710 3 1` and `!mob 2204 1 1`, following the [general acceptance sequence](MANUAL_PENDING_COHORT.md). Expect native damage/state/resource changes and normal turn completion. These commands are not a claim that the two references are already enabled on the current server.
