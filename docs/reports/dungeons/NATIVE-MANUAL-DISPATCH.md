# Native manual dungeon dispatcher

The exploration dispatcher now applies `dungeon_native_flow` to both physical
room gates and the verified native teleport policy. Its physical implementation
continues to delegate to the existing Tofulailler flow.

After a committed room victory, the server publishes unlocked native objects
and the next available monster group in the same instance. It returns before
automatic party travel or automatic exit. The existing
`physical_publication_revision` receipt name is retained for compatibility with
already stored encounters; it now also covers native teleport publication.

World bootstrap publishes the same object state. Exploration movement validates
the unlocked room frontier and native edges before position mutation. Native
exit requests allow the entrance exit or require completed progression for a
later exit. Combat geometry and spell execution are unchanged.

The shared settlement callback already creates the committed current room's
monster group for every dungeon policy; it did not require another policy
exception. These dispatcher changes do not activate unverified configurations.

## Validation

- `test_dungeon_native_flow_dispatch`: three source guard regressions pass.
- `test_dungeon_auto_transition_dispatch` and `test_dungeon_native_flow`:
  fourteen tests pass, including native teleport victory publication without
  automatic travel and the original physical publication behavior.
- PostgreSQL progression and physical compatibility gates are delegated to Luna.

## Manual acceptance after the complete build

Use a dungeon whose native manual configuration has been activated and verified.
Enter with the complete party, including owned heroes if present. Before the
first victory, try walking into a locked room and using a later exit: neither
must advance progression. Defeat the complete room group, acknowledge the
combat result, and verify that everyone remains in the room. The native gate or
teleporter must now permit the next room, where the next monster group appears.
Repeat through the boss, then use the native final exit. Re-enter or reconnect
between two rooms to verify the same committed object states. Repeat the full
Tofulailler route to confirm its physical gates retain their existing behavior.
