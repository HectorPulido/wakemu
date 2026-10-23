"""Continue the original A11 Store with paid positioning, healing and attacks."""
import importlib
import json
from pathlib import Path
import struct
import sys
import time
import traceback
import unittest


class ContinueA11ThroughFive(unittest.TestCase):
    def runTest(self):
        recipe = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = recipe.RUSHU_ACTUAL_CHECKPOINT
        verify = cp["authorized_service_transition_verifier"]
        before = verify()
        runtime = cp["runtime"]
        owners = cp["identities"]
        cast, cast_cell, move = cp["cast"], cp["cast_cell"], cp["move"]
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.boss_score_runtime import staged_score
        from wakfu_server.combat_spell_grant import granted_spells

        facts = dict(
            status="pending",
            prefix=cp.get("continuation_receipt_path"),
            boundaries=[],
            actions=[],
            same_store=True,
            verification_before=before,
        )
        output = Path(cp["receipt_path"]).with_name(
            Path(cp["receipt_path"]).stem + "-same-store-through-five.json"
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

        def state(identity, reference):
            return any(
                e.reference == reference
                for e in runtime.fight.actors[identity].state_ledger.entries
            )

        def walk_path(identity, path):
            for cell in path:
                action("paid_movement", move, identity, cell)

        iops = owners[1:5]
        arrivals = {
            owners[1]: (-47, 8, -4),
            owners[2]: (-51, 6, -4),
            owners[3]: (-50, 9, -4),
            owners[4]: (-48, 5, -4),
        }
        body_offsets = {
            owners[1]: (1, 1),
            owners[2]: (-1, -1),
            owners[3]: (-1, 1),
            owners[4]: (1, -1),
        }
        try:
            self.assertEqual(
                (runtime.fight.native_table_turn, runtime.fight.turn_id), (1, 7)
            )
            self.assertEqual(runtime.fight.current.id, owners[4])
            self.assertEqual(staged_score(runtime.fight), 12795)
            action("end_original_last_player_t1", advance_actual_turn, runtime)
            for boundary in range(40):
                while runtime.awaiting_ack is not None:
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                fight = runtime.fight
                snapshot = record()
                facts["boundaries"].append(snapshot)
                with journal.open("a") as stream:
                    stream.write(json.dumps(snapshot, default=str) + "\n")
                self.assertEqual(fight.phase, "active")
                self.assertTrue(
                    all(fight.actors[identity].hp > 0 for identity in owners)
                )
                table, identity = fight.native_table_turn, fight.current.id
                self.assertLessEqual(table, 5)
                if table == 5 and identity in owners:
                    boss = fight.actors[-200]
                    for reference in (7013, 7017, 7018, 7024):
                        self.assertTrue(
                            any(
                                e.reference == reference and e.level == 99
                                for e in boss.state_ledger.entries
                            )
                        )
                    active = [
                        (e.reference, e.level)
                        for e in boss.state_ledger.entries
                        if e.reference in (6998, *range(7011, 7026)) and e.level <= 10
                    ]
                    self.assertEqual(len(active), 4)
                    self.assertTrue(
                        any(
                            e.reference == 7092 and e.level == 4
                            for e in boss.state_ledger.entries
                        )
                    )
                    for owner, reference in zip(
                        (owners[0], owners[2], owners[3], owners[4], owners[5]),
                        (6998, 7025, 7015, 7021, 7020),
                    ):
                        self.assertTrue(
                            any(
                                e.reference == reference and e.level == 5
                                for e in fight.actors[owner].state_ledger.entries
                            )
                        )
                    facts.update(
                        status="same_a11_first_cycle_complete_four_foods_preserved",
                        final=record(),
                        next_four=active,
                    )
                    cp["phase_five_receipt_path"] = str(output)
                    return
                if identity in iops:
                    actor = fight.actors[identity]
                    if table == 2:
                        if identity == owners[2]:
                            walk_path(
                                identity, [(x, 5, -4) for x in range(-43, -48, -1)]
                            )
                            action(
                                "paid_jump",
                                cast_cell,
                                identity,
                                8404,
                                arrivals[identity],
                            )
                        elif identity == owners[3]:
                            walk_path(
                                identity,
                                [
                                    (-47, 12, -4),
                                    (-48, 12, -4),
                                    (-49, 12, -4),
                                    (-50, 12, -4),
                                    (-50, 11, -4),
                                    (-50, 10, -4),
                                    arrivals[identity],
                                ],
                            )
                        elif identity == owners[4]:
                            walk_path(
                                identity, [(x, 2, -4) for x in range(-42, -47, -1)]
                            )
                            action(
                                "paid_jump",
                                cast_cell,
                                identity,
                                8404,
                                arrivals[identity],
                            )
                    self.assertEqual(
                        runtime.fight.actors[identity].position, arrivals[identity]
                    )
                    boss = runtime.fight.actors[-200]
                    dx, dy = body_offsets[identity]
                    target = (
                        boss.position[0] + dx,
                        boss.position[1] + dy,
                        boss.position[2],
                    )
                    actor = runtime.fight.actors[identity]
                    if actor.mp == 0:
                        rotation = (4778, 4778, 4778, 4778, 4777)
                    elif actor.max_hp - actor.hp >= 2000:
                        # D establishes3444; two real C casts earn its heal branch.
                        rotation = (8402, 4775, 4775, 4777, 4778)
                    else:
                        rotation = (4778, 4776, 8402, 8402, 4777, 4778, 4778, 4776)
                    for spell in rotation:
                        current_actor = runtime.fight.actors[identity]
                        minimum_ap = {4778: 2, 4776: 1, 4775: 3, 4777: 4, 8402: 0}[
                            spell
                        ]
                        if current_actor.ap < minimum_ap or (
                            spell == 8402 and current_actor.mp < 1
                        ):
                            continue
                        action("paid_direct_attack", cast_cell, identity, spell, target)
                elif identity == owners[0]:
                    if not state(identity, 6364):
                        action("paid_peace_armor", cast, identity, 7009, identity)
                    if not state(identity, 6334) and not state(identity, 6357):
                        action("paid_self_orbe", cast, identity, 6978, identity)
                    if table == 2:
                        walk_path(
                            identity,
                            [
                                (-44, 10, -4),
                                (-44, 9, -4),
                                (-44, 8, -4),
                                (-43, 8, -4),
                                (-42, 8, -4),
                                (-41, 8, -4),
                            ],
                        )
                    elif table == 3:
                        walk_path(identity, [(-40, 8, -4), (-39, 8, -4)])
                elif identity == owners[5]:
                    if table == 2:
                        walk_path(
                            identity,
                            [
                                (-39, 14, -4),
                                (-40, 14, -4),
                                (-41, 14, -4),
                                (-41, 13, -4),
                                (-41, 12, -4),
                                (-41, 11, -4),
                            ],
                        )
                    elif table == 3:
                        walk_path(identity, [(-42, 11, -4)])
                    else:
                        walk_path(
                            identity, [(-40, 12, -4), (-41, 12, -4), (-42, 12, -4)]
                        )
                    for spell in (779, 779, 1533, 1533):
                        patient = runtime.fight.actors[owners[1]]
                        if patient.hp == patient.max_hp:
                            break
                        action("paid_consumed_heal", cast, identity, spell, owners[1])
                    if table == 3:
                        walk_path(
                            identity,
                            [
                                (-42, 12, -4),
                                (-41, 12, -4),
                                (-40, 12, -4),
                                (-39, 12, -4),
                            ],
                        )
                    elif table >= 4:
                        walk_path(
                            identity, [(-41, 12, -4), (-40, 12, -4), (-39, 12, -4)]
                        )
                action("end_actual_owned_turn", advance_actual_turn, runtime)
            self.fail(
                "Native first-cycle transition not reached within the bounded real timeline"
            )
        except BaseException as error:
            facts.update(
                status="failed_same_store_continuation",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                final=record(),
            )
            raise
        finally:
            facts["verification_after"] = verify()
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    from _qualification_rushu_dd230_eleven_slot_opening import SerialOpeningSuite

    return SerialOpeningSuite([ContinueA11ThroughFive()])
