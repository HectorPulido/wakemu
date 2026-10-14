from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import unittest
from owned_state_stack import required_caster_state_levels, bounded_repeat_count


class StackTests(unittest.TestCase):
    def test_and_uses_strongest_required_grade(self):
        self.assertEqual(
            required_caster_state_levels(
                'HasState(2071, "caster") && HasStateFromLevel(2071, 2, "caster")'
            ),
            {2071: 2},
        )

    def test_or_requires_common_state_and_lower_threshold(self):
        self.assertEqual(
            required_caster_state_levels(
                'HasStateFromLevel(2071, 2, "caster") || HasStateFromLevel(2071, 3, "caster")'
            ),
            {2071: 2},
        )
        self.assertEqual(
            required_caster_state_levels(
                'HasStateFromLevel(2071, 2, "caster") || IsEnnemy()'
            ),
            {},
        )

    def test_negative_and_target_state_do_not_supply_caster(self):
        self.assertEqual(
            required_caster_state_levels('!HasStateFromLevel(2071, 2, "caster")'), {}
        )
        self.assertEqual(
            required_caster_state_levels('HasStateFromLevel(2071, 2, "target")'), {}
        )

    def test_repeat_uses_actual_gain_and_native_additive_maximum(self):
        paths = [dict(state=2071, criteria=[], constant_state_gain=1)]
        definitions = {"2071": dict(maximum_level=6, additive=True)}
        self.assertEqual(bounded_repeat_count(paths, {2071: 2}, definitions), 2)
        self.assertIsNone(bounded_repeat_count(paths, {2071: 7}, definitions))
        definitions["2071"]["additive"] = False
        self.assertIsNone(bounded_repeat_count(paths, {2071: 2}, definitions))

    def test_ambiguous_conditional_or_nonconstant_gain_fails_closed(self):
        path = dict(state=2071, criteria=[], constant_state_gain=1)
        defs = {"2071": dict(maximum_level=6, additive=True)}
        self.assertIsNone(bounded_repeat_count([path, path], {2071: 2}, defs))
        self.assertIsNone(
            bounded_repeat_count([dict(path, criteria=["guard"])], {2071: 2}, defs)
        )
        self.assertIsNone(
            bounded_repeat_count(
                [dict(path, constant_state_gain=None)], {2071: 2}, defs
            )
        )

    def test_native_state_planner_adds_real_grade(self):
        from wakfu_server.combat_state_application import (
            ExistingState,
            plan_state_application,
        )

        result = plan_state_application(
            1, 6, [ExistingState(1, 6, True, True, False, False)]
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.level, 2)
        self.assertEqual(result.remove_indices, (0,))

    def test_exact_native_empty_area_self_selector_generates_two_real_actions(self):
        import json
        from pathlib import Path
        from conditional_owned_state import discover_conditional_owned_state_recipes

        source = json.loads(
            (
                Path(__file__).resolve().parent
                / "fixtures/owned_state_stack/representative-native-source.json"
            ).read_text()
        )
        doc = {"spells": source["spells"], "effects": source["effect_rows"]}
        recipes = discover_conditional_owned_state_recipes(
            [{"spell_id": 3922, "spell_level": 1}],
            [2071],
            doc,
            casting={"3922": {"cast_criterion_raw": ""}},
            companion_recipes=lambda _: [],
            required_levels={2071: 2},
            state_definitions={"2071": source["state_policy"]},
        )
        self.assertEqual(len(recipes), 2)
        self.assertEqual(len(recipes[0]["actions"]), 2)
        self.assertEqual(recipes[0]["native_producer_paths"][0]["effect_ids"], [100251])
        self.assertEqual(recipes[0]["actions"][0]["target"], "player")
        doc["effects"]["100251"]["native_target_selector"]["mask"] = 257
        self.assertEqual(
            discover_conditional_owned_state_recipes(
                [{"spell_id": 3922, "spell_level": 1}],
                [2071],
                doc,
                casting={"3922": {"cast_criterion_raw": ""}},
                companion_recipes=lambda _: [],
                required_levels={2071: 2},
                state_definitions={"2071": source["state_policy"]},
            ),
            [],
        )

    def test_native_companion_recipient_preserves_owned_descriptor_and_self_state_proof(
        self,
    ):
        import json
        from pathlib import Path
        from conditional_owned_state import discover_conditional_owned_state_recipes

        source = json.loads(
            (
                Path(__file__).resolve().parent
                / "fixtures/owned_state_stack/representative-native-source.json"
            ).read_text()
        )
        companion = {
            "kind": "native_opponent",
            "opponent": {"reference": 2726, "level": 127, "team": 0},
        }
        recipes = discover_conditional_owned_state_recipes(
            [{"spell_id": 3922, "spell_level": 1}],
            [2071],
            {"spells": source["spells"], "effects": source["effect_rows"]},
            casting={"3922": {"cast_criterion_raw": ""}},
            companion_recipes=lambda _: [companion],
            required_levels={2071: 2},
            state_definitions={"2071": source["state_policy"]},
        )
        self.assertEqual(recipes[0]["opponent"], companion["opponent"])
        self.assertEqual(recipes[0]["native_producer_target_id"], -201)
        self.assertEqual(recipes[0]["actions"][0]["target"], "native_opponent")
        self.assertEqual(recipes[0]["actions"][0]["next_turn"], True)
        self.assertEqual(recipes[0]["discovery"], "owned_conditional_self_state_v1")
        self.assertEqual(recipes[0]["native_producer_paths"][0]["effect_ids"], [100251])

    def test_high_grade_chooses_native_mp_zero_producer_before_recipe_cap(self):
        import json
        from pathlib import Path
        from conditional_owned_state import discover_conditional_owned_state_recipes

        source = json.loads(
            (
                Path(__file__).resolve().parent
                / "fixtures/owned_state_stack/representative-native-source.json"
            ).read_text()
        )
        companion = {
            "kind": "native_opponent",
            "opponent": {"reference": 2726, "level": 127, "team": 0},
        }
        casting = {
            "3922": {"cast_criterion_raw": "", "costs": [[3, 1, 0]]},
            "3923": {"cast_criterion_raw": "", "costs": [[1, 1, 0]]},
            "3924": {"cast_criterion_raw": "", "costs": [[1, 0, 0]]},
        }
        recipes = discover_conditional_owned_state_recipes(
            [{"spell_id": s, "spell_level": 1} for s in [3922, 3923, 3924]],
            [2071],
            {"spells": source["spells"], "effects": source["effect_rows"]},
            casting=casting,
            companion_recipes=lambda _: [companion],
            required_levels={2071: 2},
            state_definitions={"2071": source["state_policy"]},
        )
        self.assertEqual(recipes[0]["actions"][0]["spell_id"], 3924)
        self.assertEqual(recipes[0]["native_producer_paths"][0]["effect_ids"], [100258])
        self.assertEqual(len(recipes), 4)

    def test_state_grade_metadata_round_trip_keeps_numeric_authority(self):
        import json
        from owned_state_stack import state_requirement_items

        original = {2071: 2}
        self.assertEqual(state_requirement_items(original), [(2071, 2)])
        self.assertEqual(
            state_requirement_items(json.loads(json.dumps(original))), [(2071, 2)]
        )
        for malformed in [{"02071": 2}, {True: 2}, {2071: True}, {2071: 0}]:
            with self.assertRaises(ValueError):
                state_requirement_items(malformed)

    def test_grade1_presence_recipe_keeps_legacy_presence_semantics(self):
        import json
        from pathlib import Path
        from conditional_owned_state import discover_conditional_owned_state_recipes

        source = json.loads(
            (
                Path(__file__).resolve().parent
                / "fixtures/owned_state_stack/representative-native-source.json"
            ).read_text()
        )
        recipes = discover_conditional_owned_state_recipes(
            [{"spell_id": 3924, "spell_level": 1}],
            [2071],
            {"spells": source["spells"], "effects": source["effect_rows"]},
            casting={"3924": {"cast_criterion_raw": "", "costs": [[1, 0, 0]]}},
            companion_recipes=lambda _: [],
            required_levels={2071: 1},
        )
        self.assertEqual(len(recipes[0]["actions"]), 1)
        self.assertEqual(recipes[0]["required_state_levels"], {})


if __name__ == "__main__":
    unittest.main()
