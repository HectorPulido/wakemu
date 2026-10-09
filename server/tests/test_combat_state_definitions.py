"""Check completeness of native state data, independently of runtime support."""
import json
import unittest

from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_definitions import state_profile
from wakfu_server import native_catalog


class CombatStateDefinitionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with native_catalog.open(
            DATA_ROOT / "combat-state-definitions.json", "rt"
        ) as stream:
            cls.catalog = json.load(stream)

    def test_all_state_roots_and_level_selections_resolve(self):
        effects = self.catalog["effects"]
        for reference, state in self.catalog["states"].items():
            self.assertEqual(len(state["levels"]), 200, reference)
            for root in state["effect_ids"]:
                self.assertIn(str(root), effects, (reference, root))
            for level in state["levels"]:
                for root in level["effects"]:
                    self.assertIn(root, state["effect_ids"], (reference, root))
        for reference, effect in effects.items():
            for child in effect["children"]:
                self.assertIn(str(child), effects, (reference, child))

    def test_xelor_innate_unlock_effects_are_not_lost(self):
        state = self.catalog["states"]["6755"]
        self.assertEqual(state["levels"][0]["duration"], -1)
        effects = self.catalog["effects"]
        # Native hidden spell unlocks, absent from the ordinary deck catalog.
        for reference, spell in ((313107, 5345), (313108, 3909), (349284, 7794)):
            effect = effects[str(reference)]
            self.assertEqual(effect["effect_class"], 649)
            self.assertEqual(effect["parameters_by_level"][0][2], spell)

    def test_native_state_names_and_distinct_clock_properties(self):
        states = self.catalog["states"]
        self.assertEqual(states["7521"]["name"], "Uginak")
        self.assertEqual(states["6755"]["name"], "Mago Temporal")
        self.assertEqual(states["8913"]["clock_actor"], "caster")
        self.assertFalse(states["8913"]["tick_at_turn_end"])
        self.assertTrue(states["6759"]["additive"])

    def test_visual_actions_and_trigger_masks_are_preserved(self):
        effects = self.catalog["effects"]
        self.assertTrue(
            any(any(e["native_hmi_actions"].values()) for e in effects.values())
        )
        for reference, effect in effects.items():
            self.assertEqual(len(effect["target_masks"]), 7, reference)
            self.assertIs(type(effect["native_localization_enabled"]), bool)
            self.assertTrue(
                all(type(flag) is int for flag in effect["native_effect_flags"])
            )
            self.assertEqual(
                len(effect["native_effect_flags"]),
                len(set(effect["native_effect_flags"])),
            )
            self.assertEqual(
                set(effect["native_hmi_actions"]),
                {"rzc", "rzd", "rze", "rzf", "rzg", "rzh"},
                reference,
            )

    def test_state_level_limits_match_native_client_including_zero_and_above_200(self):
        for reference, definition in self.catalog["states"].items():
            for expected in definition["native_level_checks"]:
                actual = state_profile(
                    self.catalog, int(reference), expected["requested_level"]
                )
                for field in (
                    "level",
                    "duration",
                    "effects",
                    "realtime_duration",
                    "skip_turn_timer",
                ):
                    self.assertEqual(
                        actual[field],
                        expected[field],
                        (reference, expected["requested_level"], field),
                    )


if __name__ == "__main__":
    unittest.main()
