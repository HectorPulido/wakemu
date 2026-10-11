"""Native negative/zero/positive deck caps without runtime catalogs."""
import unittest
from unittest.mock import patch

from wakfu_server.combat_spell_level import NativeSpellBook
from wakfu_server.combat_class_initialization import BREEDS, plan, level_zero_catalog
from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution
from wakfu_server.spells import available_spells, encode_deck
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
)
from wakfu_server.combat_native_spell_casting import definition


class NativeDeckCapContractTests(unittest.TestCase):
    def test_negative_caps_preserve_owned_level_and_zero_is_real_cap(self):
        for cap, expected in (
            (None, 200),
            (-1, 200),
            (-5, 200),
            (0, 0),
            (1, 1),
            (100, 100),
            (300, 200),
        ):
            with self.subTest(cap=cap):
                book = NativeSpellBook({10: 200}, True, {10: 200}, cap)
                self.assertEqual(book.level(10), expected)

    def test_cap_zero_uses_native_zero_roots_without_indexing_last_level(self):
        character = dict(id=7, breed=11, level=200, x=0, y=0, z=0)
        passive = next(
            row["id"] for row in available_spells(11, 200) if row["kind"] == "passive"
        )
        spells = {
            "spells": {
                str(passive): {
                    "levels": [[1, 1, [9000 + index]] for index in range(200)]
                }
            },
            "effects": {"8500": {}},
        }
        states = {
            "states": {str(row["reference"]): {} for row in BREEDS[11]["innate_states"]}
        }
        deck = encode_deck((), [passive], level_cap=0)
        with self.assertRaisesRegex(UnsupportedEffectExecution, "level-zero roots"):
            plan(character, deck, spells, states, zero_catalog={})
        zero = {"spells": {str(passive): [1, 1, [8500]]}}
        initial = plan(character, deck, spells, states, zero_catalog=zero)
        self.assertEqual(initial.passive_invocations[0].level, 0)
        self.assertEqual(initial.passive_invocations[0].reference, 8500)
        self.assertTrue(all(row.level in (0, 1) for row in initial.innates))
        with self.assertRaisesRegex(
            UnsupportedEffectExecution, "level-zero effect closure"
        ):
            plan(character, deck, {**spells, "effects": {}}, states, zero_catalog=zero)
        for cap, expected in ((-1, 200), (100, 100)):
            initial = plan(
                character, encode_deck((), [passive], level_cap=cap), spells, states
            )
            self.assertEqual(initial.passive_invocations[0].level, expected)
            self.assertEqual(
                initial.passive_invocations[0].reference, 9000 + expected - 1
            )

    def test_installed_zero_contract_supports_every_class_passive(self):
        zero = level_zero_catalog()
        passive_rows = [
            (breed, row)
            for breed in BREEDS
            for row in available_spells(breed, 200)
            if row["kind"] == "passive" and row["breed"] == breed
        ]
        self.assertEqual({breed for breed, _ in passive_rows}, set(BREEDS))
        effects = {str(reference): {} for reference in zero["effect_reference_closure"]}
        for breed, row in passive_rows:
            reference = row["id"]
            character = dict(id=7, breed=breed, level=200, x=0, y=0, z=0)
            states = {
                "states": {
                    str(item["reference"]): {}
                    for item in BREEDS[breed]["innate_states"]
                }
            }
            # Deliberately different positive-level roots make a final-level
            # substitution fail, including when native level0 has no roots.
            spells = {
                "spells": {str(reference): {"levels": [[1, 1, [9999999]]] * 200}},
                "effects": effects,
            }
            initial = plan(
                character, encode_deck((), [reference], level_cap=0), spells, states
            )
            with self.subTest(spell=reference, breed=breed):
                self.assertEqual(
                    [item.reference for item in initial.passive_invocations],
                    zero["spells"][str(reference)][2],
                )
                self.assertTrue(
                    all(item.level == 0 for item in initial.passive_invocations)
                )

    def test_zero_cast_uses_explicit_native_table_and_conditional_level_zero(self):
        book = NativeSpellBook({6271: 200}, True, {6271: 200}, 0)
        context = ConditionContext(
            {"caster": ConditionActor(deck_spell_ids=frozenset({6271}))},
            spell_level_query=lambda reference, selector: book.level(reference),
        )
        result = definition(6285, 0, context, {})
        self.assertEqual((result["minimum"], result["maximum"]), (0, 6))
        self.assertEqual(result["costs"]["ap"], 3)
        self.assertEqual(
            result["roots"], tuple(level_zero_catalog()["spells"]["6285"][2])
        )
        with self.assertRaises(UnknownCondition):
            definition(6285, 0, ConditionContext({}), {})

    def test_missing_zero_cast_contract_never_falls_back_to_positive_levels(self):
        with patch(
            "wakfu_server.combat_class_initialization.level_zero_catalog",
            return_value={},
        ), patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"20": {"levels": [[1, 99, [5]]]}},
        ):
            with self.assertRaisesRegex(ValueError, "level unavailable"):
                definition(20, 0, ConditionContext({}), {})

    def test_zero_snapshot_preserves_distinct_native_eligibility_flags(self):
        flags = (
            "line_of_sight",
            "linear",
            "free_cell",
            "path_option",
            "diagonal",
            "linear_path",
            "allow_self",
            "range_modifiable",
        )
        records = level_zero_catalog()["casting"]
        owned_references = {
            row["id"]
            for breed in BREEDS
            for row in available_spells(breed, 200)
            if row["breed"] == breed
        }
        self.assertTrue(owned_references.issubset(map(int, records)))
        self.assertTrue(
            any(row["free_cell"] != row["path_option"] for row in records.values())
        )
        for reference, row in records.items():
            for table in (row, *row["conditional"]):
                with self.subTest(spell=reference, criterion=table.get("criteria")):
                    self.assertTrue(
                        all(type(table.get(flag)) is bool for flag in flags)
                    )
            self.assertIs(type(row["forbid_QI_P"]), bool)
            self.assertIs(type(row["cast_criterion_native_present"]), bool)


if __name__ == "__main__":
    unittest.main()
