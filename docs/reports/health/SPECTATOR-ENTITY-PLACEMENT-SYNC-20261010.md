# Existing summon and placement synchronization

After r62, live observer actions and marker removal worked, but acceptance found two remaining presentation defects: a late observer did not see an already summoned entity (fight 127, 02:12 UTC), and an early observer retained the player's old placement position (fight 126, 02:04 UTC). These are distinct from the retained-container failure fixed in r62; the new window had no corresponding snapshot rejection.

## Native entity construction

Installed client bytecode establishes the native bootstrap path: `bvT.a(cva)` calls `buK`, whose roster construction resolves each identity through `bio.jv`. An absent entity is skipped before its roster stat snapshot can construct anything. Thus listing an existing summon in `cva.participants` is necessary but insufficient for a client that never received its creation descriptor.

Fight 127's checkpoint contains the authoritative creation delivery for summon 50: opcode 12613 and a 220-byte payload. Spectator snapshots now reuse the exact recorded creation descriptors, flush their native action batch, then restore current actor effects and stats. This follows the established owned-reconnect approach and does not execute the server gameplay dispatcher or allocate new actor identities. Retained snapshot application is also terminated with a native action flush. Missing creation evidence still rejects the snapshot.

## Placement and action publication

The shared placement branch (`12806`) already commits and drains an authoritative `13652` position batch. The spectator public-event filter omitted that opcode, so the owner moved while an existing observer retained the old cell. The filter now preserves 13652. It also preserves native action flush 13420, which the installed client `cjk` registers through `cjn` and `cjq` routes to `aUb.Ac`. Filtering away a queue boundary is not safe even when the preceding effect/movement packets are public.

The observer's lack of placement selection tiles is a separate native UI policy: `bvT.j` explicitly sets `isInFightPlacement=false` and `isFightSpectator=true`. No team membership or placement authority is fabricated to change that policy. The reported position divergence is addressed by forwarding the authoritative position updates, not by changing selection tiles or team colors.

## Verification

The final focused suite ran 115 tests: 100 passed and 15 database-isolation cases were skipped. Regression coverage includes creation descriptor → flush → current effect/stat ordering; placement position and action flush preservation with recipient deduplication; the real shared drain function sending 13652 through the actual public-event filter to spectator publication; and linkage of the unchanged 12806 branch to that drain. The branch linkage is inspected through AST; the entire placement request branch is not executed by that particular test.

Manual acceptance must confirm both early placement movement and a late join after summon creation. Subsequent movement, spells and summons must remain visible, and observer activity must not block participant turns or receive participant rewards.

## Deployment and manual acceptance

Root deployed `wakemu-world:performance-20261009-r63` at approximately 21:50 America/Bogota. The complete image and running container match 674 current source/migration hashes. Health reports PostgreSQL available; both game TCP ports accept connections. Continuous profiling is enabled with a one-hour retention window. Backup image: `wakemu-world:backup-r62-before-entity-sync`.

Use two separate accounts on the same map and fresh encounters:

1. A starts a fight with a nearby monster; B observes before A presses Ready. A changes placement cells twice. B must see the same actor cell after each move. Hidden observer selection tiles are native UI behavior and are not the acceptance condition.
2. Start the fight and create a summon using the character's normal summon spell. B must see its creation and subsequent actions. Confirm turns continue without a multi-second or minute-long stall.
3. Finish and start another fight. A creates a summon before B observes. B must see the existing summon immediately upon entry, its current position and later actions.
4. Finish or surrender; the marker must disappear, both clients must return and move normally, and B must receive no participant rewards.

Record the local time of any stale actor, missing summon, or slow action. Profiler data is collected continuously; no manual capture command is required. Latency remains open until measured under fresh live combat. Ecology lock scope and repeated actor metadata construction are documented follow-ups, not changes in this release.
