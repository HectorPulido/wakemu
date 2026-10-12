# The lifecycle of a request

[Protocol home](README.md) · Next: [World synchronization](world-synchronization.md)

## A connection has state

Each accepted game socket gets a session thread. The socket is wrapped in TLS and then in `Connection`, which serializes outgoing writes. The session retains information such as its account, generation, selected character, loaded scene, and current combat context.

An opcode is therefore not enough to determine behavior. Authentication may be required; a character may need to be selected; an action may be valid only during placement or only outside combat. The same connection also processes idle maintenance and queued updates between requests.

The socket timeout is not automatically a disconnect. `receive()` can invoke the idle callback, which checks whether the session remains valid and performs bounded maintenance. Before authentication, the connection also has a limited initial lifetime.

## The processing chain

1. **Read the header.** Read four length bytes, reject an invalid frame size, then read the remaining frame exactly.
2. **Extract routing information.** Separate route, opcode, and body, and start diagnostic timing.
3. **Reconcile current context.** Adopt pending shared fight or world transitions where needed so dispatch sees the state already presented to the player.
4. **Decode the body.** Use an explicit layout, including length and trailing-byte checks for supported messages.
5. **Authorize and validate.** Check ownership, generation, phase, geometry, resources, and domain-specific rules.
6. **Apply the domain operation.** Use the appropriate database transaction or guarded in-memory transition.
7. **Publish the result.** Serialize responses and deliver them in the required order to the relevant connections.

This is the general pattern, not a claim that every handler is one uniform framework. The large session dispatcher still contains specialized branches, while reusable behavior lives in the domain modules.

## Example: walking

A `13331` request describes a path. World cancels incompatible gathering or planting occupations, decodes the steps, and validates the movement against authoritative movement state and applicable door or dungeon rules.

If the request is rejected, it can send `13530` with the server's position to correct the client. If accepted, it updates the owned position and publishes relevant scene changes. The requested endpoint never becomes trustworthy just because its bytes decode successfully.

Movement is frequent, so positions use an in-memory buffer and Redis journal rather than a synchronous PostgreSQL write per step. Flush boundaries include logout, transitions, and ownership changes. A generation check prevents a delayed old session from overwriting its replacement.

## Transactions and delivery are separate

A database commit makes a durable change; a socket write makes bytes available to the connection. They are different operations and do not form one universal atomic transaction. Some domains use durable receipts or outboxes to recover delivery and avoid duplicate work. Combat has its own prepared-action and acknowledgement paths.

For ordered publication, `send_batch()` builds complete frames and holds one connection write lock for the whole batch. This prevents another thread from interleaving bytes into that batch. It does not guarantee simultaneous delivery across all players, nor prove that a client has displayed the result.

## Shared state and shutdown

A session thread can interact with world registries, shared fights, background workers, and storage. Domain locks and ownership checks protect those boundaries; the design is not a single event loop that serializes all gameplay globally.

Disconnect cleanup must consider more than removing a socket: position flushes, session leases, occupations, party presence, shared fight membership, and recovery state can still matter. Explicit recovery is safer than pretending a disconnected player sent an acknowledgement.

Sources: [session loop](../../server/local_game_server.py), [position buffer](../../server/wakfu_server/storage/position_buffer.py), [position journal](../../server/wakfu_server/storage/position_redis.py).
