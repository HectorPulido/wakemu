"""Inspect actual Jump casting geometry on the retained actor, without a cast."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


class ActualJumpGeometry(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        verify = cp["authorized_service_transition_verifier"]
        before = verify()
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_native_spell_casting import definition
        from wakfu_server.combat_casting_range import resolve_range
        from wakfu_server.combat_casting_context import NativeOwnedCastingContext

        fight = cp["runtime"].fight
        actor = fight.current
        self.assertEqual(actor.id, cp["identities"][2])
        rng = cp["rng"].getstate()
        _, adapter = server_runtime(
            cp["characters"][actor.id],
            cp["monsters"],
            cp["decks"][actor.id],
            action_id=cp["runtime"].action_id + 1,
            critical=False,
            **cp["common"]
        )
        rows = []
        for cell in (
            (-51, 6, -4),
            (-50, 5, -4),
            (-49, 5, -4),
            (-48, 5, -4),
            (-47, 6, -4),
            (-51, 7, -4),
            (-51, 8, -4),
            (-50, 9, -4),
            (-48, 9, -4),
        ):
            request = dict(actor_id=actor.id, spell_uid=8404, target=cell)
            condition = adapter.cast_condition(fight, request)
            rule = definition(
                8404,
                230,
                condition,
                actor.spell_ap_cost_modifiers,
                calculate_costs=False,
            )
            rule = resolve_range(rule, actor, condition)
            hooks = NativeOwnedCastingContext(
                adapter,
                fight,
                request,
                SimpleNamespace(caster_id=actor.id, cell=cell),
                condition,
                rule,
            )
            hooks.resolve_target_fighter()
            rows.append(
                dict(
                    cell=cell,
                    rule=rule,
                    qi_j=hooks.qi_j(),
                    native_los=hooks.native_los(),
                    los_diagnostic=hooks.los_diagnostic,
                    distance=hooks.range_distance(),
                    target=None if hooks.target is None else hooks.target.id,
                )
            )
        self.assertEqual(cp["rng"].getstate(), rng)
        Path(
            ".runtime/rushu-phase-review-20261021/rushu-a11-iop3-actual-jump-geometry.json"
        ).write_text(
            json.dumps(
                dict(
                    position=actor.position,
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
    return unittest.TestSuite([ActualJumpGeometry()])
