# Remaining Ecaflip passive runtime qualification

The test-only suite is `server/tests/test_ecaflip_remaining_passives_pipeline.py`.
It uses actual class initialization, legal owned/granted spell requests and the
production end-turn boundaries. It does not insert states or simulate events.

## Impacto Felino (5249)

The native class innate 6892 subscribes effect359218 to event1002. Child359219
requires the passive in the actual deck and an enemy at distance1, then applies
state7950 at level1. The state is a prerequisite of the conditional zero-AP
casting table for granted action7953; the marker itself is not a critical bonus.

The first delegated run passed all three conditions: passive plus adjacent enemy,
passive plus distant enemy, and adjacent enemy without the passive. It verified
actual359219 execution and the resulting level1/absent state respectively, while
preserving the input fight.

## Healing Streak (7954)

Effect359889 receives healing channel3/event1, excluding container type12.
Child359890 applies the level5 carrier8044. Its child371348 adds its actual level
to Racha3683. The allied Pulga Arcito fixture has several injured recipients, so
a single spell can legitimately deliver multiple five-point rewards. The test
counts actual successful359890 dispatches and compares the resulting Racha to
the identical no-passive spell, then verifies actual1037 removal through360623.
The strengthened delegated run passed: three actual359890 rewards produce a
15-point difference from the matched control, and1037 removes Racha.

## Tarot Felino (7955)

Actual card postcast1025 invokes374216, followed by the distance1..6 candidate
group374217. Child374218 is the native swap runner422;374219 applies property11.
The registered-fighter qualifier on374217 is fcE bit50, already handled by the
shared selector; it is not a new relationship selector.

The first delegated run reached all four children, but final actor positions did
not change. This is not accepted as completed behavior. The strengthened test
captures actual caster/target coordinates immediately before and after each
child to identify self-swaps, multiple swaps or an execution defect. It retains
the required position and property assertions and has not changed production.

## Shared cast-anchor correction

The failing Tarot route exposed inconsistent facts in the explicit Wakemu cast
boundary policy. The context captured the real cast distance, so the distance
criterion could pass, but a null-PV replay clone retained the listener's original
installation cell. Its cell-mode child consequently selected the caster and
performed a native successful self-swap, rather than targeting the cast cell.

The shared producer now captures validated targetXYZ and nullable targetPV ID.
The replay consumer uses that XYZ only when the event is an attested cast
boundary and the selected clone target is null. Actual actor-bound recipient
positions retain their original contract. This remains a named local server
policy: it does not claim recovery of the unavailable original external-event
producer, create a fake running-effect source, or modify native selectors.
Malformed or missing typed anchors reject explicitly. The runtime acceptance
now chooses a held card with an actual legal request targeting the opponent,
then compares real coordinate/property changes with the no-passive control.
Delegated final qualification passed: the actual enemy-targeted held-card cast
swaps actor positions and applies property11 with7955, while the identical
no-passive branch does neither. The four typed cast-boundary context tests also
passed. Across the serial runs, all three passive tests passed. No service was
restarted and no catalog was activated during this work.
