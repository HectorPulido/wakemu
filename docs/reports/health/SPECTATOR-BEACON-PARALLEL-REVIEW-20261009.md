# Spectator and Cra beacon parallel review

Status: open. Read-only review of r58 live logs and current shared source; no
runtime edits, database writes, service operation, or optimization. Existing
incident timelines remain in `SPECTATOR-FREEZE-20261009.md` and
`BEACONS-LATE-SPECTATOR-20261009.md`. Current source is not automatically proof
of the exact deployed implementation: two combat files changed after the r58
build, as recorded in `EXTERNAL-PROFILER-20261009.md`.

## Findings and confidence

### Missing spectator entities: confirmed publication failure

`combat_spectator_snapshot.current_snapshot` serializes every current actor
before returning its bootstrap. `CombatSessionAdapter.actor_payload` delegates
active effects to `combat_remote_effects.active_actor_effects`. That function
requires explicit container presence and validates protobuf fields 9/10
against retained ownership. It raises the observed absence error if presence
is neither `True` nor `False`, or if an absent container still has either wire
field. The error does not distinguish these cases or identify the effect UID.

`local_game_server.publish_spectator_state` obtains this complete snapshot
before `SPECTATORS.publish_update`. An exception therefore prevents publication
of the new snapshot and associated event batch. The catch logs the error and
returns. This explains how the observer can retain an older player/monster
view while the authoritative fight already includes new beacons. It does not
prove which retained payload producer created the inconsistent row.

Do not remove validation, silently omit an effect, or fabricate a container.
The general repair must make producer ownership and its actual serialized
container agree. Diagnostic context should identify actor, retained UID,
effect class, presence value and wire fields, without dumping private payloads.
Validate constructor-state, owned-stat, group and area retained producers, then
test active join and update with their actual combined population.

### Request status: confirmed diagnostic misclassification

This is more precise than saying that a spell itself was rejected after commit.
`local_game_server.record` appends **any** event ending `_rejected` or `_failed`
to the active request's rejection list. `RequestTrace.finish` labels a request
`rejected` whenever that list is nonempty, even when the error was caught in
ancillary spectator publication and gameplay completed.

Fight 110, request `e97b813535e84f41a25a08e9d95eebf2`, ends at
21:30:39.711 UTC with this label and only a spectator-snapshot rejection.
Its before/after snapshots show Cra AP 7→5 and new actor 33 with HP 130 and
constructor state 7779. The next creation adds actor 60 with the same state.
This is confirmed committed gameplay, not evidence of rollback failure.

Proposed general repair: record authoritative gameplay outcome separately from
publication failures. A failed observer projection must remain visible as an
error, but must not turn a successfully committed cast into a gameplay rejection
or invite duplicate retries. This is a diagnostic correctness fix, not a
performance optimization.

### Beacon activation: confirmed separate functional failure; narrowed route

The two actors in fight 110 both have constructor state 7779, which the existing
native profile inventory maps to destruction beacon profile 3800. They are not
unidentified arbitrary additional actors.

The logs contain accepted casting diagnostics targeting actor 33. At
21:31:05 UTC, request `0e8c467067eb4e5fa8c2e306a34d1398` casts spell 4769.
Its ordinary damage leaf 351933 correctly skips the native criterion
`not HasStateFromUser(7778, "target") ...`: owned beacons are deliberately
excluded from direct damage. It reaches state application 350951 and the
reaction chain ending group 351932, family 999, level 2, state UID 90,
caster 6, target 33, cell (-244,-84,0). That group reports `no_effect` in
46.157 ms and no reaction damage child appears in this trace.

At 21:31:20 UTC, spell 4820 also targets actor 33. Ordinary damage leaves
352252/352253 skip the same owned-beacon condition, state application 352255
completes, and the reaction path reaches family 999 group 351951 with
`no_effect`. Both beacons stay at HP 130 and Jalató stays at HP 66 across the
reported attempts. Cra AP and its own class states do change.

Therefore this is not merely a spectator visual defect, nor proof that casting
never reached the beacon. Investigation is narrowed to reaction-state children,
family 999 target/area/level selection and actor rebinding/recipient eligibility.
The existing nine-pair/reuse test evidence does not close this live production
sequence. Do not force direct damage onto owned beacons or enable constructor
damage leaves with literal `False` criteria; those would change native rules.
Record selected child IDs, resolved recipients, transformed center, group level
and skip reasons for this exact route, then repair the shared selection contract
responsible. The precise erroneous selection step remains unproven.

### Temporary stall: confirmed duration; exact hot function still unproven

Fight 109 contains a 103.25-second cast interval. Its aggregate calling-thread
CPU counters strongly support substantial CPU work, but the first external
capture started after recovery. The capture covering fight 110 does not
establish another 103-second spell. Shared maxima shown later are cumulative.
The same snapshot correctness error recurs, but its final logged exception is
not proof that validation alone consumed the whole earlier interval.

Keep this issue open separately from the now-localized publication failure.
Do not attribute it to Redis/checkpoint, database locking or a deadlock without
an overlapping stack capture. No optimization is proposed or performed here.

## Exact combined acceptance after repair

Use two freshly relaunched clients: A is the existing Cra Npers, B observes from
another account. Start `!perfil reiniciar`, then `!perfil iniciar 120 waits`
before starting the fight. Record local time if anything pauses.

1. A starts a normal fight and presses Ready. Create a destruction beacon using
   its existing action; put an enemy in the native reaction area. B enters
   observation after creation. B must see the enemy, Cra and the existing beacon
   with correct location/owner, without replaying creation or consuming AP.
2. A targets that beacon with spell 4769, then repeat with a fresh beacon/fight
   and spell 4820. The matching reaction route must execute its native damage
   children and update the enemy's HP in both clients. Compare normal/critical
   variants; do not require a particular damage number without the actual build
   and enemy resistances. A beacon need not disappear merely because it reacts.
3. Create another beacon while B is already watching. Both clients must see the
   new actor and reaction. End a turn and verify the next turn proceeds normally.
4. During another turn send `!checkpoint`, then finish the enemy normally.
   Neither client should stall; defeated mobs disappear for both, and only A
   receives combat rewards. B must return to exploration cleanly.
5. Read `!perfil estado` after capture completion. Correlate logs with this
   interval, not previous cumulative maxima. Automated validation must assert
   retained container consistency, actor bootstrap completeness, reaction damage
   and separate gameplay/publication outcomes, including failure injection.

This review performed source/log inspection only; it claims no new test passes
or manual acceptance and does not close any of these four defects.
