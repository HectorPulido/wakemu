"""Native HP-minimum effects support only the audited detached SELF boundary."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat.combat_state import Actor
from wakfu_server.combat.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat.combat_minimum_resource import NativeMinimumResourceHandler
from wakfu_server.combat.combat_stat_handler import StatExecutionContext
from wakfu_server.combat.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat.combat_summon_creation import native_fresh_summon_authority


class MinimumResourceConstructorTests(unittest.TestCase):
    def fixture(self):
        actor = Actor(-3, 1, (0, 0, 0), 10, 6, 3, 1, 5)
        actor.team = -1
        actor.effect_stats = {1: 10}
        actor.effect_base_maxima = {1: 10}
        actor.effect_maxima = {1: 10}
        actor.effect_minima = {1: 0}
        actor.effect_base_minima = {1: 0}
        actor.effect_percentages = {1: 0}
        actor.effect_frozen = frozenset()
        fight = SimpleNamespace(
            id=8, actors={}, phase="placement", current=None, owned_stat_effects={}
        )
        packets = []
        handler = NativeMinimumResourceHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
        )
        invocation = EffectInvocation(418264, 5, actor.id, actor.id, actor.position)
        return fight, actor, handler, invocation, packets

    def test_detached_self_minimum_is_retained_without_registration_or_turn(self):
        fight, actor, handler, invocation, packets = self.fixture()
        authority = native_fresh_summon_authority(actor, 3510)
        with detached_summon_scope(fight, actor, authority):
            self.assertTrue(
                handler(dict(effect_class=877, parameters=[1, 0]), [], invocation)
            )
        self.assertEqual(actor.effect_minima[1], 1)
        self.assertEqual(actor.hp, 10)
        self.assertEqual(fight.actors, {})
        self.assertEqual(fight.phase, "placement")
        self.assertIsNone(fight.current)
        self.assertEqual(fight.owned_stat_effects[101]["actual"], 1)
        self.assertEqual([p[0] for p in packets], [13497])

    def test_registered_placement_actor_remains_rejected_without_writes(self):
        fight, actor, handler, invocation, packets = self.fixture()
        fight.actors[actor.id] = actor
        with self.assertRaisesRegex(ValueError, "Invalid native eWV actors"):
            handler(dict(effect_class=877, parameters=[1, 0]), [], invocation)
        self.assertEqual(actor.effect_minima[1], 0)
        self.assertEqual(packets, [])
        self.assertEqual(fight.owned_stat_effects, {})

    def test_detached_other_target_remains_rejected(self):
        fight, actor, handler, invocation, packets = self.fixture()
        other = Actor(-4, 1, (1, 0, 0), 10, 6, 3, 1, 5)
        fight.actors[other.id] = other
        invocation = EffectInvocation(418264, 5, actor.id, other.id, other.position)
        with detached_summon_scope(
            fight, actor, native_fresh_summon_authority(actor, 3510)
        ):
            with self.assertRaisesRegex(ValueError, "Invalid native eWV actors"):
                handler(dict(effect_class=877, parameters=[1, 0]), [], invocation)
        self.assertEqual(packets, [])
