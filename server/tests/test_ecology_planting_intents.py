"""Async intent cancellation and prepared planting ownership regression tests."""
import json
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.ecology_planting_intents import (
    EcologyPlantingIntents,
    prepare_intents,
)
from wakfu_server.planting_runtime import Plantings
from wakfu_server.planting import SEEDS
from wakfu_server.inventory_items import grant
from wakfu_server.profession_store import ensure_learned


class EcologyPlantingIntentTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = [1000.0]
        self.store.clock = lambda: self.now[0]
        self.account = self.store.register("async-planter", "local-password")["id"]
        self.char = self.store.create_character(self.account, "Async Planter")
        self.gen = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.gen, self.char["id"])
        ensure_learned(
            self.store,
            self.account,
            self.gen,
            self.char["id"],
            [SEEDS[4275]["profession_id"]],
        )
        self.item = grant(
            self.store,
            self.account,
            self.gen,
            self.char["id"],
            reference=4275,
            quantity=2,
            container=self.char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        self.body = struct.pack(
            ">iqii", SEEDS[4275]["action_id"], self.item["uid"], 10, 11
        )
        self.repo = EcologyPlantingIntents(self.store, "boot-a")
        self.runtime = Plantings(self.store, open_test_policy=True)
        self.runtime.ecology_intents = self.repo
        self.snapshot = dict(
            world_epoch="boot-a", players=[self.char], open_planting=True
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='open_planting_probability'",
                (Jsonb(1.0),),
            )

    def prepare(self):
        origin = tuple(self.char[key] for key in ("x", "y", "z"))
        with patch("wakfu_server.planting_cells.authorize", return_value=0), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(outgoing={origin: {(10, 11, 0)}}),
        ):
            return prepare_intents(self.store, self.snapshot)[0]

    def accept(self, db, proposal):
        return self.runtime.begin_prepared(
            self.account,
            self.gen,
            self.char,
            self.body,
            proposal["prepared"],
            lambda *args: 0,
            db=db,
        )

    def test_readonly_prepare_accept_and_complete_debits_once(self):
        self.repo.enqueue(self.account, self.gen, self.char, self.body)
        plan = self.prepare()
        json.dumps(plan)
        self.assertEqual(plan["kind"], "planting_begin")
        self.assertNotIn("inventory_items", plan["prepared"]["character"])
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )
        result = self.repo.apply(plan, self.accept)
        self.assertTrue(result["applied"])
        self.assertEqual(result["packet"][0], 12815)
        self.assertFalse(self.repo.apply(plan, self.accept)["applied"])
        self.now[0] += 3
        self.assertTrue(
            self.runtime.complete(self.account, self.gen, self.char, b"\x02\x00\x02")[
                "applied"
            ]
        )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            1,
        )

    def test_cancel_without_local_occupation_invalidates_late_plan(self):
        self.repo.enqueue(self.account, self.gen, self.char, self.body)
        plan = self.prepare()
        self.assertFalse(self.runtime.cancel(self.char["id"], self.gen))
        callback = Mock()
        self.assertFalse(self.repo.apply(plan, callback)["applied"])
        callback.assert_not_called()

    def test_new_intent_supersedes_previous_and_world_boot_rejects(self):
        self.repo.enqueue(self.account, self.gen, self.char, self.body)
        previous = self.prepare()
        self.repo.enqueue(self.account, self.gen, self.char, self.body)
        self.assertFalse(self.repo.apply(previous, Mock())["applied"])
        current = self.prepare()
        wrong_boot = EcologyPlantingIntents(self.store, "boot-b")
        self.assertFalse(wrong_boot.apply(current, Mock())["applied"])

    def bridge(self, *, in_combat=False):
        import threading
        from wakfu_server.world import World
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.ecology.world_bridge import EcologyWorldBridge
        from wakfu_server.ecology.runtime import configure_domains

        self.sent = []
        world = World(
            lambda _: (1, b"spawn"),
            lambda _: (2, b"remove"),
            lambda peer, opcode, body: self.sent.append((opcode, body)),
        )
        world.join(self.gen, object(), self.char)
        bridge = EcologyWorldBridge(
            store=self.store,
            world=world,
            groups=PersistentGroups(self.store),
            harvests=SimpleNamespace(lock=threading.RLock(), targets={}),
            plantings=self.runtime,
            token="secret",
            combat_sessions=SimpleNamespace(
                lookup_character=lambda _: object() if in_combat else None
            ),
        )
        bridge.epoch = "boot-a"
        self.runtime.ecology_world_epoch = "boot-a"
        return configure_domains(bridge)

    def test_external_runtime_accepts_prepared_intent_and_emits_start(self):
        self.repo.enqueue(self.account, self.gen, self.char, self.body)
        plan = self.prepare()
        bridge = self.bridge()
        result = bridge.handlers["plants"](plan)
        self.assertTrue(result["applied"])
        self.assertIn(12815, [opcode for opcode, _ in self.sent])
        self.assertIn(self.char["id"], self.runtime.pending)
        self.assertTrue(bridge.snapshot()["open_planting"])

    def test_external_runtime_combat_and_replacement_generation_reject(self):
        self.repo.enqueue(self.account, self.gen, self.char, self.body)
        plan = self.prepare()
        bridge = self.bridge(in_combat=True)
        self.assertFalse(bridge.handlers["plants"](plan)["applied"])
        self.assertNotIn(self.char["id"], self.runtime.pending)
        self.repo.enqueue(self.account, self.gen, self.char, self.body)
        plan = self.prepare()
        bridge = self.bridge()
        entry = bridge.world.players[self.char["id"]]
        bridge.world.players[self.char["id"]] = ("replacement", entry[1], entry[2])
        self.assertFalse(bridge.handlers["plants"](plan)["applied"])

    def test_final_seed_and_origin_checks_reject_stale_preparation(self):
        self.repo.enqueue(self.account, self.gen, self.char, self.body)
        plan = self.prepare()
        changed = dict(self.char, x=self.char["x"] + 1)
        with self.assertRaises(ValueError):
            self.runtime.begin_prepared(
                self.account,
                self.gen,
                changed,
                self.body,
                plan["prepared"],
                lambda *args: 0,
            )
        with self.store.connection() as db:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (self.item["uid"],))
        with self.assertRaises(ValueError):
            self.repo.apply(plan, self.accept)
        self.assertNotIn(self.char["id"], self.runtime.pending)


class EcologyIntentCancellationUnitTests(unittest.TestCase):
    def test_empty_movement_cancellation_never_opens_database(self):
        store = SimpleNamespace(
            connection=Mock(side_effect=AssertionError("unexpected SQL"))
        )
        repo = EcologyPlantingIntents(store, "boot")
        repo.cancel(17, "generation")
        store.connection.assert_not_called()

    def test_cancellation_before_insert_visibility_is_applied_after_commit(self):
        from contextlib import contextmanager

        statements = []
        repo = None

        class Connection:
            def execute(self, sql, params):
                statements.append((sql, params))
                if sql.startswith("INSERT INTO ecology_planting_intents"):
                    repo.cancel(17, "generation")

        @contextmanager
        def connection():
            yield Connection()

        repo = EcologyPlantingIntents(SimpleNamespace(connection=connection), "boot")
        character = dict(id=17, account_id=9, map_id=100, instance_id=0, x=1, y=2, z=0)
        identity = repo.enqueue(
            9, "generation", character, struct.pack(">iqii", 1, 10, 2, 2)
        )
        self.assertTrue(
            any(
                "WHERE id=%s AND status='pending'" in sql and params == (identity,)
                for sql, params in statements
            )
        )
        self.assertEqual(repo.active, {})
