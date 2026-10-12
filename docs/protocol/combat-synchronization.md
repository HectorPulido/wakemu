# Combat synchronization

[Protocol home](README.md) · Next: [Investigation and testing](investigation-and-testing.md)

## A fight is a state machine

Combat has placement, active turns, pending actions, death and result processing, and return to world. A packet can be structurally correct but invalid for the current phase, actor, or pending sequence.

Useful request examples include:

| Opcode | Client request body or purpose |
| --- | --- |
| `12523` | One-byte ready flag. |
| `12161` | Actor ID followed by a combat movement path. |
| `12889` | Actor ID, spell instance ID, mode, and target coordinates. |
| `13510` | A four-byte signed turn acknowledgement counter. |

An owned spell instance is not necessarily the catalog's spell reference. Likewise, an actor's identity is not permission to control it. The session and combat controller must establish authority.

## Preparing a cast

The common spell transaction copies the current fight, validates casting requirements, and resolves ordered effects against that preview. Earlier effects can change the conditions seen by later ones, so evaluating all conditions against the initial state would be incorrect.

The effect system works with handlers, conditions, retained states, and event triggers. A cast can change more than health: resources, positioning, summons, states, and triggered effects may all belong to the same action. An unsupported eligible effect rejects the common transaction, including its costs, rather than committing a convenient subset.

Preparation returns a proposed fight state and presentation packets. It does not send those packets or replace the live fight on its own.

## Commit checks

The common commit path checks that the source fight has not changed, the action sequence is next, and no previous action remains unsynchronized. It also validates that prepared effect packets belong to the expected fight and action.

It stages actor-state serialization and flush packets, rechecks the original state, prepares delivery, and only then adopts the preview and action ID. The owning session publishes the returned delivery. This avoids committing a cast whose outgoing representation cannot even be constructed.

Many effect packets share a prefix containing fight ID, action ID, and an additional integer field. That is not a universal header for all combat messages: `13420`, for example, carries a fight ID and closes a client-side action queue batch. It is a presentation marker, not a TCP flush or a database commit.

## Simulation, delivery, and presentation

These are three distinct milestones:

- **Simulation:** the server accepted and calculated the action.
- **Delivery:** the ordered packet batch was written to the relevant sockets.
- **Presentation:** the client processed the sequence and sent the expected acknowledgement.

The shared turn barrier expects `13510` from each participant in its membership snapshot, not just the owner of the current actor. It checks both the counter and account generation. One player's acknowledgement cannot release every other player's pending presentation.

A timeout does not fabricate a missing acknowledgement. Disconnect or abort recovery must explicitly reconcile the fight and reannounce the appropriate timeline. Confusing a round counter, action ID, and acknowledgement counter can produce stalled or prematurely advancing fights even when the spell arithmetic is correct.

The shared-fight coordinator can retire a disconnected participant from the barrier; the remaining acknowledgements may then complete it. The single-session test path processes its acknowledgement on that socket directly. Neither path should be generalized into an actor-owner-only rule for multiplayer fights.

## AI, spectators, and reconnects

AI proposes actions using legal previews and a bounded search. World still owns commit and delivery. A correct AI choice can therefore appear stalled because of synchronization rather than planning.

Spectators need a coherent snapshot and subsequent event sequence. Late entry must include existing summons, retained states, and the current timeline; forwarding only future packets leaves an incomplete scene. Reconnecting participants also need session fencing and recovery, not a blind replay from fight creation.

Test combat changes with multiple participants, summons, an observing client, and reconnects as well as single-player casts.

Sources: [spell preparation](../../server/wakfu_server/combat/combat_spell_transaction.py), [commit boundary](../../server/wakfu_server/combat/combat_spell_commit.py), [effect dispatcher](../../server/wakfu_server/combat/combat_effect_dispatch.py), [ACK barrier](../../server/wakfu_server/combat/combat_ack_barrier.py).
