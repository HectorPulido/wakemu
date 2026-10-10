# Mount identity, destruction and refresh review — 2026-10-09

Scope: read-only source and r58 log review. No runtime code, database, client or service changes. This report does not supersede the accepted low-level scaling result.

## Accepted behavior and remaining symptoms

Hector's fresh Dragopavo reference 18682, UID 1099511634091, displayed level 0 and zero mastery before and after equipment. After feeding it displayed level 2 and one mastery in both item and character panels. This agrees with the native formula floor(level * 0.8). Level transitions need not each increase integer mastery; level 1 gives 0, level 2 gives 1, level 8 gives 6 and level 10 gives 8.

Open symptoms: two mount units appeared to share a displayed level; destroying the older mount was rejected; a mount disappeared after reconnect; some feeding refreshes required another UI action. The low-level result does not validate two-unit independence, destruction reconciliation, all build sheets or immediate panel refresh.

## Confirmed destruction evidence

Boot `faa4761f4977427f85c14e36474f1238`, character 1, UTC:

| Time | Result | Authoritative evidence |
| --- | --- | --- |
| 21:16:25.800 | Rejected | Inventory unchanged; build 3 contains UID 1099511628620, reference 18704, slot 24. |
| 21:16:58.551 | Rejected | Same ownership/build reference and unchanged inventory. |
| 21:17:16.236 | Rejected | Same ownership/build reference and unchanged inventory. |
| 21:17:19.726 | Completed | UID 1099511634058, reference 18704, disappears from the inventory snapshot; old UID 1099511628620 remains linked to build 3. |
| 21:17:23.897 | Rejected | Old unit remains linked to build 3; inventory unchanged. |

The rejection is `Desequip the selected owned unit before destruction`. `inventory_actions.destroy` checks **every saved build**, not just the active build. This is an intentional dangling-reference guard, but the message fails to identify the blocking build. The successful deletion is of reference 18704, not the subsequently granted reference 18682 UID 1099511634091. Do not collapse these units into one incident or claim the new unit was deleted by that request.

The successful deletion is durable and explains why that particular unit is absent after reconnect. The reported temporary appearance of the deleted unit is consistent with client reconciliation problems, but this review does not prove the precise UI object responsible. Rejected requests did not delete inventory in the captured before/after snapshots.

## Source findings and limits

- `items/mount_inventory.py` initializes persistent state using `inventory_mounts.uid`, with `ON CONFLICT(uid) DO NOTHING`; hydration joins by UID. Feeding locks and updates the selected UID. No shared-by-reference XP assignment was found in these paths.
- `items/equipment_stats.py` evaluates native effect parameters at the selected owned mount's level. The previously accepted level 2 result matches this code.
- `items/mount_feeding_wire.py` publishes food subtraction, pet removal and same-UID reinsertion. `mount_feeding.py` then publishes the rich equipment inventory. Publication follows commit; partial delivery is not rollback.
- `sniffer/java/NativePetStateRefresh.java` retains observer identity by UID using weak references. It reconciles existing native pet state through native setters. This reduces stale open panels, but does not prove that two live item wrappers never share a native pet object through the registry path. The current oracle covers same-UID retention and observer callbacks, not a full two-distinct-UID isolation scenario.
- The destruction rejection path in `local_game_server.py` sends inventory synchronization. The success path sends removal followed by rich equipment inventory. Client panel selection, physical inventory and equipment registry may therefore reconcile through different paths; immediate visual coherence remains unaccepted.
- Logs include inventory UIDs and build links but omit per-unit pet XP in request snapshots. They cannot establish or exclude a transient client level alias from the screen alone.

## General correction proposal, not implemented

Keep server ownership and all-build deletion protection. Report the precise blocking build indices and item UID, and offer the user a normal way to remove the reference from each saved build rather than deleting referenced data silently. Preserve independent mount state by UID throughout physical inventory, equipment registry and open panel observer reconciliation. Validate that existing native pet objects are never reused across different UIDs, including remove/reinsert and delete/reject sequences. A deleted UID must disappear from all client registries and selections after the committed response; a rejected deletion must restore the correct unit without replacing another unit's state.

Add two-unit native observer tests and transaction tests covering inactive-build references, rejected deletion, successful deletion and reconnect. Treat transport publication failures separately from rejected mutations. Do not change XP scaling or bypass build ownership guards to mask the UI symptom.

## Complete manual acceptance after a correction

1. Use an otherwise unequipped test build. Grant two fresh units with `!item 18682 1` twice. Record both returned UIDs as A and B; grant food with `!item 18378 20`.
2. Open A and B separately. Both must start level 0. Equip A and save the build. Feed A until level 2: wheat must decrease, A must immediately display level 2 and mastery 1, B must remain level 0. Unequip/re-equip A: character mastery difference must be exactly 1, without HP flicker.
3. Equip B in another saved build and save. Switch back to A's build. Attempt to destroy B: reject consistently and identify the saved build holding B. Neither unit, food nor level may change.
4. Open that build, remove B and save. Destroy B through its own panel: only B's UID must disappear immediately. A must retain level 2 and mastery 1. Reconnect and verify the same inventory, build links and levels.
5. Feed A to level 10. The item and character mastery difference must be 8 immediately; reconnect and switch builds to verify persistence. Repeated feeding must respect the configured daily-limit flag; accepted unrestricted testing must not require reconnects.

These are future acceptance steps, not a request to repeat the already accepted basic feeding test during the current profiling session.
