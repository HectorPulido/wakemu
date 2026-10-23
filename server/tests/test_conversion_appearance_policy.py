"""Explicit native-compatible appearance preservation across conversion."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import conversion_item_actions as actions
from wakfu_server.conversion_appearance_policy import validate_target


class ConversionAppearancePolicyTests(unittest.TestCase):
    def test_native_type_level_and_identity_contracts(self):
        rows = {
            1: dict(normalized_type=119, item_level=20),
            2: dict(normalized_type=119, item_level=20),
            3: dict(normalized_type=119, item_level=11),
            4: dict(normalized_type=119, item_level=21),
            5: dict(normalized_type=120, item_level=11),
        }
        with patch(
            "wakfu_server.item_appearance_fusion._target",
            side_effect=lambda db, ref: rows[ref],
        ):
            self.assertEqual(validate_target(None, 1, 2, 3), 3)
            for args in ((1, 2, 4), (1, 2, 5), (True, 2, 3), (1, 0, 3)):
                with self.subTest(args=args), self.assertRaises(ValueError):
                    validate_target(None, *args)


class ConversionAppearancePostgresTests(PostgresCase):
    def fixture(self):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.fixture(self)

    def give(self, *args, **kwargs):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.give(self, *args, **kwargs)

    def body(self, item):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.body(self, item)

    def test_native_fusion_then_conversion_preserves_donor_only_on_fresh_main(self):
        from wakfu_server.item_appearance_fusion import use

        account, generation, character = self.fixture()
        catalyst = self.give(account, generation, character, 19292)
        source = self.give(account, generation, character, 24039, slot=1)
        # The native source and donor must be the same normalized equipment
        # type, with the donor no higher level than the source. Ref2023 is a
        # verified same-type, lower-level donor for this recipe.
        donor = self.give(account, generation, character, 2023, slot=2)
        use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qqq", catalyst["uid"], source["uid"], donor["uid"]),
            in_fight=False,
        )
        resident = self.give(account, generation, character, 20667, slot=0)
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(source),
            in_fight=False,
        )
        main = next(
            row
            for row in result["character"]["inventory_items"]
            if row["reference"] == 20667 and row["uid"] != resident["uid"]
        )
        self.assertNotEqual(main["uid"], source["uid"])
        self.assertEqual(main["appearance_ref"], 2023)
        self.assertEqual(result["preserved_appearances"], {20667: 2023})
        for item in result["character"]["inventory_items"]:
            if item["uid"] != main["uid"]:
                self.assertNotIn("appearance_ref", item)
        self.assertEqual(
            main,
            next(
                row
                for row in self.reopen().character(account, character["id"])[
                    "inventory_items"
                ]
                if row["uid"] == main["uid"]
            ),
        )

    def test_incompatible_appearance_refuses_without_consuming_source(self):
        account, generation, character = self.fixture()
        source = self.give(account, generation, character, 24039)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,9430)",
                (source["uid"],),
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
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT appearance_ref FROM inventory_item_appearances WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["appearance_ref"],
                9430,
            )
