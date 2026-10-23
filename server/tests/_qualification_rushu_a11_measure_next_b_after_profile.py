"""Measure one next earned B cast after the profiled big, without advancing the turn."""
import json
from pathlib import Path
import sys
import time
import traceback
import unittest


class MeasureA11NextNativeB(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        runtime = cp["runtime"]
        verify = cp["authorized_service_transition_verifier"]
        owners = cp["identities"]
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.boss_score_runtime import staged_score

        output = Path(cp["receipt_path"]).with_name(
            Path(cp["receipt_path"]).stem
            + "-same-store-one-paid-b-after-profiled-big.json"
        )
        started = time.monotonic()
        facts = dict(
            status="pending",
            same_store=True,
            verification_before=verify(),
            prefix=cp.get("profiled_big_receipt_path"),
        )

        def record():
            fight = runtime.fight
            return dict(
                table=fight.native_table_turn,
                turn=fight.turn_id,
                current=None if fight.current is None else fight.current.id,
                score=staged_score(fight),
                boss_hp=fight.actors[-200].hp,
                boss_position=fight.actors[-200].position,
                boss_stats=dict(fight.actors[-200].effect_stats),
                boss_states=[
                    (e.reference, e.level, e.caster_id)
                    for e in fight.actors[-200].state_ledger.entries
                ],
                players={
                    identity: dict(
                        hp=fight.actors[identity].hp,
                        max_hp=fight.actors[identity].max_hp,
                        ap=fight.actors[identity].ap,
                        mp=fight.actors[identity].mp,
                        wp=fight.actors[identity].effect_stats[4],
                        position=fight.actors[identity].position,
                        direction=fight.actors[identity].direction,
                        stats=dict(fight.actors[identity].effect_stats),
                        states=[
                            (e.reference, e.level, e.caster_id)
                            for e in fight.actors[identity].state_ledger.entries
                        ],
                    )
                    for identity in owners
                },
                areas=[
                    dict(
                        uid=r["uid"],
                        reference=r["reference"],
                        cell=r["cell"],
                        owner_id=r["owner_id"],
                        effect_reference=r.get("effect_reference"),
                        states=[
                            (e.reference, e.level, e.caster_id)
                            for e in r["state_ledger"].entries
                        ]
                        if r.get("state_ledger") is not None
                        else [],
                    )
                    for r in getattr(fight, "native_effect_areas", {}).values()
                ],
                elapsed_seconds=round(time.monotonic() - started, 3),
            )

        try:
            self.assertEqual(
                (runtime.fight.native_table_turn, runtime.fight.turn_id), (12, 72)
            )
            self.assertEqual(runtime.fight.current.id, owners[1])
            self.assertEqual(
                (
                    runtime.fight.current.ap,
                    runtime.fight.current.mp,
                    runtime.fight.current.effect_stats[4],
                ),
                (5, 7, 3),
            )
            facts["before"] = record()
            action_started = time.monotonic()
            cp["cast_cell"](owners[1], 4778, (-48, 6, -4))
            facts["action_seconds"] = round(time.monotonic() - action_started, 6)
            facts["after"] = record()
            self.assertEqual(runtime.fight.native_table_turn, 12)
            self.assertEqual(runtime.fight.current.id, owners[1])
            self.assertEqual(runtime.fight.current.ap, 3)
            facts["incoming_resistance_carriers"] = {
                identity: [
                    (e.reference, e.level, e.caster_id)
                    for e in runtime.fight.actors[identity].state_ledger.entries
                    if e.reference == 7113
                ]
                for identity in owners
            }
            facts["recent_events"] = list(getattr(runtime.fight, "events", ()))[-128:]
            facts["status"] = "paid_one_next_b_after_profiled_big"
        except BaseException as error:
            facts.update(
                status="failed_one_next_b_measurement",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                after=record(),
            )
            raise
        finally:
            facts["verification_after"] = verify()
            cp["one_next_b_after_profile_receipt_path"] = str(output)
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([MeasureA11NextNativeB()])
