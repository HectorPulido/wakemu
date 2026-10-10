# Profiler, persistence, and HP acceptance review

Review scope: documentation only. No code, database, service, or deployed-image changes. Existing captures were inspected read-only. The user has not authorized performance optimization in this phase.

## Prioritized evidence

1. **Gameplay stall remains open.** Fight 109 has a spell request spanning 103.25 seconds. The preserved feature summary has four casts totaling 110,432.21 ms wall / 106,491.36 ms calling-thread CPU, with full CPU coverage. Substantial CPU work is measured across that aggregate; the exclusive function and individual-call CPU remain unknown. The first external waits capture began after recovery and cannot identify the stall stack. Several background maxima near 103 seconds overlap this interval; they are not evidence of separate 103-second incidents.
2. **Late spectator publication is a confirmed correctness failure.** Fight 110 repeatedly rejects snapshots with `Unverified native remote effect container absence`; server-side actors have already been added when the request is labelled rejected. Its 120-second waits capture covers the reproduction (28 thread profiles, 1,178 shared frames, 70,755 all-thread samples). Idle conditions, socket accept and SSL reads dominate all-thread samples, which does not establish CPU cost. The observed later casts take roughly 0.89–2.31 seconds; no second 103-second cast is demonstrated. Beacon activation failure needs its own authoritative event/state analysis.
3. **Manual checkpoint coverage is narrower than its name suggests.** `MANUAL_CHECKPOINT = ManualCheckpoint(flush_positions)` in `server/local_game_server.py:198` calls the position buffer only. `storage/manual_checkpoint.py:50` runs this callback asynchronously. `storage/position_buffer.py:154` selects dirty position entries and returns zero when none are selected; successful counts represent committed position updates. The scheduled position worker defaults to every two seconds (`compose.yaml:50`, `local_game_server.py:152,201`), so a manual result of zero can legitimately mean that the scheduled worker already persisted movement. It does not verify inventory, equipment, combat state, or an older twenty-minute save path. Combat persistence has a separate `combat.checkpoint` span at `local_game_server.py:1375`. Therefore the screenshot’s 0.003–0.004 second empty saves do not close the original freeze or prove nonempty position persistence.
4. **Startup CPU hotspot is measured, not optimized.** Capture 1791579584453883663 concentrates 94.3% of 123 samples in point-area merging/identity scanning during catalog compilation. This is a startup hotspot; it is not evidence that the same function caused the gameplay stall. One cold-start RSS observation is not a memory-leak diagnosis.
5. **HP flicker remains manual acceptance pending.** The r57 serializer removed captured HP and a read-only injured-character probe emitted 300 / 1050 correctly. This establishes a stale-data fix in one publication path, not complete end-to-end closure. No fresh timestamped HP flicker reproduction was supplied in these latest tests.

## Measurement limitations

Feature spans are inclusive and nested; totals cannot be summed into a process cost. Thread CPU subtracts only measured calling-thread work from wall time; remaining time is not automatically database time. `postgres.transaction` has zero CPU measurement coverage in the preserved summary, so its reported CPU zero must not be interpreted as zero CPU work or its wall total as known waiting. Histogram p95 is an approximate bucket bound. `session.idle` is a measured maintenance label, while a waits-mode stack may simply be waiting for input. Neither label alone proves a bottleneck.

The current shared checkout contains later combat source edits absent from the fixed r58 deployed image. Source review must be matched to the actual deployed revision before attributing exact stack lines to production behavior.

## Complete next acceptance sequence

Use two fully relaunched clients A and B; record local time for any anomaly. Run the following only after the responsible fixes are deployed. These are acceptance instructions, not evidence that fixes already exist.

1. Reset counters with `!perfil reiniciar`. Run `!perfil iniciar 120 waits` before entering combat. A starts and readies, places existing beacons, then B joins observation. Both clients must see existing entities and matching ownership/effects. A attacks a beacon with its supported element: authoritative activation and damage must match visible effects. Complete the fight; B receives no participant rewards, and the defeated mob disappears for both. Save `!perfil estado` and `!perfil informe max` after completion. A responsive direct spell is insufficient to accept beacon triggers.
2. During that fight, run `!checkpoint`; gameplay must continue without a multi-second stall. Record its receipt and query the exact receipt, for example `!checkpoint 1` when the issued receipt is 1. Outside combat, A moves continuously while submitting another checkpoint. A zero count is inconclusive for nonempty flushing because the two-second worker can win the race; do not repeatedly ask the user to race it. An investigator must correlate `position_batch_timing.characters > 0`, PostgreSQL coordinates and the matching position revision, using read-only diagnostics. Verify restored coordinates after normal reconnect, while recognizing that logout itself can save them. Reconnect alone is insufficient proof of the manual callback’s write.
3. Separately capture any original periodic freeze with the profiler already running, preserving `position_checkpoint_stage`, `combat.checkpoint`, PostgreSQL pool/transaction timing and `checkpoint-slow-stacks.log`. First identify which scheduled callback actually ran. A manual position flush does not substitute for all persistence paths.
4. Injure A in combat; B watches A’s overhead HP while A equips/removes the mount, feeds it, and enters/exits the bag. Compare A’s current/max HP to B’s bar at each transition. Equipment maximum changes and regeneration are expected; unrelated momentary spikes are failures. Record the exact action/time and both clients’ values if it recurs.
5. Stop the optional profiler with `bash client-tools/profiler.sh stop`; world and ongoing play must remain responsive. `!perfil informe max` must still report lightweight counters. Starting/stopping the sidecar proves diagnostic isolation, not that underlying server latency is fixed.

## Related evidence

- [External profiler implementation and limits](EXTERNAL-PROFILER-20261009.md)
- [Fight 109 stall timeline](SPECTATOR-FREEZE-20261009.md)
- [Fight 110 beacons and spectator timeline](BEACONS-LATE-SPECTATOR-20261009.md)
- [HP publication audit](HP-FLICKER-AUDIT-20261009.md)
- [Startup sampled hotspot](../admin-chat/PROFILER-STARTUP-FINDING-20261009.md)

Private captures and raw logs remain under `.runtime/`; they are not included in this report or intended for commits.
