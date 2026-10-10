# Native copied-characteristic event clones

The captured Tofu summon rejected on 2026-10-10 while applying effect326970 (family400). That effect was the event source, not an unsupported runner. A continuation using the actual capture07 roster reproduced the failure: a newly applied family1001 clone (reference326925, UID304, manager292) was stored as a fresh retained stat. Subsequent replay therefore found a subscribed PK without a listener descriptor. The transaction rolled back; the captured creature was not consumed.

The original `Qe.k(Qe)` clones the retained listener, sets its actual actors, prepares/executes it, and decrements the original listener. It does not perform `Qf.p` on the event clone. Fresh insertion belongs to `Qe.d(Collection)` instead. Original `eWZ.c(Qe,boolean)` applies `PA.or(ddL)` followed by `PA.on(aSg)` and leaves execution status unchanged.

`NativeCopyCharacteristicHandler` previously ignored the dispatcher-allocated clone UID, allocated another UID, and inserted that executed copy into `owned_stat_effects`. The dispatcher also failed to forward its allocated clone UID to family1001. The corrected dispatcher and general family1001 path use the supplied clone UID and original base UID, preserves original listener clocks and PL, replaces the calculated current/maximum additional fields, publishes an evaluated12613, and leaves the original listener as the sole retained subscription. Fresh applications and removal behavior retain their existing path. Unknown/mismatched listener sources still reject.

Evidence: `.runtime/combat-review-20261010/capture07-restored-diagnostic.json`; original bytecode `Qe.k`, `Qe.d`, `eWZ.c`. Regression assertions cover one clone UID, no second allocation or retained insertion, original listener survival, exact native ij fields, and unchanged current/maximum after removal. End-to-end continuation validation is recorded separately; no manual client acceptance is claimed here.

Validation: `test_combat_copy_characteristic` and `test_combat_event_replay` passed 17/17, including a permanent real-dispatcher activation handoff regression. The existing captured-roster continuation then completed checkpoint restore, native324 construction and owned ability7359 attack (`actual_capture_checkpoint_restore_summon_and_owned_attack_committed`). This reused capture07; no new capture, injected slots or production database writes were needed. This is automated runtime acceptance, not a manual client claim.

## Validation

The final focused suite passed 17 tests, including the permanent dispatcher
handoff regression. A continuation from the actual saved capture07 roster
completed restoration, family324 deployment and the creature-owned7359 attack
(12 damage, target HP12 to0); its checkpoint remained serializable. Artifact:
`.runtime/combat-review-20261010/capture07-restored-final.json`. This is a full
offline production-path continuation, not a live-client acceptance or deployment.
The original two live rejection traces were preserved in
`.runtime/osamodas-incident-20261010/tofu-summon-rejection-0615.jsonl`.

The expanded post-fix gate passed **138 tests, zero failures/errors/skips** in
121.942 seconds, including the prior four classes and shared replay/serialization.
Log: `.runtime/osamodas-incident-20261010/final-regression-native-replay.log`.
