"""Equipment becomes usable before native build editing, without lost stacks."""
from postgres_case import PostgresCase


class EquipmentStackTests(PostgresCase):
    def test_on_demand_split_preserves_remainder_metadata_and_is_idempotent(self):
        from wakfu_server.equipment_stacks import ensure_singleton

        account, generation, char, item = self.setup_stack(7)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_elements VALUES(%s,2,4)", (item["uid"],)
            )
            db.execute(
                "INSERT INTO inventory_item_bindings VALUES(%s,true,123)",
                (item["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_shards VALUES(%s,%s)",
                (item["uid"], b"\x08\x01"),
            )
            unit = ensure_singleton(db, char["id"], item["uid"])
            self.assertEqual((unit["uid"], unit["quantity"]), (item["uid"], 1))
            ensure_singleton(db, char["id"], item["uid"])
            rows = list(
                db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s", (char["id"],)
                )
            )
            self.assertEqual(sorted(row["quantity"] for row in rows), [1, 6])
            for row in rows:
                self.assertEqual(
                    db.execute(
                        "SELECT damage_elements FROM inventory_item_elements WHERE uid=%s",
                        (row["uid"],),
                    ).fetchone()["damage_elements"],
                    2,
                )
                self.assertTrue(
                    db.execute(
                        "SELECT bound FROM inventory_item_bindings WHERE uid=%s",
                        (row["uid"],),
                    ).fetchone()["bound"]
                )
                self.assertEqual(
                    bytes(
                        db.execute(
                            "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                            (row["uid"],),
                        ).fetchone()["shard_state"]
                    ),
                    b"\x08\x01",
                )

    def test_on_demand_split_full_inventory_and_action_rollback_preserve_stack(self):
        from wakfu_server.equipment_stacks import ensure_singleton

        account, generation, char, item = self.setup_stack(7)
        with self.assertRaisesRegex(ValueError, "later action"):
            with self.store.connection() as db:
                ensure_singleton(db, char["id"], item["uid"])
                raise ValueError("later action failed")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
                ).fetchone()["quantity"],
                7,
            )
            db.execute(
                "UPDATE inventory_containers SET capacity=1 WHERE character_id=%s",
                (char["id"],),
            )
            db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,100,1,%s,0)",
                (char["id"], char["inventory_containers"][1]["uid"]),
            )
        with self.assertRaisesRegex(ValueError, "free slot"):
            with self.store.connection() as db:
                ensure_singleton(db, char["id"], item["uid"])
        with self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s AND reference=%s",
                    (char["id"], item["reference"]),
                )
            )
            self.assertEqual(
                [(row["uid"], row["quantity"]) for row in rows], [(item["uid"], 7)]
            )
            with self.assertRaisesRegex(ValueError, "not owned"):
                ensure_singleton(db, char["id"] + 999, item["uid"])

    def setup_stack(self, quantity=3):
        from wakfu_server.equipment import RULES
        from wakfu_server.inventory_items import grant

        account = self.store.register("equipment-splits", "local-password")["id"]
        char = self.store.create_character(account, "Equipment Splits")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char["id"])
        reference = next(
            ref for ref, rule in RULES.items() if rule["minimum_level"] <= 1
        )
        item = grant(
            self.store,
            account,
            generation,
            char["id"],
            reference=reference,
            quantity=quantity,
            container=char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={reference},
        )
        return account, generation, char, item

    def test_selection_splits_owned_gear_preserving_uid_options_quantity(self):
        account, generation, char, item = self.setup_stack()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_elements VALUES(%s,2,4)", (item["uid"],)
            )
        saved = self.store.select_character(account, generation, char["id"])
        units = [
            row
            for row in saved["inventory_items"]
            if row["reference"] == item["reference"]
        ]
        self.assertEqual(len(units), 3)
        self.assertEqual(sum(row["quantity"] for row in units), 3)
        self.assertIn(item["uid"], [row["uid"] for row in units])
        self.assertTrue(
            all(row["quantity"] == 1 and row["damage_elements"] == 2 for row in units)
        )
        again = self.store.select_character(account, generation, char["id"])
        self.assertEqual(saved["inventory_items"], again["inventory_items"])

    def test_full_bag_keeps_stack_and_one_slot_creates_usable_original(self):
        from wakfu_server.equipment_stacks import ensure_singleton, normalize

        account, generation, char, item = self.setup_stack(4)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_containers SET capacity=1 WHERE character_id=%s",
                (char["id"],),
            )
            # Both existing bags have one slot, so occupy the second with a resource.
            bag = char["inventory_containers"][1]["uid"]
            db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,100,5,%s,0)",
                (char["id"], bag),
            )
            # Login normalization leaves ordinary unidentified stacks intact.
            self.assertEqual(normalize(db, char["id"]), [])
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
                ).fetchone()["quantity"],
                4,
            )
            db.execute(
                "UPDATE inventory_containers SET capacity=2 WHERE uid=%s", (bag,)
            )
            unit = ensure_singleton(db, char["id"], item["uid"])
            self.assertEqual((unit["uid"], unit["quantity"]), (item["uid"], 1))
            rows = list(
                db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s AND reference=%s",
                    (char["id"], item["reference"]),
                )
            )
            self.assertEqual(sorted(row["quantity"] for row in rows), [1, 3])
            self.assertEqual(
                next(row["quantity"] for row in rows if row["uid"] == item["uid"]), 1
            )

    def test_effective_equipment_stack_limit_keeps_resource_rules(self):
        from wakfu_server.equipment import RULES
        from wakfu_server.inventory_move import ACQUISITION_STACKS

        _account, _generation, _character, item = self.setup_stack()
        self.assertIn(item["reference"], RULES)
        self.assertGreater(ACQUISITION_STACKS[item["reference"]]["maximum"], 1)
        self.assertTrue(
            any(rule["maximum"] > 1 for rule in ACQUISITION_STACKS.values())
        )

    def test_save_build_splits_requested_uid_and_bad_sheet_rolls_back(self):
        from wakfu_server.wire import proto_field
        from wakfu_server.inventory_items import grant

        account, generation, char, item = self.setup_stack()
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=6 WHERE id=%s", (char["id"],))
        gear = grant(
            self.store,
            account,
            generation,
            char["id"],
            reference=2021,
            quantity=3,
            container=char["inventory_containers"][0]["uid"],
            slot=1,
            allowed_references={2021},
        )
        sheet = b"".join(
            proto_field(tag, value)
            for tag, value in [(8, 0), (18, b"Owned gear"), (24, 6), (56, 0)]
        )
        equipment = proto_field(10, proto_field(8, gear["uid"]) + proto_field(16, 7))
        blobs = dict(sheet=sheet, equipment=equipment, deck=b"", aptitudes=b"")
        with self.assertRaises(ValueError):
            self.store.save_build(account, generation, char["id"], 0, blobs)
        current = self.store.character(account, char["id"])
        self.assertEqual(
            next(
                row["quantity"]
                for row in current["inventory_items"]
                if row["uid"] == gear["uid"]
            ),
            3,
        )
        equipment = proto_field(10, proto_field(8, gear["uid"]) + proto_field(16, 4))
        saved = self.store.save_build(
            account, generation, char["id"], 0, dict(blobs, equipment=equipment)
        )
        units = [row for row in saved["inventory_items"] if row["reference"] == 2021]
        self.assertEqual(sum(row["quantity"] for row in units), 3)
        self.assertEqual(sorted(row["quantity"] for row in units), [1, 2])
        self.assertEqual(
            next(row["quantity"] for row in units if row["uid"] == gear["uid"]), 1
        )
        self.assertEqual(saved["builds"][0]["equipment"], equipment.hex())
