"""Continue the original A11 Store with paid positioning, healing and attacks."""
import importlib
import json
from pathlib import Path
import struct
import sys
import time
import traceback
import unittest


class ContinueA11NativeJumpLos(unittest.TestCase):
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
            Path(cp["receipt_path"]).stem
            + "-same-store-through-five-native-jump-los.json"
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
            owners[1]: (-47, 6, -4),
            owners[2]: (-50, 5, -4),
            owners[3]: (-48, 9, -4),
            owners[4]: (-51, 8, -4),
        }
        body_offsets = {
            owners[1]: (1, -1),
            owners[2]: (-1, -1),
            owners[3]: (1, 1),
            owners[4]: (-1, 1),
        }

        def contact_path(identity, path):
            # One native path preserves the positive-radius tackle-once rule.
            from wakfu_server.combat_tackle_movement import movement_tackle_cost
            from wakfu_server.combat_movement_runtime import apply_client
            from wakfu_server.combat_area_transaction import prepare_area_movement

            actor = runtime.fight.actors[identity]
            ap_before, mp_before = actor.ap, actor.mp
            ap_loss, mp_loss = movement_tackle_cost(runtime.fight, actor, path)
            apply_client(
                runtime,
                actor.owner_id,
                struct.pack(">q", identity)
                + b"".join(struct.pack(">iih", *cell) for cell in path),
                lambda selected: cp["serialize"](selected, runtime.fight),
                runtime_stats_serializer=cp["serialize"],
                area_provider=lambda candidate, **kwargs: prepare_area_movement(
                    cp["characters"][identity],
                    cp["monsters"],
                    candidate,
                    cp["decks"][identity],
                    **cp["common"],
                    **kwargs
                ),
            )
            self.assertEqual(runtime.fight.actors[identity].position, path[-1])
            self.assertEqual(ap_before - runtime.fight.actors[identity].ap, ap_loss)
            self.assertEqual(
                mp_before - runtime.fight.actors[identity].mp, len(path) + mp_loss
            )

        try:
            self.assertEqual(
                (runtime.fight.native_table_turn, runtime.fight.turn_id), (2, 13)
            )
            self.assertEqual(runtime.fight.current.id, owners[2])
            self.assertEqual(runtime.fight.actors[owners[2]].position, (-47, 5, -4))
            self.assertEqual(
                (
                    runtime.fight.actors[owners[2]].ap,
                    runtime.fight.actors[owners[2]].mp,
                ),
                (12, 2),
            )
            self.assertEqual(staged_score(runtime.fight), 37711)
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
                            # The five approach steps already committed before the rejected Jump.
                            action(
                                "paid_los_legal_jump",
                                cast_cell,
                                identity,
                                8404,
                                arrivals[identity],
                            )
                        elif identity == owners[4]:
                            walk_path(
                                identity,
                                [(x, 2, -4) for x in range(-42, -48, -1)]
                                + [(-47, 3, -4)],
                            )
                            # Keep Jump available for the next real turn. This temporary
                            # outer point receives Explosion but has no Saccage neighbours.
                            action(
                                "end_temporary_outer_turn", advance_actual_turn, runtime
                            )
                            continue
                    elif table == 3:
                        if identity == owners[1]:
                            action(
                                "paid_parallel_jump",
                                cast_cell,
                                identity,
                                8404,
                                arrivals[identity],
                            )
                        elif identity == owners[3]:
                            action(
                                "paid_single_path_with_tackle",
                                contact_path,
                                identity,
                                [(-49, 9, -4), arrivals[identity]],
                            )
                        elif identity == owners[4]:
                            walk_path(
                                identity, [(x, 3, -4) for x in range(-48, -52, -1)]
                            )
                            action(
                                "paid_western_parallel_jump",
                                cast_cell,
                                identity,
                                8404,
                                arrivals[identity],
                            )
                    if table >= 3 or identity == owners[2]:
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
                        walk_path(
                            identity,
                            [(-40, 8, -4), (-39, 8, -4), (-38, 8, -4), (-38, 7, -4)],
                        )
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
                    elif table >= 4:
                        walk_path(
                            identity, [(-40, 10, -4), (-41, 10, -4), (-42, 10, -4)]
                        )
                    # Three casts per patient, no overall1533 cap. Spend the ten
                    # genuine AP across reachable injured allies rather than using779fixed5.
                    counts = {}
                    for _ in range(5):
                        healer = runtime.fight.actors[identity]
                        candidates = [
                            p
                            for p in runtime.fight.actors.values()
                            if p.id in owners
                            and p.id != identity
                            and 0 < p.hp < p.max_hp
                            and counts.get(p.id, 0) < 3
                            and 1
                            <= abs(p.position[0] - healer.position[0])
                            + abs(p.position[1] - healer.position[1])
                            <= 10
                        ]
                        if not candidates or healer.ap < 2:
                            break
                        patient = min(candidates, key=lambda p: (p.hp / p.max_hp, p.id))
                        action("paid_consumed_heal", cast, identity, 1533, patient.id)
                        counts[patient.id] = counts.get(patient.id, 0) + 1
                    if table == 3:
                        walk_path(
                            identity,
                            [
                                (-41, 11, -4),
                                (-40, 11, -4),
                                (-39, 11, -4),
                                (-39, 10, -4),
                            ],
                        )
                    elif table >= 4:
                        walk_path(
                            identity, [(-41, 10, -4), (-40, 10, -4), (-39, 10, -4)]
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

    return SerialOpeningSuite([ContinueA11NativeJumpLos()])
