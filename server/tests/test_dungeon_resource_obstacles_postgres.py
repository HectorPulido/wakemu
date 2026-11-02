"""Private native resource lifecycle against disposable PostgreSQL only."""
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import struct
import threading
from unittest.mock import patch

from postgres_case import PostgresCase
from dungeon_resource_fixture import PhysicalChoiceFixture


class DungeonResourceProviderPostgresTests(PhysicalChoiceFixture, PostgresCase):
    def setUp(self):
        super().setUp()
        recipe = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "dungeon139"
                / "resource-prepare-input.json"
            ).read_text()
        )["prepare_kwargs"]
        self.build_choice_fixture(
            configuration_override=dict(
                compiled_plan=recipe["plan"],
                topology=recipe["topology"],
                route=recipe["route"],
                provenance=recipe["provenance"],
                level_policy=recipe["level_policy"],
            )
        )
        self.clock = 2_000_000_000.0
        self.store.clock = lambda: self.clock

    def rows(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM dungeon_resource_obstacles WHERE instance_id=%s ORDER BY obstacle_key",
                (self.instance_id,),
            ).fetchall()

    def stock(self, index, ref):
        with self.store.connection() as db:
            return db.execute(
                "SELECT COALESCE(sum(quantity),0) AS n FROM inventory_items WHERE character_id=%s AND reference=%s",
                (self.members[index]["character"]["id"], ref),
            ).fetchone()["n"]

    def grant(self, index, ref, quantity):
        from wakfu_server.harvest_inventory import grant

        member = self.members[index]
        with self.store.connection() as db:
            grant(
                db,
                self.store.character(member["account"], member["character"]["id"], db),
                ref,
                quantity,
            )

    def position(self, index, point):
        member = self.members[index]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                (*point, member["character"]["id"]),
            )
        member["character"] = self.store.character(
            member["account"], member["character"]["id"]
        )
        self.positions.attach(
            member["account"], member["generation"], member["character"]
        )

    def prepared(self, index, obstacle, ref):
        from wakfu_server import resource_collect
        from wakfu_server.wire import proto_field

        member = self.members[index]
        row = next(r for r in self.rows() if r["obstacle_key"] == obstacle)
        action = next(
            a
            for a in self.config["topology"]["resource_obstacles"]["actions"]
            if a["stage"] == row["current_stage"] and a["item_reference"] == ref
        )
        body = b"".join(
            proto_field(tag, v if v >= 0 else 2**64 + v)
            for tag, v in [(8, action["action_id"]), (16, row["x"]), (24, row["y"])]
        )
        edges = {(tuple(a), tuple(b)) for a, b in self.geometry["edges"]}

        def reachable(actor, resource):
            return (
                tuple(actor[k] for k in ("x", "y", "z")),
                tuple(resource[k] for k in ("x", "y", "z")),
            ) in edges

        return resource_collect.prepare(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            body,
            reachable=reachable,
        )

    def reserve(self, index, prepared):
        from wakfu_server.resource_collect import reserve

        member = self.members[index]
        return reserve(self.store, member["account"], member["generation"], prepared)

    def complete(self, ticket, *, cancel=False):
        from wakfu_server import resource_collect, dungeon_runtime

        return resource_collect.complete(
            self.store,
            ticket,
            struct.pack(">Bh", 3 if cancel else 2, 3),
            on_dungeon_unlocked=lambda db, iid: dungeon_runtime.ensure_current_room(
                db, self.groups, iid, self.geometry
            ),
        )

    def assert_group_count(self, expected):
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                    (self.instance_id,),
                ).fetchone()["n"],
                expected,
            )
        self.assertEqual(len(self.groups.available(301, self.instance_id)), expected)

    def collision(self, index, target):
        from wakfu_server import dungeon_resource_obstacles

        member = self.members[index]
        key = (member["account"], member["generation"], member["character"]["id"])
        start = self.positions.entries[key]["current"]
        p = tuple(start[k] for k in ("x", "y", "z"))
        self.assertIn(
            (p, tuple(target)),
            {(tuple(a), tuple(b)) for a, b in self.geometry["edges"]},
        )
        move = dict(
            start_position=dict(zip(("x", "y", "z"), p)),
            steps=[dict(zip(("dx", "dy", "dz"), (target[i] - p[i] for i in range(3))))],
        )
        before = copy.deepcopy(self.positions.entries[key])
        with self.store.connection() as db:
            try:
                dungeon_resource_obstacles.validate_movement(
                    db, self.config, self.instance_id, move
                )
            except ValueError:
                self.assertEqual(self.positions.entries[key], before)
                raise

    def test_four_rocks_mega_native_states_reconnect_collision_and_first_group(self):
        from wakfu_server import dungeon_runtime, resource_collect
        from wakfu_server.planting_runtime import state_packet

        self.grant(0, 10303, 8)
        original = self.rows()
        self.assertEqual(len(original), 4)
        self.assert_group_count(0)
        for i, row in enumerate(original):
            point = (row["x"], row["y"], row["z"])
            previous = (
                (-2, -22, 0)
                if i == 0
                else (original[i - 1]["x"], original[i - 1]["y"], original[i - 1]["z"])
            )
            self.position(0, previous)
            with self.assertRaises(ValueError):
                self.collision(0, point)
            for stage in [2, 0]:
                ticket = self.reserve(0, self.prepared(0, row["obstacle_key"], 10303))
                self.assertEqual(ticket["duration_ms"], 6000)
                self.assertEqual(
                    self.stock(0, 10303), 8 - (2 * i + (0 if stage == 2 else 1))
                )
                self.clock += 6.01
                result = self.complete(ticket)
                self.assertTrue(result["applied"])
                self.assertEqual(result["outcome"]["stage"], stage)
                self.assertEqual(result["world_packets"][0][0], 12782)
                self.assertEqual(
                    result["world_packets"], [state_packet(result["event"], stage)]
                )
                self.assertFalse(self.complete(ticket)["applied"])
                expected_group = int(i == 3 and stage == 0)
                self.assert_group_count(expected_group)
                if not expected_group:
                    self.assertIsNone(result["dungeon_group"])
                # A fresh Store reads durable resource state, not a process cache.
                reopened = self.reopen()
                with reopened.connection() as db:
                    replay = dungeon_runtime.ensure_current_room(
                        db, self.groups, self.instance_id, self.geometry
                    )
                    if not expected_group:
                        self.assertIsNone(replay)
                self.assertEqual(
                    [r["resource_uid"] for r in self.rows()],
                    [r["resource_uid"] for r in original],
                )
            self.collision(0, point)
        self.assertEqual(self.stock(0, 10303), 0)
        with self.store.connection() as db:
            replay = dungeon_runtime.ensure_current_room(
                db, self.groups, self.instance_id, self.geometry
            )
            self.assertTrue(replay["replay"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planted_resources WHERE instance_id=%s",
                    (self.instance_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts WHERE character_id=%s",
                    (self.members[0]["character"]["id"],),
                ).fetchone()["n"],
                8,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planting_growth_outbox WHERE resource->>'instance_id'=%s",
                    (str(self.instance_id),),
                ).fetchone()["n"],
                4,
            )
        self.assertEqual(
            [r["resource_uid"] for r in self.rows()],
            [r["resource_uid"] for r in original],
        )
        self.assertTrue(all(r["current_stage"] == 0 for r in self.rows()))
        self.assertTrue(
            all(
                tuple(m[k] for k in ("x", "y", "z"))
                in set(
                    map(
                        tuple,
                        self.config["topology"]["rooms"][0]["encounter_region"][
                            "cells"
                        ],
                    )
                )
                for m in replay["members"]
            )
        )

    def test_cancel_early_failure_and_sql_rollback_do_not_spend_or_advance(self):
        from wakfu_server import dungeon_resource_obstacles, resource_collect

        self.grant(0, 11793, 1)
        before = self.rows()
        ticket = self.reserve(0, self.prepared(0, "initial_rock_1", 11793))
        self.assertFalse(self.complete(ticket, cancel=True)["applied"])
        self.assertEqual(self.stock(0, 11793), 1)
        ticket = self.reserve(0, self.prepared(0, "initial_rock_1", 11793))
        with self.assertRaises(resource_collect.HarvestNotReady):
            self.complete(ticket)
        self.assertEqual(self.stock(0, 11793), 1)
        self.clock += 6.01
        original = dungeon_resource_obstacles.apply

        def fail_after_write(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("Injected fault after debit/stage/outbox before commit")

        with patch.object(
            dungeon_resource_obstacles, "apply", side_effect=fail_after_write
        ):
            with self.assertRaisesRegex(ValueError, "Injected fault"):
                self.complete(ticket)
        self.assertEqual(self.stock(0, 11793), 1)
        self.assertEqual(self.rows(), before)
        self.assert_group_count(0)
        result = self.complete(ticket)
        self.assertTrue(result["applied"])
        self.assertEqual(result["outcome"]["stage"], 0)
        self.assertEqual(self.stock(0, 11793), 0)
        self.assert_group_count(0)
        with self.assertRaises(ValueError):
            self.prepared(0, "initial_rock_2", 11793)

    def test_two_participants_last_bombs_one_occupation_and_duplicate_completion(self):
        self.grant(0, 11793, 1)
        self.grant(1, 11793, 1)
        prepared = [self.prepared(i, "initial_rock_1", 11793) for i in range(2)]
        barrier = threading.Barrier(2)

        def attempt(index):
            barrier.wait(timeout=5)
            try:
                return index, self.reserve(index, prepared[index]), None
            except ValueError as error:
                return index, None, str(error)

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(attempt, range(2)))
        winners = [r for r in results if r[1] is not None]
        self.assertEqual(len(winners), 1)
        winner, ticket, _ = winners[0]
        loser = 1 - winner
        self.assertEqual(self.stock(winner, 11793), 1)
        self.assertEqual(self.stock(loser, 11793), 1)
        self.clock += 6.01
        with ThreadPoolExecutor(max_workers=2) as workers:
            done = list(workers.map(lambda _: self.complete(ticket), range(2)))
        self.assertEqual(sum(bool(r["applied"]) for r in done), 1)
        self.assertEqual(self.stock(winner, 11793), 0)
        self.assertEqual(self.stock(loser, 11793), 1)
        self.assertEqual(sum(r["current_stage"] == 0 for r in self.rows()), 1)
        self.assert_group_count(0)

    def test_owned_partial_rock_cannot_regrow_and_normal_outbox_publishes_once(self):
        from wakfu_server.planting_runtime import Plantings
        from wakfu_server import dungeon_resource_obstacles

        invalid = copy.deepcopy(self.config)
        first = invalid["topology"]["resource_obstacles"]["placements"][0]["position"]
        alias = [first[0], first[1], first[2] + 1]
        invalid["topology"]["rooms"][0]["cells"].append(alias)
        invalid["topology"]["resource_obstacles"]["placements"][1]["position"] = alias
        with self.assertRaisesRegex(ValueError, "aliases an occupied XY"):
            dungeon_resource_obstacles.policy(invalid)
        self.grant(0, 10303, 2)
        ticket = self.reserve(0, self.prepared(0, "initial_rock_1", 10303))
        self.clock += 6.01
        result = self.complete(ticket)
        self.assertEqual(result["outcome"]["stage"], 2)
        with self.store.connection() as db:
            # Counterfactual unrelated native-valid growth rule. Ownership must
            # exclude it; this is not a claim about official Toudur regrowth.
            db.execute(
                "INSERT INTO resource_growth_transitions(resource_reference,from_stage,to_stage,delay_ms,probability) "
                "VALUES(368,2,4,1000,1) ON CONFLICT DO NOTHING"
            )
            self.assertEqual(
                dungeon_resource_obstacles.owned_uids(db),
                frozenset(r["resource_uid"] for r in self.rows()),
            )
        self.clock += 2
        published = []
        worker = Plantings(self.store)
        first = worker.mature(self.groups, publish=published.append)
        second = worker.publish_growth(self.groups, publish=published.append)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(first[0]["packets"][0][0], 12782)
        self.assertEqual(self.rows()[0]["current_stage"], 2)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT stage FROM planted_resources WHERE resource_uid=%s",
                    (self.rows()[0]["resource_uid"],),
                ).fetchone()["stage"],
                2,
            )
        self.assert_group_count(0)
