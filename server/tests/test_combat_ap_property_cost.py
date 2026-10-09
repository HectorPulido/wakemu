import copy
import unittest
from types import SimpleNamespace

from wakfu_server.combat_ap_property_cost import (
    native_ap_cost_available,
    require_native_ap_cost,
)
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
)


class APPropertyCostTests(unittest.TestCase):
    def test_native_positive_ap_rejection_and_zero_bypass_have_no_remapping(self):
        self.assertFalse(native_ap_cost_available(4, frozenset({50})))
        self.assertTrue(native_ap_cost_available(4, frozenset()))
        self.assertTrue(native_ap_cost_available(0, None))
        self.assertTrue(native_ap_cost_available(-1, None))
        with self.assertRaises(UnknownCondition):
            native_ap_cost_available(4, None)
        for weapon in (False, True):
            with self.assertRaises(ValueError) as caught:
                require_native_ap_cost(4, frozenset({50}), weapon=weapon)
            self.assertEqual(caught.exception.native_casting_result, "twJ")

    def test_shared_cast_guard_rejects_before_any_resource_or_query_mutation(self):
        from wakfu_server.combat_cast import _validate_target

        actor = SimpleNamespace(ap=6, mp=9, id=7)
        context = ConditionContext(
            {"caster": ConditionActor(fight_properties=frozenset({50}))}
        )
        before = copy.deepcopy(actor.__dict__)
        costs = dict(ap=4, mp=0, wp=0)
        with self.assertRaises(ValueError) as caught:
            _validate_target(
                request={"target": (0, 0, 0)},
                actor=actor,
                fight=SimpleNamespace(),
                wp=6,
                costs=costs,
                rule={},
                roots=(),
                evaluation_level=1,
                line_of_sight=None,
                spell_id=2016,
                context=context,
            )
        self.assertEqual(caught.exception.native_casting_result, "twJ")
        self.assertEqual(actor.__dict__, before)
        self.assertEqual(costs, dict(ap=4, mp=0, wp=0))

    def test_actual_conditional_fyp_selects_mp_payment_instead_of_transferring_ap(self):
        from wakfu_server.combat_native_spell_casting import definition
        from test_combat_resource_pa_notifications import ResourcePANotificationTests
        from wakfu_server.combat_resource_pa_notifications import (
            set_resource_maximum,
            set_resource_current,
            shift_resource_current,
        )

        # The conditional deck criterion is evaluated on the actual owned PC.
        caster = ConditionActor(
            is_player=True,
            state_ids=frozenset({702}),
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            fight_properties=frozenset({50}),
        )
        rule = definition(2016, 1, ConditionContext({"caster": caster}), {})
        self.assertEqual(
            {key: rule["costs"][key] for key in ("ap", "mp", "wp")},
            dict(ap=0, mp=4, wp=0),
        )
        fight, actor = ResourcePANotificationTests().fixture()
        set_resource_maximum(fight, actor, 3, 9)
        set_resource_current(fight, actor, 3, 9)
        require_native_ap_cost(rule["costs"]["ap"], caster.fight_properties)
        shift_resource_current(fight, actor, 2, rule["costs"]["ap"], subtract=True)
        shift_resource_current(fight, actor, 3, rule["costs"]["mp"], subtract=True)
        self.assertEqual((actor.ap, actor.mp), (6, 5))
