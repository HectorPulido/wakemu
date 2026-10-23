"""Native268501 companion-disabled property and eWw namespace asymmetry."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_world_property_handler import (
    NativeWorldPropertyHandler,
    remove_world_property,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class WorldPropertyHandlerTests(unittest.TestCase):
    def fixture(self):
        from test_combat_damage_handler import DamageHandlerTests

        f = DamageHandlerTests()
        f.setUp()
        fight, actor = f.fight, f.fight.actors[-7]
        actor.native_world_property_counts = {12: 2}
        actor.native_fight_property_counts = {31: 2}

        class Authority:
            def __call__(self, *args):
                return SimpleNamespace(targeting={"is_eGj": True, "bcN": 0})

            def world_property_counts(self, fight, actor):
                return actor.native_world_property_counts

            def property_counts(self, fight, actor):
                return actor.native_fight_property_counts

        packets = []
        h = NativeWorldPropertyHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 901,
            context=lambda *a: StatExecutionContext(True, True, None, True, None),
            authority=Authority(),
            rng=lambda: 0,
        )
        effect = dict(
            effect_class=449,
            parameters=[83.0, 0.0],
            target_masks=[[] for _ in range(7)],
        )
        inv = EffectInvocation(268501, 1, 7, -7, (1, 0, 0))
        return fight, actor, h, packets, effect, inv

    def test_actual268501_retains_distinct_world_counter_and_removes_it(self):
        fight, actor, h, packets, effect, inv = self.fixture()
        from wakfu_server.combat_effects import _integer
        from wakfu_server.combat_protocol_reconstruction import decode_packet, _effect

        timing = _integer(2, -1) + _integer(3, 17) + _integer(5, 1)
        h.context = lambda *a: StatExecutionContext(True, True, None, True, timing)
        with patch(
            "wakfu_server.combat_world_property_handler.registry",
            return_value={"83": {"fight_property": -1}},
        ):
            self.assertTrue(h(effect, {}, inv))
        self.assertEqual(actor.native_world_property_counts, {12: 2, 83: 1})
        self.assertEqual(actor.native_fight_property_counts, {31: 2})
        self.assertFalse(hasattr(actor, "native_world_property_since_ms"))
        retained = _effect(bytes.fromhex(fight.owned_stat_effects[901]["payload"]), 449)
        application = decode_packet(*packets[0])["effect"]
        self.assertEqual(application["timing"], retained["timing"])
        self.assertNotIn(1, application["timing"])
        remove_world_property(h, 901)
        self.assertEqual(actor.native_world_property_counts, {12: 2})
        self.assertEqual([p[0] for p in packets], [12613, 13560])
        removal = decode_packet(*packets[-1])["effect"]
        self.assertEqual(removal["timing"].get(1), [(0, 1)])
        self.assertEqual(
            {k: v for k, v in removal["timing"].items() if k != 1},
            retained["timing"],
        )

    def test_constructor_skips_mapped_apply_but_removal_always_decrements(self):
        fight, actor, h, packets, effect, inv = self.fixture()
        before = (actor.ap, actor.mp)
        with patch(
            "wakfu_server.combat_world_property_handler.registry",
            return_value={"83": {"fight_property": 31}},
        ), patch(
            "wakfu_server.combat_world_property_handler.context_kind", return_value=3
        ):
            h(effect, {}, inv)
        self.assertEqual(actor.native_fight_property_counts, {31: 2})
        remove_world_property(h, 901)
        self.assertEqual(actor.native_fight_property_counts, {31: 1})
        self.assertEqual((actor.ap, actor.mp), before)

    def test_fight_mapping_mutates_counts_without_invented_eWt_resource_reset(self):
        fight, actor, h, packets, effect, inv = self.fixture()
        before = actor.ap
        with patch(
            "wakfu_server.combat_world_property_handler.registry",
            return_value={"83": {"fight_property": 31}},
        ):
            h(effect, {}, inv)
        self.assertEqual(actor.native_fight_property_counts, {31: 3})
        self.assertEqual(actor.ap, before)
        remove_world_property(h, 901)
        self.assertEqual(actor.native_fight_property_counts, {31: 2})

    def test_missing_counter_population_fails_before_mutation(self):
        fight, actor, h, packets, effect, inv = self.fixture()
        actor.native_world_property_counts = None
        with patch(
            "wakfu_server.combat_world_property_handler.registry",
            return_value={"83": {"fight_property": -1}},
        ), self.assertRaisesRegex(
            ValueError, "complete native world-property counters"
        ):
            h(effect, {}, inv)
        self.assertEqual(actor.native_fight_property_counts, {31: 2})
        self.assertEqual(packets, [])
