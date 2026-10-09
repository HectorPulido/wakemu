# Native dispel flag and null-target boundary

The normal-cast report rejected class-18 spell4694 at effect145261, family421,
for `Unaudited native dispel flags`. Its installed definition has flag3:
`DONT_DISPLAY_ZONE`. The original family421 runner is `eXe`, not `eXY`.

`eXe.c` first calls `mu(true)`, suppressing its own application notification.
It returns immediately when its definition, target PV or target Qf is null.
A null cell invocation therefore does not justify a missing-target exception
or removal from the caster's Qf. For a real target it snapshots selected effects
in Qf encounter order, then forces their removal. Existing exact-reference or
action-class matches precede the default protection filter; the default filter
still preserves protected/unremovable states, protected spells and unsupported
container types. None of those selection rules is changed by this correction.

The handler now validates explicit source flag semantics. Flag3 controls client
zone display and does not change server dispel selection. Flags20 (guild tag)
and24 (damage distance tag) are not read by `eXe.c/E`. Generic flags5/6 remain
owned by the actual Qe event lifecycle; they are accepted only with that producer.
Other or malformed flag sets remain explicit errors rather than being silently
ignored. Enumeration IDs are taken from `eVl.fLK`, not its ordinal positions.

Production factory421 now prepares a fresh source runner and delivers the shared
L1/L2/L3/L4 phases. Original inherited `eZR.C` and
`Qe.a(int,float,boolean)` are both no-ops: this runner's fresh zero amount remains
zero even when a listener requests a triggering-value modification. The running
UID is cancellable and removed from the
preparation cache before application. `mu(true)` still means no extra421
application packet is manufactured; actual selected-effect removals retain
their existing source-backed packets and ordering.

New regressions use the actual145261 definition, verify that null PV returns
before any Qf lookup or mutation, retain unknown-flag rejection, and exercise
source-runner phase/cancellation behavior. Source compilation passed; serial
validation passed all11 tests in snapshot `luna-disjunction-421-fixed-02`.
The focused class18 spell4694 replay passed both Ready deck variants: each
committed the actual5 AP cost and completed effect145261 with its native null
target. Report SHA256:
`1934667b4f7503d26372f13170e144e8c09f6f0638d371168b38b3e16cd804bf`.
This verifies that route and the generic selection regressions; it does not
claim every protected-state or triggered dispel gameplay combination is complete.

The subsequent conditional75 report exposed a separate activation boundary.
`Qe.k` allocates its actual clone after eligibility, optionally runs `n(source)`,
and calls `dr([1,2])` before application. A subscription activation therefore
cannot require a fresh normal-cast preparation or replay L1/L2. The dispatcher
now forwards that allocated identity through an optional activation-preparation
hook;421 installs its source-proved zero amount under the same clone UID and
retains the preparation guard. Only L3/L4 are emitted by this activated runner.
Cancellation and application clear its transient cache. A new regression follows
actual308272 targeted removal of a retained400 effect; focused validation and
the two class6 conditional replays are pending.
