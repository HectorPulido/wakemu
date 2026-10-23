"""Explicit Wakemu identified-only conversion policy; no official inheritance claim."""
from collections import Counter
from copy import deepcopy
import unittest

from postgres_case import PostgresCase
from wakfu_server import conversion_item_actions as actions
from wakfu_server.item_action_delivery import validate_selections


class IdentifiedConversionContractTests(unittest.TestCase):
    def test_104_native_contracts_match_and_output_selections_validate_strictly(self):
        from wakfu_server.element_selection import _required_counts

        compatible = []
        for plan in actions.descriptors()["items"]:
            try:
                target = actions.identified_contract(plan)
            except ValueError:
                continue
            compatible.append(plan["item_ref"])
            self.assertEqual(plan["products"][str(target)], 1)
            self.assertEqual(
                _required_counts(plan["item_ref"]), _required_counts(target)
            )
        self.assertEqual(len(compatible), 104)
        self.assertEqual(len(set(compatible)), 104)
        self.assertIn(24110, compatible)
        selection = {20720: dict(damage_elements=14, resistance_elements=0)}
        before = deepcopy(selection)
        self.assertEqual(selection, validate_selections({20720: 1}, selection))
        self.assertEqual(before, selection)
        for products, selected in (
            ({20720: 2}, selection),
            ({20720: True}, selection),
            ({20720: 1}, {20720: dict(damage_elements=2, resistance_elements=0)}),
            ({20720: 1}, {20720: dict(damage_elements=14, resistance_elements=2)}),
            (
                {20720: 1},
                {20720: dict(damage_elements=14, resistance_elements=0, extra=1)},
            ),
            ({2504: 1}, {2504: dict(damage_elements=2, resistance_elements=0)}),
        ):
            with self.subTest(products=products, selected=selected), self.assertRaises(
                ValueError
            ):
                validate_selections(products, selected)


class IdentifiedConversionPostgresTests(PostgresCase):
    def fixture(self):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.fixture(self)

    def give(self, *args, **kwargs):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.give(self, *args, **kwargs)

    def body(self, item):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.body(self, item)

    def selected(self, account, generation, character, *, quantity=1, damage=14):
        source = self.give(account, generation, character, 24110, quantity=quantity)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_item_elements SET damage_elements=%s WHERE uid=%s",
                (damage, source["uid"]),
            )
        return source

    def test_actual_24110_preserves_only_main_masks_new_uid_binding_and_reconnect(self):
        import struct
        from wakfu_server.element_selection import select

        account, generation, character = self.fixture()
        source = self.give(account, generation, character, 24110)
        selection = select(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qBB", source["uid"], 14, 0),
        )
        self.assertTrue(selection["applied"])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_item_shards WHERE uid=%s", (source["uid"],)
                ).fetchone()
            )
        existing = self.give(account, generation, character, 20720, slot=1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_item_elements SET damage_elements=28 WHERE uid=%s",
                (existing["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,24110)",
                (source["uid"],),
            )
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(source),
            in_fight=False,
        )
        items = result["character"]["inventory_items"]
        main = next(
            row
            for row in items
            if row["reference"] == 20720 and row["uid"] != existing["uid"]
        )
        self.assertNotEqual(main["uid"], source["uid"])
        self.assertEqual(
            (main["quantity"], main["damage_elements"], main["resistance_elements"]),
            (1, 14, 0),
        )
        unchanged = next(row for row in items if row["uid"] == existing["uid"])
        self.assertEqual((unchanged["quantity"], unchanged["damage_elements"]), (1, 28))
        self.assertEqual(
            {20720: dict(damage_elements=14, resistance_elements=0)},
            result["preserved_selections"],
        )
        expected = Counter({int(ref): qty for ref, qty in result["products"].items()})
        expected[20720] += 1
        self.assertEqual(
            Counter(
                {
                    ref: sum(
                        row["quantity"] for row in items if row["reference"] == ref
                    )
                    for ref in expected
                }
            ),
            expected,
        )
        for item in items:
            if item["uid"] == existing["uid"]:
                continue
            if item["reference"] != 20720:
                self.assertEqual(
                    (
                        item.get("damage_elements", 0),
                        item.get("resistance_elements", 0),
                    ),
                    (0, 0),
                )
            with self.store.connection() as db:
                self.assertTrue(
                    db.execute(
                        "SELECT bound FROM inventory_item_bindings WHERE uid=%s",
                        (item["uid"],),
                    ).fetchone()["bound"]
                )
        restored = self.reopen().character(account, character["id"])
        self.assertEqual(items, restored["inventory_items"])

    def test_unsupported_state_invalid_masks_and_nonsingleton_preserve_source(self):
        account, generation, character = self.fixture()
        for state in ("cardinality", "quantity", "shards", "appearance", "nonce"):
            with self.subTest(state=state):
                source = self.selected(
                    account,
                    generation,
                    character,
                    quantity=2 if state == "quantity" else 1,
                    damage=2 if state == "cardinality" else 14,
                )
                with self.store.connection() as db:
                    if state == "shards":
                        db.execute(
                            "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                            (source["uid"], b"\x18\x00"),
                        )
                    elif state == "appearance":
                        db.execute(
                            "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,2024)",
                            (source["uid"],),
                        )
                    elif state == "nonce":
                        db.execute(
                            "INSERT INTO random_item_use_counters(source_uid,next_use) VALUES(%s,7)",
                            (source["uid"],),
                        )
                    before = dict(
                        db.execute(
                            "SELECT * FROM inventory_items WHERE uid=%s",
                            (source["uid"],),
                        ).fetchone()
                    )
                    masks = dict(
                        db.execute(
                            "SELECT * FROM inventory_item_elements WHERE uid=%s",
                            (source["uid"],),
                        ).fetchone()
                    )
                with self.assertRaises(ValueError):
                    actions.use(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        self.body(source),
                        in_fight=False,
                    )
                with self.store.connection() as db:
                    self.assertEqual(
                        before,
                        dict(
                            db.execute(
                                "SELECT * FROM inventory_items WHERE uid=%s",
                                (source["uid"],),
                            ).fetchone()
                        ),
                    )
                    self.assertEqual(
                        masks,
                        dict(
                            db.execute(
                                "SELECT * FROM inventory_item_elements WHERE uid=%s",
                                (source["uid"],),
                            ).fetchone()
                        ),
                    )
                    self.assertEqual(
                        1,
                        db.execute(
                            "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                            (character["id"],),
                        ).fetchone()["n"],
                    )
                    db.execute(
                        "DELETE FROM inventory_items WHERE character_id=%s",
                        (character["id"],),
                    )

    def test_metadata_aware_capacity_rolls_back_source_masks_and_earlier_refund(self):
        from wakfu_server.combat_drop_delivery import _container_can_hold

        account, generation, character = self.fixture()
        source = self.selected(account, generation, character)
        # An unidentified existing main unit must not absorb the selected output.
        self.give(account, generation, character, 20720, slot=1)
        plan = next(
            row for row in actions.descriptors()["items"] if row["item_ref"] == 24110
        )
        next_slot = 2
        for reference in sorted(
            int(ref) for ref in plan["products"] if int(ref) not in (16367, 20720)
        ):
            self.give(account, generation, character, reference, slot=next_slot)
            next_slot += 1
        bag = character["inventory_containers"][0]["uid"]
        for container in character["inventory_containers"]:
            if not _container_can_hold(container, character["id"]):
                continue
            for slot in range(
                next_slot if container["uid"] == bag else 0, container["capacity"]
            ):
                self.give(
                    account,
                    generation,
                    character,
                    9724,
                    slot=slot,
                    container=container["uid"],
                )
        with self.store.connection() as db:
            before = list(
                db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (character["id"],),
                )
            )
            masks = list(
                db.execute(
                    "SELECT * FROM inventory_item_elements WHERE uid=ANY(%s) ORDER BY uid",
                    ([row["uid"] for row in before],),
                )
            )
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(source),
                in_fight=False,
            )
        with self.store.connection() as db:
            self.assertEqual(
                before,
                list(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                ),
            )
            self.assertEqual(
                masks,
                list(
                    db.execute(
                        "SELECT * FROM inventory_item_elements WHERE uid=ANY(%s) ORDER BY uid",
                        ([row["uid"] for row in before],),
                    )
                ),
            )

    def test_active_hero_receives_identified_main_in_its_own_inventory(self):
        from wakfu_server.characters import heroes

        account, generation, main = self.fixture()
        hero = self.store.create_character(account, "Identified Hero")
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        source = self.selected(account, generation, hero)
        result = actions.use(
            self.store,
            account,
            generation,
            main["id"],
            self.body(source),
            in_fight=False,
        )
        self.assertEqual(hero["id"], result["character"]["id"])
        product = next(
            row
            for row in result["character"]["inventory_items"]
            if row["reference"] == 20720
        )
        self.assertEqual(
            (
                product["quantity"],
                product["damage_elements"],
                product["resistance_elements"],
            ),
            (1, 14, 0),
        )
        self.assertNotEqual(product["uid"], source["uid"])
        self.assertEqual(
            [], self.store.character(account, main["id"])["inventory_items"]
        )
