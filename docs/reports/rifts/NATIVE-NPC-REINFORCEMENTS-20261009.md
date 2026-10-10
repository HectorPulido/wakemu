# Ordinary NPC reinforcement protocol

Installed client: `client/lib/wakfu-client.jar`. This investigation is read-only
against the native catalog; no world restart or deployment was performed.

## Proven client path

1. `ctE` / 12608 publishes the ordinary NPC world appearance. `cgN.a(ctF,
   boolean)` constructs `bjo`, deserializes the appearance and registers it with
   `bio.ae(big)`. The existing `combat_monster_world.spawn_monster` owns that
   encoding and preserves a false native summoned flag.
2. `cvg` / 13091 admits that existing actor into a fight. Its exact fields are
   fight ID, actor UID, actor type, team, short-length actor stats, int-length
   effects, and an optional native controller descriptor. This already has a
   codec in `combat_multiplayer_wire.added`.
3. The ordinary fight handler `cjs.a(cvg)` queues an `aVH` action using the
   currently registered fight. `aVH.cXi()` looks up the actor in `bio` or `fkK`,
   calls `buH.b(actor, team, false)`, then `big.a(fight, stats, effects)` and
   `cYp.c(fight, actor)`. It also handles `AnimApparition` when present.

The handler does not issue a placement bootstrap or reset the phase. It does
not create an `eZl` / 307 summon. A missing world appearance is a real failure:
`aVH` logs the absent actor and returns, so packet ordering is mandatory.

## Implementation and validation

`rift_npc_creation.creation_packets` supplies the ordered 12608 + 13091 pair,
with ordinary NPC actor type 0, enemy team 1, no controller, authoritative
obstacle ID and catalog characteristics. The combat adapter remains responsible
for registering the actor, obstacle occupancy, initiative order and AI state
before publication. Replay must preserve both packets in order.

Three unit tests pass: ordered ordinary admission, rejection of altered catalog
data, and invalid obstacle rejection. `VerifyRiftNpcAdmission.java` successfully
decodes the generated packet through the installed native `cvg` implementation.
This oracle proves the binary admission contract, not graphical acceptance of a
full wave, movement or spell mechanics.

Native disassembly evidence is reproducible with `javap -c -p` for `cvg`, `cjs`,
`aVH`, and `cgN`; private working copies are under `.runtime/local/` and are not
part of the published artifact.
