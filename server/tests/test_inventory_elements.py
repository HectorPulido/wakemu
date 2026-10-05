import struct
import tempfile
import unittest
from pathlib import Path
from random import Random
from unittest.mock import patch
from wakfu_server.inventory_elements import create, masks, bonuses as selected_bonuses
from wakfu_server.inventory_items import grant, item_proto, item_form
from wakfu_server.equipment_stats import bonuses, CATALOG, _flat
from wakfu_server.store import Store
from wakfu_server.wire import proto_field, proto_fields


class InventoryElementsTests(unittest.TestCase):
    def test_native_creation_selection_and_legacy_absence_are_distinct(self):
        selected = create(2869, rng=Random(0))
        self.assertEqual(selected["damage_elements"].bit_count(), 3)
        self.assertNotEqual(selected["damage_elements"], (1 << 1) | (1 << 2) | (1 << 3))
        effect = next(x for x in CATALOG[2869]["effects"] if x["generic"] == 1068)
        self.assertEqual(selected_bonuses({}, effect), {})
        actual = selected_bonuses(selected, effect)
        expected = {
            20 + element: 21
            for element in (1, 2, 3, 4)
            if selected["damage_elements"] & (1 << element)
        }
        self.assertEqual(actual, expected)
        self.assertEqual(
            selected_bonuses(
                dict(damage_elements=2, resistance_elements=8),
                dict(effect, generic=1069),
            ),
            {30: 21},
        )
        for bad in (
            dict(damage_elements=1, resistance_elements=0),
            dict(damage_elements=32, resistance_elements=0),
            dict(damage_elements=2),
        ):
            with self.assertRaises(ValueError):
                masks(bad)

    def test_sql_grant_reopen_item_codecs_and_repeated_equipment_preserve_masks(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("element-unit", "local-test-password")["id"]
            char = store.create_character(account, "Element Unit")
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            with patch(
                "wakfu_server.inventory_elements.SystemRandom", return_value=Random(0)
            ):
                item = grant(
                    store,
                    account,
                    generation,
                    char["id"],
                    reference=2869,
                    quantity=1,
                    container=char["inventory_containers"][0]["uid"],
                    slot=0,
                    allowed_references={2869},
                )
            selected = masks(item)
            reopened = Store(store.path).character(account, char["id"])[
                "inventory_items"
            ][0]
            self.assertEqual(masks(reopened), selected)
            nested = dict(proto_fields(item_proto(item)))[450]
            self.assertEqual(
                dict(proto_fields(nested)), {8: selected[0], 16: selected[1]}
            )
            self.assertEqual(
                item_form(item)[14:], bytes(5) + bytes((1, *selected, 0, 0))
            )
            sheet = proto_field(
                10, proto_field(8, item["uid"]) + proto_field(16, 15)
            ).hex()
            loaded = dict(
                store.character(account, char["id"]),
                level=200,
                effective_level=200,
                builds={0: dict(equipment=sheet)},
            )
            first = bonuses(loaded)
            self.assertFalse(first["unsupported"])
            self.assertEqual(first, bonuses(loaded))
            for element in (1, 2, 3, 4):
                self.assertEqual(
                    first["stats"].get(20 + element, 0),
                    21 if selected[0] & (1 << element) else 0,
                )

    def test_native_copy_minus_one_with_absent_equipment_trigger_is_zero(self):
        effect = dict(
            runner="eWQ",
            values=[-1],
            stat_id=27,
            effect_criteria=False,
            has_triggers=False,
            target_mask=0,
            parameter_count=1,
        )
        self.assertEqual(_flat(effect), (27, 0))
        self.assertEqual(_flat(dict(effect, values=[-3])), (27, -3))
        self.assertEqual(_flat(dict(effect, values=[-2])), (27, -2))
