# Caster-based HP maximum: native family 250

## Source contract

The installed registry maps family 250 to `eWM(ffw.sgC)`. Calculation evaluates the percentage and two booleans through the actual level parameter evaluator. With an actual caster HP PA, amount is Java signed-int32 `percentage * casterEffectiveMaximum`, divided by 100 with truncation toward zero. A null or HP-absent caster leaves the existing running amount unchanged. This is not a percentage of the target's maximum.

Execution requires an actual target HP PA, otherwise native `mu(true)` marks nonexecution. It calls `PA.op(amount)` to change raw maximum. On the first application (`bbs()`), it records the actual raw maximum difference as running amount and the effective maximum difference as `rCn`. If the apply-current boolean is true, it calls `PA.nG(rCn)` and sets `rEj`.

Removal is guarded by `rEj`, **not by the third parameter**. The parsed third boolean `rCm` is serialized but is not read in `eWM.bbR()`. When reversal applies and current HP is positive, it subtracts `rCn`, substituting current minus one when the delta exceeds current; then it calls `PA.op(-runningAmount)`. Preserving these differences requires a separate handler rather than registering an HP alias of `eWN`.

The native additional-data fields are 31 (apply-current), 32 (third boolean), and 10 (effective maximum delta). Generic native lifecycle and source guards remain in force. There is no invented damage or KO-clock event.

## Reused implementation and actual area authority

`combat_caster_hp_maximum.py` reuses maximum-runner preparation and actual HP raw-current setters for ordinary registered/detached actors. Missing raw current or characteristic metadata rejects rather than reconstructing it from effective HP. Actual registered faW/fbd targets and casters use their validated Qq/PV resources.

`combat_area_hp_pa.py` separates immutable constructor receipts from an explicit mutable HP PA record. It preserves raw current, raw minimum/maximum, percentage, frozen state and effective values, with signed-int32 and hard-bound validation. Existing faW/fbd HP readers, current writers and damage snapshots consume this record. faW serialization and group PA lookup use the same current/effective maximum reader. The area remains a Qq PV and gains no fighter alias. Current-only writes preserve the maximum and reject inconsistent records. Constructor data remains unchanged. Unknown resource authority rejects.

The family is registered locally in the runtime, preparation/lifecycle and retained-removal dispatch. No active catalogs, databases or services were changed.

## Representative and evidence

Reference 5851 Neoespíritu merodeador (native monster level 100) has initial state triple `[9153, 1, 1]` and owned spell 8501. Its initial state subtree is 410295 → 330/304/315; the historical family closure also identifies extracted state effect 410294 as family 250 with parameters `[0, 15, 1, 0, 0, 0]`: the percentage scales with the actual effect/container level, not automatically with monster level. Other extracted family-250 states include fixed percentages 100/200/300/400/500 and a negative/scaling definition. Historical coverage mentions seven references; this does not qualify seven activations.

Installed Java probes are `next-family-runners/ProbeNativeMaximum250.java` and `ProbeNativeMaximum250Calculation.java` under `.runtime/monster-blocker-recovery-20261011`. Their outputs seal 64 application/removal cases (minima 0/17, current 20/80, four signed amounts, frozen/unfrozen and apply-current true/false), and 24 caster-calculation cases including int32 overflow and truncation. The tests intentionally keep remove-current false while confirming native reversal when apply-current is true.

Independent focused validation passed 38/38: five new tests, existing wall tests 10, faW HP integration four, zero-copy integration four, family-830 tests six, and existing maximum-resource tests nine. Receipt: `.runtime/monster-blocker-recovery-20261011/offline-family21-final250-area-tests.json` (the combined gate also contains 14 tests owned by the family-21 agent). No existing tests were edited. Real faW566 and fbd1063 tests exercise creation, caster/target PA lookup, application, damage snapshots, faW HP wire, reversal and rollback with preserved QI identity.

A final independent 12/12 incremental gate covers the new frozen-area/percentage regression and the family-830 event now reporting the actual PA writer result rather than a requested minimum. Receipt: `offline-frozen-area250-830-final-tests.json`; the unchanged 38-test gate was not repeated.

Current supported execution uses first-application owned runners. Native historical monster closure, full spell-book/initial-state replay and activation remain parent-owned qualification work; no readiness or deployment claim is made.
