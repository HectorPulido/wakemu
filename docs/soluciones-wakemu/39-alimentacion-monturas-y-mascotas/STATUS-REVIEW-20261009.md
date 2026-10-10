# Mount characteristic reset review — 2026-10-09

## User acceptance and remaining failure

Repeated feeding and low-level scaling have prior manual acceptance. The user now
reports that equipping or removing a Dragoturkey intermittently makes character
characteristics display zero. Reconnecting or changing spells/aptitudes restores
them. This remains open. Neither server arithmetic becoming zero nor a purely
visual failure has been established from a capture of the failing transition.

## Current deployment evidence

During this review the sole world container was healthy and used
`wakemu-world:performance-20261009-r60`. SHA-256 comparisons matched the checkout
and deployed copies of all four relevant files:

- `server/local_game_server.py`
- `server/wakfu_server/items/mount_publication.py`
- `server/wakfu_server/items/builds.py`
- `server/wakfu_server/wire.py`

Therefore the earlier README statement that the owned public-characteristic fix
is undeployed is stale for these files. This does not establish manual acceptance
of that fix or equivalence of the entire checkout with the image. No service was
restarted or changed during this review.

## Confirmed implementation and ordering gap

`wire.minimal_entity()` now replaces `PUBLIC_CHARACTERISTICS` through
`owned_public_characteristics()`. That function starts with explicit native
defaults and overlays owned effective equipment/aptitude values; it no longer
copies captured mastery values. Mount publication still sends a full entity
refresh (15548), followed by riding/dismount state.

The successful build-save handler (opcode 12772) currently sends:

1. Capacity, ACK, equipment registry and aptitude registry.
2. The canonical `outside_progression()` characteristic snapshot from
   `builds.response_messages()`.
3. `publish_mount_equipment()`, which sends the full entity refresh and dismount
   if the PET section changed.

Build activation (13776) and deletion (13169) instead publish mount changes before
their final `outside_progression()` snapshot. An unrelated spell/aptitude edit
with unchanged PET does not publish the full mount entity refresh. This is a
concrete integration-order difference consistent with the user's recovery
workaround, but it is not yet proof of causality.

## Native client evidence

The installed JAR's `ciu` handler for 15548 resolves the local player first and
calls `biB.as(byte[])` on the existing actor. `eGj.as()` delegates to
`eHd.ew()`. The latter decodes and applies each section in order, invoking
`gp.DM().zp()` after each decoded section; `fj.zp()` invokes the registered
`fi.zm()` callback. This is not a PET-only mutation.

The verified format11 layout places `PUBLIC_CHARACTERISTICS` before
`RUNNING_EFFECTS`, PET and the remaining world sections. The server currently
serializes an empty running-effect list. Thus checking the decoded public-stat
bytes alone does not establish the actor's final state after all section
callbacks and possible deferred work.

The installed native `eGj.doT()` delegates to `eHi.doT()`. That method performs a
sequence including `fuP()`, which walks the equipment sheet and re-applies item
effects through `bW()` / `eZV.g(item,true)`. This confirms a native recalculation
path exists. This review has **not** proved that the particular 15548 callbacks
schedule it, that it clears all characteristics, or that moving the final
snapshot is sufficient against deferred execution.

## Verification performed

Two existing private artifacts were re-read using the installed native JAR:

```sh
java -cp '.runtime/local/classes:client/lib/*' ProbeWorldPublicCharacteristics \
  .runtime/local/pet-stats-world-refresh-20261009/actor6-owned-format11.bin \
  1=860 20=123 21=0 22=0 23=0 24=0

java -cp '.runtime/local/classes:client/lib/*' ProbeWorldPublicCharacteristics \
  .runtime/local/dragopavo-owned-fmt11-xp400.bin \
  20=6 21=0 22=0 23=0 24=0
```

Both passed: format `FOR_REMOTE_CHARACTER_INFORMATION`, 92 characteristic rows,
complete decoding with no trailing bytes. These owned snapshots contain nonzero
HP/mastery where expected; they are not snapshots captured from the newly
reported zero-stat failure. Zero elemental rows in these examples are explicit
defaults, not evidence that every characteristic became zero.

Existing `test_mount_publication.py` covers full format11 persisted equip,
feeding to XP400, unequip and re-equip, including owned public characteristics.
It asserts the mount-only packet order `[15548, 13928]`. It does not cover the
complete opcode12772 publication sequence or final native actor characteristics
after callbacks. No test suite was rerun in this read-only review.

## Proposed next change and acceptance

Make the active-equipment save path finish with the owner's canonical
`outside_progression()` snapshot **after** mount entity/riding publication,
preserving ACK and registry ordering and normal peer publication. Match the
already-existing activation/deletion behavior rather than adding timer-based
resends. Add an integration regression for the complete publication order.

Before claiming a fix, exercise the native full entity apply path, including
running-effect and equipment callbacks, and compare final values with the
authoritative snapshot. If deferred recalculation still overwrites the final
snapshot, identify that callback and fix the relevant refresh contract instead
of adding an arbitrary delay.

Manual acceptance should cover repeated equip/unequip on one character with
nonzero gear and aptitude bonuses, followed by feeding and build activation;
HP, AP/MP and mastery must remain coherent without reconnecting or editing a
deck. A failure capture should record the final server-sent characteristic
values and their packet order so display state can be distinguished from
authoritative server state. Do not mark this issue accepted until that complete
transition succeeds.
