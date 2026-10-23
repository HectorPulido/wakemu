"""Focused qualification for migration 214's ten native Rift box extensions."""
import json
import struct
from pathlib import Path
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.random_item_actions import draw_products, use
from wakfu_server.random_item_criteria import evaluate
from wakfu_server.haven_bag_furniture_knowledge import _rules
from wakfu_server.inventory_items import grant


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = json.loads(
    (ROOT / "protocol/native-random-item-extensions.json").read_text()
)
ACTION = next(row for row in EXTENSION["actions"] if row["item_ref"] == 28821)
CRITERIA = EXTENSION["policy"]["criteria"]


class Rolls:
    def __init__(self, *values):
        self.values = iter(values)

    def randbelow(self, upper):
        if upper == 1:
            return 0
        value = next(self.values)
        if not 0 <= value < upper:
            raise AssertionError((value, upper))
        return value


def entry(reference, weight=1, criterion=""):
    return {
        "aAi": reference,
        "cmY": weight,
        "bfh": 1,
        "cqy": 1,
        "cqz": 1,
        "cqA": False,
        "csE": 1,
        "czl": 0,
        "czk": criterion,
        "gBO": [],
    }


class RandomItemExtensionTests(unittest.TestCase):
    def test_native_state_and_neo_map_criteria_boundaries(self):
        character = {"consumable_states": []}
        self.assertFalse(
            evaluate(CRITERIA[0], character, native_map_id=1134, is_neo_server=False)
        )
        self.assertFalse(
            evaluate(CRITERIA[1], character, native_map_id=1134, is_neo_server=False)
        )
        self.assertTrue(
            evaluate(CRITERIA[0], character, native_map_id=1134, is_neo_server=True)
        )
        self.assertTrue(
            evaluate(CRITERIA[1], character, native_map_id=1134, is_neo_server=True)
        )
        for excluded in (1314, 1316, 1318, 1320, 1322, 1324, 1329, 1330, 1345, 1347):
            self.assertFalse(
                evaluate(
                    CRITERIA[0], character, native_map_id=excluded, is_neo_server=True
                )
            )
            self.assertFalse(
                evaluate(
                    CRITERIA[1], character, native_map_id=excluded, is_neo_server=True
                )
            )
        character["consumable_states"] = [{"state_id": 6836, "level": 11}]
        self.assertTrue(
            evaluate(CRITERIA[0], character, native_map_id=1314, is_neo_server=True)
        )
        self.assertTrue(
            evaluate(CRITERIA[1], character, native_map_id=1314, is_neo_server=False)
        )
        character["consumable_states"][0]["level"] = 6
        self.assertFalse(
            evaluate(CRITERIA[0], character, native_map_id=1314, is_neo_server=False)
        )
        self.assertTrue(
            evaluate(CRITERIA[1], character, native_map_id=1314, is_neo_server=False)
        )

    def test_type_three_requires_opt_in_and_criteria_filter_before_weighted_roll(self):
        table = {
            "d": 3335,
            "czg": 3,
            "gBN": [entry(20595, 1, "native-criterion"), entry(20597, 1)],
        }
        lookup = {3335: table}.__getitem__
        with self.assertRaisesRegex(ValueError, "table kind"):
            draw_products(3335, lookup, Rolls(0))
        self.assertEqual(
            {20597: 1},
            draw_products(
                3335,
                lookup,
                Rolls(0),
                allowed_table_types=(1, 3),
                entry_allowed=lambda text: False,
            ),
        )
        self.assertEqual(
            {20595: 1},
            draw_products(
                3335,
                lookup,
                Rolls(0),
                allowed_table_types=(1, 3),
                entry_allowed=lambda text: text == "native-criterion",
            ),
        )
        only_filtered = {3335: {**table, "gBN": [entry(20595, 1, "native-criterion")]}}
        self.assertEqual(
            {},
            draw_products(
                3335,
                only_filtered.__getitem__,
                Rolls(),
                allowed_table_types=(1, 3),
                entry_allowed=lambda text: False,
            ),
        )


class RandomItemExtensionPostgresTests(PostgresCase):
    def fixture(self):
        account = self.store.register("rift-box-test", "local-password")["id"]
        character = self.store.create_character(account, "Rift Box Main")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=0 WHERE id=%s",
                (character["id"],),
            )
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_server_mode',%s) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps({"version": 1, "is_neo_server": True}),),
            )
        character = self.store.character(account, character["id"])
        container = next(
            row for row in character["inventory_containers"] if row["kind"] == 0
        )
        box = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=28821,
            quantity=1,
            container=container["uid"],
            slot=0,
            allowed_references={28821},
        )
        action_id = _rules()[28821]["use_action_id"]
        return (
            account,
            generation,
            character,
            box,
            struct.pack(">iq", action_id, box["uid"]),
        )

    def test_native_extension_use_accepts_type_three_and_rolls_back_atomically(self):
        account, generation, character, box, body = self.fixture()

        class FixedDraw:
            def __init__(self, *args):
                self.rng = Rolls(1, 0, 0, 0)

            def randbelow(self, upper):
                return self.rng.randbelow(upper)

        from wakfu_server.random_item_criteria import evaluate as native_evaluate

        criteria_calls = []

        def observed_criterion(text, owned_character, **kwargs):
            accepted = native_evaluate(text, owned_character, **kwargs)
            criteria_calls.append(
                (text, accepted, kwargs["native_map_id"], kwargs["is_neo_server"])
            )
            return accepted

        resolved = {}

        def fail_delivery(*args):
            resolved.update(args[-1])
            raise ValueError("capacity fixture")

        with patch("wakfu_server.random_item_actions.PrivateDraw", FixedDraw), patch(
            "wakfu_server.random_item_criteria.evaluate", side_effect=observed_criterion
        ), patch(
            "wakfu_server.item_action_delivery.grant_outputs", side_effect=fail_delivery
        ):
            with self.assertRaisesRegex(ValueError, "capacity"):
                use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    body,
                    in_fight=False,
                )

        self.assertTrue(criteria_calls)
        self.assertTrue(all(call[1:] == (True, 1134, True) for call in criteria_calls))
        self.assertTrue(resolved)
        self.assertIn(
            20595, resolved
        )  # Type-3 guaranteed child table 3335 was traversed.
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (box["uid"],)
                ).fetchone()["quantity"],
            )
            self.assertIsNone(
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (box["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                10,
                db.execute(
                    "SELECT count(*) FROM native_random_item_extensions"
                ).fetchone()["count"],
            )
            self.assertEqual(
                10,
                db.execute(
                    "SELECT count(*) FROM native_random_item_actions WHERE available=true AND item_ref IN (SELECT item_ref FROM native_random_item_extensions)"
                ).fetchone()["count"],
            )
