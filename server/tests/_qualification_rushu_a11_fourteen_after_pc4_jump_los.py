"""Continue after a genuine blocked Jump using the actual clear alternative ray."""
import json
from pathlib import Path
import sys
import time
import traceback
import unittest


class ContinueA11FourteenAfterActualJumpLos(unittest.TestCase):
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
            + "-same-store-clear-pc4-jump-and-native-fifteen.json"
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

        offsets = {
            owners[1]: (1, -1),
            owners[2]: (1, -1),
            owners[3]: (1, 0),
            owners[4]: (0, -1),
        }
        relocation = {
            owners[1]: ((-44, 4, -4), (-44, 3, -4)),
            owners[3]: ((-46, 4, -4), (-43, 2, -4)),
            owners[2]: ((-45, 3, -4), (-44, 2, -4)),
            owners[4]: ((-45, 4, -4), (-43, 3, -4)),
        }
        planned = {identity: end for identity, (_, end) in relocation.items()}
        planned[owners[0]] = (-40, 9, -4)

        def paid_damage_before_relocation(identity):
            actor = runtime.fight.actors[identity]
            healing = actor.max_hp - actor.hp >= 2500
            if healing:
                rotation = (8402, 4775, 4775, 4778)
            elif staged_score(runtime.fight) >= 3000000:
                rotation = ()
            else:
                rotation = (4778, 4776, 8402, 8402, 8403, 4777, 4776)
            boss = runtime.fight.actors[-200]
            dx, dy = offsets[identity]
            target = (boss.position[0] + dx, boss.position[1] + dy, boss.position[2])
            for index, spell in enumerate(rotation):
                if staged_score(runtime.fight) >= 3000000 and not (
                    healing and index < 3
                ):
                    break
                actor = runtime.fight.actors[identity]
                cost = {4778: 2, 4776: 1, 8402: 0, 8403: 0, 4777: 4, 4775: 3}[spell]
                if (
                    actor.ap < cost + 4
                    or (spell == 8402 and actor.mp < 1)
                    or (spell == 8403 and actor.effect_stats[4] < 1)
                ):
                    continue
                action(
                    "paid_melee_damage_or_required_dcc_reserving_jump_ap",
                    cast_cell,
                    identity,
                    spell,
                    target,
                )

        def verify_final_geometry():
            fight = runtime.fight
            centers = [fight.actors[i] for i in owners]
            for identity, target in planned.items():
                actor = fight.actors[identity]
                if actor.hp <= 0:
                    continue
                self.assertEqual(actor.position, target)
                for center in centers:
                    if center.id == identity:
                        continue
                    distance = abs(actor.position[0] - center.position[0]) + abs(
                        actor.position[1] - center.position[1]
                    )
                    self.assertFalse(5 <= distance <= 8)
                for row in fight.native_effect_areas.values():
                    if row["reference"] in (1650, *range(1652, 1667)):
                        self.assertGreaterEqual(
                            abs(actor.position[0] - row["cell"][0])
                            + abs(actor.position[1] - row["cell"][1]),
                            4,
                        )

        try:
            self.assertEqual(
                (runtime.fight.native_table_turn, runtime.fight.turn_id), (14, 85)
            )
            self.assertEqual(runtime.fight.current.id, owners[3])
            self.assertEqual(
                (
                    runtime.fight.current.ap,
                    runtime.fight.current.mp,
                    runtime.fight.current.effect_stats[4],
                ),
                (6, 6, 5),
            )
            self.assertGreaterEqual(staged_score(runtime.fight), 3000000)
            for _ in range(8):
                fight = runtime.fight
                snapshot = record()
                facts["boundaries"].append(snapshot)
                with journal.open("a") as stream:
                    stream.write(json.dumps(snapshot, default=str) + "\n")
                if fight.phase != "active":
                    facts.update(
                        status="native_terminal_during_paid_phase_fifteen_preparation",
                        final=snapshot,
                    )
                    return
                identity = fight.current.id
                table = fight.native_table_turn
                if table == 15 and identity in owners:
                    facts.update(
                        status="observed_native_phase_fifteen_after_paid_score_and_relocation",
                        earned_three_million=staged_score(fight) >= 3000000,
                        final=snapshot,
                    )
                    return
                self.assertLessEqual(table, 15)
                if table == 14 and identity in relocation:
                    # Damage and DCC happen from the already-admitted melee position.
                    # The first movement is Jump, preserving four AP and avoiding a tackle exit.
                    paid_damage_before_relocation(identity)
                    landing, destination = relocation[identity]
                    action(
                        "paid_first_movement_native_jump_after_melee_actions",
                        cast_cell,
                        identity,
                        8404,
                        landing,
                    )
                    action(
                        "paid_native_post_jump_destination", move, identity, destination
                    )
                    self.assertEqual(
                        runtime.fight.actors[identity].position, destination
                    )
                elif table == 14 and identity == owners[0]:
                    action(
                        "paid_self_immunity_before_relocation_and_boss_fifteen",
                        cast,
                        identity,
                        6982,
                        identity,
                    )
                    action(
                        "paid_corpse_aware_feca_fourteen_destination",
                        move,
                        identity,
                        planned[identity],
                    )
                    self.assertEqual(
                        runtime.fight.actors[identity].position, planned[identity]
                    )
                    actor = runtime.fight.actors[identity]
                    if (
                        not any(e.reference == 6364 for e in actor.state_ledger.entries)
                        and actor.ap >= 2
                        and actor.effect_stats[4] >= 1
                    ):
                        action(
                            "paid_eligible_peace_armor", cast, identity, 7009, identity
                        )
                    actor = runtime.fight.actors[identity]
                    if (
                        not any(
                            e.reference in (6334, 6357)
                            for e in actor.state_ledger.entries
                        )
                        and actor.ap >= 3
                    ):
                        action(
                            "paid_eligible_self_orbe", cast, identity, 6978, identity
                        )
                if table == 14 and identity == owners[4]:
                    verify_final_geometry()
                action("end_actual_owned_turn", advance_actual_turn, runtime)
            self.fail("Finite native phase-fifteen endpoint not reached")
        except BaseException as error:
            facts.update(
                status="failed_same_store_paid_fourteen_preparation",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                final=record(),
            )
            raise
        finally:
            facts["verification_after"] = verify()
            cp["clear_pc4_jump_native_fifteen_receipt_path"] = str(output)
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ContinueA11FourteenAfterActualJumpLos()])
