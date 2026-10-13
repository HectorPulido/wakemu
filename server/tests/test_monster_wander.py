import unittest
from postgres_case import PostgresCase
from copy import deepcopy
from unittest.mock import call, patch
from wakfu_server.monster_wander import (
    edge_index,
    plan,
    plan_path,
    policy,
    wander_location,
)
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_group_store import PersistentGroups
from protocol_codec import decode_body
from psycopg.types.json import Jsonb


class FixedRng:
    def __init__(self, *, rolls=(), steps=1):
        self.rolls = iter(rolls)
        self.steps = steps
        self.random_calls = 0

    def random(self):
        self.random_calls += 1
        return next(self.rolls)

    def randint(self, low, high):
        return min(max(self.steps, low), high)

    def choice(self, values):
        return values[0]


class WanderTests(PostgresCase):
    def setUp(self):
        super().setUp()
        # These fixtures isolate movement/locking behavior on synthetic cells.
        habitat = patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=True,
        )
        habitat.start()
        self.addCleanup(habitat.stop)

    def test_nearness_edges_and_occupancy(self):
        members = [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)]
        edges = [((0, 0, 0), (1, 0, 1))]
        self.assertIsNone(plan(members, [], edges))
        self.assertIsNone(plan(members, [dict(x=50, y=50, z=0)], edges))
        self.assertIsNone(
            plan(members, [dict(x=2, y=0, z=0)], edges, occupied=[(1, 0, 1)])
        )
        result = plan(members, [dict(x=2, y=0, z=0)], edges)
        op, body = result["packets"][0]
        decoded = decode_body("in", op, body)
        self.assertEqual(op, 13852)
        self.assertEqual(result["members"][0]["z"], 1)
        self.assertEqual(members[0]["x"], 0)

    def test_durable_positions_claim_race_and_postgres_cas(self):
        groups = PersistentGroups(self.store)
        members = [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)]
        key = groups.register(1134, 0, 500, members)
        player = dict(map_id=1134, instance_id=0, x=2, y=0, z=0)
        packets = []
        self.assertEqual(
            wander_location(
                groups,
                1134,
                0,
                [player],
                [((0, 0, 0), (1, 0, 0))],
                lambda *p: packets.append(p),
                move_probability=1,
                min_steps=1,
                max_steps=1,
            ),
            [key],
        )
        recovered = PersistentGroups(self.reopen())
        self.assertEqual(recovered.available(1134, 0)[0]["members"][0]["x"], 1)
        self.assertFalse(groups.move_members(key, members, members))
        self.assertEqual(groups.register_seed(1134, 0, 500, members), key)
        badseed = deepcopy(members)
        badseed[0]["id"] = -201
        with self.assertRaises(ValueError):
            groups.register_seed(1134, 0, 500, badseed)
        self.assertEqual(
            wander_location(
                groups,
                1134,
                0,
                [player],
                [((1, 0, 0), (0, 0, 0))],
                lambda *p: packets.append(p),
                excluded_ids={-200},
                move_probability=1,
                min_steps=1,
                max_steps=1,
            ),
            [],
        )
        with self.store.connection() as db:
            row = db.execute("SELECT members FROM combat_groups").fetchone()["members"]
            self.assertEqual(row[0]["x"], 1)
        current = groups.available(1134, 0)[0]["members"]
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = groups.claim(key, "generation", fight)
        changed = deepcopy(current)
        changed[0]["x"] = 0
        self.assertFalse(groups.move_members(key, current, changed))
        self.assertEqual(
            wander_location(
                groups,
                1134,
                0,
                [player],
                [((1, 0, 0), (0, 0, 0))],
                lambda *p: packets.append(p),
                move_probability=1,
                min_steps=1,
                max_steps=1,
            ),
            [],
        )
        self.assertEqual(len(packets), 1)
        self.assertTrue(groups.finish(lease, defeated=False))

    def test_probability_threshold_is_independent_for_each_durable_group(self):
        groups = PersistentGroups(self.store)
        first = [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)]
        second = [owned_instance(5525, 1, -201, map_id=1134, x=4, y=0, z=0)]
        first_key = groups.register(1134, 0, 501, first)
        second_key = groups.register(1134, 0, 502, second)
        player = dict(map_id=1134, instance_id=0, x=3, y=0, z=0)
        rng = FixedRng(rolls=(0.249, 0.25))
        packets = []
        moved = wander_location(
            groups,
            1134,
            0,
            [player],
            [((0, 0, 0), (1, 0, 0)), ((4, 0, 0), (5, 0, 0))],
            lambda *packet: packets.append(packet),
            rng=rng,
            move_probability=0.25,
            min_steps=1,
            max_steps=1,
        )
        self.assertEqual(moved, [first_key])
        self.assertEqual(rng.random_calls, 2)
        current = {
            group["key"]: group["members"] for group in groups.available(1134, 0)
        }
        self.assertEqual(current[first_key][0]["x"], 1)
        self.assertEqual(current[second_key][0]["x"], 4)
        self.assertEqual(len(packets), 1)

    def test_path_serializes_one_or_three_verified_height_steps(self):
        member = owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)
        edges = [
            ((0, 0, 0), (1, 0, 2)),
            ((1, 0, 2), (1, 1, 1)),
            ((1, 1, 1), (0, 1, 0)),
        ]
        player = dict(x=10, y=10, z=0)
        for count in (1, 3):
            with self.subTest(steps=count):
                result = plan_path(
                    [member],
                    [player],
                    edges,
                    rng=FixedRng(steps=count),
                    min_steps=1,
                    max_steps=3,
                )
                self.assertIsNotNone(result)
                opcode, body = result["packets"][0]
                decoded = decode_body("in", opcode, body)
                self.assertEqual(opcode, 13852)
                self.assertEqual(decoded["actor_id"], -200)
                self.assertEqual(decoded["step_count"], count)
                self.assertEqual(decoded["start_position"], {"x": 0, "y": 0, "z": 0})
                self.assertEqual(result["members"][0]["z"], (2 if count == 1 else 0))
                self.assertTrue(
                    all(-16 <= step["dz"] <= 15 for step in decoded["steps"])
                )
        # The edge graph ends after step three; no unverified fourth step appears.
        full = plan_path(
            [member],
            [player],
            edges,
            rng=FixedRng(steps=4),
            min_steps=1,
            max_steps=3,
        )
        self.assertEqual(
            decode_body("in", 13852, full["packets"][0][1])["step_count"], 3
        )

        indexed = edge_index(edges)
        expected = plan_path(
            [member],
            [player],
            edges,
            rng=FixedRng(steps=3),
            min_steps=1,
            max_steps=3,
        )
        actual = plan_path(
            [member],
            [player],
            (),
            indexed=indexed,
            rng=FixedRng(steps=3),
            min_steps=1,
            max_steps=3,
        )
        self.assertEqual(actual, expected)

    def test_players_absent_does_not_consume_rng_or_move_group(self):
        groups = PersistentGroups(self.store)
        members = [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)]
        key = groups.register(1134, 0, 503, members)
        rng = FixedRng(rolls=())
        packets = []
        with patch.object(
            self.store,
            "connection",
            side_effect=AssertionError("wander queried without players"),
        ) as connection:
            self.assertEqual(
                wander_location(
                    groups,
                    1134,
                    0,
                    [],
                    [((0, 0, 0), (1, 0, 0))],
                    lambda *packet: packets.append(packet),
                    rng=rng,
                ),
                [],
            )
            connection.assert_not_called()
        self.assertEqual(rng.random_calls, 0)
        self.assertEqual(packets, [])
        self.assertEqual(groups.available(1134, 0)[0]["key"], key)
        self.assertEqual(groups.available(1134, 0)[0]["members"][0]["x"], 0)

    def test_fighting_neighbor_is_blocked_by_one_snapshot_without_available_query(self):
        groups = PersistentGroups(self.store)
        roaming = [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)]
        fighting = [owned_instance(5525, 1, -201, map_id=1134, x=1, y=0, z=0)]
        roaming_key = groups.register(1134, 0, 506, roaming)
        fighting_key = groups.register(1134, 0, 507, fighting)
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = groups.claim(fighting_key, "wander-fight", fight_id)
        player = dict(map_id=1134, instance_id=0, x=3, y=0, z=0)
        emitted = []
        rng = FixedRng(rolls=(0.0,), steps=1)
        with patch.object(
            groups, "snapshot", wraps=groups.snapshot
        ) as snapshot, patch.object(
            groups,
            "available",
            side_effect=AssertionError("wander queried available groups"),
        ):
            moved = wander_location(
                groups,
                1134,
                0,
                [player],
                [((0, 0, 0), (1, 0, 0))],
                lambda *packet: emitted.append(packet),
                rng=rng,
                move_probability=1,
                min_steps=1,
                max_steps=1,
            )
        self.assertEqual(snapshot.call_args_list, [call(1134, 0)])
        self.assertEqual(moved, [])
        self.assertEqual(emitted, [])
        self.assertEqual(rng.random_calls, 1)
        self.assertEqual(groups.available(1134, 0)[0]["key"], roaming_key)
        self.assertEqual(groups.available(1134, 0)[0]["members"][0]["x"], 0)
        self.assertTrue(groups.finish(lease, defeated=False))

    def test_wander_location_reuses_preindexed_geometry_without_recomputing(self):
        groups = PersistentGroups(self.store)
        members = [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)]
        key = groups.register(1134, 0, 505, members)
        edges = [((0, 0, 0), (1, 0, 0))]
        indexed = edge_index(edges)
        emitted = []
        with patch(
            "wakfu_server.monster_wander.edge_index",
            side_effect=AssertionError("rebuilt"),
        ):
            moved = wander_location(
                groups,
                1134,
                0,
                [dict(map_id=1134, instance_id=0, x=3, y=0, z=0)],
                (),
                lambda *packet: emitted.append(packet),
                indexed=indexed,
                rng=FixedRng(rolls=(0.0,), steps=1),
                move_probability=1,
                min_steps=1,
                max_steps=1,
            )
        self.assertEqual(moved, [key])
        self.assertEqual(len(emitted), 1)

    def test_durable_policy_reloads_from_postgres_and_rejects_invalid_shapes(self):
        expected = {
            "interval_seconds": 2,
            "move_probability": 0.6,
            "min_steps": 1,
            "max_steps": 3,
            "radius": 20,
        }
        self.assertEqual(policy(self.store), expected)
        updated = dict(
            expected,
            interval_seconds=9,
            move_probability=0.6,
            min_steps=2,
            max_steps=4,
            radius=25,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_wander'",
                (Jsonb(updated),),
            )
        self.assertEqual(policy(self.store), updated)

        invalid = [
            dict(updated, extra=True),
            dict(updated, interval_seconds="9"),
            dict(updated, interval_seconds=3601),
            dict(updated, move_probability=1.01),
            dict(updated, min_steps=0),
            dict(updated, min_steps=5, max_steps=4),
            dict(updated, radius=1001),
        ]
        for value in invalid:
            with self.subTest(policy=value):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE settings SET value=%s WHERE name='monster_wander'",
                        (Jsonb(value),),
                    )
                with self.assertRaises(ValueError):
                    policy(self.store)

    def test_invalid_terrain_collision_fight_claim_and_harvest_exclusions(self):
        member = owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)
        player = dict(x=5, y=5, z=0)
        rng = FixedRng(steps=1)
        self.assertIsNone(
            plan_path(
                [member],
                [player],
                [((0, 0, 0), (1, 0, 20))],
                rng=rng,
                min_steps=1,
                max_steps=1,
            )
        )
        self.assertIsNone(
            plan_path(
                [member],
                [player],
                [((0, 0, 0), (1, 0, 0))],
                occupied=[(1, 0, 0)],
                rng=FixedRng(steps=1),
                min_steps=1,
                max_steps=1,
            )
        )

        groups = PersistentGroups(self.store)
        key = groups.register(1134, 0, 504, [member])
        rng = FixedRng(rolls=())
        emitted = []
        self.assertEqual(
            wander_location(
                groups,
                1134,
                0,
                [dict(map_id=1134, instance_id=0, x=5, y=5, z=0)],
                [((0, 0, 0), (1, 0, 0))],
                lambda *packet: emitted.append(packet),
                rng=rng,
                excluded_ids={-200},
                move_probability=1,
            ),
            [],
        )
        self.assertEqual(rng.random_calls, 0)
        self.assertEqual(emitted, [])
        current = groups.available(1134, 0)[0]["members"]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = groups.claim(key, "harvest-or-fight", fight_id)
        self.assertFalse(groups.move_members(key, current, [dict(current[0], x=1)]))
        self.assertTrue(groups.finish(lease, defeated=False))

    def test_five_member_group_uses_one_roll_and_keeps_formation(self):
        groups = PersistentGroups(self.store)
        members = [
            owned_instance(
                5525,
                1,
                -200 - index,
                map_id=1134,
                x=index,
                y=0,
                z=0,
            )
            for index in range(5)
        ]
        original = deepcopy(members)
        key = groups.register(1134, 0, 508, members)
        destinations = [(member["x"], 1, 0) for member in members]
        edges = [
            ((member["x"], member["y"], member["z"]), destination)
            for member, destination in zip(members, destinations)
        ]
        rng = FixedRng(rolls=(0.1, 0.249, 0.25, 0.9, 0.01), steps=1)
        emitted = []
        with patch.object(groups, "move_members", wraps=groups.move_members) as cas:
            moved = wander_location(
                groups,
                1134,
                0,
                [dict(map_id=1134, instance_id=0, x=20, y=10, z=0)],
                edges,
                lambda *packet: emitted.append(packet),
                rng=rng,
                move_probability=0.25,
                min_steps=1,
                max_steps=1,
            )

        self.assertEqual(moved, [key])
        self.assertEqual(rng.random_calls, 1)
        cas.assert_called_once()
        current = groups.available(1134, 0)[0]["members"]
        moved_ids = {-200, -201, -202, -203, -204}
        for before, after, destination in zip(original, current, destinations):
            expected = (
                destination
                if before["id"] in moved_ids
                else (before["x"], before["y"], before["z"])
            )
            self.assertEqual((after["x"], after["y"], after["z"]), expected)
            self.assertEqual(after["id"], before["id"])
            self.assertEqual(after["ref"], before["ref"])
        decoded = [decode_body("in", opcode, body) for opcode, body in emitted]
        self.assertEqual(
            [row["actor_id"] for row in decoded], [-200, -201, -202, -203, -204]
        )
        self.assertEqual(len(emitted), 5)

    def test_excluding_one_member_holds_entire_group(self):
        groups = PersistentGroups(self.store)
        members = [
            owned_instance(
                5525,
                1,
                -210 - index,
                map_id=1134,
                x=index * 10,
                y=0,
                z=0,
            )
            for index in range(5)
        ]
        key = groups.register(1134, 0, 509, members)
        edges = [((member["x"], 0, 0), (member["x"], 1, 0)) for member in members]
        rng = FixedRng(rolls=(0.0, 0.0, 0.0, 0.0), steps=1)
        emitted = []
        moved = wander_location(
            groups,
            1134,
            0,
            [dict(map_id=1134, instance_id=0, x=20, y=10, z=0)],
            edges,
            lambda *packet: emitted.append(packet),
            rng=rng,
            excluded_ids={-212},
            move_probability=1,
            min_steps=1,
            max_steps=1,
        )

        self.assertEqual(moved, [])
        self.assertEqual(rng.random_calls, 0)
        current = groups.available(1134, 0)[0]["members"]
        for before, after in zip(members, current):
            expected_y = 0
            self.assertEqual(after["y"], expected_y)
            self.assertEqual(after["id"], before["id"])
            self.assertEqual(after["ref"], before["ref"])
        decoded = [decode_body("in", opcode, body) for opcode, body in emitted]
        self.assertEqual(
            {row["actor_id"] for row in decoded},
            set(),
        )

    def test_failed_group_position_cas_emits_no_packets(self):
        groups = PersistentGroups(self.store)
        members = [
            owned_instance(
                5525,
                1,
                -220 - index,
                map_id=1134,
                x=index,
                y=0,
                z=0,
            )
            for index in range(5)
        ]
        key = groups.register(1134, 0, 510, members)
        edges = [((member["x"], 0, 0), (member["x"], 1, 0)) for member in members]
        emitted = []
        with patch.object(groups, "move_members", return_value=False) as cas:
            moved = wander_location(
                groups,
                1134,
                0,
                [dict(map_id=1134, instance_id=0, x=20, y=10, z=0)],
                edges,
                lambda *packet: emitted.append(packet),
                rng=FixedRng(rolls=(0.0,) * 5, steps=1),
                move_probability=1,
                min_steps=1,
                max_steps=1,
            )

        self.assertEqual(moved, [])
        cas.assert_called_once()
        self.assertEqual(emitted, [])
        persisted = groups.available(1134, 0)[0]
        self.assertEqual(persisted["key"], key)
        self.assertEqual(list(persisted["members"]), members)


class WanderTerritoryTests(unittest.TestCase):
    def test_each_path_step_checks_destination_before_entering_unassigned_cell(self):
        member = dict(id=-200, x=0, y=0, z=0)
        checked = []

        def allowed(cell):
            checked.append(cell)
            return cell == (1, 0, 0)

        result = plan_path(
            [member],
            [dict(x=10, y=0, z=0)],
            [((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (2, 0, 0))],
            rng=FixedRng(steps=3),
            min_steps=1,
            max_steps=3,
            destination_allowed=allowed,
        )
        self.assertEqual(result["members"][0]["x"], 1)
        self.assertEqual(checked, [(1, 0, 0), (2, 0, 0)])
        self.assertEqual(
            decode_body("in", 13852, result["packets"][0][1])["step_count"], 1
        )

    def test_live_wander_rejects_destination_without_persisting_or_publishing(self):
        from threading import RLock
        from unittest.mock import Mock

        groups = Mock()
        groups.lock = RLock()
        groups.snapshot.return_value = [
            dict(
                key=(527, 0, 1),
                status="available",
                members=[dict(id=-200, x=0, y=0, z=0)],
            )
        ]
        emitted = []
        with patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=False,
        ) as allowed:
            moved = wander_location(
                groups,
                527,
                0,
                [dict(map_id=527, instance_id=0, x=10, y=0, z=0)],
                [((0, 0, 0), (1, 0, 0))],
                lambda *packet: emitted.append(packet),
                rng=FixedRng(rolls=(0.0, 0.0), steps=1),
                move_probability=1,
                min_steps=1,
                max_steps=1,
            )
        allowed.assert_called_once_with(527, 0, (1, 0, 0))
        self.assertEqual(moved, [])
        groups.move_members.assert_not_called()
        self.assertEqual(emitted, [])

    def test_native_path_stops_before_returning_to_its_start(self):
        member = dict(id=-201, x=0, y=0, z=0)
        edges = [
            ((0, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (1, 1, 0)),
            ((1, 1, 0), (0, 1, 0)),
            ((0, 1, 0), (0, 0, 0)),
        ]
        result = plan_path(
            [member],
            [dict(x=10, y=10, z=0)],
            edges,
            rng=FixedRng(steps=4),
            min_steps=4,
            max_steps=4,
        )
        decoded = decode_body("in", 13852, result["packets"][0][1])
        self.assertEqual(decoded["step_count"], 3)
        self.assertEqual(decoded["start_position"], {"x": 0, "y": 0, "z": 0})
        self.assertEqual(decoded["end_position"], {"x": 0, "y": 1, "z": 0})
