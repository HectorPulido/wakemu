"""Pay the actual fifteen-through-eighteen defensive paths and the native nineteen self ward."""
import json
from pathlib import Path
import sys
import struct
import time
import traceback
import unittest


class ContinueA11DefensiveFifteenToPaidWardNineteen(unittest.TestCase):
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
            + "-same-store-defensive-fifteen-eighteen-paid-ward-nineteen.json"
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

        # These endpoints were checked against the actual 235-area snapshot, including
        # the complete native lava cross and real faW/corpse occupancy.
        moves = {
            (16, owners[0]): (-41, 9, -4),
            (17, owners[0]): (-42, 9, -4),
            (17, owners[2]): (-45, 2, -4),
            (17, owners[4]): (-43, 4, -4),
            (18, owners[1]): (-45, 3, -4),
            (18, owners[0]): (-43, 9, -4),
            (18, owners[2]): (-46, 2, -4),
            (18, owners[4]): (-44, 4, -4),
        }
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
            self.assertEqual(
                (runtime.fight.native_table_turn, runtime.fight.turn_id), (15, 90)
            )
            self.assertEqual(runtime.fight.current.id, owners[1])
            self.assertGreaterEqual(staged_score(runtime.fight), 3000000)
            for _ in range(32):
                fight = runtime.fight
                snapshot = record()
                facts["boundaries"].append(snapshot)
                with journal.open("a") as stream:
                    stream.write(json.dumps(snapshot, default=str) + "\n")
                if fight.phase != "active":
                    facts.update(
                        status="native_terminal_during_defensive_window", final=snapshot
                    )
                    return
                identity = fight.current.id
                table = fight.native_table_turn
                self.assertLessEqual(table, 19)
                if identity in owners:
                    if table == 19 and identity == owners[0]:
                        action(
                            "paid_native_self_immunity_nineteen",
                            cast,
                            identity,
                            6982,
                            identity,
                        )
                        ward = [
                            (e.uid, e.reference, e.level, e.caster_id)
                            for e in runtime.fight.actors[identity].state_ledger.entries
                            if e.reference == 6361
                        ]
                        self.assertTrue(ward)
                        facts.update(
                            status="retained_after_paid_ward_nineteen_before_inner_lava_hole_move",
                            paid_ward19=ward,
                            final=record(),
                        )
                        return
                    destination = moves.get((table, identity))
                    if destination is not None:
                        action(
                            "paid_native_single_edge_defensive_band_move",
                            move,
                            identity,
                            destination,
                        )
                        self.assertEqual(
                            runtime.fight.actors[identity].position, destination
                        )
                    if identity == owners[0]:
                        actor = runtime.fight.actors[identity]
                        if (
                            not any(
                                e.reference == 6364 for e in actor.state_ledger.entries
                            )
                            and actor.ap >= 2
                            and actor.effect_stats[4] >= 1
                        ):
                            action(
                                "paid_eligible_self_peace_armor",
                                cast,
                                identity,
                                7009,
                                identity,
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
                                "paid_eligible_self_orbe",
                                cast,
                                identity,
                                6978,
                                identity,
                            )
                    action(
                        "native_owned_cardinal_facing_toward_boss", face_boss, identity
                    )
                # No offensive spell or out-of-range D/C/C is attempted after the earned threshold.
                action("end_actual_owned_turn", advance_actual_turn, runtime)
            self.fail("Finite paid ward-nineteen endpoint not reached")
        except BaseException as error:
            facts.update(
                status="failed_same_store_defensive_fifteen_to_nineteen",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                final=record(),
            )
            raise
        finally:
            facts["verification_after"] = verify()
            cp["defensive_fifteen_paid_ward_nineteen_receipt_path"] = str(output)
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ContinueA11DefensiveFifteenToPaidWardNineteen()])
