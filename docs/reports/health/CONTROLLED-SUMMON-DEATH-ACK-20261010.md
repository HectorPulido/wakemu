# Controlled current-actor death and shared turn acknowledgement

Date: 2026-10-10. Incident: fight 159 at approximately 10:49 local (15:49 UTC).

## Evidence and cause

Jamajam actor 115 used a lethal action at 15:48:49.721 UTC while owning global turn 23. Native death settlement removed that actor from the timeline and advanced the fight to enemy turn 24. The runtime had no pending acknowledgement for the defeated actor's presentation. AI consequently ended turn 24 and advanced the server to owner 19, global turn 25, while waiting for acknowledgement 24.

The client was still finishing the defeated actor's turn and sent acknowledgement 23 at 15:48:52.972 UTC. The shared registry rejected it as `Invalid/stale shared turn ACK`. A subsequent end-turn command for dead actor 115 was correctly rejected. This was a presentation synchronization defect, not a long AI search or transport disconnection.

A separate pre-death stale actor-turn counter issue is investigated independently; it must not be conflated with this acknowledgement ordering defect.

## General fix

`combat_shared.Registry.execute` and `execute_server` now stage a shared acknowledgement barrier for every accepted transition that sets `runtime.awaiting_ack`. Barrier preparation occurs before adopting candidate state or publishing packets. It snapshots only live connected participants and preserves acknowledgements already received for an unchanged barrier. A conflicting pending counter rejects the candidate without committing gameplay mutations.

When a lethal accepted action defeats the previous current actor and native settlement already advanced to a successor, the dispatcher calls `RuntimeMessages.synchronize_defeated_turn`. It preserves the lethal action and death deliveries, then closes the old actor presentation with native 12502, holds successor turn-start packets in `pending`, and awaits the old global turn counter. It does not execute death effects or advance the timeline again. The successor's deadline and AI execution cannot start until the old presentation acknowledgement releases the held packets.

Legacy socket `arm_ack` calls remain compatible and idempotent only for the identical already armed turn; they cannot reset the membership fence or received acknowledgements.

## Validation

`server/tests/test_combat_defeated_turn_ack.py` covers:

- Controlled actor 115 self-defeat, preserved existing death presentation, old-turn acknowledgement before successor publication, rejection of premature AI end-turn, then normal server-turn acknowledgement and owner resumption.
- Conflicting acknowledgement counters reject the candidate without publishing packets or mutating live actor HP.
- Repeating a legacy arm request preserves received acknowledgements.

Independent broader run: **66 tests passed** across the focused regression, shared combat, disconnect acknowledgement, runtime messages, and a separate multi-owner regression. The latter verifies two actual registry participants, spectator exclusion, a controlled summon not becoming a barrier participant, stale-counter rejection, and waiting for both owners before successor AI and owner resumption. Evidence: `.runtime/local/diagnostics/shared-defeated-turn-ack-tests.log`. This document does not claim deployment or completed live acceptance.

## Manual acceptance after deployment

1. Enter a fight with a controlled summon and a surviving opponent; have the controlled summon use its self-destruct or another action that kills it during its own turn.
2. Confirm its lethal effects and death animation finish, the enemy begins its next turn once, and the owner's following turn becomes playable without a stale ACK error or a 30-second wait.
3. Repeat with another participant and a spectator. Both participants must receive the same successor actor and movement; the spectator must not become an acknowledgement barrier member.
4. End an ordinary player turn and an ordinary monster turn to confirm unchanged acknowledgement behavior.
