"""Prepare a finite same-Store continuation with native Iop self-healing."""
import json
from pathlib import Path
import sys
import time
import traceback
import unittest


class ContinueA11FiveSurvivorsToNine(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        runtime = cp["runtime"]
        verify = cp["authorized_service_transition_verifier"]
        owners = cp["identities"]
        cast, cast_cell = cp["cast"], cp["cast_cell"]
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.boss_score_runtime import staged_score

        facts = dict(
            status="pending",
            same_store=True,
            prefix=cp.get("end_five_after_ko_receipt_path"),
            verification_before=verify(),
            boundaries=[],
            actions=[],
        )
        output = Path(cp["receipt_path"]).with_name(
            Path(cp["receipt_path"]).stem
            + "-same-store-five-survivors-through-nine.json"
        )
        journal = output.with_suffix(".boundaries.jsonl")
        action_journal = output.with_suffix(".actions.jsonl")
        started = time.monotonic()

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
                        stats=dict(fight.actors[identity].effect_stats),
                        states=[
                            (e.reference, e.level, e.caster_id)
                            for e in fight.actors[identity].state_ledger.entries
                        ],
                    )
                    for identity in owners
                },
                elapsed_seconds=round(time.monotonic() - started, 3),
            )

        def action(label, fn, *args):
            row = dict(action=label, args=args, before=record())
            try:
                return fn(*args)
            finally:
                row["after"] = record()
                facts["actions"].append(row)
                with action_journal.open("a") as stream:
                    stream.write(json.dumps(row, default=str) + "\n")

        offsets = {
            owners[1]: (1, -1),
            owners[2]: (-1, -1),
            owners[3]: (1, 1),
            owners[4]: (-1, 1),
        }
        try:
            self.assertEqual(
                (runtime.fight.native_table_turn, runtime.fight.turn_id), (5, 30)
            )
            self.assertEqual(runtime.fight.current.id, owners[1])
            self.assertEqual(staged_score(runtime.fight), 293430)
            for _ in range(30):
                fight = runtime.fight
                row = record()
                facts["boundaries"].append(row)
                with journal.open("a") as stream:
                    stream.write(json.dumps(row, default=str) + "\n")
                if fight.phase != "active":
                    facts.update(status="native_terminal_before_nine", final=row)
                    return
                if fight.native_table_turn == 9 and fight.current.id in owners:
                    facts.update(
                        status="retained_before_paid_table_nine_actions", final=row
                    )
                    return
                self.assertLessEqual(fight.native_table_turn, 9)
                identity = fight.current.id
                if identity in offsets:
                    actor = fight.actors[identity]
                    boss = fight.actors[-200]
                    dx, dy = offsets[identity]
                    target = (
                        boss.position[0] + dx,
                        boss.position[1] + dy,
                        boss.position[2],
                    )
                    # This exact D/C/C route has already produced a paid native heal.
                    rotation = (
                        (8402, 4775, 4775, 4777, 4778)
                        if actor.max_hp - actor.hp >= 2000
                        else (4778, 4776, 8402, 8402, 4777, 4778, 4778, 4776)
                    )
                    for spell in rotation:
                        actor = runtime.fight.actors[identity]
                        needed = {8402: 0, 4775: 3, 4777: 4, 4778: 2, 4776: 1}[spell]
                        if actor.ap < needed or (spell == 8402 and actor.mp < 1):
                            continue
                        action(
                            "paid_owned_damage_or_native_self_heal",
                            cast_cell,
                            identity,
                            spell,
                            target,
                        )
                elif identity == owners[0]:
                    actor = fight.actors[identity]
                    states = {e.reference for e in actor.state_ledger.entries}
                    if (
                        6364 not in states
                        and actor.ap >= 2
                        and actor.effect_stats[4] >= 1
                    ):
                        action("paid_peace_armor", cast, identity, 7009, identity)
                    actor = runtime.fight.actors[identity]
                    states = {e.reference for e in actor.state_ledger.entries}
                    if not states.intersection((6334, 6357)) and actor.ap >= 3:
                        action(
                            "paid_eligible_self_orbe", cast, identity, 6978, identity
                        )
                action("end_actual_owned_turn", advance_actual_turn, runtime)
            self.fail("Finite table-nine endpoint not reached")
        except BaseException as error:
            facts.update(
                status="failed_same_store_five_survivor_continuation",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                final=record(),
            )
            raise
        finally:
            facts["verification_after"] = verify()
            cp["five_survivor_continuation_receipt_path"] = str(output)
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ContinueA11FiveSurvivorsToNine()])
