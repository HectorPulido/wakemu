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

    def test_equipped_target_keeps_active_and_inactive_build_references(self):
        from wakfu_server.equipment import RULES

        slot = RULES[2869]["slots"][0]
        equipment = proto_field(
            10, proto_field(8, self.target["uid"]) + proto_field(16, slot)
        )
        with self.store.connection() as db:
            for index in (0, 1):
                db.execute(
                    "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                    "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(character_id,build_index) "
                    "DO UPDATE SET equipment=EXCLUDED.equipment",
                    (self.char["id"], index, proto_field(24, 100), equipment, b"", b""),
                )
        result = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            12365,
            struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"]),
        )
        self.assertTrue(result["applied"])
        saved = self.store.character(self.account, self.char["id"])
        for index in (0, 1):
            self.assertEqual(saved["builds"][index]["equipment"], equipment.hex())
        from wakfu_server.equipment_stats import effective_character

        self.assertEqual(saved["max_hp"], effective_character(saved)["max_hp"])

    def test_socket_mutation_splits_target_and_preserves_remainder_state(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET quantity=4 WHERE uid=%s",
                (self.target["uid"],),
            )
        result = mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            12365,
            struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"]),
        )
        self.assertTrue(result["applied"])
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT i.uid,i.quantity,s.shard_state FROM inventory_items i "
                "LEFT JOIN inventory_item_shards s ON s.uid=i.uid "
                "WHERE i.character_id=%s AND i.reference=2869",
                (self.char["id"],),
            ).fetchall()
            self.assertEqual(sum(row["quantity"] for row in rows), 4)
            self.assertEqual(len(rows), 2)
            remainder = next(row for row in rows if row["uid"] != self.target["uid"])
            self.assertEqual(remainder["quantity"], 3)
            self.assertEqual(bytes(remainder["shard_state"]), socket_blob())
            self.assertEqual(
                next(
                    row["quantity"] for row in rows if row["uid"] == self.target["uid"]
                ),
                1,
            )

    def test_bonus_response_failure_rolls_back_shards_state_fee_and_receipt(self):
        from unittest.mock import patch

        material = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=27083,
            quantity=2,
            container=self.bag,
            slot=3,
            allowed_references={27083},
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','7') "
                "WHERE name='socket_bonus_installation_policy'"
            )
        request = struct.pack(">qBBii", self.target["uid"], 1, 0, 27097, 1)
        for serializer in (
            "wakfu_server.socket_enchantment_wire.bonus_installation_packets",
            "wakfu_server.inventory_items.equipment_inventory",
        ):
            with self.subTest(serializer=serializer), patch(
                serializer, side_effect=ValueError("native response rejected")
            ):
                with self.assertRaisesRegex(ValueError, "native response rejected"):
                    install_bonus(
                        self.store,
                        self.account,
                        self.generation,
                        self.char["id"],
                        request,
                    )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (material["uid"],),
                ).fetchone()["quantity"],
                2,
            )
            self.assertEqual(
                bytes(
                    db.execute(
                        "SELECT shard_state FROM inventory_item_shards " "WHERE uid=%s",
                        (self.target["uid"],),
                    ).fetchone()["shard_state"]
                ),
                socket_blob(),
            )
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                100,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM "
                    "inventory_socket_bonus_installation_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_target_cannot_be_consumed_as_its_own_sacrifice(self):
        body = struct.pack(">qBq", self.target["uid"], 0, self.target["uid"])
        with self.assertRaisesRegex(
            ValueError, "Invalid native socket sacrifice request"
        ):
            mutate(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                12365,
                body,
            )
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.target["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_equipment_registry_failure_rolls_back_sacrifice_and_state(self):
        from unittest.mock import patch

        body = struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"])
        with patch(
            "wakfu_server.inventory_items.equipment_inventory",
            side_effect=ValueError("equipment registry rejected"),
        ):
            with self.assertRaisesRegex(ValueError, "equipment registry rejected"):
                mutate(
                    self.store,
                    self.account,
                    self.generation,
                    self.char["id"],
                    12365,
                    body,
                )
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.sacrifice["uid"],),
                ).fetchone()
            )
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

    def test_reference_scroll_request_skips_protected_first_copy(self):
        from unittest.mock import patch

        available = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=27111,
            quantity=1,
            container=self.bag,
            slot=3,
            allowed_references={27111},
        )
        state = b"".join(
            proto_field(10, proto_field(80, position) + proto_field(96, 1))
            for position in range(3)
        )
        with self.store.connection() as db:
            save(db, self.target["uid"], state)
        # The ownership guard can protect a UID independently of native item
        # eligibility. The reference-only request must choose an eligible copy.
        with patch(
            "wakfu_server.socket_enchantment._equipped",
            side_effect=lambda store, db, account, character, uid: uid
            == self.sublimation["uid"],
        ):
            result = mutate(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                12221,
                struct.pack(">qi", self.target["uid"], 27111),
            )
        self.assertTrue(result["applied"])
        self.assertEqual(result["consumed_uid"], available["uid"])
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.sublimation["uid"],),
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (available["uid"],),
                ).fetchone()
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
            reference=27083,
            quantity=3,
            container=self.bag,
            slot=3,
            allowed_references={27083},
        )
        bonus_item = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=27097,
            quantity=1,
            container=self.bag,
            slot=4,
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
        self.assertEqual(first["consumed"][0]["reference"], 27083)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (shard_stack["uid"],),
                ).fetchone()["quantity"],
                2,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (bonus_item["uid"],),
                ).fetchone()["quantity"],
                1,
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

        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_socket_bonus_installation_receipts "
                "SET applied_at=applied_at - interval '1 minute'"
            )
        late_retry = install_bonus(
            self.store, self.account, self.generation, self.char["id"], body
        )
        self.assertFalse(late_retry["applied"])
        self.assertEqual(late_retry["consumed"], [])
        self.assertEqual(late_retry["cost_kamas"], 0)
        self.assertEqual(late_retry["inventory_packet"][0], 13713)

        upgrade = struct.pack(">qB", self.target["uid"], 1) + struct.pack(
            ">Bii", 0, 27097, 3
        )
        upgraded = install_bonus(
            self.store, self.account, self.generation, self.char["id"], upgrade
        )
        self.assertTrue(upgraded["applied"])
        # A fresh character snapshot must expose the persisted effect to the
        # same evaluator used by equipment snapshots and combat bootstraps.
        from wakfu_server.shard_bonuses import bonuses

        loaded = self.store.character(self.account, self.char["id"])
        equipped_item = next(
            item
            for item in loaded["inventory_items"]
            if item["uid"] == self.target["uid"]
        )
        actual = bonuses(equipped_item, 0)
        self.assertTrue(actual["stats"])
        clean = dict(equipped_item, shard_state=socket_blob())
        self.assertEqual(bonuses(clean, 0)["stats"], {})
        self.assertEqual(
            actual, bonuses(dict(equipped_item, shard_state=upgraded["shard_state"]), 0)
        )
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

    def test_bonus_upgrade_is_limited_by_target_item_level_not_owner_level(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=100 WHERE id=%s", (self.char["id"],)
            )
            db.execute(
                "UPDATE inventory_items SET reference=2024 WHERE uid=%s",
                (self.target["uid"],),
            )
            save(db, self.target["uid"], socket_blob(color=3))
        body = struct.pack(">qB", self.target["uid"], 1) + struct.pack(
            ">Bii", 0, 27094, 3
        )
        with self.assertRaisesRegex(ValueError, "native item-level gate"):
            install_bonus(
                self.store, self.account, self.generation, self.char["id"], body
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_bonus_installation_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_native_13269_rejects_color_level_and_inventory_without_partial_mutation(
        self,
    ):
        shard_stack = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=27083,
            quantity=1,
            container=self.bag,
            slot=3,
            allowed_references={27083},
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
        with self.assertRaisesRegex(ValueError, "Insufficient owned shard items"):
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

    def test_owned_higher_level_target_can_be_modified(self):
        body = struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"])
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=1 WHERE id=%s", (self.char["id"],))
        result = mutate(
            self.store, self.account, self.generation, self.char["id"], 12365, body
        )
        self.assertTrue(result["applied"])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s",
                    (self.sacrifice["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                1,
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
                    "SELECT count(*) AS n FROM native_sublimation_patterns WHERE pattern_type='BASIC'"
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

    def test_sublimation_consumes_one_scroll_from_stack_and_late_retry_consumes_none(
        self,
    ):
        state = b"".join(
            proto_field(10, proto_field(80, position) + proto_field(96, 1))
            for position in range(3)
        )
        with self.store.connection() as db:
            save(db, self.target["uid"], state)
            db.execute(
                "UPDATE inventory_items SET quantity=3 WHERE uid=%s",
                (self.sublimation["uid"],),
            )
        body = struct.pack(">qi", self.target["uid"], 27111)
        result = mutate(
            self.store, self.account, self.generation, self.char["id"], 12221, body
        )
        self.assertTrue(result["applied"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (self.sublimation["uid"],),
                ).fetchone()["quantity"],
                2,
            )
            db.execute(
                "UPDATE inventory_socket_enchantment_receipts SET applied_at=%s",
                (self.store.now() - timedelta(days=1),),
            )
        retry = mutate(
            self.store, self.account, self.generation, self.char["id"], 12221, body
        )
        self.assertFalse(retry["applied"])
        self.assertEqual(retry["shard_state"], result["shard_state"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (self.sublimation["uid"],),
                ).fetchone()["quantity"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts WHERE operation='apply_sublimation'"
                ).fetchone()["n"],
                1,
            )

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

    def test_sacrifice_must_match_reference_and_automatically_splits_one(self):
        body = struct.pack(">qBq", self.target["uid"], 0, self.sacrifice["uid"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=9001,quantity=3 WHERE uid=%s",
                (self.sacrifice["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "reference is incompatible"):
            mutate(
                self.store, self.account, self.generation, self.char["id"], 12365, body
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (self.sacrifice["uid"],),
                ).fetchone()["quantity"],
                3,
            )
            db.execute(
                "UPDATE inventory_items SET reference=2869 WHERE uid=%s",
                (self.sacrifice["uid"],),
            )
        result = mutate(
            self.store, self.account, self.generation, self.char["id"], 12365, body
        )
        self.assertTrue(result["applied"])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_items WHERE uid=%s",
                    (self.sacrifice["uid"],),
                ).fetchone()
            )
            rows = db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE character_id=%s "
                "AND reference=2869",
                (self.char["id"],),
            ).fetchall()
            self.assertEqual(sum(row["quantity"] for row in rows), 3)
            self.assertEqual(len(rows), 2)
            self.assertIn(2, [row["quantity"] for row in rows])

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
