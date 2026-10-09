"""eZG adds protections before HP-minimum and KO-maximum assignments."""
import unittest
from types import SimpleNamespace
import test_combat_kill as kill_tests

from wakfu_server.combat_protected_kill import (
    NativeProtectedKillHandler,
    remove_protected_kill,
    registered_protected_kill,
)
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    global_fighter_guards,
)


class NativeProtectedKillTests(unittest.TestCase):
    def fixture(self, frozen=()):
        fixture = kill_tests.NativeKillTests()
        fight, target, packets, phases, original, effect, invocation = fixture.fixture(
            frozen=frozen
        )
        target.native_fight_property_counts = {19: 127, 12: 2, 7: 3}
        target.native_is_dead = False
        if not hasattr(fight, "native_global_pv_collections"):
            initialize_global_pv_collections(fight, tuple(fight.actors))
        handler = NativeProtectedKillHandler(
            original.fight,
            packets,
            action_id=original.action_id,
            allocate_uid=original.allocate_uid,
            context=original.context,
            rng=original.rng,
            authority=SimpleNamespace(
                property_counts=lambda fight, actor: actor.native_fight_property_counts
            ),
        )
        effect = dict(effect, effect_class=332)
        return handler, effect, invocation, target, packets

    def test_protection_wrap_minimum_and_removal_preserve_independent_life(self):
        handler, effect, invocation, target, packets = self.fixture()
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(
            (target.hp, target.effect_stats[14], target.effect_maxima[14]), (0, 0, 0)
        )
        self.assertEqual(target.native_fight_property_counts, {19: -128, 12: 3, 7: 3})
        self.assertFalse(target.native_is_dead)
        self.assertEqual(
            global_fighter_guards(handler.fight, target.id),
            dict(baF=True, baG=False, baK=False),
        )
        self.assertTrue(registered_protected_kill(handler.fight, target))
        uid = next(iter(handler.fight.owned_stat_effects))
        remove_protected_kill(handler, uid)
        self.assertEqual((target.hp, target.native_fight_property_counts[12]), (0, 3))
        self.assertEqual([opcode for opcode, payload in packets], [12613, 13560])

    def test_frozen_hp_still_adds_properties_and_resets_clock(self):
        handler, effect, invocation, target, packets = self.fixture(frozen=(1,))
        before = target.hp
        handler(effect, {}, invocation)
        self.assertEqual(target.hp, before)
        self.assertEqual(target.effect_maxima[14], 0)
        self.assertEqual(target.native_fight_property_counts[12], 3)

    def test_missing_property_authority_rejects_before_any_write(self):
        handler, effect, invocation, target, packets = self.fixture()
        handler.authority = None
        before = (
            target.hp,
            dict(target.effect_stats),
            dict(target.native_fight_property_counts),
        )
        with self.assertRaisesRegex(ValueError, "property counters"):
            handler(effect, {}, invocation)
        self.assertEqual(
            (target.hp, target.effect_stats, target.native_fight_property_counts),
            before,
        )
        self.assertEqual(packets, [])

    def test_raw_or_stale_hp0_does_not_accredit_protected_transition(self):
        handler, effect, invocation, target, packets = self.fixture()
        target.hp = 0
        self.assertFalse(registered_protected_kill(handler.fight, target))
        target.hp = target.effect_stats[1]
        handler(effect, {}, invocation)
        self.assertTrue(registered_protected_kill(handler.fight, target))
        handler.fight._event("damage", target_id=target.id, hp=0)
        self.assertFalse(registered_protected_kill(handler.fight, target))

    def test_prepare_cancel_and_all_event_phases_keep_native_zero_value(self):
        handler, effect, invocation, target, packets = self.fixture()
        phases = []
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda effect, invocation, **kw: phases.append(
                (kw["channel"], kw["value"], kw["_event_ids"])
            ),
            register_applied=lambda *args: None,
        )
        prepared = handler.prepare(effect, {}, invocation)
        handler.cancel_prepared(prepared)
        self.assertEqual((handler.prepared, handler.runners), ({}, {}))
        self.assertEqual(target.hp, 80)
        phases.clear()
        prepared = handler.prepare(effect, {}, invocation)
        handler(effect, {}, prepared)
        self.assertEqual(phases, [(channel, 0, (0,)) for channel in (1, 2, 3, 4)])
        self.assertEqual((handler.prepared, handler.runners), ({}, {}))
