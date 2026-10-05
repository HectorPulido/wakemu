import unittest
from wakfu_server.combat_range_conditions import (
    own_team_state_carriers,
    RangeFighter,
    range_count,
    area_state_count,
)
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)


class OwnTeamStateRangeTests(unittest.TestCase):
    def test_filter_uses_state_caster_not_recipient_team(self):
        states = ((3442, 1, 7), (3442, 2, -7), (3442, 3, None))
        self.assertEqual(
            own_team_state_carriers(states, 0, {7: 0, -7: 1}), ((3442, 1, 7),)
        )
        self.assertEqual(
            own_team_state_carriers(states, 1, {7: 0, -7: 1}), ((3442, 2, -7),)
        )

    def test_range_counts_recipient_once_and_keeps_exact_level_and_area_managers(self):
        states = own_team_state_carriers(((3442, 1, 7), (3442, 2, 7)), 0, {7: 0})
        foe = RangeFighter((2, 0, 0), 0, 1, True, False, False, states=states)
        kwargs = dict(
            affiliation=0,
            center=(0, 0, 0),
            minimum=0,
            maximum=3,
            relation="state",
            state_reference=3442,
        )
        self.assertEqual(range_count((foe,), **kwargs), 1)
        self.assertEqual(range_count((foe,), state_level=2, **kwargs), 1)
        self.assertEqual(range_count((foe,), state_level=3, **kwargs), 0)
        self.assertEqual(
            area_state_count(
                (((2, 0, 0), states),),
                center=(0, 0, 0),
                minimum=0,
                maximum=3,
                reference=3442,
            ),
            1,
        )

    def test_unknown_source_affiliation_remains_rejected(self):
        for mapping in ({}, {7: None}, {7: 128}):
            with self.assertRaises(ValueError):
                own_team_state_carriers(((3442, 1, 7),), 0, mapping)

    def test_native_signature_passes_distinct_callback_without_changing_state_query(
        self,
    ):
        observed = []
        context = ConditionContext(
            {},
            own_team_state_range_query=lambda *args: observed.append(args) or 2,
            state_range_query=lambda *args: 9,
        )
        self.assertTrue(
            evaluate_condition(
                'GetOwnTeamStateCountInRange(3,"caster",3442,1,"target") == 2', context
            )
        )
        self.assertEqual(observed, [(3, "caster", 3442, 1, True, "target")])
        self.assertTrue(
            evaluate_condition('GetStateCountInRange(3,"caster",3442) == 9', context)
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'GetOwnTeamStateCountInRange(3,"caster",3442)', ConditionContext({})
            )
