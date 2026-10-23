"""Native fusion transaction and durable typed appearance custody regressions."""
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server import item_appearance_fusion as fusion
from wakfu_server.inventory_items import grant, item_form, item_proto
from wakfu_server.wire import proto_fields


class ItemAppearanceWireTests(unittest.TestCase):
    def test_equipped_skin_projection_changes_visuals_without_changing_stat_reference(
        self,
    ):
        from wakfu_server.equipment_appearance import rows, change_packet
        from wakfu_server.wire import proto_field

        character = dict(
            id=7,
            account_id=9,
            level=20,
            breed=8,
            active_build_index=0,
            inventory_items=[
                dict(
                    uid=123,
                    character_id=7,
                    reference=2040,
                    quantity=1,
                    appearance_ref=2026,
                )
            ],
            builds={
                0: dict(
                    sheet=proto_field(24, (1 << 64) - 1).hex(),
                    equipment=proto_field(
                        10, proto_field(8, 123) + proto_field(16, 0)
                    ).hex(),
                )
            },
        )
        self.assertEqual(rows(character), ((0, 2040, 2026),))
        previous = dict(
            character,
            inventory_items=[dict(character["inventory_items"][0], appearance_ref=0)],
        )
        self.assertEqual(
            change_packet(previous, character),
            (13060, struct.pack(">qBBii", 7, 1, 0, 2040, 2026)),
        )

    def test_exact_native_three_uid_request_and_both_item_skin_carriers(self):
        self.assertEqual(fusion.decode(struct.pack(">qqq", 11, 12, 13)), (11, 12, 13))
        for data in (
            b"",
            struct.pack(">qqq", 1, 1, 2),
            struct.pack(">qqq", 1, 2, -1),
            struct.pack(">qqq", 1, 2, 3) + b"\x00",
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                fusion.decode(data)
        item = dict(uid=123, reference=2040, quantity=1, appearance_ref=2026)
        self.assertEqual(dict(proto_fields(item_proto(item)))[464], 2026)
        self.assertEqual(item_form(item)[-5:], b"\x01" + struct.pack(">i", 2026))
        bare = dict(item, appearance_ref=0)
        self.assertNotIn(464, dict(proto_fields(item_proto(bare))))


class ItemAppearanceFusionPostgresTests(PostgresCase):
    def fixture(self):
        account = self.store.register("fusion-owner", "local-password")["id"]
        character = self.store.create_character(account, "Fusion Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def give(self, account, generation, character, reference, slot, quantity=1):
        bag = character["inventory_containers"][0]["uid"]
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=quantity,
            container=bag,
            slot=slot,
            allowed_references={reference},
        )

    def setup_items(self):
        account, generation, character = self.fixture()
        source = self.give(account, generation, character, 19292, 0, quantity=2)
        stat = self.give(account, generation, character, 2040, 1)
        skin = self.give(account, generation, character, 2026, 2)
        body = struct.pack(">qqq", source["uid"], stat["uid"], skin["uid"])
        return account, generation, character, source, stat, skin, body

    def test_fusion_preserves_stat_identity_metadata_builds_and_replay_without_double_debit(
        self,
    ):
        from test_inventory_shards import sample_shard_state
        from wakfu_server.inventory_shards import save

        account, generation, character, source, stat, skin, body = self.setup_items()
        shard = sample_shard_state()
        with self.store.connection() as db:
            save(db, stat["uid"], shard)
            before = dict(
                db.execute(
                    "SELECT * FROM inventory_items WHERE uid=%s", (stat["uid"],)
                ).fetchone()
            )
        builds = self.store.character(account, character["id"])["builds"]
        result = fusion.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        self.assertTrue(result["applied"])
        self.assertEqual(result["appearance_ref"], 2026)
        self.assertEqual([p[0] for p in result["packets"]], [13713, 13078])
        with self.store.connection() as db:
            after = dict(
                db.execute(
                    "SELECT * FROM inventory_items WHERE uid=%s", (stat["uid"],)
                ).fetchone()
            )
            self.assertEqual(before, after)
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_items WHERE uid=%s", (skin["uid"],)
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(
                bytes(
                    db.execute(
                        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                        (stat["uid"],),
                    ).fetchone()["shard_state"]
                ),
                shard,
            )
        restored = self.reopen().character(account, character["id"])
        target = next(
            row for row in restored["inventory_items"] if row["uid"] == stat["uid"]
        )
        self.assertEqual(target["appearance_ref"], 2026)
        self.assertEqual(restored["builds"], builds)
        replay = fusion.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        self.assertFalse(replay["applied"])
        self.assertEqual(
            next(
                row
                for row in replay["character"]["inventory_items"]
                if row["uid"] == source["uid"]
            )["quantity"],
            1,
        )

    def test_level_type_stack_combat_and_foreign_guards_leave_all_units_unchanged(self):
        account, generation, character, source, stat, skin, body = self.setup_items()
        wrong_type = self.give(account, generation, character, 2023, 3)
        same_skin = self.give(account, generation, character, 2040, 4)
        before = self.store.character(account, character["id"])["inventory_items"]
        attempts = [
            (body, True),
            (struct.pack(">qqq", source["uid"], skin["uid"], stat["uid"]), False),
            (struct.pack(">qqq", source["uid"], stat["uid"], wrong_type["uid"]), False),
            (struct.pack(">qqq", source["uid"], stat["uid"], same_skin["uid"]), False),
        ]
        for request, combat in attempts:
            with self.subTest(request=request, combat=combat), self.assertRaises(
                ValueError
            ):
                fusion.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    request,
                    in_fight=combat,
                )
        other = self.store.register("fusion-outsider", "local-password")["id"]
        outsider = self.store.create_character(other, "Fusion Outsider")
        other_generation = self.store.begin_session(other)
        self.store.select_character(other, other_generation, outsider["id"])
        with self.assertRaises(ValueError):
            fusion.use(
                self.store,
                other,
                other_generation,
                outsider["id"],
                body,
                in_fight=False,
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET quantity=2 WHERE uid=%s", (skin["uid"],)
            )
        with self.assertRaises(ValueError):
            fusion.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET quantity=1 WHERE uid=%s", (skin["uid"],)
            )
        self.assertEqual(
            self.store.character(account, character["id"])["inventory_items"], before
        )

    def test_fused_item_exchange_custody_keeps_appearance_and_rejects_bare_stack_merge(
        self,
    ):
        from wakfu_server.exchange_transfer import apply, _same_stack
        from wakfu_server.inventory_items import load

        account, generation, character, source, stat, skin, body = self.setup_items()
        fusion.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        other = self.store.register("fusion-recipient", "local-password")["id"]
        recipient = self.store.create_character(other, "Fusion Recipient")
        with self.store.connection() as db:
            target = next(
                row for row in load(db, character["id"]) if row["uid"] == stat["uid"]
            )
            bare = dict(target)
            bare.pop("appearance_ref")
            self.assertFalse(_same_stack(target, bare))
            moved = dict(
                target,
                character_id=recipient["id"],
                container=recipient["inventory_containers"][0]["uid"],
                slot=0,
            )
            apply(db, [target], {stat["uid"]: moved})
        saved = self.reopen().character(other, recipient["id"])
        received = next(
            row for row in saved["inventory_items"] if row["uid"] == stat["uid"]
        )
        self.assertEqual(
            (received["reference"], received["appearance_ref"]), (2040, 2026)
        )

    def test_account_appearance_learning_uses_fused_skin_and_replay_retains_it(self):
        from wakfu_server.mimisymbic_learning import learn

        account, generation, character, source, stat, skin, body = self.setup_items()
        fusion.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        mirror = self.give(account, generation, character, 31508, 2)
        request = struct.pack(">iqq", 13882, mirror["uid"], stat["uid"])
        result = learn(self.store, account, generation, character["id"], request)
        self.assertTrue(result["applied"])
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT * FROM mimisymbic_learning_receipts WHERE source_uid=%s",
                (mirror["uid"],),
            ).fetchone()
        self.assertEqual(
            (receipt["target_ref"], receipt["appearance_ref"]), (2040, 2026)
        )
        replay = learn(self.store, account, generation, character["id"], request)
        self.assertFalse(replay["applied"])
        target = next(
            item
            for item in replay["character"]["inventory_items"]
            if item["uid"] == stat["uid"]
        )
        self.assertEqual((target["reference"], target["appearance_ref"]), (2040, 2026))
