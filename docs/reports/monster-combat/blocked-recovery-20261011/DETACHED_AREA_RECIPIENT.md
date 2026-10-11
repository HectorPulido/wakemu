# Actual detached SELF eYQ area creation

Historical representative5304 Residuo, cluster8 (5329,5342,4915,2120,1639,5075,4318) reported `Unregistered native eYQ actor recipient` during ordinary NPC initialization. This is a screening cluster, not a claimed recovered total.

Native `eYQ` bytecode was captured from the current client jar at `.runtime/monster-blocked-recovery-20261011/eYQ.javap`. Its constructor path feeds `bch()` directly into `fbm`, passing the actual creator PV and Sn identity; `bch` returns `bfr`. It does not demand authoritative fight-roster registration. The existing descriptor constructor producer supplies actual SELF via the scoped eZQ/PO boundary.

`combat_effect_area.py` now allows the exact `constructor_stat_context` recipient before taking the existing registered-area fallback. Configured actor/cell delivery flags remain enforced first. Source context guards remain enforced. Arbitrary unregistered recipients and a registered foreign caster targeting a detached actor remain rejected.

The area creator orientation also resolves the actual registered-or-detached caster. Previously the missing registered caster silently selected direction7 and the effect cell as geometry reference; constructor execution must preserve the actual actor direction/position. Target-aura registration restrictions were deliberately not relaxed: they have separate producer requirements and no equivalent demonstrated recovery case.

Five new focused regressions verify actual owner/direction/geometry, no roster insertion, unscoped recipient rejection without area/packet mutation, foreign-caster rejection, configured owner flags, and unverified execution context. Combined with10 existing area/codec tests,15 tests pass,0 failures/errors. Existing tests remain unchanged.

Command: `.runtime/local/verification-venv/bin/python .runtime/monster-blocked-recovery-20261011/run_area_tests.py`. Receipt and log: `area-tests.json`, `area-tests.log` in that runtime directory. PostgreSQL reads use read-only transactions; Redis writes disabled. No service/data mutation or deployment occurred. Actual eight-reference replay belongs to the coordinator.

The separate `Missing registered native area PV` error is not justification to weaken `combat_area_authority.area_guards`: that helper correctly enforces real Qq area ownership. `combat_state_handler._area_target_blocked` was identified as a suspect actor-to-area fallback when detached SELF is absent from the roster; coordinator notified so that file's owner can apply the actor resolver at the caller instead.
