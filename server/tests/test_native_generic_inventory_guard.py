"""Native School 3 pickup guards accept only fixed, positive inventory rules."""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tools import publish_native_generic_rewards as publisher
from tools import install_mission_bundle
from wakfu_server.maps import native_generic_rewards
from wakfu_server.maps import dungeon_criteria


ROOT = Path(__file__).parents[1] / "wakfu_server/maps/native_generic_profiles"


def _school_entries():
    return json.loads((ROOT / "huppermage-registration-pickups.json").read_text())[
        "entries"
    ]


class NativeGenericInventoryGuardTests(unittest.TestCase):
    def test_actual_school3_programs_have_exact_single_fixed_leaf_and_positive_guard(
        self,
    ):
        expected = {
            983: (26212, 2542, 20035),
            984: (26215, 2541, 20037),
            985: (26216, 2540, 20036),
        }
        for entry in _school_entries():
            descriptor = entry["program"]["descriptor_id"]
            location_id, table_id, item_id = expected[descriptor]
            with self.subTest(descriptor=descriptor):
                rule, effects, location, tables = publisher._records(entry)
                loot = next(effect for effect in effects if effect["effect_type"] == 4)
                self.assertEqual(location["object_id"], location_id)
                self.assertEqual(loot["loot_list_id"], table_id)
                self.assertEqual(
                    native_generic_rewards._inventory_loot_reference(
                        type(
                            "DB",
                            (),
                            {
                                "execute": lambda _self, *_: type(
                                    "R",
                                    (),
                                    {
                                        "fetchone": lambda _s: dict(
                                            payload=tables[table_id]["payload"],
                                            source_sha256=tables[table_id][
                                                "source_sha256"
                                            ],
                                        )
                                    },
                                )()
                            },
                        )(),
                        loot,
                    ),
                    item_id,
                )
                self.assertTrue(
                    native_generic_rewards._positive_inventory_guard(
                        loot["criterion"], item_id
                    )
                )

    def test_compiler_fails_closed_for_or_wrong_item_nested_multi_leaf_and_quantity_range(
        self,
    ):
        entries = _school_entries()
        original = entries[0]
        variants = {}

        wrong_or = deepcopy(original)
        loot_effect = next(
            e
            for e in wrong_or["program"]["groups"][0]["actions"][0]["effects"]
            if e["effect_type"] == 4
        )
        loot_effect["criterion"] += " or true"
        variants["or"] = wrong_or

        wrong_item = deepcopy(original)
        wrong_item["program"]["groups"][0]["actions"][0]["effects"][-1]["criterion"] = (
            "IsAchievementRunning(2776) and IsAchievementObjectiveComplete(5596) "
            "and GetItemQuantity(20037) == 0"
        )
        variants["wrong item"] = wrong_item

        nested = deepcopy(original)
        row = nested["loot_tables"]["2542"]["payload"]["gBN"][0]
        row["cqA"], row["aAi"] = True, 2541
        variants["nested"] = nested

        multiple = deepcopy(original)
        multiple["loot_tables"]["2542"]["payload"]["gBN"].append(
            deepcopy(multiple["loot_tables"]["2542"]["payload"]["gBN"][0])
        )
        variants["multiple leaves"] = multiple

        ranged = deepcopy(original)
        ranged["loot_tables"]["2542"]["payload"]["gBN"][0]["cqz"] = 2
        variants["random quantity range"] = ranged

        for label, entry in variants.items():
            with self.subTest(case=label), self.assertRaises(ValueError):
                publisher._records(entry)

    def test_guard_parser_accepts_only_positive_conjunction_with_exact_item_absence(
        self,
    ):
        accepted = (
            "IsAchievementRunning(2776) and GetItemQuantity(20036) == 0",
            "IsAchievementActive(2776) and IsAchievementObjectiveComplete(5596) "
            "and GetItemQuantity(20036) <= 0",
        )
        rejected = (
            "IsAchievementRunning(2776) or GetItemQuantity(20036) == 0",
            "IsAchievementRunning(2776) and GetItemQuantity(20037) == 0",
            "IsAchievementRunning(2776) and (GetItemQuantity(20036) == 0)",
            "IsAchievementComplete(2776) and GetItemQuantity(20036) == 0",
            "GetItemQuantity(20036) == 0 and GetItemQuantity(20037) == 0",
        )
        self.assertTrue(
            all(
                native_generic_rewards._positive_inventory_guard(x, 20036)
                for x in accepted
            )
        )
        self.assertTrue(
            all(
                not native_generic_rewards._positive_inventory_guard(x, 20036)
                for x in rejected
            )
        )

    def test_native_integer_addition_accepts_item_sums_and_rejects_bad_arithmetic(self):
        store = SimpleNamespace(clock=lambda: 1_800_000_000)
        actor = dict(
            id=17,
            inventory_items=[
                dict(uid=1, reference=20035, quantity=1),
                dict(uid=2, reference=20036, quantity=1),
            ],
            quest_items=[],
            account_quest_items=[],
        )
        criterion = "(GetItemQuantity(20035)+GetItemQuantity(20036)) == 2"
        self.assertTrue(dungeon_criteria.evaluate(store, criterion, character=actor))
        self.assertFalse(
            dungeon_criteria.evaluate(
                store,
                "GetItemQuantity(20035)+GetItemQuantity(20036) == 3",
                character=actor,
            )
        )
        with self.assertRaisesRegex(ValueError, "integer authority"):
            dungeon_criteria.evaluate(store, "true + 1 == 2", character=actor)
        with self.assertRaisesRegex(ValueError, "syntax"):
            dungeon_criteria.evaluate(
                store, "GetItemQuantity(20035) * 2 == 2", character=actor
            )
        with self.assertRaisesRegex(ValueError, "integral bounds"):
            dungeon_criteria.evaluate(
                store, "9223372036854775807 + 1 == 2", character=actor
            )

    def test_script_only_clues_never_compile_as_inventory_grants(self):
        document = json.loads((ROOT / "wild-estate-clue-feedback.json").read_text())
        self.assertEqual(len(document["entries"]), 6)
        for entry in document["entries"]:
            _rule, effects, _location, _tables = publisher._records(entry)
            self.assertTrue(effects)
            self.assertTrue(all(effect["effect_type"] == 1 for effect in effects))
            self.assertTrue(all(effect["item_reference"] is None for effect in effects))

    def test_mission_bundle_dispatch_uses_the_fixed_native_generic_publisher(self):
        result = {"programs": 9, "inserted": 9, "locations": 9}
        entry = dict(
            kind="native_generic", document={"schema": publisher.SCHEMA, "entries": []}
        )
        with patch.object(publisher, "install", return_value=result) as install:
            self.assertIs(
                install_mission_bundle._publish_entry(object(), entry), result
            )
        install.assert_called_once()


if __name__ == "__main__":
    unittest.main()
