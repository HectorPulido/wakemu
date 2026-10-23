"""Observe one genuine retained Rushu END5 after a party member's KO."""
import json
from pathlib import Path
import sys
import traceback
import unittest


class ObserveA11EndFiveAfterKo(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        runtime = cp["runtime"]
        verify = cp["authorized_service_transition_verifier"]
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.boss_score_runtime import staged_score

        def snapshot():
            fight = runtime.fight
            return dict(
                table=fight.native_table_turn,
                turn=fight.turn_id,
                phase=fight.phase,
                current=None if fight.current is None else fight.current.id,
                score=staged_score(fight),
                actors={
                    identity: dict(
                        hp=actor.hp,
                        max_hp=actor.max_hp,
                        position=actor.position,
                        ap=actor.ap,
                        mp=actor.mp,
                        stats=dict(actor.effect_stats),
                        states=[
                            (entry.reference, entry.level, entry.caster_id)
                            for entry in actor.state_ledger.entries
                        ],
                    )
                    for identity, actor in fight.actors.items()
                },
                areas=[
                    dict(
                        uid=row.get("uid"),
                        reference=row.get("reference"),
                        owner_id=row.get("owner_id"),
                        cell=row.get("cell"),
                        effect_reference=row.get("effect_reference"),
                        states=[
                            (entry.reference, entry.level, entry.caster_id)
                            for entry in row["state_ledger"].entries
                        ]
                        if row.get("state_ledger") is not None
                        else [],
                    )
                    for row in getattr(fight, "native_effect_areas", {}).values()
                ],
            )

        output = Path(cp["receipt_path"]).with_name(
            Path(cp["receipt_path"]).stem + "-same-store-native-end5-after-eni-ko.json"
        )
        facts = dict(
            status="pending",
            same_store=True,
            prefix=cp.get("continuation_receipt_path"),
            verification_before=verify(),
        )
        try:
            facts["before"] = snapshot()
            self.assertEqual(
                (runtime.fight.native_table_turn, runtime.fight.turn_id), (5, 29)
            )
            self.assertEqual(runtime.fight.current.id, -200)
            self.assertEqual(runtime.fight.actors[cp["identities"][5]].hp, 0)
            # No player action, revival or admission: finish exactly this owned NPC turn.
            advance_actual_turn(runtime)
            facts["after"] = snapshot()
            facts["status"] = "observed_one_native_end5_after_eni_ko"
            cp["end_five_after_ko_receipt_path"] = str(output)
        except BaseException as error:
            facts.update(
                status="failed_native_end5_observation",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                after=snapshot(),
            )
            raise
        finally:
            facts["verification_after"] = verify()
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ObserveA11EndFiveAfterKo()])
