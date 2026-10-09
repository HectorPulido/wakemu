# Death-changing turn timeline synchronization

Fight 80 exposed an actual client/server divergence at 2026-10-08 20:46:45 UTC. A beacon reaction killed two NPCs in one committed cast; both 12727 death actions were delivered at 20:46:43.215. The server selected the next surviving actor. The client still had the two defeated actors in SU when 13337 prepared the next turn, asserted a different next UID, and requested recovery.

The native timing explains the race. `aTS.r` schedules its full death-animation completion callback, but returns at most 250 ms to the action queue. Only the later `aAo(-2)` callback invokes `G` and `D`, then `buH.aC/aD` to remove the fighter from the client's timeline. Consequently a legitimate end-turn ACK can precede that removal; a successful server-side HP transition alone does not synchronize the client's next-slot calculation. Sources: `/tmp/wakemu-native-aTS-death-source.txt` and `/tmp/live-death-turn.txt`.

The explicit owned server policy now uses the existing authoritative 12053 SU snapshot plus native 12514 ACTION controller presentation when new actual `native_timeline_removed` records exist. It replaces the incremental 13337/13482 pair for that boundary. The normal turn-start effects execute once before presentation, as before. This does not recreate the fight scene, actors, spell effects or rewards. Subsequent ordinary turns retain their normal incremental packets until another removal changes the timeline.

A snapshot queued behind a turn ACK receives its Unix-millisecond deadline at actual ACK publication. The server's timeout clock remains monotonic. Explicit recovery also uses ACTION presentation rather than replaying the 13482 native turn-begin lifecycle on an already-current SU.

Late death callbacks cannot remove a different fighter from the restored timeline: native `fem.eT(long)` first checks `Tb.eY` for that exact UID and returns before reading a slot or mutating state when it is absent. A callback can still produce an absent-UID diagnostic; it does not substitute another row. Source: `.runtime/local/combat-timeline-fem.txt`, method eT offsets 0–29.

Initial verification: `test_combat_turn_events` and `test_combat_recovery`, 17 tests: 16 passed; the remaining legacy assertion expected 13482 instead of the intentionally corrected 12514. The final focused multi-death/ACK regression and updated expectation are tracked separately. No deployment or manual-client acceptance is claimed by this source report.
