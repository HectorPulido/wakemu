import struct
import unittest
from datetime import timedelta

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_shards import save
from wakfu_server.shard_identification import identify
from wakfu_server.exchange_transfer import (
    apply as apply_exchange,
    plan as plan_exchange,
)
from wakfu_server.wire import proto_field, proto_fields


class ShardIdentificationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("socket-policy", "local-test-password")["id"]
        self.char = self.store.create_character(self.account, "Socket Policy")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])
        self.bag = self.char["inventory_containers"][0]["uid"]
        self.item = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=2869,
            quantity=1,
            container=self.bag,
            slot=0,
            allowed_references={2869},
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=100 WHERE id=%s", (self.char["id"],)
            )

    def test_identification_roll_is_saved_once_and_retry_returns_receipt(self):
        draws = iter((0, 0))  # native utility count bucket 0, color enum 1.
        result = identify(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            struct.pack(">q", self.item["uid"]),
            randbelow=lambda limit: next(draws),
        )
        self.assertEqual(
            (result["status"], result["applied"], result["cost_kamas"]), (0, True, 0)
        )
        self.assertEqual(result["wallet_kamas"], 0)
        self.assertEqual(
            list(proto_fields(result["shard_state"])), [(10, b"\x50\x00\x60\x01")]
        )
        retry = identify(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            struct.pack(">q", self.item["uid"]),
            randbelow=lambda _limit: self.fail("retry must not reroll"),
        )
        self.assertEqual(retry["shard_state"], result["shard_state"])
        self.assertFalse(retry["applied"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_identification_receipts"
                ).fetchone()["n"],
                1,
            )

    def test_level_gate_returns_native_too_high_level_without_drawing(self):
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=1 WHERE id=%s", (self.char["id"],))
        result = identify(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            struct.pack(">q", self.item["uid"]),
            randbelow=lambda _limit: self.fail("level gate must precede RNG"),
        )
        self.assertEqual(result["status"], 2)
        self.assertIsNone(result["shard_state"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_identification_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_unknown_template_and_stack_fail_closed_without_mutation(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=1 WHERE uid=%s",
                (self.item["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "not eligible"):
            identify(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                struct.pack(">q", self.item["uid"]),
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=2869,quantity=2 WHERE uid=%s",
                (self.item["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "unstacked"):
            identify(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                struct.pack(">q", self.item["uid"]),
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

    def test_nonzero_local_cost_is_charged_once_and_retry_uses_receipt(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','10') WHERE name='socket_identification_policy'"
            )
            db.execute(
                "UPDATE account_wallets SET kamas=100 WHERE account_id=%s",
                (self.account,),
            )
        draws = iter((0, 0))
        body = struct.pack(">q", self.item["uid"])
        result = identify(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            body,
            randbelow=lambda _limit: next(draws),
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                90,
            )
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','99') WHERE name='socket_identification_policy'"
            )
        retry = identify(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            body,
            randbelow=lambda _limit: self.fail("receipt retry must not draw RNG"),
        )
        self.assertEqual(retry["shard_state"], result["shard_state"])
        self.assertEqual(retry["cost_kamas"], 10)
        self.assertEqual(retry["wallet_kamas"], 90)
        self.assertFalse(retry["applied"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                90,
            )

    def test_insufficient_funds_fails_before_rng_or_receipt(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','10') WHERE name='socket_identification_policy'"
            )
            db.execute(
                "UPDATE account_wallets SET kamas=0 WHERE account_id=%s",
                (self.account,),
            )
        with self.assertRaisesRegex(ValueError, "Insufficient local-policy kamas"):
            identify(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                struct.pack(">q", self.item["uid"]),
                randbelow=lambda _limit: self.fail("funds check must precede RNG"),
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

    def test_retry_requires_current_ownership_and_returns_current_shard_state(self):
        body = struct.pack(">q", self.item["uid"])
        first = identify(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            body,
            randbelow=lambda _limit: 0,
        )
        changed = proto_field(10, proto_field(80, 0) + proto_field(96, 2))
        with self.store.connection() as db:
            save(db, self.item["uid"], changed)
        retry = identify(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            body,
            randbelow=lambda _limit: self.fail("retry must not reroll"),
        )
        self.assertNotEqual(first["shard_state"], changed)
        self.assertEqual(retry["shard_state"], changed)

        recipient_account = self.store.register(
            "socket-recipient", "local-test-password"
        )["id"]
        recipient = self.store.create_character(recipient_account, "Socket Recipient")
        with self.store.connection() as db:
            original = [
                *self.store_items(db, self.char["id"]),
                *self.store_items(db, recipient["id"]),
            ]
            containers = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=ANY(%s)",
                    ([self.char["id"], recipient["id"]],),
                )
            ]
            final, _ = plan_exchange(
                original,
                containers,
                [dict(uid=self.item["uid"], quantity=1, character_id=self.char["id"])],
                allocate=lambda: 987654322,
            )
            apply_exchange(db, original, final)
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            identify(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                body,
                randbelow=lambda _limit: self.fail("foreign retry must not draw"),
            )

    def test_retry_still_enforces_combat_exchange_and_equipment_guards(self):
        body = struct.pack(">q", self.item["uid"])
        identify(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            body,
            randbelow=lambda _limit: 0,
        )
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, self.char["id"], self.account),
            )
        with self.assertRaisesRegex(ValueError, "during combat"):
            identify(self.store, self.account, self.generation, self.char["id"], body)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM combat_fight_participants WHERE fight_id=%s", (fight_id,)
            )
            db.execute("DELETE FROM combat_fights WHERE id=%s", (fight_id,))

        recipient_account = self.store.register(
            "socket-trade-party", "local-test-password"
        )["id"]
        recipient = self.store.create_character(recipient_account, "Socket Trade Party")
        now = self.store.now()
        with self.store.connection() as db:
            exchange_id = db.execute(
                "INSERT INTO player_exchanges(inviter_id,invitee_id,inviter_account,invitee_account,inviter_generation,invitee_generation,state,revision,delivery_sequence,created_at,expires_at) "
                "VALUES(%s,%s,%s,%s,'g1','g2','invitation',1,1,%s,%s) RETURNING id",
                (
                    self.char["id"],
                    recipient["id"],
                    self.account,
                    recipient_account,
                    now,
                    now + timedelta(seconds=60),
                ),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_exchange_members(character_id,exchange_id) VALUES(%s,%s)",
                (self.char["id"], exchange_id),
            )
        with self.assertRaisesRegex(ValueError, "during exchange"):
            identify(self.store, self.account, self.generation, self.char["id"], body)
        with self.store.connection() as db:
            db.execute("DELETE FROM player_exchanges WHERE id=%s", (exchange_id,))

        equipped = proto_field(
            10, proto_field(8, self.item["uid"]) + proto_field(16, 4)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                "VALUES(%s,0,%s,%s,%s,%s) ON CONFLICT(character_id,build_index) DO UPDATE SET equipment=EXCLUDED.equipment",
                (self.char["id"], proto_field(24, 100), equipped, b"", b""),
            )
        with self.assertRaisesRegex(ValueError, "Unequip"):
            identify(self.store, self.account, self.generation, self.char["id"], body)

    def test_deleted_uid_does_not_replay_durable_identification_receipt(self):
        body = struct.pack(">q", self.item["uid"])
        identify(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            body,
            randbelow=lambda _limit: 0,
        )
        with self.store.connection() as db:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (self.item["uid"],))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_identification_receipts WHERE uid=%s",
                    (self.item["uid"],),
                ).fetchone()["n"],
                1,
            )
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            identify(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                body,
                randbelow=lambda _limit: self.fail("deleted UID retry must not draw"),
            )

    @staticmethod
    def store_items(db, character_id):
        from wakfu_server.inventory_items import load

        return load(db, character_id)


if __name__ == "__main__":
    unittest.main()
