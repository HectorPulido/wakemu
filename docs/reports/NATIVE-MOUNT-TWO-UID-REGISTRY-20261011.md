# Original-client two-UID mount registry audit — 2026-10-11

This offline oracle uses the installed original JARs without patching files,
attaching an agent, or controlling a running client. It does not call the
historical `NativePetStateRefresh` reconciliation helper.

## Exact scope

`sniffer/java/VerifyNativeMountUidIsolation.java` consumes fixtures produced by
current server serializers for two owned Dragopavo18682 units. Physical12471
insertion uses original `cxa.dp` and `fox.eM`;12470 removal uses `cwZ.dp`. Full
13078 registry snapshots use `cxC.dp`, `fpi.a`, `fox.y`, `kX/lz`, `fvN` and `fpd`.

The oracle supplies a minimal identity-only subclass of `fpC` because native
item definitions are normally installed by the game's content loader. Its
stack limit1 is a minimal unstacked-identity fixture, not an exhaustive native
item-definition export. It
certifies no item effects, graphics, equipment eligibility or full content
bootstrap. The actual native `fwt` mount model, pinned to read-only catalog metadata, uses definition76, gfx24, speed6,
health20, XP per level50 and maximum level50. Native lookup registries and
hydration implementations remain unmodified.

The scenarios are initialA0/B0, fedA100/B0, rejected-deleteA100/B0, successful
B deletion withA100 retained, and an independent A500/B0 level10 continuation.
The native `bIM.a` and `fph.a/aM` publication path is executed: the same owner
registry object retains its identity while its contents switch to the refreshed
UID instances. GET uses original `fpd.C`; `fpd.B` is REMOVE. Rejection/success are serializer snapshots supplied
to the original consumer, not newly executed database mutations. Each UID must
resolve independently with the expected XP/level. Physical decoder tests are
not execution of the complete game's actor/container dispatcher.

## Native panel and handler boundary

Original `fnR.f(fvH)` simply assigns a field. `fnR.a(wS)` and `fox.y(kX)` allocate
fresh native pet state during hydration. Original `bLK(fnR)` passes its initial
`fvH` to `bLE`; `bLE.kuu` is final. These facts alone do not establish a live GUI
bug: the complete handler may rebuild or rebind the selected panel.

Original13078 handler `chZ` hydrates `fpi.a`, publishes into `bIM`, refreshes via
`fph`, then calls `dbU.oV`. That last method conditionally synchronizes an open
build editor's registry. It does not by itself prove that the mount panel's
selected observer follows a replaced native pet object.

The genuine `bLK` constructor succeeds when the installed native-library path
is supplied. The panel is opened before registry updates; its retained original
pet remains XP0 while the published replacement is XP100. This is evidence of
that isolated observer lifetime, not evidence that the complete UI handler
fails to rebind the selected panel. It never substitutes a custom mount panel
or marks a missing UI context as passing. The complete original `chZ` handler now also executes with a genuine native
`aTJ` context and updates owner1's registry correctly. There is no selected mount
panel registered in the native UI manager, so this does not prove its rebind.
A genuine `biB(false)` actor/inventory constructs, but normal `aTx.f(actor)`
bootstrap stops at absent loaded breed definitions (`biB.dom()` returns null
before `bgZ.getName()`). Completing original content/actor bootstrap remains
required; no fake breed or custom replacement UI was installed.

Full physical handler `chK` additionally
requires `fkH` current actor lookup, a real `biB` inventory with container state,
and the native UI lifecycle. PET actor hydration and selected-panel rebinding
remain separate requirements unless explicitly exercised.

## Evidence and acceptance

Private reproducible fixtures, bytecode dumps, source hashes and terminal log
are under `.runtime/local/native-two-uid-mount-20261011/`. The final owner run exits0 and passes the stated decoder, registry, publication
and genuine panel-constructor assertions. Actual native `rw` also decodes the
server actor PET section with definition76/health20; that carrier has no UID/XP,
and the complete actor application path remains unexecuted. The final extension also passed independent Luna review and a sequential128MiB
rerun, including the complete original13078 handler. Earlier corrected
registry/panel-only evidence is superseded by this final receipt. The complete manual
journey remains the [complete systems acceptance](SYSTEMS-ACCEPTANCE-20261011.md), section17,
not a request for isolated user probes. No runtime fix is justified until the
full producer/consumer chain identifies a missing server action.


## Reproduction and superseded probes

```sh
javac -J-Xmx128m -proc:none -cp 'client/lib/*' -d .runtime/local/native-two-uid-mount-20261011 sniffer/java/VerifyNativeMountUidIsolation.java
java -Xmx128m -Djava.awt.headless=true -Djava.library.path="$PWD/client/natives" -cp '.runtime/local/native-two-uid-mount-20261011:client/lib/*' VerifyNativeMountUidIsolation .runtime/local/native-two-uid-mount-20261011/server-fixtures.json
```

Hashes of source, installed JAR, native library, fixtures and final terminal log
are in `oracle-evidence.json`; serializer and read-only catalog provenance are
in `fixture-provenance.json`. Both processes are bounded to128MiB Java heap and
run sequentially. No native files were modified.

Earlier probes are superseded: an initial minimal definition omitted stack
limit1; a subsequent isolated replay incorrectly used `fpd.B` as lookup, although
it removes entries. Neither is persistent-registry evidence. Final code uses
`fpd.C` for all lookups and exercises actual `bIM` publication. The initial GL
library error was resolved by the installed `client/natives` path; it is not a
remaining obstacle to this constructor. No server serialization defect or
live GUI defect was established, and no speculative runtime correction was made.

## Actual Store/PostgreSQL ownership regression

The dedicated `server/tests/test_mount_same_reference_isolation.py` passed
1/1 in1.953seconds against a fresh isolated schema with migrations1–143. Real
grant creates two separate reference18682 units. Actual feeding consumes two
18378 items and gives A100XP while B remains0XP. An inactive saved build protects
B from destruction with the complete inventory unchanged. After clearing that
reference with native `EMPTY_EQUIPMENT`, actual destruction removes only B.
Reopening the Store retains A100XP/revision1, the three remaining food items and
exactly one A feeding receipt; B's mount row is absent. Setup changes only test
character level and the native due-meal timestamp, with no XP, ownership or
deletion bypass. This proves durable owned transactions, not live transport or
selected-panel rendering. The log and scoped hashes are
`store-regression.log` and `store-regression-evidence.json` in the private
evidence directory above. No runtime implementation correction was needed.
