"""Actual113822 eZy1049 native values, retention and ordered PA execution."""
import unittest
from wakfu_server.combat_characteristic_swap_handler import (
    NativeCharacteristicSwapHandler,
    remove_characteristic_swap,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class CharacteristicSwapHandlerTests(unittest.TestCase):
    def fixture(self):
        from test_combat_damage_handler import DamageHandlerTests

        fixture = DamageHandlerTests()
        fixture.setUp()
        fight, actor = fixture.fight, fixture.fight.actors[-7]
        for name in ("effect_stats", "effect_minima", "effect_maxima"):
            if not isinstance(getattr(actor, name, None), dict):
                setattr(actor, name, {})
        for stat, value in ((21, 40), (23, 90)):
            actor.effect_stats[stat] = value
            actor.effect_minima[stat] = -5000
            actor.effect_maxima[stat] = 50000
        actor.effect_frozen = frozenset()
        packets = []
        handler = NativeCharacteristicSwapHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 901,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
            rng=lambda: 0,
        )
        effect = dict(
            effect_class=1049,
            parameters=[21.0, 0.0, 23.0, 0.0],
            target_masks=[[], [], [], [], [], [], []],
        )
        invocation = EffectInvocation(113822, 1, 7, -7, (1, 0, 0))
        return fight, actor, handler, packets, effect, invocation

    def test_actual_native_swap_payload_and_retained_removal(self):
        fight, actor, handler, packets, effect, invocation = self.fixture()
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual((actor.effect_stats[21], actor.effect_stats[23]), (90, 40))
        row = fight.owned_stat_effects[901]
        self.assertEqual(row["native_captured_currents"], [40, 90])
        self.assertTrue(
            bytes.fromhex(row["payload"]).endswith(
                bytes.fromhex("420a50286015980117a0015a")
            )
        )
        remove_characteristic_swap(handler, 901)
        self.assertEqual((actor.effect_stats[21], actor.effect_stats[23]), (40, 90))
        self.assertNotIn(901, fight.owned_stat_effects)
        self.assertEqual([packet[0] for packet in packets], [13497, 13560])

    def test_phase_two_precedes_capture_of_private_currents(self):
        fight, actor, handler, packets, effect, invocation = self.fixture()
        phases = []

        class Lifecycle:
            def phase(self, effect, invocation, **kw):
                phases.append(kw["channel"])
                if kw["channel"] == 2:
                    actor.effect_stats[21] = 70

            def register_applied(self, *args):
                pass

        handler.event_lifecycle = Lifecycle()
        handler(effect, {}, invocation)
        self.assertEqual(phases, [1, 2, 3, 4])
        self.assertEqual(
            fight.owned_stat_effects[901]["native_captured_currents"], [70, 90]
        )
        self.assertEqual((actor.effect_stats[21], actor.effect_stats[23]), (90, 70))

    def test_copied_frozen_first_pa_preserves_four_native_operations(self):
        fight, actor, handler, packets, effect, invocation = self.fixture()
        actor.native_copy_pa_source = dict(
            producer="eHI.pRU.ffh.a",
            actor_id=actor.id,
            profile=2382,
            effect_reference=1,
            source_actor_id=7,
        )
        actor.effect_characteristic_raw_currents = {21: 40, 23: 90}
        actor.effect_frozen = frozenset((21,))
        handler(effect, {}, invocation)
        self.assertEqual((actor.effect_stats[21], actor.effect_stats[23]), (40, 40))
        self.assertEqual(actor.effect_characteristic_raw_currents, {21: 40, 23: 40})
        remove_characteristic_swap(handler, 901)
        self.assertEqual((actor.effect_stats[21], actor.effect_stats[23]), (40, 90))

    def test_unknown_raw_authority_rejects_before_pa_writes(self):
        fight, actor, handler, packets, effect, invocation = self.fixture()
        actor.effect_frozen = frozenset((23,))
        with self.assertRaisesRegex(ValueError, "hidden raw-current authority"):
            handler(effect, {}, invocation)
        self.assertEqual((actor.effect_stats[21], actor.effect_stats[23]), (40, 90))
        self.assertEqual(packets, [])
        self.assertEqual(fight.owned_stat_effects, {})
