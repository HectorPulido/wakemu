"""NPC wire identities remain distinct through the client's Lua number path."""

import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch
from psycopg.pq import TransactionStatus

from wakfu_server.maps.npc_actor_identity import (
    allocate_block,
    lua_exact_identity,
    repair_available_dungeon_members,
)
from wakfu_server import monster_initial_population
from wakfu_server.monster_reproduction import allocate_identity


class _Row:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row

    def __iter__(self):
        return iter(self.row or ())


class _Updated:
    rowcount = 1


class _IdentityDB:
    def __init__(self, *, first=1 << 50, collisions=()):
        self.next_id = first
        self.collisions = iter(collisions)
        self.calls = []
        self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.group = None
        self.aliases = {}

    def execute(self, query, params=()):
        self.calls.append((query, params))
        if "nextval('lua_exact_npc_actor_ids')" in query:
            value = self.next_id
            self.next_id += 1
            return _Row({"id": value})
        if "SELECT members,status FROM combat_groups" in query:
            return _Row(self.group)
        if "SELECT old_actor_id,new_actor_id FROM npc_actor_identity_aliases" in query:
            return _Row(
                [
                    {"old_actor_id": old, "new_actor_id": new}
                    for old, new in self.aliases.items()
                ]
            )
        if "SELECT monster_id FROM combat_group_members" in query:
            return _Row(
                [{"monster_id": member["id"]} for member in self.group["members"]]
            )
        if "INSERT INTO npc_actor_identity_aliases" in query:
            self.aliases[params[-2]] = params[-1]
            return _Updated()
        if "UPDATE combat_group_members" in query or "UPDATE combat_groups" in query:
            return _Updated()
        if "FROM combat_group_members" in query:
            collision = next(self.collisions, None)
            return _Row({"id": 1} if collision else None)
        return _Row(None)

    def transaction(self):
        return nullcontext(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class NpcActorIdentityTests(unittest.TestCase):
    def test_adjacent_safe_ids_survive_lua_double_conversion(self):
        start = (1 << 50) + 17
        ids = [start + offset for offset in range(128)]
        encoded = [float(identity) for identity in ids]
        self.assertEqual([int(value) for value in encoded], ids)
        self.assertEqual(len(set(encoded)), len(ids))
        self.assertTrue(all(lua_exact_identity(value) for value in ids))

        unsafe = [-(1 << 58), -((1 << 58) + 1)]
        self.assertEqual(float(unsafe[0]), float(unsafe[1]))
        self.assertFalse(any(lua_exact_identity(value) for value in unsafe))

    def test_allocator_skips_claimed_block_and_bounds_requests(self):
        db = _IdentityDB(first=1 << 50, collisions=(True, False))
        identity = allocate_block(db, 2)
        self.assertEqual(identity, (1 << 50) + 1)
        self.assertEqual(len([call for call in db.calls if "nextval" in call[0]]), 2)
        low, high = db.calls[1][1]
        self.assertEqual((low, high), (-((1 << 50) + 127), -(1 << 50)))
        for invalid in (0, 129, True, 1.0):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                allocate_block(db, invalid)

    def test_available_dungeon_rekey_preserves_group_receipt_and_member_data(self):
        db = _IdentityDB()
        old_members = (
            {"id": -(1 << 58), "reference": 6, "level": 4, "x": 3, "y": 8, "z": 0},
            {
                "id": -((1 << 58) + 1),
                "reference": 6,
                "level": 4,
                "x": 4,
                "y": 8,
                "z": 0,
            },
        )
        with patch("psycopg.types.json.Jsonb", side_effect=lambda value: value):
            db.group = {"members": list(old_members), "status": "available"}
            members = repair_available_dungeon_members(
                db,
                (1086, 9001, 73),
                {"members": old_members, "status": "available"},
            )
        new_ids = [member["id"] for member in members]
        self.assertEqual(new_ids, [-(1 << 50), -((1 << 50) + 1)])
        self.assertEqual(len({float(identity) for identity in new_ids}), 2)
        self.assertEqual([member["reference"] for member in members], [6, 6])
        self.assertEqual([member["x"] for member in members], [3, 4])
        group_updates = [
            (query, params)
            for query, params in db.calls
            if "UPDATE combat_groups" in query
        ]
        self.assertEqual(len(group_updates), 1)
        self.assertEqual(group_updates[0][1][1:], (1086, 9001, 73))
        self.assertFalse(any("DELETE" in query.upper() for query, _ in db.calls))

    def test_fighting_group_is_not_rekeyed(self):
        db = _IdentityDB()
        members = ({"id": -(1 << 58), "reference": 6},)
        result = repair_available_dungeon_members(
            db, (1086, 9001, 73), {"members": members, "status": "fighting"}
        )
        self.assertIs(result, members)
        self.assertEqual(db.calls, [])

    def test_reproduction_and_initial_population_allocate_distinct_exact_ids(self):
        db = _IdentityDB(first=1 << 50)
        magnitude, actor_id = allocate_identity(db)
        self.assertEqual((magnitude, actor_id), (1 << 50, -(1 << 50)))
        self.assertEqual(int(float(actor_id)), actor_id)

        class Store:
            def connection(self):
                return db

        class Groups:
            lock = nullcontext()

            def register_transaction(self, _db, map_id, instance_id, group_id, members):
                self.members = members
                return map_id, instance_id, group_id

        groups = Groups()
        region = {
            "monster_capacity": 4,
            "monster_families": [{"family_id": 42}],
        }
        plan = [
            {"reference": 6, "level": 4, "x": 3, "y": 8, "z": 0},
            {"reference": 6, "level": 4, "x": 4, "y": 8, "z": 0},
        ]

        def fake_execute(query, params=()):
            db.calls.append((query, params))
            if "nextval('lua_exact_npc_actor_ids')" in query:
                value = db.next_id
                db.next_id += 1
                return _Row({"id": value})
            if "FROM combat_group_members" in query:
                return _Row(None)
            if "SELECT * FROM monster_initial_population" in query:
                return _Row(None)
            if "SELECT value FROM settings" in query:
                return _Row(
                    {"value": {"version": 1, "enabled": True, "members_per_zone": 2}}
                )
            if "SELECT members FROM combat_groups" in query:
                return []
            if "SELECT x,y,z FROM planted_resources" in query:
                return []
            return _Row(None)

        db.execute = fake_execute
        with (
            patch.dict(
                monster_initial_population.REGIONS, {(1086, 1): region}, clear=True
            ),
            patch.object(
                monster_initial_population,
                "owned_instance",
                side_effect=lambda _r, _l, identity, **fields: dict(
                    id=identity, **fields
                ),
            ),
            patch.object(
                monster_initial_population, "reference", return_value={"family_id": 42}
            ),
            patch.object(
                monster_initial_population,
                "snapshot",
                return_value={"complete": True, "regions": {}},
            ),
            patch.object(
                monster_initial_population,
                "surface",
                side_effect=lambda _map, x, y, z: {"region_id": 1},
            ),
        ):
            result = monster_initial_population.seed_zone(
                Store(),
                groups,
                1086,
                0,
                1,
                plan,
                locate=lambda _map, _x, _y, _z: {"region_id": 1},
            )
        generated = [member["id"] for member in result["members"]]
        self.assertEqual(generated, [-(1 << 50) - 1, -(1 << 50) - 2])
        self.assertEqual(len({float(identity) for identity in generated}), 2)
        self.assertEqual(result["key"][2], (1 << 50) + 1)


if __name__ == "__main__":
    unittest.main()
