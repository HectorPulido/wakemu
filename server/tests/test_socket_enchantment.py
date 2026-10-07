import struct
import unittest
from datetime import timedelta

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_shards import save
from wakfu_server.socket_enchantment import (
    install_bonus,
    mutate,
    _native_pattern_matches,
)
from wakfu_server.wire import proto_field, proto_fields


def socket_blob(*, color=1, charges=0, sublimation=0):
    slot = proto_field(80, 0) + proto_field(96, color)
    return (
        proto_field(10, slot)
        + proto_field(72, charges)
        + (b"" if sublimation == 0 else proto_field(24, sublimation))
    )


class SocketEnchantmentTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("socket-mutation", "local-test-password")[
            "id"
        ]
        self.char = self.store.create_character(self.account, "Socket Mutation")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])
        self.bag = self.char["inventory_containers"][0]["uid"]
        self.target = grant(
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
        self.sacrifice = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=2869,
            quantity=1,
            container=self.bag,
            slot=1,
            allowed_references={2869},
        )
        self.sublimation = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=27111,
            quantity=1,
            container=self.bag,
            slot=2,
            allowed_references={27111},
        )
        with self.store.connection() as db:
            save(db, self.target["uid"], socket_blob())
            db.execute(
                "UPDATE account_wallets SET kamas=100 WHERE account_id=%s",
                (self.account,),
            )
            db.execute(
                "UPDATE characters SET level=100 WHERE id=%s", (self.char["id"],)
            )

    def test_sacrifice_adds_one_local_charge_and_consumes_only_one_uid(self):
        body = struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"])
        result = mutate(
            self.store, self.account, self.generation, self.char["id"], 12365, body
        )
        self.assertTrue(result["applied"])
        self.assertEqual(result["consumed_uid"], self.sacrifice["uid"])
        self.assertEqual(result["inventory_packet"][0], 13713)
        self.assertEqual(
            result["inventory_packet"][1][:9], struct.pack(">qB", self.char["id"], 35)
        )
        fields = dict(proto_fields(result["shard_state"]))
        self.assertEqual(fields[72], 1)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.sacrifice["uid"],),
                ).fetchone()
            )
            receipt = db.execute(
                "SELECT operation,cost_kamas,policy_version FROM inventory_socket_enchantment_receipts"
            ).fetchone()
            self.assertEqual(tuple(receipt.values()), ("add_charges", 0, 1))

    def test_native_13269_installs_changed_bonus_and_consumes_only_incremental_shard_count(
        self,
    ):
        shard_stack = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=27097,
            quantity=3,
            container=self.bag,
            slot=3,
            allowed_references={27097},
        )
        body = struct.pack(">qB", self.target["uid"], 1) + struct.pack(
            ">Bii", 0, 27097, 1
        )
        first = install_bonus(
            self.store, self.account, self.generation, self.char["id"], body
        )
        slot_blob = dict(proto_fields(first["shard_state"]))[10]
        slot = dict(proto_fields(slot_blob))
        self.assertEqual((slot[88], slot[112]), (27097, 1))
        self.assertTrue(first["applied"])
        self.assertEqual(first["inventory_packet"][0], 13713)
        self.assertEqual(first["consumed"][0]["quantity"], 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (shard_stack["uid"],),
                ).fetchone()["quantity"],
                2,
            )
        retry = install_bonus(
            self.store, self.account, self.generation, self.char["id"], body
        )
        self.assertFalse(retry["applied"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (shard_stack["uid"],),
                ).fetchone()["quantity"],
                2,
            )

        upgrade = struct.pack(">qB", self.target["uid"], 1) + struct.pack(
            ">Bii", 0, 27097, 3
        )
        upgraded = install_bonus(
            self.store, self.account, self.generation, self.char["id"], upgrade
        )
        self.assertTrue(upgraded["applied"])
        slot_blob = dict(proto_fields(upgraded["shard_state"]))[10]
        self.assertEqual(dict(proto_fields(slot_blob))[112], 3)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (shard_stack["uid"],),
                ).fetchone()
            )
            receipt = db.execute(
                "SELECT consumed FROM inventory_socket_bonus_installation_receipts ORDER BY id LIMIT 1"
            ).fetchone()["consumed"]
            self.assertEqual([row["quantity"] for row in receipt], [1])

    def test_native_13269_rejects_color_level_and_inventory_without_partial_mutation(
        self,
    ):
        shard_stack = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=27097,
            quantity=1,
            container=self.bag,
            slot=3,
            allowed_references={27097},
        )
        wrong_color = struct.pack(">qB", self.target["uid"], 1) + struct.pack(
            ">Bii", 0, 27094, 1
        )
        with self.assertRaisesRegex(ValueError, "color"):
            install_bonus(
                self.store, self.account, self.generation, self.char["id"], wrong_color
            )
        high_level = struct.pack(">qB", self.target["uid"], 1) + struct.pack(
            ">Bii", 0, 27097, 3
        )
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=1 WHERE id=%s", (self.char["id"],))
        with self.assertRaisesRegex(ValueError, "character-level gate"):
            install_bonus(
                self.store, self.account, self.generation, self.char["id"], high_level
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=100 WHERE id=%s", (self.char["id"],)
            )
        insufficient = struct.pack(">qB", self.target["uid"], 1) + struct.pack(
            ">Bii", 0, 27097, 3
        )
        with self.assertRaisesRegex(ValueError, "Insufficient owned shard items"):
            install_bonus(
                self.store, self.account, self.generation, self.char["id"], insufficient
            )
        with self.store.connection() as db:
            self.assertEqual(
                bytes(
                    db.execute(
                        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                        (self.target["uid"],),
                    ).fetchone()["shard_state"]
                ),
                socket_blob(),
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (shard_stack["uid"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_bonus_installation_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_native_color_request_changes_only_selected_slot_and_consumes_sacrifice(
        self,
    ):
        body = struct.pack(">qBqBB", self.target["uid"], 2, self.sacrifice["uid"], 0, 4)
        result = mutate(
            self.store, self.account, self.generation, self.char["id"], 12365, body
        )
        slot = dict(proto_fields(dict(proto_fields(result["shard_state"]))[10]))
        self.assertEqual(slot[96], 4)

    def test_sacrifice_and_workshop_can_add_slots_without_exceeding_native_template(
        self,
    ):
        body = struct.pack(">qBq", self.target["uid"], 1, self.sacrifice["uid"])
        sacrificed = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            12365,
            body,
            randbelow=lambda _limit: 0,
        )
        self.assertEqual(
            len([1 for tag, _ in proto_fields(sacrificed["shard_state"]) if tag == 10]),
            2,
        )
        with self.store.connection() as db:
            second_slot = proto_field(80, 1) + proto_field(96, 1)
            save(
                db,
                self.target["uid"],
                socket_blob(charges=1) + proto_field(10, second_slot),
            )

        workshop = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            13257,
            struct.pack(">qB", self.target["uid"], 0),
            randbelow=lambda _limit: 1,
        )
        self.assertEqual(
            len([1 for tag, _ in proto_fields(workshop["shard_state"]) if tag == 10]), 3
        )
        self.assertEqual(dict(proto_fields(workshop["shard_state"]))[72], 0)

    def test_workshop_mutation_is_blocked_during_combat(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_item_shards SET shard_state=%s WHERE uid=%s",
                (socket_blob(charges=2), self.target["uid"]),
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, self.char["id"], self.account),
            )
        with self.assertRaisesRegex(ValueError, "during combat"):
            mutate(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                13257,
                struct.pack(">qB", self.target["uid"], 0),
                randbelow=lambda _limit: self.fail("combat guard must precede RNG"),
            )
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM combat_fight_participants WHERE character_id=%s",
                (self.char["id"],),
            )
            db.execute("DELETE FROM combat_fights")
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_target_item_level_gate_precedes_charge_or_item_consumption(self):
        body = struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"])
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=1 WHERE id=%s", (self.char["id"],))
        with self.assertRaisesRegex(ValueError, "character-level gate"):
            mutate(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                12365,
                body,
                randbelow=lambda _limit: self.fail("level gate must precede RNG"),
            )
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.sacrifice["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_workshop_change_order_spends_local_charge_and_preserves_slots(self):
        state = socket_blob(color=1, charges=2) + proto_field(
            10, proto_field(80, 1) + proto_field(96, 2)
        )
        with self.store.connection() as db:
            save(db, self.target["uid"], state)
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{charge_costs,change_order}','1') "
                "WHERE name='socket_enchantment_policy'"
            )
        result = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            13257,
            struct.pack(">qB", self.target["uid"], 2),
            randbelow=lambda _limit: 0,
        )
        top = list(proto_fields(result["shard_state"]))
        self.assertEqual(
            [dict(proto_fields(v))[96] for tag, v in top if tag == 10], [2, 1]
        )
        self.assertEqual(dict(top)[72], 1)

    def test_workshop_retry_is_suppressed_in_window_but_same_action_can_repeat_afterward(
        self,
    ):
        with self.store.connection() as db:
            save(
                db,
                self.target["uid"],
                socket_blob(color=1, charges=3)
                + proto_field(10, proto_field(80, 1) + proto_field(96, 2)),
            )
        body = struct.pack(">qB", self.target["uid"], 2)
        first = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            13257,
            body,
            randbelow=lambda _limit: 0,
        )
        retry = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            13257,
            body,
            randbelow=lambda _limit: self.fail(
                "retry in dedupe window must not reroll"
            ),
        )
        self.assertTrue(first["applied"])
        self.assertFalse(retry["applied"])
        self.assertEqual(retry["shard_state"], first["shard_state"])
        self.assertIsNone(retry["consumed_uid"])
        self.assertEqual(retry["inventory_packet"][0], 13713)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_socket_enchantment_receipts SET applied_at=%s",
                (self.store.now() - timedelta(seconds=4),),
            )
        repeated = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            13257,
            body,
            randbelow=lambda _limit: 0,
        )
        self.assertTrue(repeated["applied"])
        self.assertEqual(dict(proto_fields(repeated["shard_state"]))[72], 1)

    def test_native_sublimation_pattern_applies_consumes_once_and_remove_is_scoped(
        self,
    ):
        state = b"".join(
            proto_field(10, proto_field(80, position) + proto_field(96, 1))
            for position in range(3)
        ) + proto_field(72, 0)
        with self.store.connection() as db:
            save(db, self.target["uid"], state)
            pattern = db.execute(
                "SELECT slot_colors,pattern_type FROM native_sublimation_patterns WHERE reference=27111"
            ).fetchone()
            self.assertEqual(
                (list(pattern["slot_colors"]), pattern["pattern_type"]),
                ([1, 1, 1], "BASIC"),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_sublimation_patterns"
                ).fetchone()["n"],
                388,
            )
        body = struct.pack(">qi", self.target["uid"], 27111)
        applied = mutate(
            self.store, self.account, self.generation, self.char["id"], 12221, body
        )
        self.assertTrue(applied["applied"])
        self.assertEqual(dict(proto_fields(applied["shard_state"]))[24], 27111)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.sublimation["uid"],),
                ).fetchone()
            )
        retry = mutate(
            self.store, self.account, self.generation, self.char["id"], 12221, body
        )
        self.assertFalse(retry["applied"])
        self.assertEqual(retry["shard_state"], applied["shard_state"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts WHERE operation='apply_sublimation'"
                ).fetchone()["n"],
                1,
            )
        removed = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            12364,
            struct.pack(">qB", self.target["uid"], 0),
        )
        self.assertEqual(dict(proto_fields(removed["shard_state"]))[24], 0)

    def test_native_sublimation_requires_contiguous_order_and_enabled_native_row(self):
        mismatched = b"".join(
            proto_field(10, proto_field(80, position) + proto_field(96, color))
            for position, color in enumerate((1, 2, 1))
        ) + proto_field(72, 0)
        body = struct.pack(">qi", self.target["uid"], 27111)
        with self.store.connection() as db:
            save(db, self.target["uid"], mismatched)
        with self.assertRaisesRegex(ValueError, "native sublimation pattern"):
            mutate(
                self.store, self.account, self.generation, self.char["id"], 12221, body
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE native_sublimation_patterns SET enabled=FALSE WHERE reference=27111"
            )
        with self.assertRaisesRegex(ValueError, "no enabled native pattern"):
            mutate(
                self.store, self.account, self.generation, self.char["id"], 12221, body
            )
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.sublimation["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts WHERE operation='apply_sublimation'"
                ).fetchone()["n"],
                0,
            )

    def test_native_sublimation_matcher_uses_white_target_wildcard_and_contiguous_subsequence(
        self,
    ):
        pattern = (1, 2, 3)
        rows = [{"color": color} for color in (3, 4, 2, 3)]
        self.assertTrue(_native_pattern_matches(rows, pattern))
        self.assertFalse(
            _native_pattern_matches([{"color": c} for c in (1, 2, 1)], pattern)
        )
        self.assertTrue(_native_pattern_matches([{"color": 4}], (3,)))
        self.assertTrue(_native_pattern_matches([{"color": 2}], (0,)))

    def test_local_fee_and_charge_cost_rollback_atomically_on_short_wallet(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{operation_kamas,change_order}','5') "
                "WHERE name='socket_enchantment_policy'"
            )
            db.execute(
                "UPDATE account_wallets SET kamas=2 WHERE account_id=%s",
                (self.account,),
            )
        with self.assertRaisesRegex(ValueError, "Insufficient kamas"):
            mutate(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                13257,
                struct.pack(">qB", self.target["uid"], 2),
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_malformed_or_foreign_sacrifice_fails_without_mutation(self):
        body = struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"] + 999)
        with self.assertRaisesRegex(ValueError, "sacrifice item is unavailable"):
            mutate(
                self.store, self.account, self.generation, self.char["id"], 12365, body
            )
        with self.assertRaisesRegex(ValueError, "length"):
            mutate(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                12365,
                b"bad",
            )
        with self.store.connection() as db:
            self.assertEqual(
                bytes(
                    db.execute(
                        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                        (self.target["uid"],),
                    ).fetchone()["shard_state"]
                ),
                socket_blob(),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_sacrifice_must_match_target_reference_and_be_unstacked(self):
        body = struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=9001 WHERE uid=%s",
                (self.sacrifice["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "reference is incompatible"):
            mutate(
                self.store, self.account, self.generation, self.char["id"], 12365, body
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=2869,quantity=2 WHERE uid=%s",
                (self.sacrifice["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "unstacked"):
            mutate(
                self.store, self.account, self.generation, self.char["id"], 12365, body
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_sacrifice_retry_after_commit_is_idempotent_and_old_owner_cannot_replay(
        self,
    ):
        body = struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"])
        first = mutate(
            self.store, self.account, self.generation, self.char["id"], 12365, body
        )
        retry = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            12365,
            body,
            randbelow=lambda _limit: self.fail("sacrifice retry must not draw"),
        )
        self.assertTrue(first["applied"])
        self.assertFalse(retry["applied"])
        self.assertEqual(retry["shard_state"], first["shard_state"])

        recipient_account = self.store.register(
            "socket-new-owner", "local-test-password"
        )["id"]
        recipient = self.store.create_character(recipient_account, "Socket New Owner")
        with self.store.connection() as db:
            recipient_bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s ORDER BY uid LIMIT 1",
                (recipient["id"],),
            ).fetchone()["uid"]
            db.execute(
                "UPDATE inventory_items SET character_id=%s,container=%s,slot=0 WHERE uid=%s",
                (recipient["id"], recipient_bag, self.target["uid"]),
            )
        with self.assertRaisesRegex(
            ValueError, "target has no identified|requires one owned"
        ):
            mutate(
                self.store, self.account, self.generation, self.char["id"], 12365, body
            )


if __name__ == "__main__":
    unittest.main()
