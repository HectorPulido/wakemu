"""Continue the original paid ward endpoint through native twenty and twenty-one."""
import json
from pathlib import Path
import sys
import struct
import time
import traceback
import unittest


class ContinueA11PaidWardNineteenToNativeTerminal(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        runtime = cp["runtime"]
        verify = cp["authorized_service_transition_verifier"]
        owners = cp["identities"]
        cast, cast_cell, move = cp["cast"], cp["cast_cell"], cp["move"]
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.boss_score_runtime import staged_score

        facts = dict(
            status="pending",
            same_store=True,
            actions=[],
            boundaries=[],
            prefix=cp.get("first_native_start12_receipt_path"),
            verification_before=verify(),
        )
        output = Path(cp["receipt_path"]).with_name(
            Path(cp["receipt_path"]).stem
            + "-same-store-paid-ward-nineteen-through-native-twentyone.json"
        )
        journal = output.with_suffix(".boundaries.jsonl")
        action_journal = output.with_suffix(".actions.jsonl")
        started = time.monotonic()

        def record():
            fight = runtime.fight
            return dict(
                table=fight.native_table_turn,
                turn=fight.turn_id,
                phase=fight.phase,
                winner=fight.winner,
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

        def action(label, fn, *args):
            row = dict(action=label, args=args, before=record())
            action_started = time.monotonic()
            try:
                return fn(*args)
            finally:
                row["action_seconds"] = round(time.monotonic() - action_started, 6)
                row["after"] = record()
                facts["actions"].append(row)
                with action_journal.open("a") as stream:
                    stream.write(json.dumps(row, default=str) + "\n")

        from wakfu_server.combat_orientation import apply as apply_orientation

        def face_boss(identity):
            actor = runtime.fight.actors[identity]
            boss = runtime.fight.actors[-200]
            dx = boss.position[0] - actor.position[0]
            dy = boss.position[1] - actor.position[1]
            direction = (
                (1 if dx > 0 else 5) if abs(dx) >= abs(dy) else (3 if dy > 0 else 7)
            )
            return apply_orientation(
                runtime, actor.owner_id, struct.pack(">qB", identity, direction)
            )

        try:
            self.assertEqual(runtime.fight.native_table_turn, 19)
            self.assertEqual(runtime.fight.current.id, owners[0])
            self.assertEqual(runtime.fight.actors[owners[0]].position, (-43, 9, -4))
            self.assertGreater(runtime.fight.actors[owners[0]].hp, 0)
            self.assertTrue(
                any(
                    e.reference == 6361 and e.caster_id == owners[0]
                    for e in runtime.fight.actors[owners[0]].state_ledger.entries
                )
            )
            self.assertGreaterEqual(staged_score(runtime.fight), 3000000)
            facts[
                "existing_end20_lava_forecast"
            ] = ".runtime/rushu-phase-review-20261021/rushu-end20-lava-conservative-safe-cells.json"
            facts["feca_stays_in_existing_and_conservative_future_safe_cell"] = (
                -43,
                9,
                -4,
            )
            for _ in range(16):
                fight = runtime.fight
                snapshot = record()
                facts["boundaries"].append(snapshot)
                with journal.open("a") as stream:
                    stream.write(json.dumps(snapshot, default=str) + "\n")
                if fight.phase != "active":
                    facts.update(
                        status="observed_native_terminal_after_original_twentyone_callbacks",
                        genuine_three_million_player_victory=(
                            fight.phase == "finished"
                            and fight.winner == 1
                            and staged_score(fight) >= 3000000
                            and fight.actors[-200].hp <= 0
                        ),
                        final=snapshot,
                    )
                    return
                self.assertLessEqual(fight.native_table_turn, 21)
                identity = fight.current.id
                if identity in owners:
                    # Keep the proven safe cell; orientation is the real zero-cost UI request.
                    action(
                        "native_owned_cardinal_facing_toward_boss", face_boss, identity
                    )
                if (
                    fight.native_table_turn == 20
                    and identity == -200
                    and not facts.get("profiled_native_end20")
                ):
                    from _qualification_rushu_profile_native_end_twenty import (
                        profiled_advance,
                    )

                    def profile_one_end20():
                        return profiled_advance(
                            cp, advance_actual_turn, output.with_suffix("")
                        )

                    action("one_profiled_native_public_end20_call", profile_one_end20)
                    facts["profiled_native_end20"] = True
                else:
                    action("end_actual_owned_turn", advance_actual_turn, runtime)
            facts.update(
                status="retained_after_bounded_twentyone_without_native_terminal",
                final=record(),
            )
        except BaseException as error:
            facts.update(
                status="failed_same_store_native_twentyone_continuation",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                final=record(),
            )
            raise
        finally:
            facts["verification_after"] = verify()
            cp["paid_ward_nineteen_native_twentyone_receipt_path"] = str(output)
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ContinueA11PaidWardNineteenToNativeTerminal()])
