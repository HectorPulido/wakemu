# Spectator terminal world cleanup — 2026-10-09

## Live evidence

Hector accepts external sword location, joining and observation on r56. Rewards
belong only to the participant. After fight106 at map527/instance0, observer
character6 retains defeated NPC-1125899906865024 while participant character4
does not. This is a world presentation defect, not reward eligibility.

Local captures `2026-10-09T19-41-13.468160Z-938e38eb` (A) and
`2026-10-09T19-41-28.460678Z-87dc6043` (B) show:

- B registers observation13413 at19:44:30.053991Z.
- B receives two normal12238 packets at19:45:08.004053Z and19:45:08.004446Z,
  same fight106, different native action IDs16 and17.
- B does not send12925 or12154 afterward. Its12304 at19:45:09.728542Z removes
  player4, not the NPC: `000001000000000000000004`.
- A sends12925 at19:45:09.604915Z and receives NPC12304 at19:45:09.714311Z.

The marker publishes12608 before13753, re-registering the fighting group in B's
world registry. Terminal marker removal is independent from NPC removal.
The participant return route sends `dead_world_removals`; observer world replay
previously only added available actors and could not remove a retained NPC.

## Native ordering

Original-client `aUH.cbj` returns before constructing `coQ/12925` when its
`huP` spectator flag is true. `bvU.bGG` emits `cpg/12154` only if a retained fight
pointer remains; this capture proves neither ACK arrives in this terminal path.
`cgN.a(ctA)` can affect a still attached combat actor. Do not send raw NPC12304
immediately behind a queued12238 and assume native cleanup has completed.

## Source changes and remaining integration

- Delay terminal marker publication until `settlement_ready`, after durable
  group settlement, instead of consuming the marker at lethal-preview time.
- Remove world NPCs for exterior peers using durable defeated group status and
  exact completed lease revision; do not remove a respawned/replaced group.
- Before additive exploration replay, remove authoritative defeated NPCs in
  the current map/instance; then register available actors. Hold the group lock
  through delivery so respawn cannot race that snapshot.
- Keep lethal action/death spectator delivery, but defer normal terminal cleanup
  until settlement commits so the observer ACK cannot precede its tombstone.
- Publish one native terminal cleanup per spectator subscription, even if
  several owner drains visit the finished fight before the observer polls.
- Accept an explicit12154 for the matching pending terminal session even if
  the subscription has already been retired.

The capture agent now changes only the `aUH.cbj()` spectator suppression check
to preserve the existing native coQ12925 callback for observers too. It runs
after native cleanup and retains the original participant loss flag, packet
codec, null-fight guard and every other spectator transition. Exactly one
matching GETFIELD is required; a different client layout fails validation.
No restart/deployment occurred during Hector's ongoing tests. Client JVMs must
be relaunched after the full server changes are deployed.

## Verification

Luna ran53 focused tests, zero skips: world group cleanup (real isolated
PostgreSQL), spectator registry/events/return dispatcher, deaths and markers.
Tests cover map and owned-instance isolation, stale lease revisions, respawn,
chunking at255 actors, refusing player removal and repeated terminal dispatch.
The original Java `ctA` decoder accepted the actual NPC removal body as opcode
12304, two false flags, one type1 record, identity-1125899906865024.

`bash sniffer/build-capture-agent.sh` builds the full current agent successfully.
`VerifySpectatorTerminalAck` loads the transformed installed aUH class with
`-Xverify:all`, verifies unchanged native methods and exactly one coQ constructor
in the completion callback, and checks native12925 serialization for both
participant flags. The spectator check in native cXi remains unchanged. This
is a bytecode/codec oracle, not a visual acceptance claim.

After integration, test A fighting, B observing and C standing outside on the
same map. A alone must receive rewards; the defeated group must disappear for
all three after terminal cleanup. Reconnect and return to the map: it must stay
absent until a real respawn. A defeat must preserve/restore the available group.
