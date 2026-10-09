import unittest
from dataclasses import replace
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_captured_roster_condition import (
    selected_creature_status,
    space_in_symbiot,
)
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from types import SimpleNamespace


class SelectedCreatureConditionTests(unittest.TestCase):
    def test_space_counts_occupied_descriptors_independently_of_availability(self):
        for occupied in range(11):
            slots = tuple(
                CapturedCreature(i, 1620, "owned") if i < occupied else None
                for i in range(10)
            )
            for available in (False, True):
                roster = OwnedCapturedRoster(7, slots, (available,) * 10)
                authority = SimpleNamespace(
                    native_is_ehp=True, native_captured_roster=roster
                )
                query = lambda: space_in_symbiot(authority)
                self.assertEqual(query(), 10 - occupied)
                self.assertTrue(
                    evaluate_condition(
                        "GetSpaceInSymbiot() == " + str(10 - occupied),
                        ConditionContext({}, space_in_symbiot_query=query),
                    )
                )
        self.assertEqual(space_in_symbiot(SimpleNamespace(native_is_ehp=False)), -1)
        for authority in (
            SimpleNamespace(native_is_ehp=None),
            SimpleNamespace(native_is_ehp=True, native_captured_roster=None),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    "GetSpaceInSymbiot() > 0",
                    ConditionContext(
                        {}, space_in_symbiot_query=lambda: space_in_symbiot(authority)
                    ),
                )
        for arguments in ("", '"caster"', '"target"', "1", '"ignored", 1 / 0'):
            self.assertTrue(
                evaluate_condition(
                    "GetSpaceInSymbiot(" + arguments + ") == 10",
                    ConditionContext({}, space_in_symbiot_query=lambda: 10),
                )
            )

    def test_actual_owned_selection_and_availability_status(self):
        empty = OwnedCapturedRoster(7)
        slots = (CapturedCreature(0, 1620, "owned"),) + (None,) * 9
        occupied = replace(empty, slots=slots)
        available = replace(occupied, available=(True,) + (False,) * 9)
        for roster, expected in (
            (empty, -1),
            (occupied, -2),
            (available, 0),
            (replace(available, selected_slot=-1), -1),
            (replace(available, selected_slot=10), -1),
        ):
            authority = SimpleNamespace(
                native_is_ehp=True, native_captured_roster=roster
            )
            query = lambda: selected_creature_status(authority)
            self.assertEqual(query(), expected)
            self.assertEqual(
                evaluate_condition(
                    "IsSelectedCreatureAvailable()",
                    ConditionContext({}, selected_creature_available_query=query),
                ),
                expected == 0,
            )

    def test_type_component_missing_and_invalid_results_are_unknown(self):
        for typed, roster in (
            (None, None),
            (False, OwnedCapturedRoster(7)),
            (True, None),
        ):
            authority = SimpleNamespace(
                native_is_ehp=typed, native_captured_roster=roster
            )
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    "IsSelectedCreatureAvailable()",
                    ConditionContext(
                        {},
                        selected_creature_available_query=lambda: selected_creature_status(
                            authority
                        ),
                    ),
                )
        for result in (True, None, 1, -3):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    "IsSelectedCreatureAvailable()",
                    ConditionContext(
                        {}, selected_creature_available_query=lambda: result
                    ),
                )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'IsSelectedCreatureAvailable("target")', ConditionContext({})
            )
