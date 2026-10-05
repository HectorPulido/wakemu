import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_minimum_resource import (
    NativeMinimumResourceHandler,
    remove_minimum_resource,
    transition,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class MinimumTests(unittest.TestCase):
    def test_native_clamp_and_removal_never_damage(self):
        self.assertEqual(transition(0, 100, 0, 0, 2147483647, 1), (1, 1, 1, 1))
        self.assertEqual(
            transition(1, 100, 1, 0, 2147483647, -1, fresh=False), (1, 0, 0, -1)
        )
        self.assertEqual(
            transition(2, 100, 0, 0, 2147483647, 150), (100, 100, 100, 100)
        )

    def test_owned_packets_and_reversible_minimum(self):
        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 1, 3, True)
        enemy = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 0, 1)
        fight = Fight(
            8, [actor, enemy], {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        fight.ready(3)
        actor.effect_stats = {1: 60}
        actor.effect_base_maxima = {1: 60}
        actor.effect_maxima = {1: 60}
        actor.effect_minima = {1: 0}
        actor.effect_base_minima = {1: 0}
        actor.effect_percentages = {1: 0}
        actor.effect_frozen = frozenset()
        packets = []
        handler = NativeMinimumResourceHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 101,
            context=lambda *a: StatExecutionContext(True, True, None, True, None),
        )
        handler(
            dict(effect_class=877, parameters=[1.0, 0.0]),
            [],
            EffectInvocation(418264, 20, 7, 7, (0, 0, 0)),
        )
        self.assertEqual(actor.effect_minima[1], 1)
        self.assertEqual(actor.hp, 60)
        self.assertEqual(fight.owned_stat_effects[101]["actual"], 1)
        remove_minimum_resource(handler, 101)
        self.assertEqual(actor.effect_minima[1], 0)
        self.assertEqual(actor.hp, 60)
        self.assertEqual([p[0] for p in packets], [13497, 13560])

    def test_unknown_definition_rejected_without_writes(self):
        handler = NativeMinimumResourceHandler(
            None, [], action_id=1, allocate_uid=lambda: 1, context=None
        )
        with self.assertRaises(ValueError):
            handler(dict(effect_class=876, parameters=[1.0, 0.0]), [], None)
