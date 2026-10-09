# Multiplayer placement registration and surrender

Fight 87 exposed two separate failures with Npers and Prueba Oficios.
The second player was added to the shared roster without registering the
native global fighter collection or QI obstacle. Ready and placement expiry
then failed with `Missing actual native fighter participation authority`.
Opcode 13952 also dereferenced `shared.runtime.fight` during placement,
when the runtime is legitimately absent, disconnecting the surrendering socket.

## Changes

`combat_join_registration.register_joined_fighter` registers the newly admitted
player in the existing native PV and QI collections, updates the physical XYZ
to the selected placement cell, and preserves slot and byte topology. It runs
on the unpublished candidate before serialization and persistence. Failed
admission leaves the original encounter and membership unchanged. Ready builds
the normal timeline from the registered roster.

The surrender dispatcher now reads the authoritative `shared.fight.phase`.
Existing individual withdrawal handles private return and preserves the
remaining owner's encounter. No authority guard is disabled and no historical
registration topology is reconstructed. Interrupted encounters follow the
existing restart policy.

Reconnect exposed a third failure: durable participant takeover changed the
session generation while the checkpoint worker retained the old owner
generation. The session now drains pending writes before taking the registry
lock, and the worker advances its generation only after successful durable
takeover. Stale generations remain rejected and other owners remain unchanged.
Server snapshots and the placement bootstrap still contain all five actors;
the reported missing NPC presentation needs visual revalidation.

## Automatic validation

- Native join registration, both Ready orders, expiry and rollback: 4 tests.
- Shared registry, placement capacity, Ready and start: 55 tests.
- Surrender dispatcher and selected individual withdrawal cases: 11 tests.
- Actual Iop and Cra spell regressions: 7 tests.
- Checkpoint worker and reconnect fencing: 11 tests.
- Full withdrawal/dispatcher suite: 28 tests, 6 isolated-PostgreSQL skips.

These tests passed before deployment. They do not replace two-client visual
acceptance. Full current server image and source manifest are checked before
restarting the single world service.

Deployed complete image: `wakemu-world:multiplayer-complete-20261009-r48`,
image SHA256 `c29843149af128f3eabaa2085000cd2b9f6eb0c2d90acf87c8434e497e7a1f61`.
The image matched all 623 manifest files and loaded the current native catalog
before restart. No parallel world server or older-code overlay was used.

## Manual acceptance

1. Reconnect both characters after deployment. Start a fresh PvE encounter
   with one and join with the other during placement.
2. Move each to a distinct legal placement cell; click Ready on both. Repeat
   with the opposite Ready order. Both clients must enter the same active fight
   and show the same current fighter.
3. In another encounter, let placement expire. Both must enter combat without
   a participation authority rejection.
4. During placement, surrender only one character. That client must return
   to the world without disconnecting; the other keeps the encounter and can
   start and finish it. Repeat surrender during an active turn.
5. In a shared encounter, cast and move with each character on its own turn.
   Finish the encounter and check each client's result and world return.
6. Reconnect one client during placement and another during active combat.
   Both must see every player and NPC, preserve turns, and allow continued
   play without checkpoint ownership errors. Reconnect order must not change
   the encounter roster.

Cra remains accepted as 1/18 with partial manual validation; Iop spell
implementation status is unchanged by these shared lifecycle corrections.
