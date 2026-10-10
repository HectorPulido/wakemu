import struct
from concurrent.futures import ThreadPoolExecutor
import threading

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_shards import save
from wakfu_server.socket_enchantment import mutate
from wakfu_server.wire import proto_field, proto_fields


class EnchantmentConcurrencyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("enchantment-race", "test-password")["id"]
        self.character = self.store.create_character(self.account, "Enchantment Race")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        items = [
            grant(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                reference=2869,
                quantity=1,
                container=self.character["inventory_containers"][0]["uid"],
                slot=slot,
                allowed_references={2869},
            )
            for slot in range(2)
        ]
        self.target, self.ingredient = items
        self.body = struct.pack(">qBq", self.target["uid"], 0, self.ingredient["uid"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=80 WHERE id=%s", (self.character["id"],)
            )
            save(
                db,
                self.target["uid"],
                proto_field(10, proto_field(80, 0) + proto_field(96, 1)),
            )
            db.execute(
                "UPDATE account_wallets SET kamas=100 WHERE account_id=%s",
                (self.account,),
            )
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{operation_kamas,add_charges}','7') "
                "WHERE name='socket_enchantment_policy'"
            )

    def apply(self, generation=None):
        return mutate(
            self.store,
            self.account,
            generation or self.generation,
            self.character["id"],
            12365,
            self.body,
        )

    def assert_once(self):
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                93,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.ingredient["uid"],),
                ).fetchone()
            )
            blob = db.execute(
                "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                (self.target["uid"],),
            ).fetchone()["shard_state"]
            self.assertEqual(dict(proto_fields(bytes(blob)))[72], 1)

    def test_concurrent_duplicate_consumes_and_charges_once(self):
        barrier = threading.Barrier(2)

        def request():
            barrier.wait(timeout=5)
            return self.apply()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(request) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(sum(result["applied"] for result in results), 1)
        self.assert_once()

    def test_reconnect_retry_preserves_receipt_and_stale_session_is_rejected(self):
        self.apply()
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, self.character["id"])
        with self.assertRaises(ValueError):
            self.apply()
        self.assertFalse(self.apply(generation)["applied"])
        self.assert_once()

    def test_unpublishable_state_rolls_back_cost_and_sacrifice(self):
        # Unknown protobuf fields are valid durable data. They must not permit
        # a commit whose response exceeds the native signed-short carrier.
        state = proto_field(10, proto_field(96, 1)) + proto_field(802, b"x" * 32768)
        with self.store.connection() as db:
            save(db, self.target["uid"], state)
        with self.assertRaises(ValueError):
            self.apply()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                100,
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.ingredient["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                0,
            )
            saved = db.execute(
                "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                (self.target["uid"],),
            ).fetchone()["shard_state"]
            self.assertEqual(bytes(saved), state)
