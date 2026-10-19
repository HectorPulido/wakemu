"""Live public positions must survive asynchronous planting preparation."""
import struct
import threading
import time
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.planting_location import owned_character
from wakfu_server.position_buffer import Positions
from wakfu_server.world import World
from wakfu_server.inventory_items import grant
from wakfu_server.planting import SEEDS
from wakfu_server.planting import complete as complete_planting
from wakfu_server.planting_location import active_character
from wakfu_server.planting_runtime import Plantings
from wakfu_server.profession_store import ensure_learned
from wakfu_server.ecology_planting_intents import (
    EcologyPlantingIntents,
    prepare_intents,
)


class EcologyPlantingLiveOriginTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("live-origin", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Live Origin")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.now = [1000.0]
        self.store.clock = lambda: self.now[0]
        seed = SEEDS[4275]
        ensure_learned(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            [seed["profession_id"]],
        )
        self.item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=seed["item_reference"],
            quantity=2,
            container=self.character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        self.body = struct.pack(">iqii", seed["action_id"], self.item["uid"], 10, 11)
        self.intents = EcologyPlantingIntents(self.store, "live-origin-epoch")

    def make_world_and_positions(self):
        leases = {(self.account, self.generation, self.character["id"])}
        positions = Positions(self.store, lease_active=lambda *key: key in leases)
        positions.attach(self.account, self.generation, self.character)
        world = World(
            lambda _: (1, b"spawn"),
            lambda _: (2, b"remove"),
            lambda *_: None,
        )
        world.join(self.generation, object(), self.character)
        return world, positions

    def set_fast_success_policy(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='planting_duration_ms'",
                (Jsonb(1),),
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name='open_planting_probability'",
                (Jsonb(1.0),),
            )

    def database_now_ms(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT (extract(epoch FROM clock_timestamp()) * 1000)::bigint AS value"
            ).fetchone()["value"]

    def test_live_public_position_is_used_instead_of_stale_sql_location(self):
        """An intent captured after movement must prepare from that same origin."""
        live = dict(self.character, x=self.character["x"] + 1)
        intent_id = self.intents.enqueue(self.account, self.generation, live, self.body)
        snapshot = {
            "world_epoch": "live-origin-epoch",
            "players": [
                {
                    key: live[key]
                    for key in (
                        "id",
                        "account_id",
                        "map_id",
                        "instance_id",
                        "x",
                        "y",
                        "z",
                    )
                }
            ],
            "open_planting": True,
            "started_at_ms": self.database_now_ms(),
        }
        source = tuple(live[key] for key in ("x", "y", "z"))
        with patch("wakfu_server.planting_cells.authorize", return_value=0), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(outgoing={source: {(10, 11, 0)}}),
        ):
            proposal = next(
                plan
                for plan in prepare_intents(self.store, snapshot)
                if plan["intent_id"] == intent_id
            )

        self.assertEqual(proposal["kind"], "planting_begin", proposal)
        self.assertEqual(
            tuple(proposal["prepared"]["character"][key] for key in ("x", "y", "z")),
            source,
        )

    def test_dirty_position_survives_sql_refresh_and_completion_debits_once(self):
        """A successful async planting cannot put the owner back at stale SQL xyz."""
        self.set_fast_success_policy()
        world, positions = self.make_world_and_positions()
        start = {key: self.character[key] for key in ("x", "y", "z")}
        # A one-cell 13331 here represents the native planting autoapproach
        # that completes before the following 13220 intent is enqueued.
        destination = dict(start, x=start["x"] + 1, direction=3)
        positions.move(
            self.account, self.generation, self.character["id"], start, destination
        )
        # This is the raw SQL reload performed after async work. Merge the
        # authoritative position buffer before refreshing the live World entry.
        refreshed = owned_character(
            self.store.character(self.account, self.character["id"]),
            world,
            positions,
            store=self.store,
            generation=self.generation,
        )
        world.refresh_location(self.generation, refreshed)
        self.assertEqual(
            (refreshed["x"], refreshed["y"], refreshed["z"], refreshed["direction"]),
            (destination["x"], destination["y"], destination["z"], 3),
        )
        self.assertEqual(world.ecology_snapshot()[0]["x"], destination["x"])

        intent_id = self.intents.enqueue(
            self.account, self.generation, refreshed, self.body
        )
        snapshot = dict(
            world_epoch="live-origin-epoch",
            players=world.ecology_snapshot(),
            open_planting=True,
            started_at_ms=self.database_now_ms(),
        )
        source = tuple(destination[key] for key in ("x", "y", "z"))
        with patch("wakfu_server.planting_cells.authorize", return_value=0), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(outgoing={source: {(10, 11, 0)}}),
        ):
            proposal = next(
                plan
                for plan in prepare_intents(self.store, snapshot)
                if plan["intent_id"] == intent_id
            )
        self.assertEqual(proposal["kind"], "planting_begin", proposal)
        self.assertEqual(proposal["prepared"]["character"]["x"], destination["x"])

        runtime = Plantings(self.store, open_test_policy=True)
        runtime.ecology_intents = self.intents
        runtime.location_context = lambda stored: owned_character(
            stored, world, positions, store=self.store, generation=self.generation
        )

        def accept(db, plan):
            current = owned_character(
                self.store.character(self.account, self.character["id"], db),
                world,
                positions,
                store=self.store,
                generation=self.generation,
            )
            return runtime.begin_prepared(
                self.account,
                self.generation,
                current,
                self.body,
                plan["prepared"],
                lambda *_: 0,
                db=db,
            )

        accepted = self.intents.apply(proposal, accept)
        self.assertTrue(accepted["applied"])
        ticket = runtime.pending[self.character["id"]]
        operation_id = ticket["token"]
        self.now[0] += 2
        completed = runtime.complete(
            self.account,
            self.generation,
            proposal["prepared"]["character"],
            b"\x02\x00\x02",
        )
        self.assertTrue(completed["applied"])
        self.assertTrue(completed["success"])
        self.assertEqual(
            tuple(completed["character"][key] for key in ("x", "y", "z", "direction")),
            (destination["x"], destination["y"], destination["z"], 3),
        )
        context_updates = [
            (opcode, payload)
            for opcode, payload in completed["packets"]
            if opcode == 13574
        ]
        for opcode, payload in context_updates:
            world.update(
                self.generation,
                completed["character"],
                opcode,
                payload,
                include_sender=False,
            )
        self.assertEqual(world.ecology_snapshot()[0]["x"], destination["x"])

        # The duplicate durable completion returns its receipt without another
        # inventory debit, even after the worker's SQL refresh.
        duplicate = complete_planting(
            self.store,
            self.account,
            self.generation,
            proposal["prepared"],
            operation_id=operation_id,
            stage=1,
            creation_time=1002000,
            result_prefix=(self.character["id"], SEEDS[4275]["action_id"]),
            probability=ticket["probability"],
            location_context=runtime.location_context,
        )
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"][
                0
            ]["quantity"],
            1,
        )
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["x"],
            self.character["x"],
            "public buffered movement remains unpersisted by this planting refresh",
        )
        after = owned_character(
            self.store.character(self.account, self.character["id"]),
            world,
            positions,
            store=self.store,
            generation=self.generation,
        )
        world.refresh_location(self.generation, after)
        self.assertEqual(world.ecology_snapshot()[0]["x"], destination["x"])

    def test_real_movement_after_enqueue_rejects_old_origin(self):
        world, positions = self.make_world_and_positions()
        start = {key: self.character[key] for key in ("x", "y", "z")}
        first = dict(start, x=start["x"] + 1, direction=3)
        positions.move(
            self.account, self.generation, self.character["id"], start, first
        )
        captured = owned_character(
            self.store.character(self.account, self.character["id"]),
            world,
            positions,
            store=self.store,
            generation=self.generation,
        )
        world.refresh_location(self.generation, captured)
        intent_id = self.intents.enqueue(
            self.account, self.generation, captured, self.body
        )

        second = dict(first, x=first["x"] + 1, direction=5)
        positions.move(
            self.account, self.generation, self.character["id"], first, second
        )
        moved = owned_character(
            self.store.character(self.account, self.character["id"]),
            world,
            positions,
            store=self.store,
            generation=self.generation,
        )
        world.refresh_location(self.generation, moved)
        with patch("wakfu_server.planting_cells.authorize", return_value=0), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(
                outgoing={(second["x"], second["y"], second["z"]): {(10, 11, 0)}}
            ),
        ):
            proposal = next(
                plan
                for plan in prepare_intents(
                    self.store,
                    dict(
                        world_epoch="live-origin-epoch",
                        players=world.ecology_snapshot(),
                        open_planting=True,
                        started_at_ms=self.database_now_ms(),
                    ),
                )
                if plan["intent_id"] == intent_id
            )
        self.assertEqual(proposal["kind"], "planting_rejected")
        self.assertEqual(
            proposal["error"], "Planting origin changed during preparation"
        )

    def test_intent_created_after_snapshot_cutoff_is_deferred(self):
        """A late intent waits for the next snapshot, even in an old SQL txn."""
        with self.store.connection() as db:
            # Starting this transaction before the cutoff exposes PostgreSQL's
            # CURRENT_TIMESTAMP transaction-start semantics.
            cutoff = db.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
            snapshot = {
                "world_epoch": "live-origin-epoch",
                "players": [
                    {
                        key: self.character[key]
                        for key in (
                            "id",
                            "account_id",
                            "map_id",
                            "instance_id",
                            "x",
                            "y",
                            "z",
                        )
                    }
                ],
                "open_planting": True,
                "started_at_ms": int(cutoff.timestamp() * 1000),
            }
            time.sleep(0.05)

            @contextmanager
            def existing_transaction(*_args, **_kwargs):
                yield db

            with patch.object(
                self.store, "connection", side_effect=existing_transaction
            ):
                intent_id = self.intents.enqueue(
                    self.account, self.generation, self.character, self.body
                )

        source = tuple(self.character[key] for key in ("x", "y", "z"))
        with patch("wakfu_server.planting_cells.authorize", return_value=0), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(outgoing={source: {(10, 11, 0)}}),
        ):
            proposals = prepare_intents(self.store, snapshot)

        self.assertEqual(
            proposals, [], f"post-cutoff intent {intent_id} was not deferred"
        )
        quantity = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ][0]["quantity"]
        time.sleep(0.01)
        next_snapshot = dict(snapshot, started_at_ms=self.database_now_ms())
        with patch("wakfu_server.planting_cells.authorize", return_value=0), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(outgoing={source: {(10, 11, 0)}}),
        ):
            next_proposals = prepare_intents(self.store, next_snapshot)
        self.assertEqual(len(next_proposals), 1)
        self.assertEqual(next_proposals[0]["intent_id"], intent_id)
        self.assertEqual(next_proposals[0]["kind"], "planting_begin")
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"][
                0
            ]["quantity"],
            quantity,
            "deferral and preparation must not debit the seed",
        )

    def test_worker_rejects_missing_or_invalid_snapshot_start_time(self):
        snapshots = [{"world_epoch": "live-origin-epoch", "players": []}]
        snapshots.extend(
            {
                "world_epoch": "live-origin-epoch",
                "players": [],
                "started_at_ms": value,
            }
            for value in (None, 0, -1, True, 1.5, "123", 2**53)
        )
        for snapshot in snapshots:
            with self.subTest(started_at_ms=snapshot.get("started_at_ms", "missing")):
                with patch.object(
                    self.store,
                    "connection",
                    side_effect=AssertionError("invalid cutoff must fail before SQL"),
                ):
                    with self.assertRaisesRegex(ValueError, "snapshot start time"):
                        prepare_intents(self.store, snapshot)

    def test_worker_requires_unique_account_matched_expected_live_origin(self):
        live = {
            key: self.character[key]
            for key in ("id", "account_id", "map_id", "instance_id", "x", "y", "z")
        }
        expected = {key: live[key] for key in ("map_id", "instance_id", "x", "y", "z")}
        stored = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            active_character(
                stored, [live], store=self.store, expected_location=expected
            )["x"],
            live["x"],
        )
        with self.assertRaisesRegex(ValueError, "one active actor"):
            active_character(stored, [], store=self.store, expected_location=expected)
        with self.assertRaisesRegex(ValueError, "one active actor"):
            active_character(
                stored, [live, dict(live)], store=self.store, expected_location=expected
            )
        with self.assertRaisesRegex(ValueError, "account"):
            active_character(
                stored, [dict(live, account_id=self.account + 1)], store=self.store
            )
        with self.assertRaisesRegex(ValueError, "origin changed"):
            active_character(
                stored,
                [dict(live, x=live["x"] + 1)],
                store=self.store,
                expected_location=expected,
            )

    def test_owned_location_rejects_replaced_world_generation(self):
        from unittest.mock import Mock

        world, _ = self.make_world_and_positions()
        positions = Mock()
        peer = world.players[self.character["id"]][1]
        replacement = self.generation + "-replacement"
        world.players[self.character["id"]] = (replacement, peer, dict(self.character))
        with self.assertRaisesRegex(ValueError, "no longer active"):
            owned_character(
                self.store.character(self.account, self.character["id"]),
                world,
                positions,
                store=self.store,
                generation=self.generation,
            )
        positions.merge.assert_not_called()


class EcologySnapshotCutoffOrderTests(unittest.TestCase):
    def test_cutoff_clock_is_sampled_before_world_snapshot(self):
        from wakfu_server.ecology.world_bridge import EcologyWorldBridge

        events = []
        clock_values = iter((1000.001, 1000.009))

        def clock():
            events.append("clock")
            return next(clock_values)

        class World:
            def ecology_snapshot(self):
                events.append("world")
                return []

        bridge = EcologyWorldBridge(
            store=object(),
            world=World(),
            groups=object(),
            harvests=SimpleNamespace(lock=threading.RLock(), targets=set()),
            plantings=SimpleNamespace(growth_seconds=0, open_test_policy=True),
            token="test-token",
            clock=clock,
        )

        snapshot = bridge.snapshot()

        self.assertEqual(events, ["clock", "world", "clock"])
        self.assertEqual(snapshot["started_at_ms"], 1_000_001)
        self.assertEqual(snapshot["now_ms"], 1_000_009)


if __name__ == "__main__":
    unittest.main()
