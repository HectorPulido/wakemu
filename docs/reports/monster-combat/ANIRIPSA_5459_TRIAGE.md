# Aniripsa 5459: transmitted target duplication

The unchanged original `test_all_cunejo_actions_use_owned_turn_and_produce_semantic_effects` reported two upgraded-Cunejo subtest errors at ability 5459. Logging-only wrappers around the real dispatcher and healing calculation established that the live fight remains byte-for-byte snapshot-equivalent after each failed private preview. The player remains at 100 HP in the source fight while the private player reaches zero. This is not a source-state leak.

## Execution evidence

Effect 367978 is an actor group with selector mask zero, transmitted explicit PV, and actor rebind mode 2. The fresh-child resolver nevertheless enumerated both the Cunejo and player. Its two bindings run the same transfer group 367974 twice:

1. The unintended Cunejo-caster branch damages the player by 63 (100 to 37) and heals the already-full Cunejo.
2. The intended player-caster branch damages the player again (37 to zero), then attempts to heal the corpse. The existing corpse guard raises correctly.

Native level-200 parameters of damage 367979 are `[3, 0.3]`, producing 63. Transfer group 367974 uses 50%. With one intended branch, the player takes 63 and receives 32 healing, ending at 69: exactly the original unchanged assertion. Event accumulator effects between these actions do not re-enter group 367974; the duplicate actor binding precedes them.

Private evidence is in `.runtime/monster-local-unit-20261010/aniripsa-5459-source-trace.json` and its source-check log. The trace records invocation, effect definitions, HP before/after, and source snapshot equality. Two original runs each produced one test with two subtest errors; no return values or guards were overridden.

## Independent installed-client evidence

Fresh `javap -c -p` output from `client/lib/*` is retained privately as `aniripsa-native-Qe-eYg-eVy.txt` and `aniripsa-native-eVE.txt` in that directory. Qe.a at offsets 290–355 checks the transmitted PV and PK.aZX: a non-null PV with aZX false reaches Qe.g. Qe.g uses `Collections.singletonList` at offset 7. eYg forwards the current bfs to the child when rFn is true (offsets 140–150), and rebind mode rFo=2 swaps bfr/bfs (offsets 74–89 in fPP). These contracts support preserving a transmitted singleton instead of running null-PV target enumeration. A read-only receipt of the active native direct-target document confirms effect 367978 is `[330, false, false]` (aZX recalculation false). The document contains 178,337 effect rows and SHA-256 `a5f2d533e80c27a20cfd1d8c9ce8acd09381682203ba1e3e3b4fea4291fd0af2`; the private receipt is `aniripsa-native-policy-receipt.json`.

## Minimal correction and retained discrepancy

The authorized production change adds `not invocation.native_explicit_target` only to the fresh actor-group mask-zero enumeration branch. Relationship masks, area selection, and corpse guards are unchanged. A separate new regression checks both transmitted singleton PV and absent-PV enumeration.

The pre-existing resolver unit `test_fresh_zero_mask_enumerates_candidates_but_replay_keeps_explicit_pv` asserts the opposite fresh explicit-PV behavior. Its body and expectations are preserved as an explicit discrepancy for review; it has not been rewritten to conceal the behavior change. Read-only validation completed using `.runtime/local/verification-venv/bin/python .runtime/monster-failure-triage-20261010/run_selected.py test_combat_effect_resolver test_combat_direct_target test_aniripsa_grant_summon_pipeline.AniripsaGrantSummonPipelineTests.test_all_cunejo_actions_use_owned_turn_and_produce_semantic_effects`. PostgreSQL was transaction-read-only and Redis was disabled in process. The original Aniripsa test passed all dark/upgraded/ability subtests, including both upgraded 5459 cases and their unchanged HP-69/state assertions. The new explicit/null-PV regression passed.

The run reported 37 test executions in 18.334 seconds: 35 passed, two failed, zero errors. Both failures are the same preserved contradictory resolver assertion, loaded twice because `test_combat_direct_target` imports `NativeResolverTests`. The original failure expects `[1, 2, 3]` for explicit PV while the corrected resolver returns `[3]`. This is not a green full resolver suite. Complete output is retained privately as `aniripsa-minimal-fix-validation.log`. No existing test expectation was changed. Broader class validation is still required before deployment.
