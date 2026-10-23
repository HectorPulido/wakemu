"""Read actual retained Eni casting range without consuming gameplay or RNG."""
import json
from pathlib import Path
import sys
import unittest


class ActualHealingRanges(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        verify = cp["authorized_service_transition_verifier"]
        before = verify()
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_native_spell_casting import definition
        from wakfu_server.combat_casting_range import resolve_range

        current = cp["runtime"].fight
        actor = current.current
        self.assertEqual(actor.id, cp["identities"][-1])
        state = cp["rng"].getstate()
        _, adapter = server_runtime(
            cp["characters"][actor.id],
            cp["monsters"],
            cp["decks"][actor.id],
            action_id=cp["runtime"].action_id + 1,
            critical=False,
            **cp["common"]
        )
        rows = []
        for spell in (779, 1533, 625, 780, 781, 627, 638, 782, 1534, 1535, 1538, 7985):
            request = dict(
                actor_id=actor.id,
                spell_uid=(actor.id << 32) | spell,
                target=current.actors[cp["identities"][1]].position,
            )
            context = adapter.cast_condition(current, request)
            rule = definition(
                spell,
                230,
                context,
                actor.spell_ap_cost_modifiers,
                calculate_costs=False,
            )
            rows.append(
                dict(
                    spell=spell, rule=rule, resolved=resolve_range(rule, actor, context)
                )
            )
        self.assertEqual(cp["rng"].getstate(), state)
        Path(
            ".runtime/rushu-phase-review-20261021/rushu-a11-actual-t2-healing-ranges.json"
        ).write_text(
            json.dumps(
                dict(
                    actor=actor.id,
                    position=actor.position,
                    range_stat=actor.effect_stats[11],
                    range_modifiers=actor.spell_range_modifiers,
                    rows=rows,
                    no_cast_or_commit=True,
                    verification_before=before,
                    verification_after=verify(),
                ),
                indent=2,
                default=str,
            )
            + "\n"
        )


def qualify():
    return unittest.TestSuite([ActualHealingRanges()])
