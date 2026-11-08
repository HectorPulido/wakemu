"""Selected final summon clocks preserve native absent-index scheduling."""
import unittest
from types import SimpleNamespace
from test_combat_summon_retirement import SummonRetirementTests
from wakfu_server.combat_native_timing_context import (
    NativeEffectTimingProvider,
    native_state_timeline,
)
from wakfu_server.combat_summon_retirement import retired_summon_actor
from wakfu_server.combat_state_timing import StateTimingDefinition, schedule_state_timer


class SelectedReceipts(dict):
    def items(self):
        raise AssertionError("Selected clock must not scan all retirement receipts")


class SummonClockFixTests(unittest.TestCase):
    def test_retired_summon_live_target_state_clock_and_selected_proof(self):
        fight, owner, enemy, summon = SummonRetirementTests().fight(ko=0)
        fight.native_summon_registrations[summon.id]["fight_properties"] = []
        fight.apply_effect_damage(owner.id, summon.id, summon.hp)
        fight.native_summon_retirements = SelectedReceipts(
            fight.native_summon_retirements
        )
        fight.native_summon_retirements[999] = {"source": "unrelated malformed receipt"}
        self.assertTrue(retired_summon_actor(fight, summon.id))
        # Exercise the public carrier provider on the living target. This is a
        # small definition fixture, not a claim of replaying a published spell.
        definition = dict(
            maximum_level=10,
            duration_base=2,
            duration_per_level=0,
            realtime_duration_base=0,
            realtime_duration_per_level=0,
            clock_actor="caster",
            tick_at_turn_end=False,
            additive=False,
            replace=True,
            refresh=False,
            protected=False,
            skip_turn_timer=False,
            effect_ids=[],
        )
        provider = NativeEffectTimingProvider(
            {"states": {"1": definition}, "effects": {}}
        )
        invocation = SimpleNamespace(
            level=1, caster_id=summon.id, target_id=enemy.id, base_uid=123
        )
        context = provider.state_reference(
            fight, None, {"native_execution_mode": 0, "variant": 0}, invocation, 1, 1
        )
        self.assertEqual(context.timeline.clock_actor_index, -1)
        self.assertEqual(context.parent_uid, 123)
        timer = schedule_state_timer(
            StateTimingDefinition(2, 0, 10, False, True),
            level=1,
            caster_id=summon.id,
            target_id=enemy.id,
            **vars(context.timeline)
        )
        self.assertEqual(timer.actor_id, summon.id)
        self.assertTrue(timer.expires_at_round_cleanup(timer.expiration_round + 1))
        saved = fight.native_summon_retirements.pop(summon.id)
        with self.assertRaisesRegex(ValueError, "Missing state clock actor"):
            native_state_timeline(fight, summon.id)
        fight.native_summon_retirements[summon.id] = dict(saved, source="forged")
        with self.assertRaisesRegex(
            ValueError, "Invalid native summon retirement record"
        ):
            native_state_timeline(fight, summon.id)
