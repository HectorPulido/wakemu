# Pandawa and Ecaflip final technical and manual acceptance

## Status contract

This record closes remaining technical checks before the user performs manual acceptance. It does not certify unexecuted client visuals, real sockets or every multiplayer combination. The provisional register remains 10/18 until the user accepts these classes.

The reproducible class gate loads every `test_combat_pandawa*.py` and `test_ecaflip*.py` module with native runtime opt-ins. Results must record the complete PostgreSQL revision, source hashes, failures, errors and skips. Prior-class and shared combat gates must be rerun after any shared production correction. NPC-owned failures remain excluded at the user's request.

## Complete manual procedure

Use the [Pandawa full battery](pandawa-manual-acceptance-20261010.md) and [Ecaflip full battery](ecaflip-manual-acceptance-20261010.md) as the spell/passive checklists. Execute this common sequence for each class:

1. Outside combat, use `!nivel 200` on the test character if needed, then return to character selection and select it again. The command raises levels only; reselecting refreshes spells and characteristic points. Use the normal deck editor for active spells and passives. Start without equipment or optional passives for baseline comparisons.
2. First run a friendly challenge with both characters connected. Ready both clients. Confirm the same roster and first actor, correct character-owned action bars and usable movement/casts during both first turns.
3. Run the entire class-specific checklist, rotating passives outside combat. Check real HP, armor, state levels, positions and AP/MP/WP alongside the tooltip. Use durable opponents for multi-turn thresholds; a dead opponent cannot demonstrate a later nonlethal callback.
4. For a weak single-enemy PvM control outside a dungeon, `!mob 4 8 1` creates one native profile4 level8 monster. The command is deliberately rejected inside an active dungeon room. Use ordinary durable encounters for complete level200 tests.
5. During a multiplayer PvM fight, kill a monster or summon, move through its vacated cell and cast through the cleared line of sight. Only the correct actor must disappear. Both clients must continue taking turns.
6. Reconnect one character mid-fight. Verify the complete roster, summons, states, current actor and owned spells on both clients. Finish normally, then repeat a separate fight with surrender. No stale swords, empty bar, frozen timer or disconnection should remain.
7. Finish a dungeon room with both clients connected. Confirm both reach the next room and see its monsters and join markers without reconnecting.
8. Run short Cra beacon activation/Desbalizaje and Iop combo controls. For the Iop, Borrasca → Borrasca → Uppercut must prepare the next Jabs; Jabs consumes that preparation. Existing class behavior must remain intact.

Record any failure with character, equipped passives, spell, turn, target cell, visible AP/MP/WP, exact message and local time. Keep the fight open when practical for log correlation.

## Deployment prerequisite

Local test success and live deployment are separate evidence. Before the manual run, identify the deployed image and catalog revision, and verify all required shared production files match the qualified checkout. If a rebuild is needed, build the complete current checkout and preserve concurrent changes; use the existing single world container. The copied-book metadata correction is staged separately and must not be described as active until its release is actually selected.

## Final automatic result

The frozen combined gate passed **182 tests across 51 modules, with zero failures, errors or skips**, in313.214 seconds. It includes all32 Pandawa/Ecaflip modules, the21-test summon/property module, Aniripsa, casting/LOS, Heart Blood, original-controller/wall areas, and shared pre-end/death/ACK/recovery scenarios. Catalog revision: `13c8122abba26ca40757c48df137540a5f0e6defdc6676cde6fd19ac6b84b33d`.

Private execution evidence: `.runtime/full-regression-20261010/final-frozen.log`. Before/after manifests `final-frozen-before.sha256` and `final-frozen-after.sha256` are identical across combat and test Python sources. Earlier mixed-source/nonterminal attempts are superseded by this run.

Pandawa's5152 case exposed an actual general provider defect: registered summons returned constructor properties instead of their current native property counters/set. `combat_summon.py` now returns the validated current snapshot; overlapping application/removal, isolated preview rollback and inconsistent snapshot rejection are covered alongside actual barrel LOS. Local file SHA256: `a60ba7fb5a1e0531e73f077d80e7dac63cfb13dad7b4335be2713575d9698892`.

Pandawa4725 nearby recipients,8600 constructor restriction/actual expiry/repeated restriction and nearby ally/enemy recipients, and the2223/417331 restoration path pass. Ecaflip7957 positive dodge,7958 actual equipped critical excess and5250 exact draw candidates/weights plus real-turn exclusions pass. Disabled native branches stay disabled. Ecaflip7959 remains an attested source marker without an invented downstream effect; this source limit is explicitly documented.

Both classes are technically prepared for manual acceptance at this scoped level. This does not certify the complete repository: the separately tracked Xelor sphere test still observes14 areas against15 expected, and broad discovery has unrelated unresolved failures. NPC investigation belongs to the separate owner.

The user requests one coordinated class/monster deployment. Shared handoff: `.runtime/combat-joint-release-20261010/README.md`. No service restart or activation by this class workstream is claimed yet. A live read before deployment still returned the previous summon provider hash `1ac72b92569d2dce0f456b6531ea599f7b9695ff2e543bd3e5c1228ecd97990b`.

## Joint deployment observed

The monster-spell owner subsequently deployed the complete shared implementation. World image `sha256:01f4e3318f541327b2cb8920a07ea4eb276779cc4ba699ebac3db95081b69e20` and AI image `sha256:175088b588d1f733e52faebe16d4711283ca4651b48db345efb182a602033c1f` are healthy against active release `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd`. A separate live read confirms the summon-property fix hash matches. Current-source comparison found zero differences across775 world and875 AI image source entries. Evidence: `.runtime/combat-joint-release-20261010/current-source-proof.json`; operator health/startup receipt: `.runtime/monster-remaining-20261010/deployment.json`.

The class owner did not perform a second restart. The same182-test gate passed again against this new active monster release:182/182, zero failures/errors/skips,274.879 seconds; combat/test hashes unchanged. Evidence: `.runtime/full-regression-20261010/final-active-548.log` and `active-548-before.sha256`/`active-548-after.sha256`. The separate821-row copied-book metadata fix was rebased without losing monster documents into inactive complete release `fab5f0a7b323af3a954b77a776f64bf0deefb9b5e2a3f804056fa629cce6f088`. This correction is not active; the stale43ede6 release must never replace the new monster release. These copied-book metadata limits remain separate from the Pandawa/Ecaflip ordinary class acceptance cases.

Inactive rebased copy-book runtime qualification passed5/5 without activation (`.runtime/full-regression-20261010/copybook-fab5.log`). Pandawa and Ecaflip are ready for the linked manual batteries on the active deployment. This is scoped technical acceptance, not a claim of a globally green discovery suite.
