"""Pay four genuine grade-nine DROPs and prepare the native phase-ten window."""
import json
from pathlib import Path
import struct
import sys
import time
import traceback
import unittest


class ContinueA11FeedsAfterReturnedConsumption(unittest.TestCase):
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
            drops=[],
            verification_before=verify(),
            prefix=cp.get("five_survivor_continuation_receipt_path"),
        )
        output = Path(cp["receipt_path"]).with_name(
            Path(cp["receipt_path"]).stem
            + "-same-store-four-live-feeds-after-returned-consumption-fix.json"
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
            try:
                return fn(*args)
            finally:
                row["after"] = record()
                facts["actions"].append(row)
                with action_journal.open("a") as stream:
                    stream.write(json.dumps(row, default=str) + "\n")

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

        feed = {
            owners[0]: (6998, 1650, (-40, 7, -4)),
            owners[2]: (7025, 1666, (-50, 2, -4)),
            owners[3]: (7015, 1656, (-49, 10, -4)),
            owners[4]: (7021, 1662, (-52, 7, -4)),
        }
        offsets = {
            owners[1]: (1, -1),
            owners[2]: (1, -1),
            owners[3]: (1, 0),
            owners[4]: (0, -1),
        }
        ends = {
            owners[1]: (-47, 6, -4),
            owners[2]: (-48, 5, -4),
            owners[3]: (-47, 7, -4),
            owners[4]: (-49, 5, -4),
            owners[0]: (-36, 8, -4),
        }

        def drop(identity):
            reference, area, cell = feed[identity]
            actor = runtime.fight.actors[identity]
            self.assertTrue(
                any(
                    e.reference == reference and e.level == 9
                    for e in actor.state_ledger.entries
                )
            )
            previous = set(runtime.fight.native_effect_areas)
            action("paid_original_drop_to_free_cell", cast_cell, identity, 7271, cell)
            created = [
                row
                for uid, row in runtime.fight.native_effect_areas.items()
                if uid not in previous
                and row["reference"] == area
                and tuple(row["cell"]) == cell
            ]
            self.assertEqual(len(created), 1)
            row = created[0]
            self.assertEqual(row["owner_id"], identity)
            self.assertTrue(
                any(
                    e.reference == 7001 and e.level == 9
                    for e in row["state_ledger"].entries
                )
            )
            facts["drops"].append(
                dict(
                    owner=identity,
                    reference=reference,
                    area=area,
                    uid=row["uid"],
                    cell=cell,
                    level=9,
                )
            )
            self.assertFalse(
                any(
                    e.reference == 6999
                    for e in runtime.fight.actors[identity].state_ledger.entries
                )
            )

        def attacks(identity, rotation):
            boss = runtime.fight.actors[-200]
            dx, dy = offsets[identity]
            target = (boss.position[0] + dx, boss.position[1] + dy, boss.position[2])
            for spell in rotation:
                actor = runtime.fight.actors[identity]
                cost = {8402: 0, 4775: 3, 4777: 4, 4778: 2, 4776: 1}[spell]
                if actor.ap < cost or (spell == 8402 and actor.mp < 1):
                    continue
                action(
                    "paid_t9_damage_or_native_self_heal",
                    cast_cell,
                    identity,
                    spell,
                    target,
                )

        def geometry_before_npc10():
            fight = runtime.fight
            living = [fight.actors[i] for i in owners if fight.actors[i].hp > 0]
            for actor in living:
                for row in fight.native_effect_areas.values():
                    if 1650 <= row["reference"] <= 1666:
                        self.assertGreaterEqual(
                            abs(actor.position[0] - row["cell"][0])
                            + abs(actor.position[1] - row["cell"][1]),
                            4,
                        )
            for index, actor in enumerate(living):
                for other in living[index + 1 :]:
                    distance = abs(actor.position[0] - other.position[0]) + abs(
                        actor.position[1] - other.position[1]
                    )
                    self.assertFalse(5 <= distance <= 8)

        try:
            self.assertEqual(
                (runtime.fight.native_table_turn, runtime.fight.turn_id), (9, 54)
            )
            self.assertEqual(runtime.fight.current.id, owners[1])
            self.assertEqual(staged_score(runtime.fight), 821782)
            for _ in range(8):
                fight = runtime.fight
                row = record()
                facts["boundaries"].append(row)
                with journal.open("a") as stream:
                    stream.write(json.dumps(row, default=str) + "\n")
                self.assertEqual(fight.phase, "active")
                identity = fight.current.id
                if fight.native_table_turn == 10 and identity in owners:
                    boss = fight.actors[-200]
                    for reference in (6998, 7025, 7015, 7021):
                        self.assertTrue(
                            any(
                                e.reference == reference and e.level == 10
                                for e in boss.state_ledger.entries
                            )
                        )
                    self.assertTrue(
                        all(
                            d["uid"] not in fight.native_effect_areas
                            for d in facts["drops"]
                        )
                    )
                    facts.update(
                        status="four_living_grade_nine_feeds_became_native_boss_grade_ten",
                        final=row,
                    )
                    return
                if fight.native_table_turn == 9 and identity in owners:
                    if identity == owners[1]:
                        self.assertEqual(
                            runtime.fight.actors[identity].position, (-45, 7, -4)
                        )
                        self.assertEqual(
                            (
                                runtime.fight.actors[identity].ap,
                                runtime.fight.actors[identity].mp,
                            ),
                            (11, 2),
                        )
                        self.assertNotIn(4881, runtime.fight.native_effect_areas)
                        self.assertTrue(
                            any(
                                e.reference == 7013 and e.level == 5
                                for e in runtime.fight.actors[
                                    identity
                                ].state_ledger.entries
                            )
                        )
                        action(
                            "paid_melee_return_jump",
                            cast_cell,
                            identity,
                            8404,
                            ends[identity],
                        )
                        attacks(identity, (8402, 4775, 4775, 4776))
                    elif identity == owners[3]:
                        drop(identity)
                        action(
                            "paid_single_tackle_path",
                            contact_path,
                            identity,
                            [(-47, 9, -4), (-47, 8, -4), ends[identity]],
                        )
                        attacks(identity, (4778, 4776, 8402, 8402, 4777, 4778, 4776))
                    elif identity == owners[0]:
                        drop(identity)
                        for cell in ((-37, 7, -4), (-36, 7, -4), ends[identity]):
                            action("paid_feca_withdrawal", move, identity, cell)
                        actor = runtime.fight.actors[identity]
                        states = {e.reference for e in actor.state_ledger.entries}
                        if (
                            6364 not in states
                            and actor.ap >= 2
                            and actor.effect_stats[4] >= 1
                        ):
                            action("paid_peace_armor", cast, identity, 7009, identity)
                        actor = runtime.fight.actors[identity]
                        if (
                            not any(
                                e.reference in (6334, 6357)
                                for e in actor.state_ledger.entries
                            )
                            and actor.ap >= 3
                        ):
                            action("paid_eligible_orbe", cast, identity, 6978, identity)
                    elif identity == owners[2]:
                        action(
                            "paid_predrop_tackle_path",
                            contact_path,
                            identity,
                            [(-50, 4, -4)],
                        )
                        drop(identity)
                        action(
                            "paid_real_old_explosion_pickup",
                            contact_path,
                            identity,
                            [(-49, 4, -4), (-48, 4, -4), (-47, 4, -4), (-47, 3, -4)],
                        )
                        self.assertNotIn(4899, runtime.fight.native_effect_areas)
                        self.assertTrue(
                            any(
                                e.reference == 7024 and e.level == 5
                                for e in runtime.fight.actors[
                                    identity
                                ].state_ledger.entries
                            )
                        )
                        facts["kept_old_explosion_after_single_drop_cap"] = True
                        action(
                            "paid_return_jump_after_old_ground_clearance",
                            cast_cell,
                            identity,
                            8404,
                            ends[identity],
                        )
                        attacks(identity, (4777, 4778))
                    elif identity == owners[4]:
                        drop(identity)
                        action(
                            "paid_northward_tackle_path",
                            contact_path,
                            identity,
                            [(-51, 7, -4), (-51, 6, -4), (-51, 5, -4)],
                        )
                        action(
                            "paid_northern_jump",
                            cast_cell,
                            identity,
                            8404,
                            ends[identity],
                        )
                        attacks(identity, (8402, 4775, 4775))
                    self.assertEqual(
                        runtime.fight.actors[identity].position, ends[identity]
                    )
                    if identity == owners[4]:
                        self.assertEqual(len(facts["drops"]), 4)
                        geometry_before_npc10()
                action("end_actual_owned_turn", advance_actual_turn, runtime)
            self.fail("Native END10 not reached within finite transition")
        except BaseException as error:
            facts.update(
                status="failed_same_store_four_feed_transition",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                final=record(),
            )
            raise
        finally:
            facts["verification_after"] = verify()
            cp["four_live_feed_receipt_path"] = str(output)
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ContinueA11FeedsAfterReturnedConsumption()])
