"""Shared lifecycle integration over the original retained-event fixture."""
import unittest
from dataclasses import replace
from unittest.mock import patch

import test_combat_ordinary_events as ordinary_fixture
import test_combat_summon as summon_fixture
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
)


class GlobalPVLifecycleDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ordinary_fixture.OrdinaryHealingEventTests.setUpClass()

    setUp = ordinary_fixture.OrdinaryHealingEventTests.setUp

    def test_global_delivery_visits_native_order_after_both_local_channels(self):
        initialize_global_pv_collections(self.fight, (7, -7))
        seen = []
        self.events.replay = lambda source, **kwargs: seen.append(
            (source.channel, source.manager_actor_id)
        )
        self.events.phase(self.effect, self.inv, uid=800, value=1, channel=3)
        self.assertEqual(seen, [(30, 7), (3, 7), (31, 7), (31, -7)])

    def test_previous_global_reaction_can_remove_later_fighter_membership(self):
        initialize_global_pv_collections(self.fight, (7, -7))
        seen = []

        def replay(source, **kwargs):
            seen.append((source.channel, source.manager_actor_id))
            if source.channel == 31 and source.manager_actor_id == 7:
                set_global_fighter_status(self.fight, -7, "OUT_OF_PLAY")

        self.events.replay = replay
        self.events.phase(self.effect, self.inv, uid=800, value=1, channel=3)
        self.assertEqual(seen, [(30, 7), (3, 7), (31, 7)])

    def test_own_lethal_damage_records_off_play_without_removing_native_map(self):
        initialize_global_pv_collections(self.fight, (7, -7))
        with self.fight.effect_resolution():
            self.fight.apply_effect_damage(7, -7, self.fight.actors[-7].hp)
            self.assertEqual(
                self.fight.native_global_pv_collections["fighter_status"]["-7"],
                "OFF_PLAY",
            )
            self.assertEqual(
                self.fight.native_global_pv_collections["fighters"]["size"], 2
            )

    def test_ordinary_actor_authority_reads_actual_fdy_guards(self):
        initialize_global_pv_collections(self.fight, (7, -7))
        set_global_fighter_status(self.fight, -7, "OFF_PLAY")
        authority = self.adapter.actor_authority(self.fight, self.fight.actors[-7])
        self.assertTrue(authority.targeting["baG"])
        self.assertFalse(authority.targeting["baF"])
        self.assertFalse(authority.targeting["baK"])
        self.assertFalse(authority.native_in_play)

    def test_retained_original_target_corpse_gate_uses_status_before_rebinding(self):
        initialize_global_pv_collections(self.fight, (7, -7))
        set_global_fighter_status(self.fight, -7, "OFF_PLAY")
        self.fight.native_owned_group_effects[900]["invocation"]["target_id"] = -7
        invocation = replace(self.inv, base_uid=900)
        with patch(
            "wakfu_server.combat_ordinary_death.corpse_gate_bypassed",
            return_value=False,
        ):
            self.assertFalse(self.events.executable(self.effect, invocation, None))
        with patch(
            "wakfu_server.combat_ordinary_death.corpse_gate_bypassed", return_value=True
        ):
            self.assertTrue(self.events.executable(self.effect, invocation, None))


class GlobalPVRegisteredSummonLifeTests(unittest.TestCase):
    def test_registered_summon_death_updates_live_guard_authority(self):
        from wakfu_server.combat_summon import RegisteredSummonAuthority

        fight, summon, registration = summon_fixture.SummonTests().fixture()
        initialize_global_pv_collections(fight, (7, -7))
        from wakfu_server.combat_timeline_snapshot import initialize

        initialize(fight, fight.order)
        authority = RegisteredSummonAuthority(summon_fixture.Ordinary())
        authority.register(
            fight, summon, registration, new_order=[7, 901, -7], new_turn_index=0
        )
        self.assertTrue(authority(fight, summon).targeting["baF"])
        # This contract covers the live fdy guard inside a nested effect chain,
        # not final KO_TIME retirement. Keep the outer chain open until the
        # surrounding system owns its native summon-retirement context.
        fight._resolution_depth = 1
        try:
            with fight.effect_resolution():
                fight.apply_effect_damage(-7, summon.id, summon.hp)
                life = authority(fight, summon)
                self.assertTrue(life.targeting["baG"])
                self.assertFalse(life.targeting["baF"])
                self.assertFalse(life.targeting["baK"])
                self.assertIn(summon.id, fight.actors)
            self.assertEqual(fight._resolution_depth, 1)
        finally:
            fight._resolution_depth = 0
