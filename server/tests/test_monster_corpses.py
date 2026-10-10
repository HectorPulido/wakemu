import unittest
import struct
from types import SimpleNamespace
from unittest.mock import patch

from psycopg.pq import TransactionStatus
from protocol_codec import Reader
from wakfu_server import monsters
from wakfu_server import monster_corpses as corpses
from wakfu_server import combat_monster_world

owned_instance = monsters.owned_instance


def member(identity=-201, *, map_id=1134, instance_id=7, team=1):
    return owned_instance(
        5525,
        1,
        identity,
        map_id=map_id,
        instance_id=instance_id,
        x=-7,
        y=-7,
        z=-1,
        team=team,
    )


class FakeDB:
    def __init__(self, *, status=TransactionStatus.INTRANS, existing=(), rows=()):
        self.info = SimpleNamespace(transaction_status=status)
        self.existing = set(existing)
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if "SELECT value FROM settings" in sql:
            return Result([{"value": {"lifetime_seconds": 3600}}])
        if "SELECT actor_id FROM monster_corpses WHERE fight_id" in sql:
            return Result([{"actor_id": -1}] if params[1] in self.existing else [])
        if "SELECT nextval('lua_exact_npc_actor_ids')" in sql:
            return Result([{"id": 1 << 50}])
        if "combat_group_members" in sql:
            return Result([])
        if "RETURNING map_id,instance_id,actor_id" in sql:
            return Result(self.rows)
        if "SELECT actor_id FROM monster_corpses" in sql:
            return Result(self.rows)
        if "SELECT actor_id,map_id,instance_id,monster FROM monster_corpses" in sql:
            return Result(self.rows)
        if "pg_advisory_xact_lock" in sql:
            return Result([])
        if sql.startswith("INSERT INTO monster_corpses"):
            return Result([])
        raise AssertionError(f"Unexpected SQL: {sql}")


class Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class MonsterCorpsesTests(unittest.TestCase):
    def test_native_collection_actions_are_derived_per_breed_and_alive_is_unchanged(
        self,
    ):
        catalog = {
            "monsters": [
                {
                    "ref": 5525,
                    "collect_actions": [
                        {"d": 81, "clT": 'not IsDead("target")'},
                        {"d": 12, "clT": 'IsDead("target")'},
                        {"d": 81, "clT": 'not IsDead("target")'},
                    ],
                },
                {"ref": 999, "collect_actions": [{"d": 92, "clT": ""}]},
            ]
        }
        combat_monster_world.corpse_collect_actions.cache_clear()
        self.addCleanup(combat_monster_world.corpse_collect_actions.cache_clear)
        with patch("wakfu_server.native_catalog.load", return_value=catalog):
            self.assertEqual(combat_monster_world.corpse_collect_actions(5525), ())
            self.assertEqual(combat_monster_world.corpse_collect_actions(999), (92,))
        npc = member()
        with patch.object(
            combat_monster_world,
            "corpse_collect_actions",
            side_effect=AssertionError("Living actor queried corpse actions"),
        ):
            first = combat_monster_world.world_actor(npc, group_id=201)
            second = combat_monster_world.world_actor(npc, group_id=201, dead=False)
        self.assertEqual(first, second)
        with patch.object(
            combat_monster_world, "corpse_collect_actions", return_value=(12, 81)
        ):
            dead = combat_monster_world.world_actor(npc, group_id=201, dead=True)
        self.assertEqual(dead[-31:-21], struct.pack(">Hii", 2, 12, 81))

    def test_gobball_seed_requires_living_target_and_corpse_resource_requires_dead(
        self,
    ):
        from wakfu_server.monster_collect import action, validate_action

        living = {"hp": 10}
        dead = {"hp": 0}
        seed, resource = action(1, 3723), action(1, 3722)
        self.assertEqual(seed["condition"], 'not IsDead("target")')
        self.assertEqual(resource["condition"], 'IsDead("target")')
        validate_action(seed, living, profession_level=0)
        validate_action(resource, dead, profession_level=0)
        with self.assertRaisesRegex(ValueError, "target criterion failed"):
            validate_action(seed, dead, profession_level=0)
        with self.assertRaisesRegex(ValueError, "target criterion failed"):
            validate_action(resource, living, profession_level=0)
        disabled = combat_monster_world.corpse_collect_actions(1)
        self.assertNotIn(3723, disabled)  # No fake "collected recently" state.
        self.assertNotIn(3722, disabled)

    def fight(self, roster, dead=(), controlled=()):
        actors = {
            row["id"]: SimpleNamespace(
                hp=0 if row["id"] in dead else 10,
                controlled=row["id"] in controlled,
            )
            for row in roster
        }
        return SimpleNamespace(id=88, phase="finished", actors=actors)

    def test_roster_is_fully_validated_before_any_database_access(self):
        valid, foreign = member(-201), member(-202)
        fight = self.fight((valid, foreign), dead=(-201, -202))
        bad = dict(foreign, ref=999999)
        db = FakeDB()
        with self.assertRaises(ValueError):
            corpses.retain(db, fight, (valid, bad))
        self.assertEqual(db.calls, [])

    def test_rejects_controlled_actor_and_does_not_touch_database(self):
        npc = member()
        db = FakeDB()
        fight = self.fight((npc,), dead=(npc["id"],), controlled=(npc["id"],))
        with self.assertRaises(ValueError):
            corpses.retain(db, fight, (npc,))
        self.assertEqual(db.calls, [])

    def test_retain_skips_living_and_keeps_existing_corpse_without_allocation(self):
        dead, alive = member(-201), member(-202)
        db = FakeDB(existing=(dead["id"],))
        fight = self.fight((dead, alive), dead=(dead["id"],))
        count = corpses.retain(db, fight, (dead, alive))
        self.assertEqual(count, 1)
        self.assertFalse(any("nextval" in sql for sql, _ in db.calls))
        self.assertFalse(any(sql.startswith("INSERT") for sql, _ in db.calls))

    def test_retain_requires_settlement_transaction(self):
        npc = member()
        db = FakeDB(status=TransactionStatus.IDLE)
        with self.assertRaises(ValueError):
            corpses.retain(db, self.fight((npc,), dead=(npc["id"],)), (npc,))
        self.assertEqual(db.calls, [])

    def test_new_remains_use_separate_identity_and_original_exploration_position(self):
        npc = member()
        db = FakeDB()
        fight = self.fight((npc,), dead=(npc["id"],))
        fight.actors[npc["id"]].x = 999  # Fight placement must not move remains.
        with patch.object(corpses, "allocate_block", return_value=1125899906842624):
            self.assertEqual(corpses.retain(db, fight, (npc,)), 1)
        inserts = [
            (sql, params) for sql, params in db.calls if sql.startswith("INSERT")
        ]
        self.assertEqual(len(inserts), 1)
        sql, params = inserts[0]
        self.assertEqual(params[:5], (88, npc["id"], -1125899906842624, 1134, 7))
        saved = params[5].obj
        self.assertEqual(saved["x"], npc["x"])
        self.assertNotEqual(saved["id"], npc["id"])
        self.assertIn("CURRENT_TIMESTAMP+make_interval(secs=>%s)", sql)
        self.assertEqual(params[-2:], (3600, 3600))

    def test_dead_appearance_sets_native_isdead_field_and_not_is_ko(self):
        npc = member()
        opcode, packet = corpses.spawn(
            {
                "actor_id": npc["id"],
                "map_id": npc["map_id"],
                "instance_id": npc["instance_id"],
                "monster": npc,
            }
        )
        self.assertEqual(opcode, 12608)
        reader = Reader(packet)
        self.assertEqual(
            (reader.number("B"), reader.number("B"), reader.number("B")),
            (0, 1, 1),
        )
        self.assertEqual(reader.number("q"), npc["id"])
        body = reader.take(reader.number("H"))
        reader.finish()
        appearance = Reader(body)
        appearance.number("B")
        appearance.number("q")
        appearance.number("B")
        appearance.number("q")
        appearance.text("H")
        appearance.number("h")
        appearance.take(20)  # coordinates, direction, visibility
        appearance.take(5)  # breed level and public characteristics
        appearance.number("B")  # empty fight-properties section
        appearance.number("i")  # no fight ID
        self.assertEqual(appearance.number("B"), 0)  # isKo
        self.assertEqual(appearance.number("B"), 1)  # isDead
        self.assertEqual(appearance.number("B"), 0)  # isSummoned
        self.assertEqual(appearance.number("B"), 0)  # isFleeing
        self.assertEqual(appearance.number("b"), -1)  # obstacle
        self.assertEqual(appearance.number("B"), 0)  # no summon data
        self.assertEqual(appearance.number("B"), 1)  # world rK present
        self.assertEqual(appearance.number("H"), 1)  # one property
        self.assertEqual((appearance.number("B"), appearance.number("B")), (19, 1))

    def test_spawn_rejects_mismatched_map_or_instance(self):
        npc = member()
        row = {
            "actor_id": npc["id"],
            "map_id": npc["map_id"],
            "instance_id": npc["instance_id"],
            "monster": npc,
        }
        for key, value in (("map_id", 1135), ("instance_id", 8)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                corpses.spawn({**row, key: value})

    def test_snapshots_query_is_scoped_to_requested_map_and_instance(self):
        db = FakeDB(rows=[])
        self.assertEqual(corpses.snapshots(db, 1134, 7), ())
        sql, params = db.calls[-1]
        self.assertIn("map_id=%s AND instance_id=%s", sql)
        self.assertEqual(params, (1134, 7))
        for invalid in ((0, 7), (1134, -1), (True, 7)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                corpses.snapshots(db, *invalid)

    def test_expired_removals_scope_and_batch_at_native_limit(self):
        ids = list(range(-1, -258, -1))
        db = FakeDB(rows=[{"actor_id": identity} for identity in ids])
        messages = corpses.expired_removals(db, 1134, 7, ids)
        self.assertEqual(
            [len(payload) for _, payload in messages], [3 + 9 * 255, 3 + 9 * 2]
        )
        sql, params = db.calls[0]
        self.assertIn("map_id=%s AND instance_id=%s", sql)
        self.assertEqual(params, (1134, 7, ids))
        self.assertIn("actor_id=ANY(%s)", sql)

    def test_fresh_scene_never_queries_historical_expiry_receipts(self):
        db = FakeDB()
        self.assertEqual(corpses.expired_removals(db, 1134, 7), ())
        self.assertEqual(db.calls, [])

    def test_retained_scene_removes_only_known_missing_corpses(self):
        npc = member()
        db = FakeDB(
            rows=[
                {
                    "actor_id": npc["id"],
                    "map_id": 1134,
                    "instance_id": 7,
                    "monster": npc,
                }
            ]
        )
        packets, active = corpses.reconcile(db, 1134, 7, (-201, -202))
        self.assertEqual(active, frozenset((-201,)))
        self.assertEqual(tuple(opcode for opcode, _ in packets), (12304, 12608))
        reader = Reader(packets[0][1])
        self.assertEqual(reader.take(4), bytes((0, 0, 1, 1)))
        self.assertEqual(reader.number("q"), -202)
        reader.finish()
        self.assertNotIn("expires_at<=", db.calls[0][0])

    def test_expire_batches_per_scope_and_marks_only_unpublished_rows(self):
        rows = [
            {"map_id": 1134, "instance_id": 7, "actor_id": -i} for i in range(1, 258)
        ] + [{"map_id": 2000, "instance_id": 0, "actor_id": -900}]
        db = FakeDB(rows=rows)
        result = corpses.expire(db)
        lengths = {
            scope: tuple(len(payload) for _, payload in messages)
            for scope, messages in result.items()
        }
        self.assertEqual(
            lengths,
            {(1134, 7): (3 + 9 * 255, 3 + 9 * 2), (2000, 0): (12,)},
        )
        self.assertIn("NOT expiry_published", db.calls[0][0])
        self.assertIn("RETURNING map_id,instance_id,actor_id", db.calls[0][0])


if __name__ == "__main__":
    unittest.main()
