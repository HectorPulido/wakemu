import unittest
from types import SimpleNamespace
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_captured_roster_condition import breed_in_symbiot
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)


class BreedInSymbiotTests(unittest.TestCase):
    def authority(self):
        slots = [None] * 10
        slots[8] = CapturedCreature(8, 5347, "")
        slots[9] = CapturedCreature(9, 32767, "")
        return SimpleNamespace(
            native_is_ehp=True,
            native_captured_roster=OwnedCapturedRoster(
                7, tuple(slots), (False,) * 10, selected_slot=0
            ),
        )

    def test_all_occupied_slots_ignore_selection_and_availability(self):
        source = self.authority()
        self.assertTrue(breed_in_symbiot(source, 5347))
        self.assertFalse(breed_in_symbiot(source, 1152))
        self.assertIsNone(source.native_captured_roster.selected_creature)

    def test_gs_cv_saturates_long_and_requires_positive_short(self):
        source = self.authority()
        for value in (32767, 32768, 2**63 - 1):
            self.assertTrue(breed_in_symbiot(source, value))
        for value in (0, -1, -32768, -(2**63)):
            self.assertFalse(breed_in_symbiot(source, value))

    def test_known_null_non_ehp_and_unknown_component_are_distinct(self):
        self.assertFalse(breed_in_symbiot(None, 5347))
        self.assertFalse(breed_in_symbiot(SimpleNamespace(native_is_ehp=False), 5347))
        with self.assertRaises(ValueError):
            breed_in_symbiot(
                SimpleNamespace(native_is_ehp=True, native_captured_roster=None), 5347
            )

    def test_general_evaluator_uses_two_arguments_and_trimmed_selector(self):
        calls = []

        def query(reference, selector):
            calls.append((reference, selector))
            return breed_in_symbiot(self.authority(), reference)

        context = ConditionContext({}, breed_in_symbiot_query=query)
        self.assertTrue(
            evaluate_condition('HasBreedInSymbiot(5347, " caster ")', context)
        )
        self.assertEqual(calls, [(5347, "caster")])
        with self.assertRaises(UnknownCondition):
            evaluate_condition("HasBreedInSymbiot(5347)", context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'HasBreedInSymbiot(5347, "caster")', ConditionContext({})
            )


if __name__ == "__main__":
    unittest.main()
