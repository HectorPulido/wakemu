# Haven Bag interior actor isolation

The live r55 report describes exterior monsters remaining visible after entering
an owned Haven Bag. Server publication already scopes player and monster
snapshots by `(map_id, instance_id)`, and the interior uses `(9, owner_id)`.
The transition omitted the native previous-world cleanup packet.

## Native evidence

The installed-client disassembly in
`.runtime/local/transports-ciu-current.txt` shows:

- Opcode `13256` dispatches at bytecode offset 1102 and invokes `a(aTx)`.
- That method invokes `eDl()`, which walks `buS` actor collections and removes
  selected actors, then clears `cdE` and `deK` registries.
- Opcode `13974` (`csW`) installs the destination entity and context, but does
  not invoke that previous-world cleanup path.
- Both existing transport bootstraps send `13256`, then `13974`, then `12318`
  to position the destination scene partitions.

Haven Bag entry and exit now use the same cleanup and partition-positioning
sequence, retaining the separate native bag entry response and exit UI cleanup.
No combat arena, monster population, or database instance policy is changed.

## Acceptance

Start outside beside visible monsters and another player. Enter the bag: no
exterior monster or player should remain. Walk through all installed rooms.
Leave: current exterior monsters and players should return from the scoped
snapshot. Repeat entry and exit twice, including a reconnect outside. Confirm
that furniture and garden plants still appear inside and that exterior actors
do not leak into a second owner's bag.

Source regression coverage is in `server/tests/test_haven_bag.py`, checking
cleanup and positioning for entry, exit, and reentry. Visual acceptance remains
pending until a complete server build containing the change is deployed.
