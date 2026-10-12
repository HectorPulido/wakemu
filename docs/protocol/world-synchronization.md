# World synchronization and bootstrap

[Protocol home](README.md) · Next: [Combat synchronization](combat-synchronization.md)

## The client needs a scene, not just coordinates

The client already has local resources for rendering the game, but it still needs server messages describing its owned character, current map context, other actors, interactive state, inventory, and progression.

Bootstrap is the ordered publication that brings those views into a usable state. A character existing in PostgreSQL does not prove that the client has received the entity identity, spellbook, or inventory representation needed to interact with it.

The protocol includes different representations for owned characters and ordinary visible actors. For example, this implementation extracts an appearance template from `12608` and an owned hero entity template from `12666`. Those blobs cannot be substituted just because they describe the same person.

## Generated state and bootstrap records

Wakemu combines explicit message builders with adapted bootstrap records. `fixture(opcode)` selects the first server-to-client record with that opcode, while `replay(start, end, ...)` traverses a selected ordered range. The replay path replaces or skips records whose state belongs to current accounts, ecology, tasks, or map-specific objects.

This is a compatibility scaffold, not an independent simulation of every packet. Replay order and original record positions remain significant. The current loader even validates the original character-selection anchor at record 44. Reordering records would break those assumptions.

## Current PostgreSQL bootstrap loader

The current source loads bootstrap records through `storage/bootstrap_capture.py`. Runtime loading is database-only: it does not parse a capture file or fall back to one when a manifest is missing.

A manifest identifies a capture key, original-source hash, ordered-content hash, and record count. Individual records have ordinal positions and hashes. Loading checks the complete sequence and its hashes before returning it. Importing the same verified records is repeatable; replacing an existing key with different content is rejected.

The offline importer, `server/tools/import_bootstrap_capture.py`, reads a supplied source file and imports it in a transaction. It requires the expected source SHA-256. This separates file parsing from runtime authority; it does not eliminate the underlying replay dependency or replace it with synthetic builders.

**Deployment distinction:** current Compose and image configuration no longer require the historical capture-file mount. Older images may still use it, and a database snapshot may lack imported bootstrap records. Check the packaged code, applied migrations, and database manifest together; restoring catalogs alone does not prove bootstrap readiness.

## Maps have visible partitions

Dynamic world objects must be published when the client can actually resolve them. The scene synchronization code models native partitions as **18 × 18 cells**, with a **3 × 3** visible neighborhood.

As an accepted walk loads new partitions, Wakemu hydrates the relevant dynamic state. Sending an update too early can fail because the client has not registered its target object; sending full snapshots repeatedly can create duplicate registrations or unnecessary work.

The code distinguishes full interactive snapshots (`13984`) from in-place updates (`12344`) for retained objects. Which form is correct depends on whether that client already owns the scene instance.

## Transitions and recovery

Changing maps or entering a private instance involves persistence, ownership, destination bootstrap, and dynamic hydration. Reconnecting may additionally require fight or dungeon reconciliation before constructing the scene. Sending an old map's captured population into a new destination is not a valid shortcut.

When diagnosing missing objects, ask: is the definition available, is the object valid in this map and instance, has its partition loaded, and did the correct connection receive registration before updates?

Sources: [bootstrap loader](../../server/wakfu_server/storage/bootstrap_capture.py), [offline importer](../../server/tools/import_bootstrap_capture.py), [replay and builders](../../server/local_game_server.py), [scene synchronization](../../server/wakfu_server/maps/world_scene_sync.py).
