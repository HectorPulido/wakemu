import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_parameter_maximum import (
    NativeParameterMaximumHandler,
    transition,
    remove_parameter_maximum,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class ParameterMaximumTests(unittest.TestCase):
    def setUp(self):
        self.actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 1, 3, True)
        enemy = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 0, 1)
        self.fight = Fight(
            8,
            [self.actor, enemy],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.fight.ready(3)
        a = self.actor
        a.effect_stats = {117: 25}
        a.effect_maxima = {117: 30}
        a.effect_minima = {117: 0}
        a.effect_base_maxima = {117: 30}
        a.effect_base_minima = {117: 0}
        a.effect_percentages = {117: 0}
        a.effect_frozen = frozenset()
        self.packets = []
        self.handler = NativeParameterMaximumHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(
                True, True, None, True, None, None
            ),
        )

    def apply(self, family, amount=10):
        self.handler(
            dict(effect_class=family, parameters=[117.0, 0.0, amount, 0.0]),
            [],
            EffectInvocation(345698 if family == 1202 else 345699, 1, 7, 7, (0, 0, 0)),
        )

    def test_native_loss_clamps_current_but_removal_does_not_heal(self):
        self.apply(1202)
        self.assertEqual(
            (self.actor.effect_stats[117], self.actor.effect_maxima[117]), (20, 20)
        )
        remove_parameter_maximum(self.handler, 101)
        self.assertEqual(
            (self.actor.effect_stats[117], self.actor.effect_maxima[117]), (20, 30)
        )
        self.assertEqual([p[0] for p in self.packets], [13497, 13560])

    def test_native_gain_changes_maximum_without_current_gain(self):
        self.apply(1201)
        self.assertEqual(
            (self.actor.effect_stats[117], self.actor.effect_maxima[117]), (25, 40)
        )
        remove_parameter_maximum(self.handler, 101)
        self.assertEqual(
            (self.actor.effect_stats[117], self.actor.effect_maxima[117]), (25, 30)
        )

    def test_native_underflow_rewrites_stored_amount_to_zero(self):
        self.apply(1202, 50)
        self.assertEqual(self.fight.owned_stat_effects[101]["actual"], 0)
        remove_parameter_maximum(self.handler, 101)
        self.assertEqual(self.actor.effect_maxima[117], 0)

    def test_effective_base_percentages_and_hard_cap_match_native(self):
        r = transition(
            family=1201,
            removing=False,
            amount=10,
            current=25,
            maximum=30,
            minimum=0,
            raw_min=0,
            percent=0,
            low=0,
            high=30,
            expandable=False,
        )
        self.assertEqual(r, (25, 40, 30, 10))
        r = transition(
            family=1201,
            removing=True,
            amount=10,
            current=r[0],
            maximum=r[2],
            minimum=0,
            raw_min=0,
            percent=0,
            low=0,
            high=30,
            expandable=False,
        )
        self.assertEqual(r, (20, 20, 20, 10))
        self.assertEqual(
            transition(
                family=1201,
                removing=False,
                amount=10,
                current=15,
                maximum=30,
                minimum=0,
                raw_min=0,
                percent=50,
                low=0,
                high=100,
                expandable=False,
            ),
            (15, 40, 60, 10),
        )
