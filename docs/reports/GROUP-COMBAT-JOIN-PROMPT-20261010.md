# Native group combat join prompt

Source prepared on 2026-10-10. Not deployed or manually accepted.

## Native evidence

Read-only inspection of `client/lib/wakfu-client.jar` with `javap -c -p`:

- `cvh.d()` returns **13599**. `cvh.dp(byte[])` reads one Java long, exposed by `aXM()`.
- `ciu.b(laAa)` handles `cvh`, resolves that long in the world actor registry, formats `fight.join.request` with the actor's name, and opens the native `bLu` modal.
- Its callbacks create `coK(actorId, accepted)`. `coK.d()` returns **12197** and its body is a big-endian long followed by one boolean byte.
- The existing manual join request, `coU` **13241**, has the same body. The modal answer is decoded separately: refusal and timeout do nothing; acceptance becomes a normal 13241 join request with autoLock disabled. The original 13241 handler remains unchanged.

No client assets or capture-agent code were modified.

## Server behavior

After a complete PvE placement bootstrap, notify currently connected real members of the starter's party. Require the same map and instance, a live owned session, positive HP, no active fight, and a free cell on the starter's placement team. Same-account characters are excluded because their admission belongs to heroes. Nearby means at most 25 horizontal cells in either axis, an explicit local policy.

A prompt does not admit a character. Accepting uses the existing join transaction, including map/instance, live lease, phase, target ownership, team and capacity checks. Declining does not alter fight membership. Stale acceptance after placement ends is rejected normally.

## Validation

`PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_combat_party_prompt.py`: **10 passed**. Includes native packet shape, acceptance/refusal/timeout semantics and actual dispatcher normalization, online/current lease checks, distance and instance boundaries, dead/busy/excluded owners, locked/full/active fights, and failed delivery without admission. Shared-combat regression suites are delegated to the configured verification environment.

## Manual acceptance after deployment

1. Use two different accounts in one party, on the same map and instance, standing within 25 cells. Do not enable heroes for this probe.
2. Start a normal monster fight with account A. During placement, account B should receive the native invitation naming A.
3. Accept on B. B should enter the same placement, appear in the turn order when combat starts, and control their own turns. Finish combat normally.
4. Repeat and decline the invitation on B. B should remain outside; A should finish alone.
5. Repeat with B farther away or in another map/instance. B should receive no prompt.
6. Repeat and leave the invitation unanswered until A starts combat. A late acceptance must not add B or disrupt A's combat.

Final verification: `PYTHONPATH=server:server/tests python -m unittest test_combat_party_prompt test_combat_shared test_combat_shared_capacity` passed62/62 in the verification environment. Catalog reads used PostgreSQL fallback; test writes used isolated schemas in wakemu_migration_test. No deployment or restart performed.
