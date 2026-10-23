"""Paid border movement earns the original Foul Moon first-phase counter."""
import json
from pathlib import Path
from random import Random
import unittest
from unittest.mock import patch


class FulMoonPaidNativeBorderTests(unittest.TestCase):
    def test_real_border_entries_and_next_turn_start_earn_five_moon_levels(self):
        from test_fulmoon_talkasha_native_bootstrap import (
            FulMoonTalKashaNativeBootstrapTests,
        )
        from native_supreme_scene_turn_runtime import native_scene_turn_runtime
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
        )
        from wakfu_server.combat_ai import (
            snapshot as ai_snapshot,
            validate as ai_validate,
        )
        from wakfu_server.combat_movement_runtime import apply_ai, _with_areas
        from wakfu_server.combat_area_transaction import prepare_area_movement

        helper = FulMoonTalKashaNativeBootstrapTests()
        fight, scene, children = helper._started(
            3870, 185, 1056, reconstructed_fulmoon_scene
        )
        character, monsters, deck = helper.encounter_context
        rng = Random(0)
        runtime, stats = native_scene_turn_runtime(
            fight, character, monsters, deck, map_id=1056, rng=rng
        )
        receipt = dict(
            scope="paid_native_1085_boss_counter_component",
            full_encounter_victory=False,
            injected_states_or_resources=False,
            scene_policy=scene["policy"],
            payments=[],
            levels=[],
        )

        def level():
            return sum(
                entry.level
                for entry in runtime.fight.actors[-200].state_ledger.entries
                if entry.reference == 4212
            )

        def move(path):
            actor = runtime.fight.actors[-200]
            self.assertEqual(runtime.fight.current.id, actor.id)
            self.assertGreaterEqual(actor.mp, len(path))
            origin, old_mp = actor.position, actor.mp

            def decide(candidate, actor_id):
                request = ai_snapshot(candidate, actor_id)
                return ai_validate(
                    candidate,
                    actor_id,
                    request,
                    dict(
                        protocol=1,
                        requestId=request["requestId"],
                        stateKey=request["stateKey"],
                        decision=dict(
                            actor_id=actor_id,
                            target_id=7,
                            path=[list(cell) for cell in path],
                            attack=None,
                        ),
                    ),
                )

            with patch("wakfu_server.combat_ai.plan", decide):
                _with_areas(
                    runtime,
                    lambda candidate, **kw: prepare_area_movement(
                        character, monsters, candidate, deck, rng=rng, **kw
                    ),
                    lambda candidate, callback: apply_ai(
                        candidate,
                        lambda actor: stats(actor, candidate.fight),
                        direction=actor.direction,
                        _step_callback=callback,
                    ),
                )
            current = runtime.fight.actors[-200]
            self.assertEqual(current.position, path[-1])
            self.assertEqual(current.mp, old_mp - len(path))
            receipt["payments"].append(
                dict(
                    origin=origin,
                    path=path,
                    mp_before=old_mp,
                    mp_after=current.mp,
                    level=level(),
                )
            )

        try:
            runtime.turn_started()
            self.assertEqual(runtime.fight.current.id, -200)
            self.assertEqual(runtime.fight.actors[-200].team, 0)
            self.assertEqual(runtime.fight.actors[7].team, 1)
            move([(0, -1, 0), (-1, -1, 0), (-2, -1, 0), (-3, -1, 0), (-4, -1, 0)])
            receipt["levels"].append(level())
            self.assertEqual(level(), 1)
            for _boundary in range(16):
                advance_actual_turn(runtime)
                self.assertEqual(runtime.fight.phase, "active")
                if runtime.fight.current.id == -200:
                    break
            self.assertEqual(runtime.fight.current.id, -200)
            receipt["levels"].append(level())
            self.assertEqual(level(), 2)
            move([(-3, -1, 0), (-4, -1, 0)] * 3)
            receipt["levels"].append(level())
            self.assertEqual(level(), 5)
            receipt["status"] = "original_border_counter_earned"
        finally:
            output = (
                Path(__file__).resolve().parents[2]
                / ".runtime/ultimate-scenes-20261021/fulmoon-paid-native-border.json"
            )
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
