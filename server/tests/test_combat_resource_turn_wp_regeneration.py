"""Trace Xelor's native end-boundary WP regeneration independently."""
import unittest
from unittest.mock import patch

import test_aniripsa_grant_summon_pipeline as turn_helpers
import test_xelor_runtime_pipeline as xelor_helpers
from wakfu_server.combat_effect_dispatch import EffectDispatcher


class ResourceTurnWPRegenerationTests(unittest.TestCase):
    def test_slowdown_payment_is_followed_by_actual_1037_wp_gain(self):
        helper = xelor_helpers.XelorRuntimePipelineTests()
        data = helper.fixture()
        fight = data[2]
        target = fight.actors[-7]
        wp_before_cast = fight.actors[7].effect_stats[4]

        transaction = helper.cast(data, 775, target.position, action_id=50)
        fight = transaction.fight
        wp_after_payment = fight.actors[7].effect_stats[4]
        self.assertEqual(wp_after_payment, wp_before_cast - 1)

        fixture = helper.adopt(data, fight)
        trace = []
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (313109, 313110, 349654):
                trace.append(
                    {
                        "reference": invocation.reference,
                        "caster_id": invocation.caster_id,
                        "target_id": invocation.target_id,
                        "result": bool(result),
                        "turn_boundary": invocation.native_turn_boundary_context,
                        "trigger": invocation.native_trigger_context,
                    }
                )
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            turn_helpers.AniripsaGrantSummonPipelineTests().end_current_turn(
                fight, fixture
            )
            owner_end_trace = list(trace)
            wp_after_owner_end = fight.actors[7].effect_stats[4]
            turn_helpers.AniripsaGrantSummonPipelineTests().end_current_turn(
                fight, fixture
            )
            npc_end_trace = trace[len(owner_end_trace) :]
            wp_after_npc_end = fight.actors[7].effect_stats[4]

        owner_regen = [
            row
            for row in owner_end_trace
            if row["turn_boundary"]
            and row["turn_boundary"].get("actor_id") == 7
            and row["turn_boundary"].get("event_id") == 1037
        ]
        self.assertTrue(
            any(row["reference"] == 313109 for row in owner_regen), owner_end_trace
        )
        self.assertTrue(
            any(
                row["reference"] == 313110 and row["target_id"] == 7 and row["result"]
                for row in owner_regen
            ),
            owner_end_trace,
        )
        self.assertEqual(fight.current.id, 7)
        self.assertEqual(wp_after_owner_end, wp_before_cast)
        self.assertEqual(wp_after_owner_end - wp_after_payment, 1)
        self.assertEqual(wp_after_npc_end, wp_after_owner_end)
        self.assertTrue(
            all(row["turn_boundary"] for row in npc_end_trace), npc_end_trace
        )


if __name__ == "__main__":
    unittest.main()
