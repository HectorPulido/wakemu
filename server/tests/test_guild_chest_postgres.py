"""Opt-in isolated PostgreSQL tests for durable guild chest custody."""
import os
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
import test_guild_service_postgres as guild_fixture
from wakfu_server.characters.guild_chest import (
    load,
    move,
    snapshot,
    transfer,
    transfer_money,
)
from wakfu_server.characters.guild_service import GuildService


class GuildChestPostgresTests(PostgresCase):
    _player = guild_fixture.GuildServicePostgresTests._player
    _create = guild_fixture.GuildServicePostgresTests._create

    def setUp(self):
        if os.environ.get("WAKFU_RUN_GUILD_POSTGRES_TESTS") != "1":
            self.skipTest(
                "Set WAKFU_RUN_GUILD_POSTGRES_TESTS=1 for isolated guild DB tests"
            )
        super().setUp()
        from wakfu_server import native_catalog

        exchange_items = {
            str(reference): {
                "reference": reference,
                "binding_template": {"default_eKo": False, "enum": "NOT_BOUND"},
                "raw_criteria": {"EXCHANGE": None},
            }
            for reference in (2504, 16942)
        }

        def synthetic_catalog(path):
            if path.name == "item-stack-rules.json":
                return {
                    "items": [
                        {"reference": reference, "maximum": 99}
                        for reference in (2504, 16942)
                    ]
                }
            if path.name == "item-exchange-metadata.json":
                return {
                    "errors": 0,
                    "raw_records": 2,
                    "loaded_records": 2,
                    "items": exchange_items,
                }
            raise AssertionError(f"Unexpected native catalog path: {path}")

        exchange_name = "wakfu_server.exchange_rules"
        move_name = "wakfu_server.inventory_move"
        prior_exchange = sys.modules.get(exchange_name)
        prior_move = sys.modules.get(move_name)
        prior_exchange_catalog = (
            getattr(prior_exchange, "CATALOG", None) if prior_exchange else None
        )
        prior_exchange_items = (
            getattr(prior_exchange, "ITEMS", None) if prior_exchange else None
        )
        prior_stack = getattr(prior_move, "STACKS", None) if prior_move else None
        prior_exchange_values = (
            dict(prior_exchange_items) if prior_exchange_items is not None else None
        )
        prior_stack_values = dict(prior_stack) if prior_stack is not None else None
        with patch.object(native_catalog, "load", side_effect=synthetic_catalog):
            exchange_rules = (
                importlib.reload(prior_exchange)
                if prior_exchange is not None
                else importlib.import_module(exchange_name)
            )
            inventory_move = (
                importlib.reload(prior_move)
                if prior_move is not None
                else importlib.import_module(move_name)
            )

        def restore_catalog_modules():
            if prior_exchange is not None:
                prior_exchange_items.clear()
                prior_exchange_items.update(prior_exchange_values)
                prior_exchange.CATALOG = prior_exchange_catalog
                prior_exchange.ITEMS = prior_exchange_items
            else:
                sys.modules.pop(exchange_name, None)
            if prior_move is not None:
                prior_stack.clear()
                prior_stack.update(prior_stack_values)
                prior_move.STACKS = prior_stack
            else:
                sys.modules.pop(move_name, None)
            import wakfu_server

            if (
                prior_exchange is None
                and getattr(wakfu_server, "exchange_rules", None) is exchange_rules
            ):
                delattr(wakfu_server, "exchange_rules")
            if (
                prior_move is None
                and getattr(wakfu_server, "inventory_move", None) is inventory_move
            ):
                delattr(wakfu_server, "inventory_move")

        self.addCleanup(restore_catalog_modules)
        inventory_move.STACKS = {2504: {"maximum": 99}}
        exchange_rules.ITEMS = exchange_items
        self.service = GuildService(self.store)
        self.policy = {
            "enabled": True,
            "native_sync_enabled": False,
            "owner_id_semantics": "account",
            "creation_kamas": 10000,
            "creation_item": 16942,
            "max_members": 20,
            "max_ranks": 15,
            "name_pattern": r"[A-Za-z][A-Za-z0-9 ]{2,30}",
            "name_normalization": "NFKC_CASEFOLD",
            "allowed_blazons": [123],
            "leader_permissions": (1 << 63) - 1,
            "member_permissions": sum(1 << bit for bit in range(10, 14)),
            "permissions": {"invite": 0},
            "economy": {
                "treasury_enabled": True,
                "permission_bits": {
                    "treasury_deposit": 14,
                    "treasury_withdraw": 15,
                },
            },
            "invitation_seconds": 3600,
            "description_max_bytes": 500,
            "message_max_bytes": 500,
            "weekly_points_limit": 7500,
            "earned_points_limit": 0,
            "last_earning_point_week": 0,
            "chest": {
                "enabled": True,
                "compartments": {
                    "1": {
                        "capacity": 40,
                        "name": "Guild Chest",
                        "requires_unlock": False,
                        "permission_bits": {
                            "view": 10,
                            "deposit": 11,
                            "withdraw": 12,
                            "move": 13,
                        },
                    },
                    "2": {
                        "capacity": 40,
                        "name": "Guild Vault",
                        "requires_unlock": False,
                        "permission_bits": {
                            "view": 10,
                            "deposit": 11,
                            "withdraw": 12,
                            "move": 13,
                        },
                    },
                },
            },
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
        self.owner = self._player("Chest Owner")
        guild = self._create(self.owner, "Guild Chest Tests")
        self.guild_id = guild["guild"]["id"]
        self.member = self._player("Chest Member")
        invitation = self.service.invite(
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            self.member["character"],
        )
        self.service.invitation_answer(
            self.member["account"],
            self.member["generation"],
            self.member["character"],
            invitation,
            True,
        )
        self.chest = load(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
        )
        with self.store.connection() as db:
            self.item_uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "SELECT %s,2504,9,uid,2 FROM inventory_containers "
                "WHERE character_id=%s AND kind=0 RETURNING uid",
                (self.owner["character"], self.owner["character"]),
            ).fetchone()["uid"]

    def _request(self, compartment=1, *, slot=0, quantity=9):
        return {
            "compartment": compartment,
            "uid": self.item_uid,
            "slot": slot,
            "quantity": quantity,
        }

    def _withdraw_as_member(self, *, key="member-withdraw", revision=1):
        with self.store.connection() as db:
            container = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.member["character"],),
            ).fetchone()["uid"]
        return transfer(
            self.store,
            self.member["account"],
            self.member["generation"],
            self.member["character"],
            1,
            [
                dict(
                    compartment=1,
                    uid=self.item_uid,
                    slot=0,
                    reference=2504,
                    quantity=9,
                    container=container,
                    destination=1,
                )
            ],
            deposit=False,
            operation_key=key,
            expected_revision=revision,
        )

    def _deposit(self, *, key="deposit", revision=None, compartment=1, quantity=9):
        return transfer(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            compartment,
            [self._request(compartment, quantity=quantity)],
            deposit=True,
            operation_key=key,
            expected_revision=self.chest["revision"] if revision is None else revision,
        )

    def test_member_shared_access_receipt_replay_and_reconnect(self):
        first = self._deposit()
        replay = self._deposit()
        self.assertTrue(first["applied"])
        self.assertFalse(replay["applied"])
        self.assertEqual(first["chest"], replay["chest"])
        self.assertEqual(first["chest"]["items"][0]["item"]["quantity"], 9)

        shared = load(
            self.store,
            self.member["account"],
            self.member["generation"],
            self.member["character"],
            1,
        )
        self.assertEqual(shared, first["chest"])
        withdrawn = self._withdraw_as_member()
        self.assertEqual(withdrawn["chest"]["items"], [])
        moved_item = next(
            item
            for item in withdrawn["character"]["inventory_items"]
            if item["uid"] == self.item_uid
        )
        self.assertEqual(moved_item["uid"], self.item_uid)

        reopened = self.reopen()
        persisted = load(
            reopened,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
        )
        self.assertEqual(persisted, withdrawn["chest"])

    def test_stale_revision_and_reused_key_do_not_mutate_inventory_or_chest(self):
        first = self._deposit()
        with self.assertRaisesRegex(ValueError, "changed"):
            self._deposit(key="stale", revision=0, quantity=1)
        with self.assertRaisesRegex(ValueError, "different request"):
            self._deposit(key="deposit", quantity=8)
        self.assertEqual(
            load(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
                1,
            ),
            first["chest"],
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (self.item_uid,),
                ).fetchone()
            )

    def test_storage_failure_rolls_back_inventory_chest_and_receipt(self):
        with patch(
            "wakfu_server.characters.guild_chest._save",
            side_effect=RuntimeError("forced chest save failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "forced chest save failure"):
                self._deposit(key="rollback")

        self.assertEqual(
            load(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
                1,
            )["items"],
            [],
        )
        with self.store.connection() as db:
            quantity = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (self.item_uid,)
            ).fetchone()["quantity"]
            receipt = db.execute(
                "SELECT 1 FROM guild_chest_receipts WHERE character_id=%s AND operation_key='rollback'",
                (self.owner["character"],),
            ).fetchone()
        self.assertEqual(quantity, 9)
        self.assertIsNone(receipt)
        self.assertTrue(self._deposit(key="rollback")["applied"])

    def test_supported_item_metadata_survives_cross_member_custody(self):
        shard_state = b"\x0a\x02\x50\x00"
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) VALUES(%s,10,20)",
                (self.item_uid,),
            )
            db.execute(
                "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                (self.item_uid, shard_state),
            )
        self._deposit()
        result = self._withdraw_as_member()
        item = next(
            item
            for item in result["character"]["inventory_items"]
            if item["uid"] == self.item_uid
        )
        self.assertEqual(item["damage_elements"], 10)
        self.assertEqual(item["resistance_elements"], 20)
        self.assertEqual(bytes(item["shard_state"]), shard_state)

    def test_permission_revocation_takes_effect_on_next_load(self):
        with self.store.connection() as db:
            rank_id = db.execute(
                "SELECT rank_id FROM guild_members WHERE guild_id=%s AND character_id=%s",
                (self.guild_id, self.member["character"]),
            ).fetchone()["rank_id"]
            db.execute(
                "UPDATE guild_ranks SET permissions=0 WHERE guild_id=%s AND id=%s",
                (self.guild_id, rank_id),
            )
        with self.assertRaisesRegex(ValueError, "permission denied"):
            load(
                self.store,
                self.member["account"],
                self.member["generation"],
                self.member["character"],
                1,
            )

    def test_full_member_inventory_rolls_back_withdrawal(self):
        self._deposit()
        with self.store.connection() as db:
            container = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.member["character"],),
            ).fetchone()["uid"]
            db.execute(
                "UPDATE inventory_containers SET capacity=1 WHERE uid=%s", (container,)
            )
        with self.assertRaisesRegex(ValueError, "full or invalid"):
            self._withdraw_as_member()
        current = load(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
        )
        self.assertEqual(current["items"][0]["item"]["uid"], self.item_uid)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_items WHERE uid=%s", (self.item_uid,)
                ).fetchone()
            )

    def test_two_members_cannot_withdraw_the_same_last_stack(self):
        self._deposit()
        second = self._player("Chest Concurrent Member")
        invitation = self.service.invite(
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            second["character"],
        )
        self.service.invitation_answer(
            second["account"],
            second["generation"],
            second["character"],
            invitation,
            True,
        )

        def withdraw(player, operation_key):
            with self.store.connection() as db:
                container = db.execute(
                    "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                    (player["character"],),
                ).fetchone()["uid"]
            return transfer(
                self.store,
                player["account"],
                player["generation"],
                player["character"],
                1,
                [
                    dict(
                        compartment=1,
                        uid=self.item_uid,
                        slot=0,
                        reference=2504,
                        quantity=9,
                        container=container,
                        destination=1,
                    )
                ],
                deposit=False,
                operation_key=operation_key,
                expected_revision=1,
            )

        def attempt(args):
            try:
                return withdraw(*args)
            except ValueError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(attempt, ((self.member, "race-a"), (second, "race-b")))
            )
        successes = [result for result in results if isinstance(result, dict)]
        failures = [result for result in results if isinstance(result, ValueError)]
        self.assertEqual((len(successes), len(failures)), (1, 1))
        self.assertRegex(str(failures[0]), "changed|unavailable")
        self.assertEqual(
            load(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
                1,
            )["items"],
            [],
        )
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE uid=%s",
                    (self.item_uid,),
                ).fetchone()["n"],
            )

    def test_guild_cannot_dissolve_while_a_chest_contains_items(self):
        self._deposit()
        with self.assertRaisesRegex(ValueError, "Empty guild chests"):
            self.service.dissolve(
                self.owner["account"], self.owner["generation"], self.owner["character"]
            )

    def test_treasury_money_conservation_replay_and_overdraft(self):
        def wallet():
            with self.store.connection() as db:
                return db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.owner["account"],),
                ).fetchone()["kamas"]

        initial = wallet()
        deposited = transfer_money(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
            500,
            operation_key="money-deposit",
        )
        replay = transfer_money(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
            500,
            operation_key="money-deposit",
        )
        self.assertTrue(deposited["applied"])
        self.assertFalse(replay["applied"])
        self.assertEqual(deposited["treasury_kamas"], replay["treasury_kamas"])
        self.assertEqual(initial, wallet() + replay["treasury_kamas"])

        withdrawn = transfer_money(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
            120,
            withdraw=True,
            operation_key="money-withdraw",
        )
        self.assertEqual(initial, wallet() + withdrawn["treasury_kamas"])
        with self.assertRaisesRegex(ValueError, "treasury balance"):
            transfer_money(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
                1,
                381,
                withdraw=True,
                operation_key="money-overdraft",
            )
        self.assertEqual(wallet() + withdrawn["treasury_kamas"], initial)

    def test_snapshot_returns_empty_visible_and_disabled_denied_compartments(self):
        transfer_money(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
            50,
            operation_key="snapshot-money",
        )
        view = snapshot(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            [1, 2],
        )
        self.assertEqual(view["money"], 50)
        self.assertEqual([row["items"] for row in view["chests"]], [[], []])
        self.assertTrue(all(row["enabled"] for row in view["chests"]))

        self.policy["chest"]["compartments"]["2"]["requires_unlock"] = True
        self.policy["chest"]["compartments"]["2"]["permission_bits"]["view"] = 20
        self.policy["chest"]["compartments"]["1"]["permission_bits"]["view"] = 20
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
        restricted = snapshot(
            self.store,
            self.member["account"],
            self.member["generation"],
            self.member["character"],
            [1, 2],
        )
        self.assertTrue(
            all(
                not row["enabled"] and row["items"] == []
                for row in restricted["chests"]
            )
        )
        self.assertEqual(restricted["money"], 0)

    def test_stale_expected_guild_cannot_mutate_after_membership_changes(self):
        with self.assertRaisesRegex(ValueError, "membership changed"):
            transfer_money(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
                1,
                10,
                operation_key="wrong-guild",
                expected_guild_id=self.guild_id + 1,
            )
        with self.store.connection() as db:
            state = db.execute(
                "SELECT record FROM guild_service_state WHERE guild_id=%s AND service='economy'",
                (self.guild_id,),
            ).fetchone()
            receipt = db.execute(
                "SELECT 1 FROM guild_chest_receipts WHERE character_id=%s AND operation_key='wrong-guild'",
                (self.owner["character"],),
            ).fetchone()
        self.assertIsNone(state)
        self.assertIsNone(receipt)

    def test_snapshot_keeps_base_container_first_when_its_uid_is_larger(self):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s",
                (self.owner["character"],),
            )
            base = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.owner["character"],),
            ).fetchone()["uid"]
            extra = db.execute(
                "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) "
                "VALUES(%s,2,1,16,0) RETURNING uid",
                (self.owner["character"],),
            ).fetchone()["uid"]
            db.execute(
                "UPDATE inventory_containers SET uid=%s WHERE uid=%s", (extra + 1, base)
            )
            db.execute(
                "UPDATE inventory_containers SET uid=%s WHERE uid=%s", (base, extra)
            )
            db.execute(
                "UPDATE inventory_containers SET uid=%s WHERE uid=%s",
                (extra, extra + 1),
            )

        result = transfer_money(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
            1,
            operation_key="container-order",
        )
        containers = result["character"]["inventory_containers"]
        self.assertEqual(containers[0]["kind"], 0)
        self.assertEqual(containers[1]["kind"], 1)
        self.assertGreater(containers[0]["uid"], containers[1]["uid"])

    def test_concurrent_same_operation_applies_once(self):
        def deposit():
            return self._deposit(key="parallel-deposit")

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: deposit(), range(2)))
        self.assertEqual(sorted(result["applied"] for result in results), [False, True])
        self.assertEqual(results[0]["chest"], results[1]["chest"])

    def test_wrong_guild_member_is_denied(self):
        other = self._player("Chest Outsider")
        with self.assertRaisesRegex(ValueError, "not a guild member"):
            load(
                self.store, other["account"], other["generation"], other["character"], 1
            )

    def test_move_between_compartments_preserves_item_identity_and_quantity(self):
        deposited = self._deposit()
        moved = move(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
            0,
            2,
            3,
            operation_key="move-one",
            expected_revisions={1: deposited["chest"]["revision"], 2: 0},
        )
        self.assertTrue(moved["applied"])
        source = load(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            1,
        )
        destination = load(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            2,
        )
        self.assertEqual(source["items"], [])
        self.assertEqual(destination["items"][0]["slot"], 3)
        self.assertEqual(destination["items"][0]["item"]["uid"], self.item_uid)
        self.assertEqual(destination["items"][0]["item"]["quantity"], 9)


if __name__ == "__main__":
    import unittest

    unittest.main()
