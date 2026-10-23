"""Read actual native casting rules on the retained endpoint without a cast."""
import importlib
import json
from pathlib import Path
import unittest


class RetainedNativeRange(unittest.TestCase):
    def runTest(self):
        recipe = importlib.import_module("test_rushu_native_party_phase_one")
        checkpoint = recipe.RUSHU_ACTUAL_CHECKPOINT
        recipe.verify_actual_checkpoint()
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_native_spell_casting import definition
        from wakfu_server.combat_casting_range import resolve_range

        current = checkpoint["runtime"].fight
        actor = current.current
        self.assertEqual(current.native_table_turn, 5)
        self.assertIn(actor.id, checkpoint["identities"][:4])
        state = checkpoint["rng"].getstate()
        _, adapter = server_runtime(
            checkpoint["characters"][actor.id],
            checkpoint["monsters"],
            checkpoint["decks"][actor.id],
            action_id=checkpoint["runtime"].action_id + 1,
            critical=False,
            **checkpoint["common"]
        )
        rows = []
        for spell in (6971, 6980, 6977, 6978):
            request = dict(
                actor_id=actor.id,
                spell_uid=(actor.id << 32) | spell,
                target=current.actors[-200].position,
            )
            context = adapter.cast_condition(current, request)
            rule = definition(
                spell,
                230,
                context,
                actor.spell_ap_cost_modifiers,
                calculate_costs=False,
            )
            resolved = resolve_range(rule, actor, context)
            rows.append(dict(spell=spell, rule=rule, resolved=resolved))
        self.assertEqual(checkpoint["rng"].getstate(), state)
        report = dict(
            actor=actor.id,
            position=actor.position,
            boss=current.actors[-200].position,
            live_range=actor.effect_stats[11],
            range_modifiers=actor.spell_range_modifiers,
            rules=rows,
            no_cast_or_commit=True,
            loaded_implementation_attestation=recipe.verify_actual_checkpoint(),
        )
        Path(
            ".runtime/rushu-phase-review-20261021/rushu-retained-t5-actual-native-range-rules.json"
        ).write_text(json.dumps(report, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([RetainedNativeRange()])
