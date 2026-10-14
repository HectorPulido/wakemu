"""Initial native counter paths use actual lifecycle boundaries, never grants."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import initial_subscription_preparation as helper


class NativeInitialTurnCounterTests(unittest.TestCase):
    def audit(self, event=1002, growth=0):
        return {
            "rows": [
                {
                    "ref": 3173,
                    "required_caster_state": 3000,
                    "owned_abilities": [{"spell_id": 4483}],
                    "initial_state_producer_paths": [{"path": [117947, 117948]}],
                }
            ],
            "native_records": {
                "117947": {
                    "effect_class": 330,
                    "criteria": "",
                    "parameters": [0, 0],
                    "target_masks": [None, None, None, None, None, [event], None],
                },
                "117948": {
                    "effect_class": 304,
                    "criteria": "",
                    "parameters": [3000, 0, 2, growth, -1, 0],
                    "target_masks": [None] * 7,
                },
            },
        }

    def test_actual_end_turn_source_path_is_executable(self):
        plans = helper.plans(self.audit(), 3173, 4483, 3000)
        self.assertEqual(plans[0]["mode"], "normal_owned_turn_cycles")
        self.assertFalse(plans[0]["state_injection"])

    def test_unknown_event_and_dynamic_increment_rejected(self):
        self.assertEqual(helper.plans(self.audit(event=9999), 3173, 4483, 3000), [])
        self.assertEqual(helper.plans(self.audit(growth=1), 3173, 4483, 3000), [])

    def test_counter_advances_only_from_normal_turn_callback(self):
        actor = SimpleNamespace(hp=20, state_ledger=SimpleNamespace(entries=[]))
        fight = SimpleNamespace(actors={-200: actor})
        calls = []

        def finish(value):
            self.assertIs(value, fight)
            calls.append("end")
            actor.state_ledger.entries = [
                SimpleNamespace(reference=3000, level=len(calls) * 2)
            ]

        recipe = helper.plans(self.audit(), 3173, 4483, 3000)[0]
        with patch("monster_spell_scenarios.finish_current_turn", finish), patch(
            "monster_spell_scenarios.advance_to"
        ):
            proof = helper.prepare_turn_cycles(
                fight,
                recipe=recipe,
                caster_id=-200,
                criterion='HasStateFromLevel(3000, 10, "caster")',
            )
        self.assertEqual(len(calls), 5)
        self.assertEqual(proof["observed_levels"], [0, 2, 4, 6, 8, 10])

    def test_no_counter_production_fails_closed(self):
        actor = SimpleNamespace(hp=20, state_ledger=SimpleNamespace(entries=[]))
        fight = SimpleNamespace(actors={-200: actor})
        recipe = helper.plans(self.audit(), 3173, 4483, 3000)[0]
        with patch("monster_spell_scenarios.finish_current_turn"), patch(
            "monster_spell_scenarios.advance_to"
        ):
            with self.assertRaises(ValueError):
                helper.prepare_turn_cycles(
                    fight,
                    recipe=recipe,
                    caster_id=-200,
                    criterion='HasStateFromLevel(3000, 10, "caster")',
                    maximum_cycles=2,
                )

    def test_native_counter_requirement_above_owned_cast_budget_is_preserved(self):
        from owned_state_stack import required_caster_state_levels

        criterion = 'HasStateFromLevel(3000, 30, "caster")'
        self.assertEqual(required_caster_state_levels(criterion), {})
        self.assertEqual(
            required_caster_state_levels(criterion, maximum_grade=32767), {3000: 30}
        )
