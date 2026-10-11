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

## Private-area prototype boundary

The first prototype deliberately tests the existing codec rather than changing
combat registration. `test_combat_constructor_private_area_codec.py` covers
serialization of an allocated area identity without any fight/Qs object,
preservation of original level/keep/orientation/status, and the distinct eYJ
additional-data layout. These tests require the project's catalog bootstrap
because importing the wire module eagerly loads the spell catalog. Their
initial standalone run encountered that environment requirement; this is not
a passing test receipt or a reason to fabricate catalog authority.

A proposed private record should reuse the complete constructed area row and
retain it on the owning runner, separate from `native_effect_areas` and global
PV collections. It needs explicit provenance `eYQ.c.PN.baf_null`, the actual
area and runner UIDs, original runner payload and construction status. It must
never imply Qs membership, callback execution, geometry refresh or `mt`.
Construction and later registration must be different transitions, with
checkpoint ownership preserving the private object and the owning runner.

Removal is an unresolved integration gate: `eYQ.bbR` checks non-null `oAP`,
false keep flag and `Ty`, then invokes `PN.baf().b(oAP)` without a null check
(offsets 21–34). Treating private-area removal as a harmless dictionary delete
would therefore invent behavior. Native retained status, context lifetime and
the actual removal entry point must be proved before introducing any such
transition. Pool reset `aWr` clears the private object; cloning `fQC` copies
the same `oAP` reference, which also rules out unconditional deep-copying as
an assumed native ownership model.

At this audit stage no private-area runtime model had been installed. The
source-qualified eYJ implementation below supersedes that boundary; generic
eYQ remains outside its scope.

## Actual Residuo representative correction

The sealed native definition resolves reference 5304 to initial state 6987,
level one. Its direct child effect 318679 is **family 338 / eYJ**, parameter
1649, native execution mode two, duration minus one and realtime zero.
The earlier generic eYQ warning does not establish an eYQ failure for this
specific chain. Private evidence is retained in
`constructor-private-area-5304-source.json`.

Crucially, `eYJ.bbR` differs from `eYQ.bbR`: it reads `PN.baf`, checks that
Qs is non-null, conditionally unregisters its `rGE`, then calls generic
`eZR.bbR` (offsets 7–30). An implementation scoped strictly to eYJ can
therefore preserve its owned retained runner while performing no area-manager
removal in the actual null-Qs constructor context. This must not be generalized
to eYQ. Generic `Ty` returns true for negative native turn duration through
`bbX`; it does not prove Qs membership.

The smallest proposed eYJ representation is a complete private area row nested
inside the existing owning `native_owned_area_effects` runner record, with
explicit constructor-null-Qs provenance. The ordinary owned runner payload and
Qf manager remain the existing authority. Global Qs, geometry refresh and
callbacks stay absent. Checkpoint validation must separately verify the nested
row's area UID, target anchor identity and provenance; replay must not promote
that row into global membership. The implementation below follows this scope.


## Scoped eYJ implementation and focused validation

The shared handler now has an early branch restricted to actual detached SELF
construction and eYJ338 with an actual prepared constructor and retained
execution context. It stores the private area inside the ordinary owning
runner record, retains the original eYJ payload/Qf registration and returns
before global area registration, geometry refresh or creation callbacks.
No eYQ315 behavior is generalized through this branch.

`validate_private_target_aura` verifies exact provenance, positive distinct
area/runner UIDs, SELF anchor identity and absence from active/retired global
areas. Retained population validation and removal invoke that verifier.
Removal preserves the ordinary retained-effect packet and skips Qs removal
only for the proven private eYJ case, matching its explicit native null guard.

Independent focused results: five creation/adjacent tests pass and eight
removal/adjacent tests pass. The original codec prototype's three tests also
pass after correcting its new test helper to distinguish raw protobuf tags
from field numbers. Production wire encoding was unchanged. A separate new
owned-record JSON roundtrip test checks private identity and dual-registration
rejection; this is not a claim of complete Fight checkpoint restore validation.

The actual `fight_checkpoint_store.snapshot(Fight)` recursively preserves the
nested private record and payload. A new test exercises that snapshot and JSON
roundtrip on a normal Fight fixture. Interrupted fights are aborted rather than
resumed, so timeline reconstruction is not an implemented product contract.
Actual reference 5304 native replay remains a qualification gate. No monster
has been activated through this offline work.
