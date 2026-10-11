# Constructor area registration audit

This is an offline source audit, not an activation receipt. Existing active
monster catalogs and the frozen 721-reference candidate are unchanged.

## Zero-only dependency: reference 2431

Sistema de seguridad III requires original state effect 38688, family 447,
whose minimum and maximum native levels are both zero. The extraction retains
its complete original definition, but the active shared catalog omits it.
`supplement_zero_level_dependencies` now appends only required, absent, complete
zero-only definitions. It preserves their original bounds, sampled arrays and
metadata, and never overwrites a shared or already exported definition.

Focused verification: `PYTHONPATH=server:server/tools
.runtime/local/verification-venv/bin/python -m unittest
server.tests.test_monster_zero_level_dependency_import` passed all five tests.
The isolated candidate preparation has no completion manifest; its log ends
after exporting four spells and 35 effects. Native replay remains pending.
The current execution sandbox denies the database socket, so no database or
successful preparation receipt is inferred from these unit tests.

## Constructor-owned areas are distinct from Qs membership

Original bytecode witnesses are available locally in
`.runtime/monster-blocked-recovery-20261011/eYJ.javap` and `eYQ.javap`.

* `eYJ.c` constructs the `faN` using the actual target PV (offsets 37–101),
  calls inherited `d(Qe, boolean)` (104–107), then conditionally registers it
  through `PN.baf().a(Qq)` only when that Qs manager exists (110–135).
* `eYQ.c` constructs its area through `d(faV)` (23–25). When its context or
  `PN.baf()` is null it returns at offset 55, before inherited `d`, `bcT`, Qs
  registration and `mt` (56–87).
* `eYQ.d(faV)` retains the constructed area as `oAP` and may connect it back
  to the retained runner (offsets 108–149), even without Qs membership.
* Serialization retains the allocated area identity: `eYJ.b(iP)` writes
  `rGF` into additional data; `eYQ.b(iP)` also writes level, keep flag and
  optional orientation. Absence from Qs does not justify dropping this data.

The current Python handler places all constructed areas in the shared active
area dictionary and can register global PV membership and creation callbacks.
It also requires a roster-backed anchor for `faN`. Relaxing that anchor alone
would incorrectly expose constructor-private areas to normal combat.

A correct general solution needs explicit constructor-owned area storage and
separate membership/application state. It must preserve runner ownership,
allocated identities, serialization and removal without fabricating Qs,
geometry refresh, callbacks or event iteration. The retained-area removal
validator currently resolves areas from the shared active dictionary, so this
is not a safe isolated anchor-condition change.

Leave affected references blocked until that lifecycle is implemented and
verified with source-qualified constructor fixtures. Ordinary registered-area
behavior and strict area-authority checks remain unchanged.
