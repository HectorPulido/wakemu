# Passive owned levels versus rank hypothesis — 2026-10-07

No native evidence found supports replacing every passive's owned level with rank0/1. The inspected installed client retains the supplied spellbook level and caps it at the spell definition maximum. The actual upstream server progression algorithm is unavailable here; therefore the current producer's character-level assignment is consistent with the inspected consumer, but is not independently certified as the original producer policy.

## Native and current-source evidence

- `owned_spell_records` supplies character level for every unlocked owned spell, and spell_inventory emits that exact signed-short level in sy records. Class initialization selects passive roots and effect parameter level using the effective character/deck level.
- All339 passive definitions across18classes have native maximum level245 in the current installed casting export. Maximum is therefore not a binary passive rank in this installed data.
- Native `fyG.e(yy)` reads yy.Yf and calls cr; fyG.cr only clamps to fyF.Fq. `bPO` constructor stores min(supplied level, Fq). No passive-specific conversion appears in these paths.
- Native GetSpellLevel (`eLo`) reads the selected owned fyG.cmZ. For player contexts it uses fzj.a, which reads the owned level and clamps to a nonnegative deck cap; only negative caps are uncapped. It does not convert to passive rank. Missing native spell returns0 under its documented branches; zero is not proof of rank0 ownership.
- Native bPO's availability display compares actor/deck level against bPK.cwe, the required unlock threshold. The inspected field cwt is UI order, not a proven rank-up threshold. UI availability treats a zero cap as character-level availability while fzj execution treats zero as an actual level cap. Never derive rank progression from these fields without further evidence.

A targeted native Java probe loads only definition6271, constructs real bPO instances, and records: maximum245, unlock75; supplied0→0,1→1,75→75,160→160,200→200,300→245. Private probe source/output: `/tmp/ProbePassiveOwnedLevel.java` and `/tmp/wakemu-passive-owned-level-native-proof.txt`.

The complete staged effect-criterion graph contains13 comparisons of GetSpellLevel to0/1. These are structural observations and can represent legacy or differently supplied levels; they do not establish a general producer rank contract. No GetSpellLevel criterion referencing6271 occurs in this staged effect graph, but the casting catalog for6285 has two conditional branches comparing6271 to0/1 and deck membership. These separate casting sources must be considered. Owned passive6271 belongs to breed15.

## Concrete general cap inconsistency

Native fzf.gvc is `tL < 0`, proven by bytecode and a real fzf Java probe for -1,0,1,100. Native fzj retains the owned level for negative caps and computes min(owned,cap) for zero/positive caps. NativeSpellBook incorrectly applied min for -1; this has been corrected generally. Zero cap is valid native execution level0, not uncapped. The separate UI availability path uses a positive cap or character level, matching current validate_deck availability behavior.

ClassInitialization.plan's effective0 calculation is therefore compatible with native execution, but its levels[effective-1] indexes the last exported level. The general native zero-level export now supplies fG(0) roots rather than substituting level1 or245. Class initialization selects this explicit table and validates root dependencies. Shared dispatcher parameter arithmetic already accepts signed-short level0. Missing zero contracts still reject explicitly instead of fabricating a positive-level fallback.

Command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python -m unittest test_combat_deck_cap_contract test_combat_spell_level test_spells`. Final result:22 tests PASS including cap contract, spell-level, spell inventory, casting-range and flag-merge modules. Six dedicated cap regressions cover negative/zero/positive lookup, zero-root initialization for all339 passives, conditional zero-level casting, and missing-zero-contract rejection. No binary passive rank normalization was introduced.

## Limits

This review is offline and read-only for production sources. It does not prove external producer progression, effect reachability, client acceptance, or that all passive branches are executable. Do not change all owned passive levels to0/1 to make a single comparison pass. Resolve the exact source reference and its actual native branch before proposing a progression conversion.

Source hashes at review time:

- `server/wakfu_server/characters/spells.py`: `e3ae19be1973ff1d2d9a8f3fd754aa3d0d1bb58dc9eaef82854588f70f8fdbe3`
- `server/wakfu_server/combat/combat_class_initialization.py`: `8323e779562089d924c8694db847a89aa73731beddcead56e69700a76e822859`
- `server/protocol/spells.json`: `290395dcd5ad392fe4eb62f6ac4fbe8d06c1d4b19302325ec94718b5e0269432`
- `server/protocol/native-spell-casting.json`: `86aa881d5ed9231baf5000b7cdcc9326591193aca0bf31699e35c3af2a7072ff`
- `client/lib/wakfu-client.jar`: `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`

## Complete class-scoped zero-level snapshot

`ExportNativeSpellLevelZero.java` reads the installed native client for the813 class/extra references from the verification ledger. It exports all813 native zero-level root tables and their13302 child-effect closure. All13302 effect definitions already exist in local class/granted/area catalogs; no zero-only effect definitions are missing. All469 unique zero-level passive root references are present in the class catalog. Native parameter values at level0 were compared with shared parameter_value for all13302 effects:0 mismatches. This verifies parameter arithmetic and structural dependencies, not every handler or lifecycle branch.

The same exporter captures baseline and651 conditional casting tables at level0: AP/MP/WP values, ranges, LOS/linear/free-cell/modifiable flags and categories. combat_native_spell_casting.definition now selects these explicit zero tables and uses its existing conditional/modifier algorithm. It does not index the last positive-level table, infer binary ranks, or widen the scope to monster spells.

The generated catalog is `server/protocol/native-class-spell-level-zero.json`. Private raw evidence and verification are under `.runtime/combat-review-20261007/level-zero/`. Source provenance hashes include every native classpath jar, bdata jar, the exporter, class-reference input, and local effect catalogs. The native probe snapshots were obtained offline; complete runtime/client behavior is not accredited.

Native reproduction command: compile `sniffer/java/ExportNativeSpellLevelZero.java` with JDK22 and `client/lib/*`, then run it with the private `class-references.txt` input and an output JSON path. No game connection is used.

Final changed-source hashes:

- `server/wakfu_server/combat/combat_class_initialization.py`: `e5185d357e3ca50c9965485285ff39655db48755b63587d852562a0795b0c3fb`
- `server/wakfu_server/combat/combat_spell_level.py`: `103f99e4020b8637bb5d0e59a49d013c0b199ab71c80d5f68c5468222641936e`
- `server/wakfu_server/combat/combat_native_spell_casting.py`: `e26074dd6d874f76f507b965885a1e5a4f6dd8680c427daed9caaca81b98eebd`
- `server/tests/test_combat_deck_cap_contract.py`: `fa4b823f28f4c98b3202c95925e55cd212a8c3e1811717a8d19991eaf62b3bf9`
- `sniffer/java/ExportNativeSpellLevelZero.java`: `1a8688deb5a14d2706d79ff4be77f47f0cee3c4d18fd2619ea0e94d811b78cfd`
- `server/protocol/native-class-spell-level-zero.json`: `9292b15537a4ea152ac299a5e71f8031043e67c290f0a0ad9c4f8e56d7844f02`

Native eligibility proof from fcO/ePI distinguishes mandatory empty-cell cwU from path-option cwN. The regenerated zero snapshot now uses free_cell=cwU and separately preserves path_option=cwN, diagonal=cwT, linear_path=cwV and allow_self=cwE in baseline and conditional tables. It also records fixed forbid_QI_P, raw cast criterion and whether a native criterion exists. Compared with the prior zero snapshot,21 baseline and13 conditional free_cell values change; all813 root tables and13302 effect records are identical. The positive-level bulk catalog/consumer are handled by the coordinated eligibility agent, avoiding duplicate catalog writers. The22-test result has no complete pre/post source manifest and is not a claim that concurrently edited sources were stable.

Regenerated zero snapshot source hashes:

- `sniffer/java/ExportNativeSpellLevelZero.java`: `f58c39ccba355707a3bdd9d9214b365b3ada8aadb642d227f777fa9324ed63c1`
- `server/protocol/native-class-spell-level-zero.json`: `70a491b7fc41213026e433ce181b0cd0c22dfc7399458100599d123619443670`
- `server/tests/test_combat_deck_cap_contract.py`: `61eb21a2bc3ca93ef94576d75f23498eac6dac76d435e4fc7ebacf9462c68fed`
