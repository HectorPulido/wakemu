import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.maps import boss_score_runtime as runtime
from wakfu_server.maps.boss_score import POLICY


class BossScoreRuntimeTests(unittest.TestCase):
    def fight(self):
        player = SimpleNamespace(id=1, team=0, hp=10)
        boss = SimpleNamespace(id=-1, team=1, hp=1)
        fight = SimpleNamespace(
            id=9,
            phase="placement",
            actors={1: player, -1: boss},
            native_timeline_round=1,
            _in_play=lambda actor: actor.hp > 0,
            _event=lambda *args, **kwargs: None,
        )
        runtime.install(
            fight,
            dict(
                policy=POLICY,
                bosses={"-1": {"reference": 4378}},
                player_ids=[1],
                player_team=0,
                round_limit=20,
            ),
        )
        return fight

    def test_preview_discard_and_commit_replay(self):
        fight = self.fight()
        preview = copy.deepcopy(fight)
        runtime.stage_damage(
            preview,
            action_id=4,
            runner_uid=8,
            source=preview.actors[1],
            target=preview.actors[-1],
            result=dict(hp_requested=500, virtual_hp_absorbed=30, armor_absorbed=70),
        )
        self.assertEqual({}, fight.boss_score_events)
        self.assertEqual(
            530,
            next(iter(preview.boss_score_events.values()))["post_mitigation_damage"],
        )
        with patch.object(runtime.boss_score, "freeze_snapshot"), patch.object(
            runtime.boss_score, "record_damage"
        ) as record:
            runtime.persist(object(), preview)
        self.assertEqual(70, record.call_args.kwargs["armor_absorbed"])

    def test_round_boundary_survival_and_no_unconfigured_finish(self):
        fight = self.fight()
        fight.phase = "active"
        fight.native_timeline_round = 20
        self.assertFalse(runtime.finish_survival(fight))
        fight.native_timeline_round = 21
        self.assertFalse(runtime.finish_survival(fight))
        self.assertEqual("active", fight.phase)
        self.assertFalse(hasattr(fight, "winner"))
        del fight.boss_score_profile
        self.assertFalse(runtime.finish_survival(fight))

    def test_adds_foreign_and_unregistered_summon_never_score(self):
        fight = self.fight()
        result = dict(hp_requested=500, virtual_hp_absorbed=0, armor_absorbed=0)
        for source, target in [
            (SimpleNamespace(id=2, team=0), fight.actors[-1]),
            (fight.actors[-1], fight.actors[-1]),
            (fight.actors[1], SimpleNamespace(id=-2, team=1)),
        ]:
            runtime.stage_damage(
                fight,
                action_id=1,
                runner_uid=1,
                source=source,
                target=target,
                result=result,
            )
        self.assertEqual({}, fight.boss_score_events)

    def test_real_native_damage_executor_stages_validated_absorption(self):
        from test_combat_damage_handler import DamageHandlerTests

        fixture = DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        fight.boss_score_profile = dict(
            policy=POLICY,
            bosses={"-7": {"reference": 4378}},
            player_ids=[7],
            player_team=0,
            round_limit=20,
        )
        fight.boss_score_events = {}
        fight.native_timeline_round = 1
        self.assertTrue(fixture.handler(fixture.effect, {}, fixture.invocation))
        event = next(iter(fight.boss_score_events.values()))
        # Native101 damage consumes source barrier15, armor20, virtualHP30,
        # then requests36 HP. Scoring excludes barrier and includes armor.
        self.assertEqual(
            (66, 20), (event["post_mitigation_damage"], event["armor_absorbed"])
        )
        self.assertEqual(64, fight.actors[-7].hp)
