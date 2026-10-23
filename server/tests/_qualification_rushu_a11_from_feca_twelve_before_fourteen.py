"""Resume the actual Feca turn using the retained destination-based movement API."""
import json
from pathlib import Path
import sys
import time
import traceback
import unittest


class ContinueA11FromFecaTwelveBeforeFourteen(unittest.TestCase):
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
            + "-same-store-feca-twelve-master-pickup-before-fourteen.json"
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
        focus = {10: owners[1], 11: owners[2], 12: owners[3], 13: owners[4]}
        try:
            self.assertEqual(runtime.fight.native_table_turn, 12)
            self.assertEqual(runtime.fight.current.id, owners[0])
            self.assertEqual(
                (
                    runtime.fight.current.ap,
                    runtime.fight.current.mp,
                    runtime.fight.current.effect_stats[4],
                ),
                (10, 6, 8),
            )
            for reference in (6998, 7015, 7021, 7025):
                self.assertTrue(
                    any(
                        e.reference == reference and e.level == 10
                        for e in runtime.fight.actors[-200].state_ledger.entries
                    )
                )
            for _ in range(30):
                fight = runtime.fight
                snapshot = record()
                facts["boundaries"].append(snapshot)
                with journal.open("a") as stream:
                    stream.write(json.dumps(snapshot, default=str) + "\n")
                if fight.phase != "active":
                    facts.update(
                        status="native_terminal_during_earned_window", final=snapshot
                    )
                    return
                if fight.native_table_turn == 14 and fight.current.id in owners:
                    facts.update(
                        status="retained_before_table14_for_phase15_ground_and_lava_plan",
                        final=snapshot,
                    )
                    return
                self.assertLessEqual(fight.native_table_turn, 14)
                identity = fight.current.id
                table = fight.native_table_turn
                if identity in offsets:
                    actor = fight.actors[identity]
                    if table == 12 and identity == owners[1]:
                        held = next(
                            (
                                e
                                for e in actor.state_ledger.entries
                                if e.reference == 7013 and e.level <= 10
                            ),
                            None,
                        )
                        if held is not None:
                            action(
                                "paid_zero_resource_melee_drop_before_damage",
                                cast_cell,
                                identity,
                                7271,
                                (-45, 6, -4),
                            )
                            self.assertFalse(
                                any(
                                    e.reference == 6999
                                    for e in runtime.fight.actors[
                                        identity
                                    ].state_ledger.entries
                                )
                            )
                    if table == 10 and identity == owners[2]:
                        held = next(
                            (
                                e
                                for e in actor.state_ledger.entries
                                if e.reference == 7024 and e.level <= 10
                            ),
                            None,
                        )
                        if held is not None:
                            # A fresh owned turn restores the native once-per-turn DROP allowance.
                            level = held.level
                            action(
                                "paid_fresh_turn_old_explosion_drop",
                                cast_cell,
                                identity,
                                7271,
                                (-48, 3, -4),
                            )
                            self.assertFalse(
                                any(
                                    e.reference == 6999
                                    for e in runtime.fight.actors[
                                        identity
                                    ].state_ledger.entries
                                )
                            )
                            facts["old_explosion_dropped_level"] = level
                    boss = runtime.fight.actors[-200]
                    dx, dy = offsets[identity]
                    target = (
                        boss.position[0] + dx,
                        boss.position[1] + dy,
                        boss.position[2],
                    )
                    actor = runtime.fight.actors[identity]
                    if (
                        staged_score(runtime.fight) < 3000000
                        and focus.get(table) == identity
                        and actor.ap >= 2
                    ):
                        action(
                            "paid_native_focus_singleton",
                            cast_cell,
                            identity,
                            4790,
                            target,
                        )
                    actor = runtime.fight.actors[identity]
                    if actor.max_hp - actor.hp >= 2500 and actor.mp >= 1:
                        rotation = (
                            (8402, 4775, 4775)
                            if staged_score(runtime.fight) >= 3000000
                            else (8402, 4775, 4775, 4777, 4778)
                        )
                    elif staged_score(runtime.fight) >= 3000000:
                        rotation = ()
                    elif actor.mp >= 2:
                        rotation = (
                            4778,
                            4776,
                            8402,
                            8402,
                            8403,
                            4777,
                            4778,
                            4778,
                            4776,
                        )
                    else:
                        rotation = (4778, 4776, 8402, 4777, 4778, 4778, 4776)
                    if table == 12 and identity == owners[1]:
                        # The original prefix, profiled big and first suffix B are already committed.
                        rotation = (4778, 4776)
                    healing_only = actor.max_hp - actor.hp >= 2500 and actor.mp >= 1
                    for spell_index, spell in enumerate(rotation):
                        if staged_score(runtime.fight) >= 3000000 and (
                            not healing_only or spell_index >= 3
                        ):
                            break
                        actor = runtime.fight.actors[identity]
                        needed = {4778: 2, 4776: 1, 8402: 0, 8403: 0, 4777: 4, 4775: 3}[
                            spell
                        ]
                        if (
                            actor.ap < needed
                            or (spell == 8402 and actor.mp < 1)
                            or (spell == 8403 and actor.effect_stats[4] < 1)
                        ):
                            continue
                        action(
                            "paid_native_window_damage_or_self_heal",
                            cast_cell,
                            identity,
                            spell,
                            target,
                        )
                elif identity == owners[0]:
                    if table == 12:
                        # The retained helper accepts one destination and avoids other glyphs.
                        # Target the real glyph first; withdrawing directly would route around it.
                        action(
                            "paid_native_master_pickup_destination",
                            move,
                            identity,
                            (-35, 5, -4),
                        )
                        self.assertTrue(
                            any(
                                e.reference == 7011 and e.level <= 10
                                for e in runtime.fight.actors[
                                    identity
                                ].state_ledger.entries
                            )
                        )
                        action(
                            "paid_master_carrier_exterior_withdraw_destination",
                            move,
                            identity,
                            (-37, 5, -4),
                        )
                    elif table == 13:
                        action(
                            "paid_exterior_master_carrier_approach",
                            move,
                            identity,
                            (-39, 5, -4),
                        )
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
                        action(
                            "paid_eligible_self_orbe", cast, identity, 6978, identity
                        )
                action("end_actual_owned_turn", advance_actual_turn, runtime)
            self.fail("Finite table-fourteen planning endpoint not reached")
        except BaseException as error:
            facts.update(
                status="failed_same_store_earned_window",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                final=record(),
            )
            raise
        finally:
            facts["verification_after"] = verify()
            cp["feca_twelve_master_before_fourteen_receipt_path"] = str(output)
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ContinueA11FromFecaTwelveBeforeFourteen()])
