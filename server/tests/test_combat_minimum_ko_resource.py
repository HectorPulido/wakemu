"""Native1003 eWV uses characteristic14, independently of HP/AP/MP."""
import unittest
from wakfu_server.combat_minimum_resource import (
    NativeMinimumResourceHandler,
    remove_minimum_resource,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class MinimumKOResourceTests(unittest.TestCase):
    def fixture(self):
        from test_combat_damage_handler import DamageHandlerTests

        fixture = DamageHandlerTests()
        fixture.setUp()
        fight, actor = fixture.fight, fixture.fight.actors[-7]
        for name, value in (
            ("effect_stats", 0),
            ("effect_base_maxima", 3),
            ("effect_maxima", 3),
            ("effect_minima", 0),
            ("effect_base_minima", 0),
            ("effect_percentages", 0),
        ):
            data = getattr(actor, name, None)
            if not isinstance(data, dict):
                data = {}
                setattr(actor, name, data)
            data[14] = value
        actor.effect_frozen = frozenset()
        packets = []
        handler = NativeMinimumResourceHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 901,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
        )
        return fight, actor, handler, packets

    def test_actual1003_changes_only_pc14_and_retains_exact_removal_identity(self):
        fight, actor, handler, packets = self.fixture()
        before = (actor.hp, actor.ap, actor.mp)
        handler(
            dict(effect_class=1003, parameters=[1.0, 0.0]),
            {},
            EffectInvocation(170709, 1, 7, -7, (1, 0, 0)),
        )
        self.assertEqual((actor.effect_stats[14], actor.effect_minima[14]), (1, 1))
        self.assertEqual((actor.hp, actor.ap, actor.mp), before)
        row = fight.owned_stat_effects[901]
        self.assertEqual(
            (row["effect_class"], row["stat_id"], row["actual"]), (1003, 14, 1)
        )
        remove_minimum_resource(handler, 901)
        self.assertEqual(actor.effect_minima[14], 0)
        self.assertEqual(actor.effect_stats[14], 1)
        self.assertEqual([packet[0] for packet in packets], [13497, 13560])

    def test_frozen_pc14_without_raw_authority_rejects_without_writes(self):
        fight, actor, handler, packets = self.fixture()
        actor.effect_frozen = frozenset((14,))
        with self.assertRaisesRegex(ValueError, "hidden raw-current authority"):
            handler(
                dict(effect_class=1003, parameters=[1.0, 0.0]),
                {},
                EffectInvocation(170709, 1, 7, -7, (1, 0, 0)),
            )
        self.assertEqual(actor.effect_minima[14], 0)
        self.assertEqual(packets, [])
        self.assertNotIn(901, fight.owned_stat_effects)

    def test_copied_frozen_raw_current_reappears_after_minimum_removal(self):
        for frozen in (False, True):
            fight, actor, handler, packets = self.fixture()
            actor.native_copy_pa_source = dict(
                producer="eHI.pRU.ffh.a",
                actor_id=actor.id,
                profile=2382,
                effect_reference=1,
                source_actor_id=7,
            )
            actor.effect_characteristic_raw_currents = {14: 0}
            actor.effect_frozen = frozenset((14,)) if frozen else frozenset()
            handler(
                dict(effect_class=1003, parameters=[1.0, 0.0]),
                {},
                EffectInvocation(170709, 1, 7, -7, (1, 0, 0)),
            )
            self.assertEqual(actor.effect_stats[14], 1)
            self.assertEqual(
                actor.effect_characteristic_raw_currents[14], 0 if frozen else 1
            )
            remove_minimum_resource(handler, 901)
            self.assertEqual(actor.effect_stats[14], 0 if frozen else 1)
            self.assertEqual(actor.effect_minima[14], 0)

    def test_retained_wrong_pc_identity_fails_before_removal(self):
        fight, actor, handler, packets = self.fixture()
        fight.owned_stat_effects[901] = dict(effect_class=1003, stat_id=1)
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            remove_minimum_resource(handler, 901)
        self.assertIn(901, fight.owned_stat_effects)
