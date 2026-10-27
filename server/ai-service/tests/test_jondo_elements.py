"""Native advisory element identity survives the Python/C# boundary."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_jondo_native_amount import WORLD

from wakfu_ai.bridge.jondo_snapshot import semantic_rows, summarize


class NativeElementProjectionTests(unittest.TestCase):
    def project(self, families):
        effects = {
            str(index): dict(
                effect_class=family,
                minimum_level=0,
                maximum_level=200,
                parameters=[100.0, 0.0, float(index % 4), 0.0],
                children=[],
                criteria="",
                native_effect_flags=[22, 34],
                native_target_selector={"class": "fcE", "mask": 9},
                area_class="anD",
                area_native="point",
                variant=0,
                application_flag="NONE",
                target_masks=[None] * 7,
                native_localization_enabled=True,
            )
            for index, family in enumerate(families, 1)
        }
        with patch.dict(
            "sys.modules",
            {
                "wakfu_server.combat_damage_parameters": SimpleNamespace(
                    damage_parameter_specification=WORLD[
                        "damage_parameter_specification"
                    ]
                ),
                "wakfu_server.combat_effect_resolver": SimpleNamespace(
                    variant_accepts=lambda *args: True
                ),
            },
        ), patch(
            "wakfu_server.combat_definitions.effect_profile",
            return_value=dict(parameters=[100], probability=100),
        ), patch(
            "wakfu_server.combat_effect_targets.native_selector_policy",
            return_value=dict(relations=frozenset({"enemy"}), in_area=True),
        ), patch(
            "wakfu_server.combat_effect_targets.area_offsets", return_value={(0, 0)}
        ), patch(
            "wakfu_server.combat_static_catalogs.characteristic_registry",
            return_value=dict(effects={}),
        ), patch(
            "wakfu_server.combat_effect_resolver.variant_accepts", return_value=True
        ):
            return semantic_rows(
                SimpleNamespace(effects=effects), list(range(1, len(families) + 1)), 10
            )

    def test_six_native_elements_and_physical_preserve_per_row_context(self):
        rows, unknown = self.project([2, 3, 4, 5, 1083, 917, 1])
        self.assertEqual(unknown, [])
        self.assertEqual(len(rows), 7)
        expected = {
            1: "fire",
            2: "earth",
            3: "water",
            4: "air",
            5: "light",
            6: "stasis",
            7: "physical",
        }
        for row in rows:
            reference = row["nativeReference"]
            self.assertEqual(row["element"], expected[reference])
            self.assertEqual(row["nativeCoefficientMask"], reference % 4)
            self.assertEqual(row["nativeDamageFlags"], [22, 34])
            self.assertTrue(row["nativeLocalization"])
            self.assertEqual(row["fixedCells"], [[0, 0]])
        self.assertEqual(summarize(rows, [])["damage"], 700)
        for row in rows:
            self.assertEqual(summarize([row], [])["element"], row["element"])

    def test_light_heal_has_native_descriptor_without_invented_flat_damage(self):
        rows, unknown = self.project([1084])
        self.assertEqual(unknown, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "heal")
        self.assertEqual(rows[0]["amount"], 0)
        self.assertEqual(rows[0]["nativeHealing"], dict(version=1, element=6))
        self.assertEqual(
            rows[0]["nativeBase"],
            dict(version=1, kind=0, value=100, sourceBindingKnown=True),
        )
        result = summarize(rows, unknown)
        self.assertEqual(result["damage"], 0)
        self.assertEqual(result["element"], "physical")
        self.assertEqual(result["utility"], 0)
