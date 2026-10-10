# Sacrifice: actual owned-cast pipeline

The focused regression uses three real snapshot actors, actual native innates, map1134 QI/terrain, owned decks, real turn advancement and prepared spell transactions. Sacrier5044 targets an ally; hostile6266 subsequently targets that ally. No state is injected, and no world service or database write is involved.

Initial reproduction: the ordinary hit redirected damage to the Sacrier and the deferred1025 boundary swapped the two positions. The original transaction source remained unchanged. The low-HP cleanup regression failed: state89 remained after the protector crossed below10% HP. The explicit server selection policy below resolves this reproduced failure.

The failure is earlier than the cleanup runner. Child416708/family304 has SELF selector2 but receives the explicit ally PV from parent416705/family330. Current direct-PV handling bypasses the selector and places state4800 on the ally. Listener417169 consequently rebinds its caster to that ally. Its child417171/family321 has selector8320 and criterion `HasStateFromUser(89,"target")`; the ally's89 correctly records the Sacrier as its source, so that criterion fails under the incorrect rebound caster. State4800 itself is removed, leaving89 behind.

An original JVM probe, after loading5044, confirms direct-target definitions416708/416713/417171 have `aZX=false,cym=false`. eYg initializes target transmission `rFn=true`; absent fifth parameter leaves it true. Its actor child branch passes `bfs` to eVn.a. Qe.a skips area/selector recalculation for an explicit PV when PK.aZX is false. Therefore dropping all explicit group targets cannot be presented as an original client behavior correction. The server must distinguish its target-selection contract from client replay semantics; any additional policy needs to be explicit and shared, with regressions for intentional target transmission.

Evidence: `server/tests/test_sacrier_sacrifice_pipeline.py`; original JVM probe output `.runtime/sacrifice-native-target-probe.log`. Initial warm unit run:2tests,1pass,1failure. This reproduced defect is resolved below; it is not a complete Sacrier acceptance result.

## Explicit Wakemu server selection policy

The implementation now marks newly executed ordered-group children with `wakemu_fresh_child_selection`. For an explicit fcE relationship selector (self2, ally4/128, enemy8, exclude-self256), or an fcE in-area selector1 with a non-point area, the server calculates candidates using the exported selector and geometry before evaluating child criteria. A null selector or selector0/point1 retains the deliberately transmitted PV. Retained event replay and explicit PT calls clear the policy flag; their existing clone/target binding remains authoritative. The native aZX/cym catalog and client delivery are unchanged. This is a named server policy, not a claim that the original client has aZX=true.

An initial broader policy recalculated passthrough selector0 as every fighter and broke redirection. The relationship boundary is necessary: explicit target transmission remains part of the execution contract and cannot be globally discarded. Final validation results are recorded below once the focused shared regression batch completes.

## Focused validation

The final shared batch ran25tests in93.626s: both actual Sacrifice regressions passed, as did direct-target/resolver coverage, four actual Iop cast-boundary cases and all eight summon initialization cases. Two Columnata subcases failed an existing expectation that surviving enemy NPCs receive armor. The original child416131 selector8194 declares SELF, so those assertions require review: the corrected server relationship selection gives that armor to the Sacrier. No runtime rejection occurred in those cases. Log: `.runtime/sacrifice-policy-final-focused.log`. No services were restarted or code deployed.

The Cra beacon regression established that preserving all selector1 targets would also be incorrect: class999 crossRing1–4 groups must enumerate nearby occupants before their point damage children receive a selected PV. The server policy now distinguishes non-point areas from point selector1 transmission. All9 actual beacon/arrow pairs pass the real summon→hit→cleanup→negative-control matrix; see `cra-beacon-area-selection-regression-20261009.md`.
