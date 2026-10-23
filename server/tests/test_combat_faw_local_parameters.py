"""One faW verification parses actual raw parameters once, never across calls."""
from contextlib import ExitStack
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server import combat_fake_fighter as faw
from wakfu_server import combat_fake_fighter_resources as resources
from wakfu_server import combat_fake_fighter_owner_copy as owner_copy


def fixture(kind):
    base, mask = {
        "hp": (8, -1),
        "zero_copy": (100, 0),
        "damage_only": (-1, 2),
        "absent": (-1, -1),
    }[kind]
    definition = dict(
        type="FAKE_FIGHTER",
        native_type_id=15,
        native_class="bcQ",
        raw_bdh=[0.0, float(base), 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0, float(mask)],
    )
    row = dict(
        native_area_contract="faW",
        level=230,
        native_obstacle_id=-1,
        native_obstacle_source="fbm.constructor",
    )
    if kind == "damage_only":
        owner_copy.install(row, definition, {21: 137})
    elif kind != "absent":
        resources.install_fake_fighter_hp(row, definition)
    row["native_faw_constructor"] = faw.fake_fighter_constructor(
        definition, 230, allow_hp=kind != "absent"
    )
    return row, definition


class FawLocalParametersTests(unittest.TestCase):
    def test_each_verification_parses_ten_parameters_once_in_all_four_branches(self):
        original = faw._float32
        for kind, expected in (
            ("hp", 12),
            ("zero_copy", 12),
            ("damage_only", 10),
            ("absent", 10),
        ):
            row, definition = fixture(kind)
            before = deepcopy((row, definition))
            with self.subTest(kind=kind), ExitStack() as stack:
                counter = stack.enter_context(
                    patch.object(faw, "_float32", wraps=original)
                )
                stack.enter_context(patch.object(resources, "_float32", counter))
                stack.enter_context(patch.object(owner_copy, "_float32", counter))
                result = faw.verified_fake_fighter(row, definition)
                self.assertEqual(counter.call_count, expected)
                faw.verified_fake_fighter(row, definition)
                self.assertEqual(counter.call_count, 2 * expected)
            self.assertEqual(result, row["native_faw_constructor"])
            self.assertEqual((row, definition), before)

    def test_next_verification_rechecks_definition_receipt_and_mutable_current(self):
        for kind in ("hp", "zero_copy"):
            for mutation in (
                "raw_boolean",
                "raw_changed",
                "current_boolean",
                "current_range",
                "receipt",
            ):
                with self.subTest(kind=kind, mutation=mutation):
                    row, definition = fixture(kind)
                    faw.verified_fake_fighter(row, definition)
                    if mutation == "raw_boolean":
                        definition["raw_bdh"][2] = True
                    elif mutation == "raw_changed":
                        definition["raw_bdh"][2] = 1.0
                    elif mutation == "current_boolean":
                        row["native_faw_hp_current"] = True
                    elif mutation == "current_range":
                        row["native_faw_hp_current"] = 1 << 31
                    else:
                        row["native_faw_hp_constructor"]["hp"]["maximum"] += 1
                    before = deepcopy((row, definition))
                    with self.assertRaises(ValueError):
                        faw.verified_fake_fighter(row, definition)
                    self.assertEqual((row, definition), before)

    def test_damage_only_copy_and_absent_resource_guards_remain_live(self):
        for mutation in ("owner_stats", "current", "invented_hp", "mask"):
            with self.subTest(mutation=mutation):
                row, definition = fixture("damage_only")
                faw.verified_fake_fighter(row, definition)
                if mutation == "owner_stats":
                    row["native_faw_damage_only_constructor"]["owner_stats"]["21"] = 138
                elif mutation == "current":
                    row["native_faw_damage_current"] = True
                elif mutation == "invented_hp":
                    row["native_faw_hp_current"] = 1
                else:
                    definition["raw_bdh"][9] = 1.0
                with self.assertRaises(ValueError):
                    faw.verified_fake_fighter(row, definition)

    def test_custom_sequences_keep_legacy_iteration_and_index_guards(self):
        class ShortIteration(list):
            def __iter__(self):
                return iter(list.__getitem__(self, slice(None, -1)))

        row, definition = fixture("damage_only")
        definition["raw_bdh"] = ShortIteration(definition["raw_bdh"])
        with self.assertRaises(IndexError):
            owner_copy.damage_only_mask(definition)
        with self.assertRaises(IndexError):
            faw.verified_fake_fighter(row, definition)

        class CustomRaw(list):
            pass

        row, definition = fixture("hp")
        definition["raw_bdh"] = CustomRaw(definition["raw_bdh"])
        original = faw._float32
        with ExitStack() as stack:
            counter = stack.enter_context(patch.object(faw, "_float32", wraps=original))
            stack.enter_context(patch.object(resources, "_float32", counter))
            stack.enter_context(patch.object(owner_copy, "_float32", counter))
            faw.verified_fake_fighter(row, definition)
            self.assertGreater(counter.call_count, 12)
