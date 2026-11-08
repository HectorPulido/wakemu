"""Absent native clocks retain their identity after certified QI retirement."""
import unittest
from copy import deepcopy

from test_combat_qi_death_lifecycle import NativeQIDeathLifecycleTests
from wakfu_server.combat_native_timing_context import native_state_timeline
from wakfu_server.combat_ordinary_qi_retirement import complete_ordinary_qi_death
from wakfu_server.combat_state_timing import StateTimingDefinition, schedule_state_timer


class RetiredStateClockTests(unittest.TestCase):
    def test_native_retirement_clock_keeps_identity_and_rejects_forged_receipt(self):
        fight, pc, clock, survivor = NativeQIDeathLifecycleTests().fight()
        clock.native_controlled_by_ai = False
        fight.apply_effect_damage(pc.id, clock.id, clock.hp)
        self.assertTrue(complete_ordinary_qi_death(fight, clock))
        self.assertNotIn(clock.id, fight.order)
        timeline = native_state_timeline(fight, clock.id)
        self.assertEqual(timeline.clock_actor_index, -1)
        timer = schedule_state_timer(
            StateTimingDefinition(2, 0, 1, False, True),
            level=1,
            caster_id=clock.id,
            target_id=survivor.id,
            round_number=timeline.round_number,
            current_actor_id=timeline.current_actor_id,
            current_actor_index=timeline.current_actor_index,
            clock_actor_index=timeline.clock_actor_index,
            current_phase=timeline.current_phase,
        )
        self.assertEqual(timer.actor_id, clock.id)
        self.assertEqual(timer.expiration_round, timeline.round_number + 2)
        self.assertTrue(timer.expires_at_round_cleanup(timer.expiration_round + 1))
        self.assertEqual(native_state_timeline(deepcopy(fight), clock.id), timeline)
        with self.assertRaisesRegex(ValueError, "Missing state clock actor"):
            native_state_timeline(fight, 999)
        fight.native_ordinary_qi_retirements[str(clock.id)]["source"] = "forged"
        with self.assertRaisesRegex(ValueError, "Unverified ordinary QI retirement"):
            native_state_timeline(fight, clock.id)
