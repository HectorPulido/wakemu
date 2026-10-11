# Pending native monster scenarios

Historical classification below. The [current generalization investigation](BLOCKER_GENERALIZATION_20261010.md) corrects the casting-table diagnosis for 2603, resolves the resistance metadata guard and records the next shared dependency gaps.


Read-only classification of the original69-reference validation receipt:30 validated,39 pending. Of the pending references,21 require initial-state initialization. The remaining18 do not all represent missing test situations.

| References | Count | Observed blocker | Safe next step |
| --- | ---: | --- | --- |
|1710,2199,2203,2204,2227|5|State resistance mode outside proven class domain; several roots also require selectors/conditions|Export original NPC state resistance metadata; preserve unknown-domain guard|
|2603|1|Missing native NPC casting table|Recover authoritative table or prove absence; do not invent casting flags|
|2617|1|Healing spell2794 rejects enemy by range and self by selector|Replay wounded ally inside native ring; retain selector guard if cast center remains illegal|
|2778|1|Insufficient authoritative spell resources|Inspect native resource costs/stats and legitimate lifecycle setup; do not inflate AP/WP|
|2819|1|Missing matching native eYk definition/criterion presence|Export required summon/cell-group definition|
|3174|1|Reference cannot initialize a living local fighter|Determine whether this is an encounter actor rather than an ordinary living mob|
|3217|1|Native criterion parser rejects compound state/breed expression|Prove parser support and establish states through actual prior native actions|
|3949,3976,3980,3981,3982,3983,3984|7|Special-scenario casting criteria twV, with range rejections on other targets|Recover encounter/map requirements and native criterion inputs before making scenario claims|

`twI` means range rejection, `twE` means that every root selector rejected the target fighter, and `twV` covers criterion/target validation. These codes alone do not identify a missing ally or prove an engine bug.

## Replayable support preparation

`server/tools/monster_spell_scenarios.py` provides finite real turn advancement and an ordinary hostile NPC cast through `NativeProvider.commit`. The validator's optional `wounded_ally` fixture creates three fresh participants before snapshots/ready: the monster under test, a player ally, and an opposing native Tofu4. The attacker uses its real owned spell5790 and resources. Preparation succeeds only if the ally remains alive and actually loses HP. It then advances ordinary turn boundaries to the monster under test. No HP setter, artificial AP/WP, invented state, or selector override is used.

Successful targets record the recipe and observed preparation HP/packets. Commit smoke rebuilds the recipe and revalidates its own cast. Native commit randomness remains unchanged, so the recipe is replayable but exact preparation HP is not promised identical across runs. Each reconstruction must independently establish the precondition.

The scenario is attempted for healing capabilities only. It is a general harness extension, not a promise that Miaumiau blanco passes. Spell2794 has native range0–0, selector fcE129, and ring1–2 area roots64489/64488. The original self target was rejected by native casting eligibility. Adding wounded allies must not bypass that rejection; a remaining failure stays pending with the exact error.

Native initial-state receipts are copied from the constructor's `fight.native_npc_initialization_receipts` into successful targets and commit receipts. Absence of a receipt does not count as initialization proof. Main validation must compare the receipt's raw triples with source metadata before clearing initialization pending status.

Two lightweight lifecycle tests pass: `PYTHONPATH=server:server/tools .runtime/local/verification-venv/bin/python -m unittest discover -s server/tests -p test_monster_spell_scenarios.py`. Native catalog execution is pending a coordinated heavy-process window.
