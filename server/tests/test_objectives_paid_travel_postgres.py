"""Paid objective travel is server-priced, transactional and dungeon-only."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.objectives import player_actions, player_travel
from wakfu_server.custom_tasks import player_actions as world_actions


class ObjectivesPaidTravelPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("paid-travel-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Travel Main")["id"]
        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.character)
        self.identity = dict(
            account_id=self.account,
            character_id=self.character,
            generation=self.generation,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value='500'::jsonb WHERE name='objectives_travel_cost_kamas'"
            )

    def test_exploration_is_not_travel_but_authored_public_dungeon_is(self):
        revision = "b" * 64
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_catalog_releases(revision,document_count,source_bytes,complete) VALUES(%s,0,0,true)",
                (revision,),
            )
            db.execute(
                "INSERT INTO native_catalog_active(id,revision) VALUES(1,%s)",
                (revision,),
            )
            route = {
                "key": "test-public-route",
                "definition_id": 77,
                "template_id": 1,
                "entry_map_id": 527,
                "entry_object_id": 2,
                "destination_id": 88,
                "start_map_id": 1087,
            }
            config = {"route": route, "version": 1}
            db.execute(
                "INSERT INTO dungeon_runtime_configurations(route_key,policy_version,configuration) VALUES(%s,1,%s)",
                (route["key"], Jsonb(config)),
            )
            db.execute(
                "INSERT INTO dungeon_runtime_active_configurations(route_key,policy_version) VALUES(%s,1)",
                (route["key"],),
            )

        rules = {
            "content-v1.map.527": {"key": "content-v1.map.527", "title": "Map"},
            "content-v1.region.527.42": {
                "key": "content-v1.region.527.42",
                "title": "Territory",
            },
            "content-v1.dungeon.77": {
                "key": "content-v1.dungeon.77",
                "title": "Dungeon",
            },
        }
        documents = {
            "native-transports.json": [{"id": 1, "kind": 1, "x": 10, "y": 20}],
            "native-transport-objects.json": [
                {"id": 1, "map_id": 527, "arrival_heights": [0]}
            ],
            "native-generic-teleporters.json": [
                {
                    "id": 2,
                    "map_id": 527,
                    "x": 11,
                    "y": 20,
                    "z": 0,
                    "destinations": [{"destination_id": 88, "map_id": 1087}],
                }
            ],
            "territory-map-cells.json": {
                "maps": [
                    {"map_id": 527, "regions": [{"region_id": 42, "cells": [[0, 0]]}]}
                ]
            },
        }

        def document(_db, _revision, path):
            return documents.get(path)

        with self.store.connection() as db, patch.object(
            player_travel, "_eligible", return_value=rules
        ), patch.object(player_travel, "_document", side_effect=document), patch.object(
            player_travel,
            "_target",
            side_effect=lambda *_a, **_k: {
                "map_id": 527,
                "instance_id": 0,
                "x": 10,
                "y": 20,
                "z": 0,
            },
        ):
            actions = player_travel.actions(db, self.identity)
            self.assertEqual(
                [action["action_key"] for action in actions], ["travel.dungeon.77"]
            )
            self.assertEqual(actions[0]["cost_kamas"], 500)
            for stale_key in ("travel.map.527", "travel.region.527.42"):
                self.assertEqual(
                    player_travel.actions(db, self.identity, stale_key), []
                )
                with self.assertRaisesRegex(ValueError, "unavailable"):
                    player_travel.resolve(db, self.identity, stale_key)
            resolved = player_travel.resolve(db, self.identity, "travel.dungeon.77")
            self.assertEqual(resolved["target"]["map_id"], 527)

    def test_migration_188_corrects_quote_idempotently_without_changing_wallet(self):
        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "188_objectives_travel_cost_500.sql"
        ).read_text()
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value='700'::jsonb WHERE name='objectives_travel_cost_kamas'"
            )
            db.execute(
                "UPDATE account_wallets SET kamas=12345 WHERE account_id=%s",
                (self.account,),
            )
            db.execute(migration)
            first_price = db.execute(
                "SELECT value FROM settings WHERE name='objectives_travel_cost_kamas'"
            ).fetchone()["value"]
            first_wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
            db.execute(migration)
            second_price = db.execute(
                "SELECT value FROM settings WHERE name='objectives_travel_cost_kamas'"
            ).fetchone()["value"]
            second_wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
        self.assertEqual((first_price, second_price), (500, 500))
        self.assertEqual((first_wallet, second_wallet), (12345, 12345))

    def _queue_travel(self, request_id, *, cost=500):
        action = {
            "key": "travel.dungeon.77",
            "label": "Go to entrance: Test Dungeon",
            "kind": "travel",
            "enabled": True,
            "target": {
                "kind": "travel",
                "destination": {
                    "map_id": 527,
                    "instance_id": 0,
                    "x": 10,
                    "y": 20,
                    "z": 0,
                },
                "cost_kamas": cost,
            },
        }
        with self.store.connection() as db, patch.object(
            player_actions, "allowed_actions", return_value=[action]
        ):
            return player_actions.enqueue(
                db, self.identity, "travel.dungeon.77", request_id
            )

    def _claim(self, receipt_id):
        with self.store.connection() as db:
            return world_actions.claim(db, self.identity)

    def test_success_debits_once_and_movement_failure_rolls_back_charge(self):
        start = self.store.character(self.account, self.character)
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=1400000 WHERE account_id=%s",
                (self.account,),
            )
        receipt = self._queue_travel("paid-once")
        action = self._claim(receipt["id"])
        self.assertEqual(action["id"], receipt["id"])
        destination = action["target"]["destination"]
        with self.store.connection() as db:
            remaining = world_actions.charge_travel(
                db, action, action["target"]["cost_kamas"]
            )
            moved = self.store.transition_map_in_transaction(
                db, self.account, self.generation, self.character, start, destination
            )
            self.assertTrue(
                world_actions.finish(
                    db,
                    action,
                    {
                        "success": True,
                        "message": "Travel completed.",
                        "map_id": destination["map_id"],
                        "instance_id": destination["instance_id"],
                        "cost_kamas": 500,
                    },
                )
            )
        self.assertEqual(remaining, 1399500)
        self.assertEqual((moved["map_id"], moved["x"], moved["y"]), (527, 10, 20))
        with self.store.connection() as db:
            wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
            replay = player_actions.enqueue(
                db, self.identity, "travel.dungeon.77", "paid-once"
            )
            self.assertIsNone(world_actions.claim(db, self.identity))
        self.assertEqual(wallet, 1399500)
        self.assertEqual(replay["id"], receipt["id"])

        # A failed transition occurs after the debit attempt, but both live in
        # one transaction, so neither the wallet nor position can partially move.
        second = self._queue_travel("paid-rollback")
        second_action = self._claim(second["id"])
        original = self.store.character(self.account, self.character)
        with self.assertRaisesRegex(ValueError, "Invalid map destination"):
            with self.store.connection() as db:
                world_actions.charge_travel(db, second_action, 500)
                self.store.transition_map_in_transaction(
                    db,
                    self.account,
                    self.generation,
                    self.character,
                    original,
                    {"map_id": 527, "instance_id": 0, "x": 10.5, "y": 20, "z": 0},
                )
        unchanged = self.store.character(self.account, self.character)
        with self.store.connection() as db:
            wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
            row = db.execute(
                "SELECT status FROM objectives_player_actions WHERE id=%s",
                (second["id"],),
            ).fetchone()
            self.assertTrue(
                world_actions.finish(
                    db, second_action, {"success": False, "error": "Travel failed"}
                )
            )
        self.assertEqual(wallet, 1399500)
        self.assertEqual(
            (unchanged["map_id"], unchanged["x"], unchanged["y"]),
            (original["map_id"], original["x"], original["y"]),
        )
        self.assertEqual(row["status"], "running")

    def test_insufficient_funds_reject_without_charging_and_price_is_server_supplied(
        self,
    ):
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=499 WHERE account_id=%s",
                (self.account,),
            )
        receipt = self._queue_travel("too-poor")
        action = self._claim(receipt["id"])
        with self.assertRaisesRegex(ValueError, "costs 500 kamas"):
            with self.store.connection() as db:
                world_actions.charge_travel(db, action, action["target"]["cost_kamas"])
        with self.store.connection() as db:
            wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
            self.assertTrue(
                world_actions.finish(
                    db, action, {"success": False, "error": "Insufficient kamas"}
                )
            )
            stored = db.execute(
                "SELECT status,target FROM objectives_player_actions WHERE id=%s",
                (receipt["id"],),
            ).fetchone()
        self.assertEqual(wallet, 499)
        self.assertEqual(stored["status"], "rejected")
        self.assertEqual(stored["target"]["cost_kamas"], 500)

    def test_charge_rejects_untrusted_invalid_cost_values(self):
        for cost in (True, 0, -1, 2**63):
            with self.subTest(cost=cost), self.assertRaisesRegex(
                ValueError, "Invalid adventures travel price"
            ):
                with self.store.connection() as db:
                    world_actions.charge_travel(db, {"id": "unused"}, cost)

    def test_pvp_actions_remain_free_and_use_the_destination_override_path(self):
        action = {
            "key": "pvp.meet.42",
            "label": "Meet opponent",
            "kind": "pvp",
            "enabled": True,
            "target": {"kind": "pvp", "event_id": 42, "action": "meet"},
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=765432 WHERE account_id=%s",
                (self.account,),
            )
        with self.store.connection() as db, patch.object(
            player_actions, "allowed_actions", return_value=[action]
        ):
            receipt = player_actions.enqueue(
                db, self.identity, "pvp.meet.42", "free-pvp-meet"
            )
            target = db.execute(
                "SELECT target FROM objectives_player_actions WHERE id=%s",
                (receipt["id"],),
            ).fetchone()["target"]
            balance = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
        self.assertEqual(target["kind"], "pvp")
        self.assertNotIn("cost_kamas", target)
        self.assertEqual(balance, 765432)

        # PvP meeting uses the same safe map transition helper with a resolver
        # override. The paid branch is reachable only for authored travel
        # destinations resolved by player_travel.
        source = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        functions = [
            node
            for node in ast.walk(source)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        travel = next(
            node for node in functions if node.name == "execute_objectives_travel"
        )
        pvp = next(node for node in functions if node.name == "execute_objectives_pvp")

        def charge(nodes):
            return any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "charge_travel"
                for node in nodes
                for child in ast.walk(node)
            )

        price_guard = next(
            node
            for node in ast.walk(travel)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "resolve_destination"
        )
        self.assertIsNotNone(price_guard)
        self.assertTrue(charge(price_guard.body))
        self.assertFalse(charge(price_guard.orelse))
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "execute_objectives_travel"
                and any(
                    keyword.arg == "resolve_destination" for keyword in node.keywords
                )
                for node in ast.walk(pvp)
            )
        )


if __name__ == "__main__":
    unittest.main()
