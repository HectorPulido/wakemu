# Families332,333,334 native reconstruction

These families were structural dependencies of90,100,100 spells respectively
in the no-summon inventory. That dependency count does not establish actual
execution reachability. They are not spell grants or spell modifications.

## Family332: eZG protected kill

`eZG` extends `eZR`. `C(Qe)` is empty, `bbz/bbA` true, `bbB` false. A null
target calls `mu(true)` and returns. The actual `c` sequence is:

1. `PV.f(ffe.sdP)` adds NO_KO19.
2. `PV.f(ffe.sdJ)` adds NO_DEATH12.
3. `d(Qe,boolean)` publishes the normal runner notification.
4. HP `PA.aZg()` calls `on(aYW())`, the effective minimum.
5. KO_TIME_BEFORE_DEATH14 `PA.or(0)` writes the raw maximum with native clamps.

The property call is an addition: `eGj.f` invokes `eHN.c`, which invokes
`PB.c` signed-byte increment. It is not removal. `fff.aYW` is the minimum
from `bqF`; the maximum is `aYU` from `bqG` and its percentage. Thus this
runner does not restore HP or constitute a proved resurrection operation.
Its clone constructs a fresh eZG; the original prototype's bfB is set1.
There is no custom running-value codec, no C assignment and no custom removal
that reverses these property/resource mutations.

`ProbeNativeProtectedKill.java` executes real `eZG.c`, actual `PB` arithmetic
and actual `fff` setters. It passed512 cases, covering all256 signed-byte
initial property counts and both mutable/frozen HP. It verifies property
order19/12, byte wrap, HP minimum, KO maximum0 and runner value0. Initial
probe setup omitted raw maximum fields, producing an incorrect test fixture;
the final probe installs the explicit raw fields before calling native code.

`combat_protected_kill.py` models this sequence using the shared verified
kill resource snapshot/cancellation machinery. It never derives fdy status
or native dsA from HP. Its distinct owned event contains the exact source,
UID, minimum, before/after HP and resulting protection counts. The optional
QI verifier requires that event and both actual nonzero protection counters;
raw HP0 and later unrelated HP writes are rejected. The caller must separately
prove actual IN_PLAY membership. Five unit tests cover permanent removal,
frozen HP, independent status, counter wrap, missing authority and stale/raw
HP0 and all four lifecycle phases plus cancellation. The shared factory,
retention gate and central removal now route332 to this handler; automated
validation is delegated to the team's controlled offline snapshot. This is
not yet gameplay-complete: HP-based turn/result settlement must also preserve
source-proven protected IN_PLAY fighters, and QI requires the scoped producer.

## Families333 and334: carrying subsystem dependencies

334/eWB requires actual eHH target and eHG caster. It checks actual native
carry properties, eHg affiliations and effect flag before calling eHG.a(eHH).
The base eGj implementation checks carrier/carried relations and height,
sets pGV/pGW reciprocally, disables the carried QK's QL indexing through
QI.a(QK,false), moves it to the carrier's coordinates and invokes bpP.
Client big overrides also perform animation work; those visual callbacks
are not server physics authority.

333/eZE requires an actual carrying caster (frA) and its actual fry target.
It stores its destination and private qcl parameter, supports replay codecs,
and follows branches involving QI placement, actual carried QK participation
and eHJ movement hooks. A complete producer must preserve reciprocal
carrier/carried identity, carried position during carrier movement, QK slots,
QL byte insertion/removal history, indexing flags and actual release order.
The existing current_registry deliberately rejects nonnull carrier fields;
merely adding two actor attributes would leave every later QI query broken.
Neither333 nor334 is registered by this work. No default carried relation,
guessed landing cell or per-spell workaround is introduced.

### Carry delivery and codec proof

`combat_carry_delivery.native_throw_additional` models the actual eZE codec:
AdditionalData ij field15 is the coordinate copied from `bft`, not private
`rDV`; field17 is explicit private `qcl`, including false. Replay `f(iN)`
reads field15 into rDV and17 into qcl only when AdditionalData is present.
`aWr()` clears rDV but does not reset qcl. These distinct fields must not
be conflated with a guessed destination selected by the server.

`native_carry_gate` models eWB's early type/property/affiliation guards. The
identities are CANNOT_BE_CARRIED70, STABILIZED11, enemy stabilization110,
ally stabilization111 and effect BYPASS_STABILIZATION_CHECKS36. Bypass36
does not bypass CANNOT_BE_CARRIED70 or actual type requirements. Remaining
height/relation eligibility belongs to the actual eHG.a(eHH) producer.

`ProbeNativeCarryDelivery.java` passed256 native eWB guard combinations and
exported six actual eZE codec byte sequences, including negative coordinates,
signed integer/short extremes and explicit false. Three focused Python tests
compare these bytes and the truth table; their execution is delegated.
Relationship/QI changes remain the carrying agent's separate producer scope.

The real shared-factory332 regression now installs explicit fresh synthetic
QI registration history, native fdy creation and exact property counters.
It targets the sole opposing fighter, then checks outside the outer effect
chain that HP0 preserves actual IN_PLAY, turn order, both teams and QI topology.
This catches the previous HP-only settlement bug rather than hiding it behind
another surviving teammate. The root agent owns the general status-based
settlement correction; this report does not duplicate that implementation.
