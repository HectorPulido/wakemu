"""Click an actual occupied cell of Rushu's native footprint and commit one cast."""
import importlib
import json
from pathlib import Path
import struct
import traceback
import unittest
from unittest.mock import patch


class RetainedFirstLegalDamage(unittest.TestCase):
    def runTest(self):
        recipe = importlib.import_module("test_rushu_native_party_phase_one")
        checkpoint = recipe.RUSHU_ACTUAL_CHECKPOINT
        recipe.verify_actual_checkpoint()
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_damage_handler import NativeDamageHandler
        from wakfu_server.boss_score_runtime import staged_score

        runtime = checkpoint["runtime"]
        current = runtime.fight
        owner = checkpoint["identities"][3]
        self.assertEqual(
            (current.native_table_turn, current.turn_id, current.current.id),
            (5, 31, owner),
        )
        actor, boss = current.actors[owner], current.actors[-200]
        body = sorted(
            footprint(boss.position, boss.physical_radius),
            key=lambda point: (
                abs(point[0] - actor.position[0]) + abs(point[1] - actor.position[1]),
                point,
            ),
        )
        target = (*body[0], boss.position[2])
        self.assertEqual(target, (-48, 8, -4))
        self.assertEqual(
            abs(target[0] - actor.position[0]) + abs(target[1] - actor.position[1]), 7
        )
        output = Path(checkpoint["receipt_path"]).with_name(
            Path(checkpoint["receipt_path"]).stem + "-first-legal-paid-damage.json"
        )
        facts = dict(
            status="pending",
            spell=6980,
            actor=owner,
            target_cell=target,
            actual_boss_footprint=body,
            boss_radius=boss.physical_radius,
            source_position=actor.position,
            boss_position=boss.position,
            before=dict(
                hp=boss.hp,
                armor=boss.effect_stats[97],
                score=staged_score(current),
                ap=actor.ap,
                mp=actor.mp,
                wp=actor.effect_stats[4],
                source_stats=dict(actor.effect_stats),
                target_stats=dict(boss.effect_stats),
            ),
            damage=[],
        )
        original = NativeDamageHandler.__call__

        def observe(handler, definition, values, invocation):
            selected = handler.fight.actors.get(invocation.target_id)
            before = None if selected is None else selected.hp
            result = original(handler, definition, values, invocation)
            facts["damage"].append(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    cell=invocation.cell,
                    level=invocation.level,
                    values=values,
                    result=result,
                    before_hp=before,
                    after_hp=None if selected is None else selected.hp,
                )
            )
            return result

        def visible(origin, target, current):
            return authoritative_visible(
                1332,
                origin,
                target,
                current,
                blocking_footprints={
                    a.id: footprint(a.position, a.physical_radius)
                    for a in current.actors.values()
                    if a.hp > 0
                },
            )

        try:
            uid = (
                6980 if 6980 in granted_spells(current, owner) else (owner << 32) | 6980
            )
            with patch.object(NativeDamageHandler, "__call__", observe):
                transaction = prepare_server_spell(
                    struct.pack(">qqiih", owner, uid, *target),
                    checkpoint["characters"][owner],
                    checkpoint["monsters"],
                    current,
                    actor.owner_id,
                    checkpoint["decks"][owner],
                    action_id=runtime.action_id + 1,
                    line_of_sight=visible,
                    critical=False,
                    **checkpoint["common"]
                )
                facts["costs"] = transaction.plan["costs"]
                commit_spell_transaction(
                    runtime, transaction, stats_serializer=checkpoint["serialize"]
                )
            after = runtime.fight
            facts.update(
                after=dict(
                    hp=after.actors[-200].hp,
                    armor=after.actors[-200].effect_stats[97],
                    score=staged_score(after),
                    ap=after.actors[owner].ap,
                    mp=after.actors[owner].mp,
                    wp=after.actors[owner].effect_stats[4],
                ),
                events=list(after.boss_score_events.values()),
            )
            self.assertTrue(
                any(row["target"] == -200 and row["result"] for row in facts["damage"])
            )
            self.assertLess(facts["after"]["hp"], facts["before"]["hp"])
            self.assertGreater(facts["after"]["score"], facts["before"]["score"])
            self.assertEqual(facts["before"]["ap"] - facts["after"]["ap"], 3)
            facts["status"] = "actual_owned_muralla_paid_damage_and_original_score"
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
    return unittest.TestSuite([RetainedFirstLegalDamage()])
