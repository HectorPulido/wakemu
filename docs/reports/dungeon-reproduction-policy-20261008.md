# Dungeon reproduction exclusion

Dungeon room monsters were entering the normal ecosystem breeding pipeline because reproduction treated every active `(map_id, instance_id)` as an ecological population. Authored room compositions could consequently gain offspring or additional groups.

`monster_reproduction.dungeon_population` checks the durable `dungeon_instances` registry. It excludes every room belonging to a dungeon run, including completed or closed runs with remaining population records. Public instance zero bypasses the lookup; unrelated private instances keep their existing behavior.

Guards cover clock observation, direct birth attempts, due ticket retrieval, unpublished birth replay, and active tick location selection. Existing authored room spawning, exterior breeding, combat, spells, and maturation remain unchanged. Previously persisted dungeon offspring are not deleted by this change.

Validation:

- `PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_monster_reproduction_dungeons.py`: 4 passed.
- `PYTHONPATH=server .runtime/local/verification-venv/bin/python -m unittest discover -s server/tests -p 'test_monster_reproduction*.py'`: 34 discovered, 4 passed, 30 skipped because an isolated PostgreSQL test DSN was unavailable.

Manual acceptance: enter a fresh dungeon with two party members, record the initial room roster, and remain outside combat longer than the configured reproduction interval. The roster must remain unchanged and no extra group may appear. Repeat after room progression. Exterior eligible adult populations must retain their normal configured breeding behavior. Random probability means a single exterior interval without offspring is not proof of failure.

Isolated PostgreSQL follow-up: the requested Docker gate ran 34 tests in 33.176 seconds, with 31 passing and 3 failing pre-existing actor-namespace assertions. Those tests require allocated IDs above `2**62`, while the current namespace begins at `2**50`. The failing assertions are unrelated to dungeon reproduction; the allocator was not modified here.

Existing contamination can be identified from frozen `dungeon_room_runs.rooms` rosters joined to `dungeon_room_spawn_receipts` and durable reproduction `child_id`/`child_group_id` receipts. Any cleanup needs run/population locks and must exclude ongoing fights. No cleanup was performed.

Final gate: after correcting the three stale test expectations to the documented `npc_actor_identity.MINIMUM/MAXIMUM` range, all **34 isolated PostgreSQL tests passed in 25.650 seconds**. The legacy-ID test now inserts a claimed identity at the new namespace boundary and verifies that allocation skips the occupied 128-identity block. Concurrent allocation and offspring identity tests also verify Lua-exact integers. The allocator itself was unchanged.
