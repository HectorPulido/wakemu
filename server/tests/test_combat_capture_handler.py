import unittest
from types import SimpleNamespace
from dataclasses import replace
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    CapturedCreature,
)
from wakfu_server.combat_capture_handler import NativeCaptureHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class CaptureHandlerTests(unittest.TestCase):
    def fixture(self, roster=None, target_type=1, dte=False):
        caster = SimpleNamespace(id=7)
        target = SimpleNamespace(id=8, hp=50, native_fight_property_counts={40: 1})
        fight = SimpleNamespace(
            id=1, phase="active", actors={7: caster, 8: target}, owned_stat_effects={}
        )
        source = SimpleNamespace(
            targeting={"is_eGj": True},
            native_is_ehp=True,
            native_captured_roster=roster or OwnedCapturedRoster(7),
        )
        destination = SimpleNamespace(
            targeting={"is_eGj": True, "dTE": dte},
            native_actor_type=target_type,
            breed_id=1152,
        )
        authority = lambda f, a: source if a.id == 7 else destination
        authority.property_counts = lambda f, a: dict(a.native_fight_property_counts)
        authority.world_property_counts = lambda f, a: {}
        packets, phases = [], []
        handler = NativeCaptureHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 99,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            rng=lambda: 0,
            authority=authority,
        )
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda *args, **kwargs: phases.append(kwargs["channel"])
        )
        effect = {
            "effect_class": 320,
            "parameters": [],
            "target_masks": [[] for _ in range(7)],
        }
        invocation = EffectInvocation(326383, 200, 7, 8, (0, 0, 0))
        return fight, target, packets, phases, handler, effect, invocation

    def test_capture_updates_actual_component_and_properties_without_hp_transition(
        self,
    ):
        fight, target, packets, phases, handler, effect, invocation = self.fixture()
        self.assertTrue(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        roster = OwnedCapturedRoster.from_record(
            fight.native_captured_rosters["7"], expected_owner_id=7
        )
        self.assertEqual(roster.selected_creature.profile_id, 1152)
        self.assertTrue(roster.available[0])
        self.assertEqual(fight.native_captured_roster_updates["7"], roster.to_record())
        self.assertEqual(
            target.native_fight_property_counts, {40: 1, 19: 1, 12: 1, 66: 1, 65: 1}
        )
        self.assertEqual(target.native_world_property_counts, {28: 1})
        self.assertEqual(target.hp, 50)
        self.assertEqual(phases, [1, 2, 3, 4])
        self.assertEqual(packets[0][0], 12613)
        self.assertEqual(packets[0][1][12], 1)

    def test_full_roster_rejects_without_target_or_component_mutation(self):
        roster = OwnedCapturedRoster(
            7, tuple(CapturedCreature(i, 1152, "") for i in range(10)), selected_slot=9
        )
        fight, target, packets, phases, handler, effect, invocation = self.fixture(
            roster
        )
        self.assertFalse(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        self.assertFalse(hasattr(fight, "native_captured_rosters"))
        self.assertEqual(target.native_fight_property_counts, {40: 1})
        self.assertEqual(target.hp, 50)
        self.assertFalse(packets)
        self.assertFalse(handler.prepared)

    def test_native_summon_dte_and_actual_actor_type_reject(self):
        for actor_type, dte in ((1, True), (0, False)):
            fight, target, packets, phases, handler, effect, invocation = self.fixture(
                target_type=actor_type, dte=dte
            )
            self.assertFalse(
                handler(effect, {}, handler.prepare(effect, {}, invocation))
            )
            self.assertFalse(hasattr(fight, "native_captured_rosters"))
            self.assertFalse(packets)

    def test_missing_world_counter_authority_rejects_before_mutation(self):
        fight, target, packets, phases, handler, effect, invocation = self.fixture()
        handler.authority.world_property_counts = None
        with self.assertRaisesRegex(ValueError, "world-property counters"):
            handler(effect, {}, handler.prepare(effect, {}, invocation))
        self.assertEqual(target.native_fight_property_counts, {40: 1})
        self.assertFalse(hasattr(fight, "native_captured_rosters"))
        self.assertFalse(packets)


if __name__ == "__main__":
    unittest.main()
