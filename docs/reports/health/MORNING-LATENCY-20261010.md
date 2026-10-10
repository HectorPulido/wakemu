## Deployment update: 2026-10-10 11:52 America/Bogota

Deployed full world image `wakemu-world:performance-20261010-r73`; all 692 Python/SQL implementation files matched the shared checkout before deployment. Activated complete catalog `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`, preserving all previous player casting roots and adding native NPC coverage. Corrected end-turn validation against the native timeline round; position-owner contention now returns a retry response before mutations instead of disconnecting the session. Validation: 69 combat tests passed; NPC import tests passed (5); position/console tests: 44 passed, 9 isolated-Redis tests skipped.

The 11:36 start-fight delay remains open: 26.228 seconds total, 24.909 seconds in native surface preparation versus 0.673 seconds in an isolated process. No speculative collector policy change was deployed. See `START-FIGHT-LATENCY-20261010-1136.md`. Duplicate interactive publication remains open. Live manual acceptance is pending.

# Morning latency follow-up, 2026-10-10

**Latest acceptance failure:** the r72 controlled-summon `SY + 1` counter assumption failed live. A new Jamajam sent 1 on its first turn, while an older summon sent 2 on its first observed turn; an owner sent 2 after recovery with SY progress 2. The implementation is being corrected from native caller semantics and captured bodies. Passing the original synthetic tests did not establish this wire assumption. The death ACK gate now advances after Jamajam dies; the apparent Wonejo skip instead records an AI turn that could not cast because native casting metadata was missing. Both follow-ups remain open.

Status: complete r71 deployed at 15:41:26 UTC. All 692 current server Python/migration files match the image and running container. World health passes; profiler reattached and capturing continuously. Prior coverage contains a 740-second gap ending at reattachment, under separate investigation; continuous capture must not be claimed uninterrupted.

## Distinct observations

- 10:02 local: duel acceptance took 7.345 seconds while cold native geometry and QI preparation held both participants' SQL row locks. Terrain preparation now runs before those locks; final invitation, session, location and catalog revision checks remain authoritative. Strong references prevent eviction from causing a second cold load inside the transaction.
- The reported minute of unresponsive placement cannot be attributed entirely to that computation. Saved client captures received bootstrap at 15:02:15 UTC; client logs completed actor creation up to 9.2 seconds later. A placement move was sent at 15:02:41.863, proving that the client was responsive at that point. Automatic placement expiry and recovery followed at 15:03:18–19, with another 6–10 seconds before client recovery logs. A full-minute server CPU freeze is not established.
- 10:14 local: server sessions mostly waited for SSL input; ordinary turn acknowledgements and subsequent world movement completed. No explicit surrender request was observed. This does not prove the UI was usable.
- 10:21 local: `!mob` request `1c108ed5ab424c389b2eefa0643291f4` took 9.291 seconds. 189 of 198 sampled console stacks rebuilt the complete map adjacency and cell set. The command now uses existing revision-pinned immutable geometry; occupancy is still read afresh. Client confirmation followed server completion by approximately 308 ms.
- Repeated interactive registrations remain a separate investigation. A historical update-only retry prototype was unsafe; replacement behavior must preserve partition loading and reentry.

## Validation

Terrain/duel preparation: 67 focused geometry, placement, recovery and abandonment tests passed. Four persistent isolated PostgreSQL regressions passed, covering lock boundaries, decline, stale invitation and rollback. The full native duel placement test was stopped during a long catalog load and is not counted as passing.

Console validation: 12 chat-console, four live-console and seven chat-channel tests passed. Four command-routing tests fail in a preexisting AST harness missing `PROFILER`; the decorator already exists in HEAD. Full server and mounted AI Python compilation passed. No whole-repository passing-suite claim is made.

## Manual acceptance

1. Open two clients with nearby characters on the same exterior map.
2. Run `!monster 5525 1 1` twice. Both clients should see two distinct groups, with unoccupied spawn positions. Record first and second command latency separately: a cold map still needs its first validated geometry load.
3. Challenge the other character to a friendly duel. Move both during placement, ready both, cast, end turn and surrender. Both clients should advance and return outside without freezing. Duel rules retain the separate 30×30 minimum when native terrain permits it.
4. Attack one spawned group, cast and surrender. Check movement, targeting and exterior return.

Client presentation latency, failed UI surrender attempts with no observed request, and duplicate interactive registrations remain open. No unsafe update-only scene retry change was deployed.

See [server investigation](LIVE-SLOW-COMBAT-20261010-1502.md), [client timeline](DUEL-CLIENT-TIMELINE-20261010.md), [command investigation](COMMAND-LAG-20261010-1021.md) and [interactive publication](INTERACTIVE-DUPLICATE-PUBLICATION-20261010.md) for preserved evidence and limits.

## Osamodas follow-up, 10:46–10:49 local

Two independent synchronization defects were demonstrated and corrected generally:

- Late-inserted controlled summons had a native timeline counter different from their logical spell-turn count. End-turn validation now uses the exact native wire counter; logical spell counters are unchanged. The stale rejection previously left the summon waiting for its complete 30-second turn.
- When an accepted action killed the current actor and advanced the FSM, its defeated turn had no matching shared ACK barrier. The client acknowledged turn 23 while the server waited for 24. Accepted transitions now stage the matching barrier atomically; current-actor death publishes the old turn end and waits for its ACK before delivering the next turn or running AI.

Validation: 14 wire-counter/runtime/timeline tests, 66 shared/death/ACK tests (including two owners and a spectator), and 17 profiler health tests passed. Full Python compilation passed. Complete r72 image SHA `d66f191476c2dfbcdab762392cafde50abb272e7ebe88a83df4b979edee9f3ec` matches 692 current source/migration files. The shared running world image `wakemu-world:heroes-owned-stats-20261010` uses that exact SHA, started 16:10:17 UTC; no redundant restart was necessary from this agent. Health is OK. Updated profiler was reattached at 16:11:14 UTC; recorder loop and sampler health are OK. Coverage gaps remain explicit, including the world-replacement gap of approximately 686 seconds; do not claim historical uninterrupted capture.

Fresh manual regression: start an Osamodas fight, advance two turns before inserting Jamajam, then alternate owner and summon end-turn three times. No stale-turn rejection or full-duration wait is expected. Repeat the recorded Nova/self-death case while the summon is current; the next actor must proceed after normal presentation ACK, and surrender must remain usable. Repeat the duel/ordinary combat sequence above. This is pending user acceptance, not a claim that all latency or duplicate interactives are fixed.

See [counter evidence](CONTROLLED-SUMMON-TURN-LATENCY-20261010.md), [death synchronization](CONTROLLED-SUMMON-DEATH-ACK-20261010.md), and [profiler liveness](CONTINUOUS-PROFILER-STALL-20261010.md).
