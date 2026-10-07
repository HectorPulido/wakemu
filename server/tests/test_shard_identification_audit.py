"""Independent lifecycle, ownership and serialization regressions for 053."""
import struct
import threading
import time
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.element_selection import encode_result
from wakfu_server.inventory_items import grant, item_proto
from wakfu_server.inventory_shards import legacy_option
from wakfu_server.exchange_transfer import apply as apply_exchange_transfer
from wakfu_server.exchange_transfer import plan as plan_exchange_transfer
from wakfu_server.shard_identification import identify
from wakfu_server.wire import proto_fields


class ShardIdentificationAuditTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("socket-audit-owner", "local-test-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Socket Audit Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.bag = self.character["inventory_containers"][0]["uid"]
        self.item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=2869,
            quantity=1,
            container=self.bag,
            slot=0,
            allowed_references={2869},
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=100 WHERE id=%s", (self.character["id"],)
            )

    def _identify(self, *, randbelow=None):
        return identify(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", self.item["uid"]),
            randbelow=randbelow,
        )

    def test_commit_survives_reopen_as_same_known_native_shard_bytes(self):
        draws = iter((0, 0))
        result = self._identify(randbelow=lambda _limit: next(draws))
        self.assertTrue(result["applied"])
        self.assertEqual(
            list(proto_fields(result["shard_state"])), [(10, b"\x50\x00\x60\x01")]
        )
        self.assertEqual(
            legacy_option(result["shard_state"]),
            struct.pack(">HBiBiHiiB", 1, 0, 0, 1, 0, 0, 0, 0, 0),
        )
        packet = encode_result(
            result["uid"],
            result["elements"][0],
            result["elements"][1],
            sockets=result["shard_state"],
        )
        self.assertEqual(
            packet,
            (
                13766,
                struct.pack(">iqBI", 0, result["uid"], 0, 2)
                + result["elements"]
                + struct.pack(">I", len(result["shard_state"]))
                + result["shard_state"],
            ),
        )

        reopened = self.reopen().character(self.account, self.character["id"])
        loaded = next(
            item
            for item in reopened["inventory_items"]
            if item["uid"] == self.item["uid"]
        )
        self.assertEqual(loaded["shard_state"], result["shard_state"])
        self.assertIn(
            (418, result["shard_state"]), list(proto_fields(item_proto(loaded)))
        )
        retry = self._identify(
            randbelow=lambda _limit: self.fail("durable retry rerolled")
        )
        self.assertEqual(retry["shard_state"], result["shard_state"])
        self.assertFalse(retry["applied"])

    def test_random_failure_rolls_back_wallet_shard_and_receipt(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','10') "
                "WHERE name='socket_identification_policy'"
            )
            db.execute(
                "UPDATE account_wallets SET kamas=100 WHERE account_id=%s",
                (self.account,),
            )

        with self.assertRaisesRegex(ValueError, "invalid draw"):
            self._identify(randbelow=lambda limit: limit)

        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                100,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_item_shards WHERE uid=%s",
                    (self.item["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_identification_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_storage_failure_after_wallet_debit_rolls_back_whole_operation(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','10') "
                "WHERE name='socket_identification_policy'"
            )
            db.execute(
                "UPDATE account_wallets SET kamas=100 WHERE account_id=%s",
                (self.account,),
            )

        with patch(
            "wakfu_server.shard_identification.save",
            side_effect=RuntimeError("injected storage failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected storage failure"):
                self._identify(randbelow=lambda _limit: 0)

        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                100,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_item_shards WHERE uid=%s",
                    (self.item["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_identification_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_boolean_policy_version_is_not_accepted_as_integer_one(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{version}','true'::jsonb) "
                "WHERE name='socket_identification_policy'"
            )
        with self.assertRaisesRegex(
            ValueError, "Unsupported socket identification policy"
        ):
            self._identify(
                randbelow=lambda _limit: self.fail("invalid policy reached RNG")
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_item_shards"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_identification_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_concurrent_identical_request_commits_one_state_and_one_cost(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','10') "
                "WHERE name='socket_identification_policy'"
            )
            db.execute(
                "UPDATE account_wallets SET kamas=100 WHERE account_id=%s",
                (self.account,),
            )

        first_draw_entered = threading.Event()
        release_first = threading.Event()
        calls = []

        def controlled_draw(_limit):
            calls.append(threading.get_ident())
            if len(calls) == 1:
                first_draw_entered.set()
                if not release_first.wait(5):
                    raise AssertionError(
                        "timed out coordinating concurrent identification"
                    )
            return 0

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(self._identify, randbelow=controlled_draw)
            self.assertTrue(first_draw_entered.wait(5))
            second = workers.submit(
                self._identify,
                randbelow=lambda _limit: self.fail("concurrent retry rerolled"),
            )
            time.sleep(0.1)
            release_first.set()
            one, two = first.result(timeout=10), second.result(timeout=10)

        self.assertEqual(one["shard_state"], two["shard_state"])
        self.assertEqual(sorted((one["applied"], two["applied"])), [False, True])
        self.assertEqual(len(calls), 2)  # one count draw and one color draw
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                90,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_identification_receipts"
                ).fetchone()["n"],
                1,
            )

    def test_old_owner_retry_cannot_replay_after_uid_transfers(self):
        self._identify(randbelow=lambda _limit: 0)
        new_account = self.store.register(
            "socket-audit-recipient", "local-test-password"
        )["id"]
        recipient = self.store.create_character(new_account, "Socket Audit Recipient")
        recipient_bag = recipient["inventory_containers"][0]["uid"]
        new_generation = self.store.begin_session(new_account)
        self.store.select_character(new_account, new_generation, recipient["id"])

        # Use the production transfer planner/application: a completed whole-
        # unit exchange preserves UID and copies its metadata across owners.
        with self.store.connection() as db:
            character_ids = [self.character["id"], recipient["id"]]
            original = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=ANY(%s) ORDER BY uid",
                    (character_ids,),
                )
            ]
            containers = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=ANY(%s) ORDER BY uid",
                    (character_ids,),
                )
            ]
            final, _ = plan_exchange_transfer(
                original,
                containers,
                [
                    dict(
                        uid=self.item["uid"],
                        quantity=1,
                        character_id=self.character["id"],
                    )
                ],
                allocate=lambda: self.item["uid"] + 1000000,
            )
            apply_exchange_transfer(db, original, final)

        with self.assertRaisesRegex(ValueError, "unavailable or foreign|session"):
            self._identify(
                randbelow=lambda _limit: self.fail("transferred retry must not draw")
            )

        current = identify(
            self.store,
            new_account,
            new_generation,
            recipient["id"],
            struct.pack(">q", self.item["uid"]),
            randbelow=lambda _limit: self.fail(
                "identified transferred item must not reroll"
            ),
        )
        self.assertFalse(current["applied"])
        self.assertEqual(current["shard_state"], self._identified_state())
        self.assertEqual(current["cost_kamas"], 0)
        self.assertIsNone(current["receipt_id"])

        with self.store.connection() as db:
            owner = db.execute(
                "SELECT character_id FROM inventory_items WHERE uid=%s",
                (self.item["uid"],),
            ).fetchone()
            receipt_count = db.execute(
                "SELECT count(*) AS n FROM inventory_socket_identification_receipts"
            ).fetchone()["n"]
            self.assertEqual(owner["character_id"], recipient["id"])
            self.assertEqual(receipt_count, 1)

    def _identified_state(self):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                (self.item["uid"],),
            ).fetchone()
        return bytes(row["shard_state"])


if __name__ == "__main__":
    unittest.main()
