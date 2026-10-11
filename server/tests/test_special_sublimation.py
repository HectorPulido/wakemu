import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant, item_proto
from wakfu_server.inventory_shards import legacy_option, save
from wakfu_server.socket_enchantment import mutate
from wakfu_server.socket_enchantment_wire import encode_success
from wakfu_server.wire import proto_field, proto_fields


class SpecialSublimationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "special-sublimation", "local-test-password"
        )["id"]
        self.char = self.store.create_character(self.account, "Special Sublimation")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])
        self.bag = self.char["inventory_containers"][0]["uid"]
        self.slot = 0
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=100 WHERE id=%s", (self.char["id"],)
            )
            db.execute(
                "UPDATE account_wallets SET kamas=100 WHERE account_id=%s",
                (self.account,),
            )

    def grant(self, reference, quantity=1):
        item = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=reference,
            quantity=quantity,
            container=self.bag,
            slot=self.slot,
            allowed_references={reference},
        )
        self.slot += 1
        return item

    def apply(self, target, scroll):
        return mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            12221,
            struct.pack(">qi", target["uid"], scroll),
        )

    def remove(self, target, special):
        return mutate(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            12364,
            struct.pack(">qB", target["uid"], special),
        )

    def quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def test_complete_native_special_catalog_and_exact_rarity_targets(self):
        with self.store.connection() as db:
            counts = {
                r["pattern_type"]: r["n"]
                for r in db.execute(
                    "SELECT pattern_type,count(*) AS n FROM native_sublimation_patterns GROUP BY pattern_type"
                ).fetchall()
            }
            self.assertEqual(counts, dict(BASIC=388, EPIC=32, RELIC=47))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_sublimation_targets"
                ).fetchone()["n"],
                348,
            )
            for reference, kind, rarity in ((10272, "EPIC", 7), (24309, "RELIC", 5)):
                row = db.execute(
                    "SELECT pattern_type,rarity_code FROM native_sublimation_targets WHERE reference=%s",
                    (reference,),
                ).fetchone()
                self.assertEqual(
                    (row["pattern_type"], row["rarity_code"]), (kind, rarity)
                )

    def test_epic_and_relic_install_without_prior_identification_or_color_pattern(self):
        for reference, scroll in ((10272, 24130), (24309, 14186)):
            with self.subTest(reference=reference):
                target, ingredient = self.grant(reference), self.grant(scroll, 2)
                before = self.store.character(self.account, self.char["id"])
                before_target = next(
                    item
                    for item in before["inventory_items"]
                    if item["uid"] == target["uid"]
                )
                result = self.apply(target, scroll)
                fields = dict(proto_fields(result["shard_state"]))
                self.assertTrue(result["applied"])
                self.assertEqual(fields[32], scroll)
                self.assertNotIn(10, fields)
                self.assertNotIn(24, fields)
                after_target = next(
                    item
                    for item in result["inventory_items"]
                    if item["uid"] == target["uid"]
                )
                for key in ("damage_elements", "resistance_elements"):
                    self.assertEqual(after_target.get(key), before_target.get(key))
                self.assertEqual(self.quantity(ingredient["uid"]), 1)
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE inventory_socket_enchantment_receipts SET applied_at=applied_at-interval '1 hour' WHERE uid=%s",
                        (target["uid"],),
                    )
                repeated = self.apply(target, scroll)
                self.assertFalse(repeated["applied"])
                self.assertEqual(self.quantity(ingredient["uid"]), 1)

    def test_basic_and_special_coexist_publish_and_survive_reopen(self):
        target = self.grant(10272)
        self.grant(27111)
        self.grant(24130)
        state = b"".join(
            proto_field(10, proto_field(80, i) + proto_field(96, 1)) for i in range(3)
        ) + proto_field(72, 0)
        with self.store.connection() as db:
            save(db, target["uid"], state)
        self.apply(target, 27111)
        applied = self.apply(target, 24130)
        fields = dict(proto_fields(applied["shard_state"]))
        self.assertEqual((fields[24], fields[32]), (27111, 24130))
        self.assertEqual(encode_success(self.char["id"], applied)[0], 13983)
        self.assertIn(
            legacy_option(applied["shard_state"]), applied["inventory_packet"][1]
        )
        reopened = self.reopen().character(self.account, self.char["id"])
        owned = next(
            item for item in reopened["inventory_items"] if item["uid"] == target["uid"]
        )
        self.assertEqual(owned["shard_state"], applied["shard_state"])
        self.assertIn(item_proto(owned), applied["equipment_packet"][1])
        removed = self.remove(target, 0)
        self.assertEqual(
            (
                dict(proto_fields(removed["shard_state"]))[24],
                dict(proto_fields(removed["shard_state"]))[32],
            ),
            (0, 24130),
        )
        self.assertEqual(encode_success(self.char["id"], removed)[0], 13793)

    def test_special_replacement_and_replay_preserve_basic_and_consume_once(self):
        target, ingredient = self.grant(10272), self.grant(24131, 2)
        with self.store.connection() as db:
            save(
                db,
                target["uid"],
                proto_field(24, 27111) + proto_field(32, 24130) + proto_field(72, 0),
            )
        result = self.apply(target, 24131)
        self.assertEqual(
            (
                dict(proto_fields(result["shard_state"]))[24],
                dict(proto_fields(result["shard_state"]))[32],
            ),
            (27111, 24131),
        )
        self.assertEqual(self.quantity(ingredient["uid"]), 1)
        repeated = self.apply(target, 24131)
        self.assertFalse(repeated["applied"])
        self.assertEqual(self.quantity(ingredient["uid"]), 1)
        reopened = self.reopen().character(self.account, self.char["id"])
        owned = next(
            item for item in reopened["inventory_items"] if item["uid"] == target["uid"]
        )
        self.assertEqual(owned["shard_state"], result["shard_state"])

    def test_special_removal_preserves_basic_and_socket_bytes(self):
        target = self.grant(10272)
        slots = b"".join(
            proto_field(10, proto_field(80, i) + proto_field(96, 1)) for i in range(3)
        )
        with self.store.connection() as db:
            save(
                db,
                target["uid"],
                slots
                + proto_field(24, 27111)
                + proto_field(32, 24130)
                + proto_field(72, 0),
            )
        result = self.remove(target, 1)
        fields = dict(proto_fields(result["shard_state"]))
        self.assertEqual((fields[24], fields[32]), (27111, 0))
        self.assertTrue(result["shard_state"].startswith(slots))

    def test_wrong_target_rarity_rejects_before_scroll_fee_or_state_mutation(self):
        ingredient = self.grant(24130, 2)
        for reference in (2869, 24309):
            target = self.grant(reference)
            with self.subTest(reference=reference), self.assertRaisesRegex(
                ValueError, "Target rarity"
            ):
                self.apply(target, 24130)
            self.assertEqual(self.quantity(ingredient["uid"]), 2)
            with self.store.connection() as db:
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM inventory_item_shards WHERE uid=%s",
                        (target["uid"],),
                    ).fetchone()
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
                        "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                    ).fetchone()["n"],
                    0,
                )

    def test_special_response_serialization_failure_rolls_back_everything(self):
        target, ingredient = self.grant(10272), self.grant(24130, 2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{operation_kamas,apply_sublimation}','7') WHERE name='socket_enchantment_policy'"
            )
        with patch(
            "wakfu_server.inventory_items.equipment_inventory",
            side_effect=ValueError("registry rejected"),
        ):
            with self.assertRaisesRegex(ValueError, "registry rejected"):
                self.apply(target, 24130)
        self.assertEqual(self.quantity(ingredient["uid"]), 2)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_item_shards WHERE uid=%s", (target["uid"],)
                ).fetchone()
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
                    "SELECT count(*) AS n FROM inventory_socket_enchantment_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_disabled_or_unaccredited_special_authority_cannot_consume_scroll(self):
        target, ingredient = self.grant(10272), self.grant(24130, 2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE native_sublimation_targets SET client_jar_sha256=%s WHERE reference=10272",
                ("0" * 64,),
            )
        with self.assertRaisesRegex(ValueError, "Malformed native sublimation target"):
            self.apply(target, 24130)
        self.assertEqual(self.quantity(ingredient["uid"]), 2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE native_sublimation_patterns SET enabled=FALSE WHERE reference=24130"
            )
        with self.assertRaisesRegex(ValueError, "enabled native pattern"):
            self.apply(target, 24130)
        self.assertEqual(self.quantity(ingredient["uid"]), 2)
