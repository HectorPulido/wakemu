"""Pure staged parsing of actual six eWG and two eYn equipment definitions."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from wakfu_server.combat_definitions import effect_profile
from wakfu_server.combat_equipment_morph_parser import (
    parse as morph,
    required_context as morph_context,
    MissingNativeMorphProfile,
)
from wakfu_server.combat_equipment_characteristic_group_parser import (
    parse as group,
    required_context as group_context,
    child_level_at_snapshot,
)


DATA = json.loads(
    (
        Path(__file__).parent
        / "fixtures/native_equipment_morph_characteristic_groups.json"
    ).read_text()
)


class EquipmentMorphCharacteristicParserTests(unittest.TestCase):
    def test_four_actual_morph_profiles_reuse_original_books_and_two_missing_defer(
        self,
    ):
        from wakfu_server.combat_morph_spellbook import native_morph_profiles

        profiles = native_morph_profiles()
        observed = []
        for reference in DATA["sources"]["30530"]:
            effect = DATA["effects"][str(reference)]
            parsed = morph(effect, effect_profile(effect, 1), profiles=profiles)
            observed.append(parsed["profile_id"])
            self.assertFalse(parsed["own_level"])
            self.assertEqual(
                [uid for uid, _ in parsed["minimum_level_book"]],
                [
                    row["reference"]
                    for row in profiles[str(parsed["profile_id"])]["abilities"]
                ],
            )
            self.assertIn("native_morph_value_context", morph_context(parsed))
            self.assertIn("native_morph_profile_dependencies", morph_context(parsed))
        self.assertEqual(set(observed), {5371, 5372, 5419, 5588})
        for item in ("14057", "17802"):
            effect = DATA["effects"][str(DATA["sources"][item][0])]
            with self.assertRaisesRegex(
                MissingNativeMorphProfile, "original native morph profile"
            ):
                morph(effect, effect_profile(effect, 1), profiles={})

    def test_morph_signed_short_default_own_level_and_parameter_guards(self):
        from wakfu_server.combat_morph_spellbook import native_morph_profiles

        profiles = native_morph_profiles()
        actual = DATA["effects"]["340246"]
        effect = dict(actual, parameter_count=2, parameters=[5371 + 65536, 0, 1, 0])
        parsed = morph(effect, effect_profile(effect, 1), profiles=profiles)
        self.assertEqual(parsed["profile_id"], 5371)
        self.assertTrue(parsed["own_level"])
        self.assertIn("native_morph_actor_level", morph_context(parsed))
        for raw in ([5371, float("nan")], [True, 0], [5371]):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                morph(
                    dict(actual, parameters=raw),
                    {"parameters": [5371]},
                    profiles=profiles,
                )
        with self.assertRaises(MissingNativeMorphProfile):
            morph(
                dict(actual, parameter_count=0, parameters=[]),
                {"parameters": []},
                profiles=profiles,
            )

    def test_actual_913_level_matrix_and_no_parent_level_substitution(self):
        for reference, stat in ((110988, 30), (111019, 27)):
            effect = DATA["effects"][str(reference)]
            for level in (5, 10):
                parsed = group(
                    effect,
                    effect_profile(effect, level),
                    characteristics={"27": {}, "30": {}},
                )
                self.assertEqual(parsed["stat_id"], stat)
                self.assertFalse(parsed["select_caster"])
                self.assertIn(
                    "native_characteristic_child_level_domain", group_context(parsed)
                )
                self.assertNotIn("child_levels", parsed)
            self.assertEqual(
                child_level_at_snapshot(effect, 10, current=169, maximum=169), 17
            )
            self.assertEqual(
                child_level_at_snapshot(effect, 5, current=169, maximum=169), 8
            )
            self.assertEqual(
                child_level_at_snapshot(effect, 10, current=65, maximum=65), 6
            )
            self.assertEqual(
                child_level_at_snapshot(effect, 5, current=65, maximum=65), 3
            )

    def test_913_byte_enum_variants_unknown_pc_and_malformed_shapes(self):
        actual = DATA["effects"]["110988"]
        for count in (9, 10, 11, 12):
            effect = dict(
                actual,
                parameter_count=count,
                parameters=actual["parameters"][: 2 * count],
            )
            if count == 12:
                effect["parameters"] = actual["parameters"] + [2, 0]
            effect["parameters"] = list(effect["parameters"])
            effect["parameters"][12] = -124
            parsed = group(
                effect, effect_profile(effect, 10), characteristics={"132": {}}
            )
            self.assertEqual(parsed["stat_id"], 132)
            unknown = group(effect, effect_profile(effect, 10), characteristics={})
            self.assertIsNone(unknown["stat_id"])
            self.assertTrue(unknown["unknown_stat_preserves_parent_level"])
            self.assertNotIn(
                "native_selected_characteristic_pa", group_context(unknown)
            )
        for count in (0, 8, 13):
            with self.subTest(count=count), self.assertRaises(ValueError):
                effect = dict(
                    actual, parameter_count=count, parameters=[0] * (2 * count)
                )
                group(effect, effect_profile(effect, 1), characteristics={})
        malformed = deepcopy(actual)
        malformed["parameters"][1] = float("inf")
        with self.assertRaises(ValueError):
            group(
                malformed,
                {"parameters": [0] * malformed["parameter_count"]},
                characteristics={},
            )
