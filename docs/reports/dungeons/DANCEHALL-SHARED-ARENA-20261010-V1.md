# Dancehall Arena sequential native encounters — V1

Definition 11 is one physical arena with three successive dances, not three different map rooms. Installed map 549 provides 249 directed-reachable arena cells and one exterior teleporter (18989), with no internal doors or transports. [The dungeon reference](https://wakfu.wiki.gg/wiki/Dancehall_Arena) describes seven ordinary enemies, then eight, then seven plus Bilby Queen. Exact ordinary species quantities are not established by that reference: the candidate explicitly cycles the four installed ordinary species rather than claiming an official distribution. Queen reference 2469 appears once, only in the last encounter.

The native minimum-level sum increases from 700 to 800 to 813. This is a measurable local encounter-size/level proxy, not proof of increasing mechanical difficulty. Native min/max monster levels and spell behavior remain unchanged. Dance-specific rhythm mechanics, conditional damage reflection and Queen scripts remain unverified.

## General server policy

`native_shared_arena_sequential_policy` is opt-in and separately validated. Every logical stage must own exactly the same nonempty, duplicate-free native cells; every anchor lies in those cells. The policy rejects physical doors, internal teleports, automatic travel edges, branches, unequal stage terrain and missing reviewed sequence evidence. It requires one verified native exterior exit whose approaches lie in the arena.

Durable dungeon progression remains authoritative for encounter ownership. `configuration_for_instance` injects the current committed stage for coordinate lookup, avoiding accidental selection of the last matching logical room. Movement checks the shared arena cells and existing native directed-edge/diagonal validator for every stage. It never opens future geometry or modifies combat terrain.

Existing settlement calls `ensure_current_room` after a committed victory. It therefore materializes the next room group in the same arena without transport or fake gates; the existing native publication path broadcasts the newly available group. Final completion publishes the native exterior exit as visible and usable. A normal native exit request is denied before final completion. `!exitdungeon` remains the explicit cancellation path through the same verified exterior destination.

The existing physical and mixed policies continue rejecting ambiguous overlapping room terrain; shared terrain is authorized only by this new policy.

## Verification

`test_dungeon_shared_arena.py`: 6/6 passed using read-only published catalogs. Regressions cover unequal terrain, invented gates, configuration-time enforcement, authoritative stage lookup, stage-specific native movement, completion/exit state and exact three-stage quantities without early/duplicated Queen. The candidate passes six-player combat formation for all three encounters and retains directed engagement witnesses.

Portable candidate: `shared-arena-v1/native_dungeon_11.json`. Audit: `DANCEHALL-SHARED-ARENA-20261010-V1.json`. PostgreSQL lifecycle/replay validation is delegated to Luna before activation. No runtime writes or restart were performed for preparation.

Manual acceptance after deployment: enter with the group, finish each dance and confirm the next group appears in the same arena without moving characters; verify seven, eight, then seven plus one Queen; finish and use native exit. In a separate run, verify the exit does not authorize completion early and `!exitdungeon` cancels outside combat. Reconnect after the second dance and confirm only the current third encounter appears.
