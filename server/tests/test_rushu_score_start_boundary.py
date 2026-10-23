"""Unit boundary premise: the final20/table receipt reaches21/start.

These tests exercise ordering and the real staging/gate code, not a played
three-million-damage fight. Native marker execution and paid damage have
separate integration witnesses.
"""
from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_boss_score_policy import RUSHU_SCORE
from wakfu_server.combat_npc_phase_controller import deliver_npc_score_result
from wakfu_server.combat_server_spell import prepare_server_turn_start
from wakfu_server.maps.boss_score_runtime import stage_damage


class BoundaryFight:
    def __init__(self):
        boss = SimpleNamespace(
            id=-200,
            team=1,
            position=(0, 0, 0),
            state_ledger=SimpleNamespace(entries=[]),
        )
        player = SimpleNamespace(id=7, team=0, position=(6, 0, 0))
        self.actors = {-200: boss, 7: player}
        self.current = boss
        self.phase = "active"
        self.native_timeline_round = 20
        self.native_table_turn = 20
        self.boss_score_events = {}
        self.native_npc_initialization_receipts = {
            -200: dict(ref=5306, initialized=True)
        }
        self.boss_score_profile = dict(
            policy="wakemu-boss-validated-damage-v1",
            encounter_controller=RUSHU_SCORE.name,
            minimum_score=3000000,
            bosses={"-200": dict(reference=5306, round_limit=20)},
            player_ids=[7],
            player_team=0,
            round_limit=20,
        )

    def effect_resolution(self):
        return nullcontext()


def dispatcher(fight):
    return SimpleNamespace(native_retention=SimpleNamespace(fight=fight))


class RushuScoreStartBoundaryTests(unittest.TestCase):
    def test_last_player_damage_after_boss_end_is_gated_before_native21_start(self):
        for damage, expected in ((2999999, False), (3000000, True)):
            with self.subTest(damage=damage):
                fight = BoundaryFight()
                # Premise: boss/end20 saw no receipts; a later player action
                # stages the final20/table receipt via production attribution.
                self.assertFalse(
                    deliver_npc_score_result(dispatcher(fight), actor_id=-200)
                )
                stage_damage(
                    fight,
                    action_id=1,
                    runner_uid=91,
                    source=fight.actors[7],
                    target=fight.actors[-200],
                    result=dict(
                        hp_requested=damage, virtual_hp_absorbed=0, armor_absorbed=0
                    ),
                )
                fight.native_timeline_round = fight.native_table_turn = 21
                seen = []

                def marker(runtime, entry):
                    self.assertEqual((entry.reference, entry.level), (7110, 1))
                    runtime.native_retention.fight.actors[
                        entry.actor_id
                    ].state_ledger.entries.append(
                        SimpleNamespace(reference=entry.reference, level=entry.level)
                    )

                def native_start(runtime, *, actor_id):
                    active = any(
                        e.reference == 7110
                        for e in runtime.native_retention.fight.actors[
                            actor_id
                        ].state_ledger.entries
                    )
                    seen.append(active)
                    self.assertEqual(active, expected)

                def factory(candidate, plan):
                    return dispatcher(candidate), []

                with patch(
                    "wakfu_server.combat_server_spell.server_runtime",
                    return_value=(factory, None),
                ), patch(
                    "wakfu_server.combat_periodic_aptitude.renew_periodic_aptitudes"
                ), patch(
                    "wakfu_server.combat_npc_phase_controller._enter_controller_state",
                    marker,
                ), patch(
                    "wakfu_server.combat_turn_events.deliver_turn_start", native_start
                ):
                    preview, packets = prepare_server_turn_start(
                        {}, {}, fight, b"", actor_id=-200, action_id=2
                    )
                self.assertEqual(seen, [expected])
                self.assertEqual(packets, ())
                self.assertFalse(fight.actors[-200].state_ledger.entries)
                self.assertEqual(
                    bool(getattr(preview, "native_npc_score_result", None)), expected
                )
