"""Complete actual first-round actions and four distinct future feed carriers."""
import importlib
import json
from pathlib import Path
import struct
import traceback
import unittest


class FirstRoundFourCarriers(unittest.TestCase):
    def runTest(self):
        recipe = importlib.import_module("test_rushu_dd230_native_opening")
        checkpoint = recipe.RUSHU_ACTUAL_CHECKPOINT
        verify_checkpoint = checkpoint.get("authorized_uid_transition_verifier")
        self.assertTrue(
            callable(verify_checkpoint),
            "Missing explicit authorized UID implementation transition verifier",
        )
        verify_checkpoint()
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_orientation import apply as orient
        from wakfu_server.combat_global_pv_collections import global_area_order
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.boss_score_runtime import staged_score

        runtime = checkpoint["runtime"]
        owners = checkpoint["identities"]
        cast = checkpoint["cast"]
        cast_cell = checkpoint["cast_cell"]
        move = checkpoint["move"]
        current = runtime.fight
        self.assertEqual(
            (current.native_table_turn, current.turn_id, current.current.id),
            (1, 2, owners[1]),
        )
        self.assertEqual(current.actors[owners[1]].position, (-47, 9, -4))
        facts = dict(
            status="pending",
            prefix_receipt=checkpoint["receipt_path"],
            first_damage_receipt=checkpoint["last_damage_receipt"],
            actions=[],
            boundaries=[],
            carriers={},
        )
        output = Path(checkpoint["receipt_path"]).with_name(
            Path(checkpoint["receipt_path"]).stem + "-four-carriers-first-round.json"
        )
        wanted = {
            owners[2]: (1666, 7025),
            owners[3]: (1656, 7015),
            owners[4]: (1662, 7021),
            owners[5]: (1661, 7020),
        }
        receipt = checkpoint["receipt"]
        old_casts = len(receipt["casts"])
        old_moves = len(receipt["movements"])

        def snapshot():
            return dict(
                table=runtime.fight.native_table_turn,
                turn=runtime.fight.turn_id,
                current=runtime.fight.current.id,
                score=staged_score(runtime.fight),
                players={
                    owner: dict(
                        hp=runtime.fight.actors[owner].hp,
                        position=runtime.fight.actors[owner].position,
                        ap=runtime.fight.actors[owner].ap,
                        mp=runtime.fight.actors[owner].mp,
                        wp=runtime.fight.actors[owner].effect_stats[4],
                        states=[
                            (entry.reference, entry.level, entry.caster_id)
                            for entry in runtime.fight.actors[
                                owner
                            ].state_ledger.entries
                        ],
                    )
                    for owner in owners
                },
            )

        try:
            # One more single-target hit; never cast area Wrath across allies.
            boss = runtime.fight.actors[-200]
            cast_cell(owners[1], 4775, (-48, 8, boss.position[2]))
            move(owners[1], (-47, 8, -4))
            orient(
                runtime,
                runtime.fight.actors[owners[1]].owner_id,
                struct.pack(">qB", owners[1], 5),
            )
            advance_actual_turn(runtime)
            for boundary in range(6):
                while runtime.awaiting_ack is not None:
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                current = runtime.fight
                facts["boundaries"].append(snapshot())
                self.assertEqual(current.native_table_turn, 1)
                self.assertTrue(all(current.actors[owner].hp > 0 for owner in owners))
                identity = current.current.id
                if identity == owners[0]:
                    cast(identity, 7009, identity)
                    move(identity, (-42, 7, -4))
                    cast(identity, 6982, owners[1])
                    move(identity, (-39, 7, -4))
                    states = {
                        entry.reference
                        for entry in runtime.fight.actors[identity].state_ledger.entries
                    }
                    if 6334 not in states and 6357 not in states:
                        cast(identity, 6978, identity)
                elif identity in wanted:
                    reference, state = wanted[identity]
                    area = next(
                        row
                        for row in runtime.fight.native_effect_areas.values()
                        if row["reference"] == reference
                    )
                    self.assertEqual(
                        next(
                            entry.level
                            for entry in area["state_ledger"].entries
                            if entry.reference == 7001
                        ),
                        1,
                    )
                    if identity == owners[3]:
                        self.assertIn(8404, granted_spells(runtime.fight, identity))
                        cast_cell(identity, 8404, (-43, 12, -4))
                    if identity == owners[5]:
                        # Heal the genuinely wounded tank before taking the
                        # distant Cyclone slot. All caps/costs remain native.
                        for spell in (779, 779, 1533, 1533):
                            target = runtime.fight.actors[owners[0]]
                            if target.hp == target.max_hp:
                                break
                            cast(identity, spell, owners[0])
                    move(identity, tuple(area["cell"]))
                    held = [
                        entry
                        for entry in runtime.fight.actors[identity].state_ledger.entries
                        if entry.reference == state and entry.level <= 10
                    ]
                    self.assertEqual(len(held), 1)
                    self.assertEqual(held[0].level, 1)
                    self.assertNotIn(area["uid"], runtime.fight.native_effect_areas)
                    self.assertNotIn(area["uid"], global_area_order(runtime.fight))
                    facts["carriers"][identity] = dict(
                        area=reference,
                        state=state,
                        grade=1,
                        consumed_uid=area["uid"],
                        caster=held[0].caster_id,
                        cell=runtime.fight.actors[identity].position,
                    )
                else:
                    self.fail("Unexpected actor before completing the first cohort")
                orient(
                    runtime,
                    runtime.fight.actors[identity].owner_id,
                    struct.pack(">qB", identity, 5),
                )
                if len(facts["carriers"]) == 4:
                    facts.update(
                        status="four_native_grade_one_carriers_before_first_cohort_end",
                        final=snapshot(),
                        casts=receipt["casts"][old_casts:],
                        movements=receipt["movements"][old_moves:],
                    )
                    return
                advance_actual_turn(runtime)
            self.fail(
                "Four real distinct carriers were not obtained in the first cohort"
            )
        except Exception as error:
            facts.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                pending_cast=receipt.get("pending_cast"),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            facts["loaded_implementation_attestation"] = verify_checkpoint()
            facts.setdefault("final", snapshot())
            facts.setdefault("casts", receipt["casts"][old_casts:])
            facts.setdefault("movements", receipt["movements"][old_moves:])
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")
            checkpoint["first_round_carriers_receipt"] = str(output)


def qualify():
    return unittest.TestSuite([FirstRoundFourCarriers()])
