# Healing after lethal damage: proven guard nonexecution

Actual Ecaflip 2065 and 2072 transactions reached a lethal damage child and then effect 113987 (healing family 258). The previous handler raised `Native runner does not bypass actual corpse guard`, discarding the whole transaction. A proven native guard rejection is not incomplete authority.

Original `eZR.bbH` returns false for a registered off-play target when its native bypasses do not apply. Original `Qe.bbJ` calls `bbH`; on false it executes `aX(false)` and returns before L2. Its separate wrapped-target guard also returns without application. No exception is raised for these authoritative negative decisions.

The shared healing handler now calls the existing `runner_target_life_eligible` helper. A proven false result returns nonexecution; unknown status, absent runner policy and incomplete authority still raise. The helper and its existing bypass semantics are unchanged. Prepared execution has already emitted L1; the normal handler clears its prepared and modifier caches, returns false and emits neither L2 nor healing packets.

Timing nuance: the server stops before requesting healing arithmetic descriptors for an already rejected corpse. The original client may have calculated its fresh runner value before `bbJ`. No value is applied or published by this rejected branch; the server does not invent dead-target healing descriptors to reproduce unused arithmetic. This does not add revival behavior or change KO-bypass branches.

Four focused tests cover authoritative negative nonexecution without descriptors, prepared L1/cache cleanup, unknown runner policy and unknown HP0 status. Actual Ecaflip lethal transactions and cross-class regressions are delegated to the coordinated validator before a completion claim.
