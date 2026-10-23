"""Continue only the rejected first-round Jump destination on the same DD encounter."""
import importlib
import json
from pathlib import Path
import traceback
import unittest
from unittest.mock import patch


class ContinueOpeningJump(unittest.TestCase):
    def runTest(self):
        recipe = importlib.import_module("test_rushu_dd230_native_opening")
        checkpoint = recipe.RUSHU_ACTUAL_CHECKPOINT
        recipe.verify_actual_checkpoint()
        from wakfu_server.combat_damage_handler import NativeDamageHandler
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.boss_score_runtime import staged_score

        runtime = checkpoint["runtime"]
        identity = checkpoint["identities"][1]
        current = runtime.fight
        self.assertEqual((current.native_table_turn, current.current.id), (1, identity))
        self.assertEqual(current.actors[identity].position, (-44, 11, -4))
        self.assertEqual(checkpoint["receipt"]["pending_cast"]["spell"], 8404)
        facts = dict(
            status="pending_same_endpoint_jump",
            prefix_receipt=checkpoint["receipt_path"],
            before=dict(
                position=current.actors[identity].position,
                ap=current.actors[identity].ap,
                mp=current.actors[identity].mp,
                wp=current.actors[identity].effect_stats[4],
                source_stats=dict(current.actors[identity].effect_stats),
                target_stats=dict(current.actors[-200].effect_stats),
                hp=current.actors[-200].hp,
                score=staged_score(current),
            ),
            damage=[],
        )
        output = Path(checkpoint["receipt_path"]).with_name(
            Path(checkpoint["receipt_path"]).stem
            + "-same-endpoint-legal-jump-paid-damage.json"
        )
        original = NativeDamageHandler.__call__

        def observe(handler, definition, values, invocation):
            actor = handler.fight.actors.get(invocation.target_id)
            before = None if actor is None else actor.hp
            result = original(handler, definition, values, invocation)
            facts["damage"].append(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    cell=invocation.cell,
                    values=values,
                    result=result,
                    hp_before=before,
                    hp_after=None if actor is None else actor.hp,
                )
            )
            return result

        try:
            destination = (-47, 9, -4)
            self.assertIn(destination, current.walkable)
            self.assertFalse(
                any(
                    actor.hp > 0
                    and destination[:2]
                    in footprint(actor.position, actor.physical_radius)
                    for actor in current.actors.values()
                )
            )
            with patch.object(NativeDamageHandler, "__call__", observe):
                checkpoint["cast_cell"](identity, 8404, destination)
                self.assertEqual(runtime.fight.actors[identity].position, destination)
                boss = runtime.fight.actors[-200]
                target = min(
                    footprint(boss.position, boss.physical_radius),
                    key=lambda cell: (
                        abs(cell[0] - destination[0]) + abs(cell[1] - destination[1]),
                        cell,
                    ),
                )
                checkpoint["cast_cell"](identity, 4775, (*target, boss.position[2]))
            current = runtime.fight
            facts.update(
                status="actual_native230_iop_paid_jump_and_first_damage",
                after=dict(
                    position=current.actors[identity].position,
                    ap=current.actors[identity].ap,
                    mp=current.actors[identity].mp,
                    wp=current.actors[identity].effect_stats[4],
                    source_stats=dict(current.actors[identity].effect_stats),
                    target_stats=dict(current.actors[-200].effect_stats),
                    hp=current.actors[-200].hp,
                    score=staged_score(current),
                ),
                events=list(current.boss_score_events.values()),
            )
            self.assertLess(facts["after"]["hp"], facts["before"]["hp"])
            self.assertGreater(facts["after"]["score"], facts["before"]["score"])
        except Exception as error:
            facts.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                native_casting_trace=getattr(error, "native_casting_trace", None),
                native_casting_context=getattr(error, "native_casting_context", None),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            facts[
                "loaded_implementation_attestation"
            ] = recipe.verify_actual_checkpoint()
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")
            checkpoint["last_damage_receipt"] = str(output)


def qualify():
    return unittest.TestSuite([ContinueOpeningJump()])
