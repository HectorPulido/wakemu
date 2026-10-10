# Late observer review — 2026-10-09

## Current acceptance

Hector reports that observers arriving after combat starts cannot see existing
summons/beacons and can become blocked. This remains open. Defeated mobs disappear
for everyone and observers receive no rewards; both behaviors are accepted.
Shared combat/rendition is owned by another investigation and was not changed.

## Deployed source verification

Read-only inspection found one healthy world container running
`wakemu-world:performance-20261009-r60`, created at 2026-10-09 19:31:52 -0500.
The previously reported r59 is no longer the current image.
SHA256 comparison found exact matches between checkout and `/app` for:

| File | SHA256 |
| --- | --- |
| `local_game_server.py` | `7facc5843b6848a23689172d3a5f68448689d5d005a404599852565dbfd0e655` |
| `wakfu_server/combat/combat_spectator_snapshot.py` | `bd08abb8d444840ce3f27187f9406cdf8a1687d677248346b2727f1e9c887884` |
| `wakfu_server/combat/combat_reconnect_snapshot.py` | `ac72e8aa802f8cd2cd3c0acb7731adb5cab8fd394d2b2d462c28872e2ba73452` |

No application code, services, or gameplay state were modified by this review.

## Real log correlation

Private evidence: `.runtime/local/logs/game-server.jsonl`; timestamps below are UTC.
The October 9 events contain 157 `combat_spectator_snapshot_rejected` records,
all with reason `Unverified native remote effect container absence` at review time.
Fight 114 provides a particularly relevant sequence on boot
`faa4761f4977427f85c14e36474f1238`:

| Time | Observed event |
| --- | --- |
| 22:23:56.455 | Snapshot rejected during spell request 13260. Its request state changes roster from two actors to three, adding actor 33. |
| 22:23:58.200 | Snapshot rejected during another spell request. Roster grows to four, adding actor 60. |
| 22:24:00.862 | Observer entry request 13413 starts. |
| 22:24:01.037 | Fresh snapshot rejected with the same remote-container error. |
| 22:24:01.038–01.046 | Server nevertheless sends bootstrap 12044 followed by 24 carrier packets 12613 and records `combat_spectator_entered`. |
| 22:24:02–22:26:00 | Snapshot rejection continues during turn progression, movement and spell requests. |
| 22:26:10.655 | Observer leaves. |

These records demonstrate admission after a failed refresh, using the previously
published snapshot. They also establish a correlation between roster additions,
snapshot failures and subsequent late entry. The compact request-state records
do not classify actors 33/60 by summon profile, so they must not be labeled as
specific beacons or species from this evidence alone. There is no exact user
timestamp tying this fight to Hector's latest report, and no correlated client
stack trace proving the precise freeze mechanism.

## Confirmed implementation gaps and cause certainty

1. **Stale snapshot admission: confirmed.** In `local_game_server.py`,
   `publish_spectator_state()` catches snapshot `ValueError` and returns without
   refreshing the registry. The 13413 handler then calls `SPECTATORS.enter()`
   anyway. Fight 114 proves this path occurred in a real session.
2. **Event loss on snapshot rejection: confirmed source path.** For an existing
   active fight, `spectator_snapshot()` is called before `publish_update()`.
   An exception prevents publication of that call's `event_packets`. This can
   leave an existing observer behind while participants continue. The logs prove
   repeated rejection, but socket-level completeness was not reconstructed here.
3. **Missing summon creation restoration: confirmed omission, visual cause
   candidate.** `current_snapshot()` serializes all actors and retained carriers
   but never reads `native_summon_creation_deliveries`. Owned reconnect already
   restores these actual native creation packets, then current actor snapshots.
   A roster entry alone has not been proven sufficient to reconstruct a summon
   in the native client. The same omission is present in the deployed image.
4. **Remote-effect rejection: confirmed upstream failure.** The error originates
   in `combat_remote_effects.py:161`: an entry does not establish container
   absence, or its payload still contains container fields 9/10. Determine the
   offending retained UID and original ownership before changing this validation.
   Do not remove the guard or fabricate missing metadata to make snapshots pass.
5. **Player-created persistent areas: unverified reconstruction.** `myK` comes
   from `environment_sections()`, which covers registered environmental glyph
   constructors, not every player-created persistent area. Audit native area
   constructors and retained ownership separately; missing player-area rendering
   was not reproduced automatically by this review.

## Proposed general correction

- Preserve authoritative remote-effect container ownership and include actor,
  retained UID and family in diagnostics for the failing absence check.
- Require successful current-snapshot publication before admitting a late
  observer; do not silently serve an old roster/timeline after a failed refresh.
- Keep public event delivery independent from refreshing the admission snapshot,
  with one committed revision boundary and no duplicate batches.
- Restore live summon/area constructors through their native presentation
  contracts, followed by current position, HP/resources and retained effects.
  Do not execute gameplay children again or replay combat from the beginning.
- Exclude retired entities and preserve read-only observers, participant ACK
  membership, rewards and the accepted world cleanup behavior.

## Automated and manual validation still required

No tests were executed by this read-only investigator. Delegate automated
verification to Luna. Existing spectator snapshot tests cover basic roster,
timeline, topology and retained carriers, but contain no summon/baliza creation
restoration regression.

Required coverage: enter after two summons exist; enter after a summon has moved
and lost HP; player-created persistent area; a retired summon must stay absent;
failed snapshot refresh must not admit a stale bootstrap or drop events for an
existing observer; deferred ACK-gap entry must receive the complete current
scene exactly once; snapshot generation must leave gameplay state unchanged.

After integrated automatic verification and deployment by the world owner, run
one complete two-client acceptance: A starts combat, creates a summon and a
beacon/area, moves or damages the summon, then B enters as observer. B must see
the current positions and HP immediately and subsequent actions live without a
freeze. A ends combat; both return, the mob disappears for both, B receives no
rewards, and both can continue playing. Do not request a repeat of the known
failure before there is a deployed correction to validate.
