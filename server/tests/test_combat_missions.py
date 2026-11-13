"""Focused native combat mission transitions for bosses, dungeons and mobs."""
import copy
import unittest
from unittest.mock import patch

from wakfu_server.achievements import combat_mission_activation, combat_missions


def definition(quest_id, objective_ids, *, rewards=()):
    return {
        "d": quest_id,
        "native_class": "aJM",
        "aqb": False,
        "cjI": {"always": True},
        "cjJ": [
            {"d": objective_id, "ckc": {"always": True}, "cke": {"always": True}}
            for objective_id in objective_ids
        ],
        "cjK": [{"d": reward_id} for reward_id in rewards],
    }


class CombatMissionTransitionTests(unittest.TestCase):
    def setUp(self):
        self.definitions = {
            10: definition(10, [101], rewards=[501]),  # one boss kill
            20: definition(20, [201], rewards=[502]),  # completed dungeon
            30: definition(30, [301], rewards=[503]),  # two matching monsters
            40: definition(40, [401]),  # second objective gates final reward
            50: definition(50, [501], rewards=[504]),  # boss in its required dungeon
        }
        self.rules = [
            {
                "quest_id": 10,
                "objective_id": 101,
                "kind": "monster",
                "target_id": 700,
                "count": 1,
                "evidence": "boss quest",
            },
            {
                "quest_id": 20,
                "objective_id": 201,
                "kind": "dungeon",
                "target_id": 88,
                "count": 1,
                "evidence": "dungeon quest",
            },
            {
                "quest_id": 30,
                "objective_id": 301,
                "kind": "monster",
                "target_id": 701,
                "count": 2,
                "evidence": "monster quest",
            },
            {
                "quest_id": 40,
                "objective_id": 401,
                "kind": "monster",
                "target_id": 700,
                "count": 1,
                "evidence": "active only",
            },
            {
                "quest_id": 50,
                "objective_id": 501,
                "kind": "boss",
                "target_id": 800,
                "dungeon_id": 88,
                "count": 1,
                "evidence": "boss in final dungeon",
            },
        ]
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [10, 20, 30, 40, 50],
            "completed": [],
            "tracking": [10, 20, 30, 40, 50],
            "recent": [],
            "completion_dates": {},
        }
        self.character = {"id": 5, "account_id": 6, "level": 100}

    def advance(self, state, event, counts=None, *, criteria=True):
        with patch("wakfu_server.dungeon_criteria.evaluate", return_value=criteria):
            return combat_missions.advance(
                state,
                event,
                self.rules,
                self.definitions,
                character=self.character,
                store=object(),
                now_ms=1234,
                counts={} if counts is None else counts,
            )

    def test_boss_kill_and_multi_monster_threshold_progress_only_matching_active_quests(
        self,
    ):
        updated, intents, objectives, completed, counts = self.advance(
            self.state,
            {
                "fight_id": 1,
                "original_breeds": [700, 701, 701],
                "completed_dungeon_id": None,
            },
        )
        self.assertEqual([101, 301, 401], objectives)
        self.assertEqual([10, 30, 40], completed)
        self.assertEqual([(10, {"d": 501}), (30, {"d": 503})], intents)
        self.assertEqual([101, 301, 401], updated["objectives"])
        self.assertEqual({101: 1, 301: 2, 401: 1}, counts)
        self.assertNotIn(30, updated["running"])

    def test_dungeon_completion_matches_definition_and_native_criteria(self):
        updated, intents, objectives, completed, counts = self.advance(
            self.state,
            {"fight_id": 2, "original_breeds": [], "completed_dungeon_id": 88},
        )
        self.assertEqual(
            ([201], [20], [(20, {"d": 502})]), (objectives, completed, intents)
        )
        self.assertEqual({201: 1}, counts)
        self.assertNotIn(20, updated["running"])

        blocked, intents, objectives, completed, counts = self.advance(
            self.state,
            {"fight_id": 3, "original_breeds": [], "completed_dungeon_id": 88},
            criteria=False,
        )
        self.assertEqual(self.state, blocked)
        self.assertEqual(([], [], [], {}), (intents, objectives, completed, counts))

    def test_monster_threshold_accumulates_across_fights_then_replay_cannot_repeat_reward(
        self,
    ):
        first, intents, objectives, completed, counts = self.advance(
            self.state,
            {"fight_id": 8, "original_breeds": [701], "completed_dungeon_id": None},
        )
        self.assertEqual(
            ([], [], [], {301: 1}), (intents, objectives, completed, counts)
        )
        second, intents, objectives, completed, counts = self.advance(
            first,
            {"fight_id": 9, "original_breeds": [701], "completed_dungeon_id": None},
            counts,
        )
        self.assertEqual(
            ([301], [30], [(30, {"d": 503})]), (objectives, completed, intents)
        )
        replay, intents, objectives, completed, replay_counts = self.advance(
            second,
            {"fight_id": 9, "original_breeds": [701], "completed_dungeon_id": None},
            counts,
        )
        self.assertEqual(
            (second, [], [], [], counts),
            (replay, intents, objectives, completed, replay_counts),
        )

    def test_boss_requires_both_breed_and_completed_dungeon(self):
        self.rules = [
            {
                "quest_id": 10,
                "objective_id": 101,
                "kind": "boss",
                "target_id": 700,
                "dungeon_id": 88,
                "count": 1,
                "evidence": "boss",
            }
        ]
        for event in (
            {"original_breeds": [700], "completed_dungeon_id": None},
            {"original_breeds": [700], "completed_dungeon_id": 89},
            {"original_breeds": [701], "completed_dungeon_id": 88},
        ):
            updated, intents, objectives, completed, counts = self.advance(
                self.state, event
            )
            self.assertEqual(
                (self.state, [], [], [], {}),
                (updated, intents, objectives, completed, counts),
            )
        updated, intents, objectives, completed, counts = self.advance(
            self.state, {"original_breeds": [700], "completed_dungeon_id": 88}
        )
        self.assertEqual(([101], [10]), (objectives, completed))

    def test_nonmatching_dungeon_and_inactive_mission_do_not_advance(self):
        inactive = copy.deepcopy(self.state)
        inactive["running"].remove(20)
        updated, intents, objectives, completed, counts = self.advance(
            inactive,
            {"fight_id": 4, "original_breeds": [702], "completed_dungeon_id": 999},
        )
        self.assertEqual(inactive, updated)
        self.assertEqual(([], [], [], {}), (intents, objectives, completed, counts))

    def test_mission_reward_waits_for_final_native_objective(self):
        definition_with_two = definition(10, [101, 102], rewards=[501])
        self.definitions[10] = definition_with_two
        self.rules.append(
            {
                "quest_id": 10,
                "objective_id": 102,
                "kind": "dungeon",
                "target_id": 88,
                "count": 1,
                "evidence": "second objective",
            }
        )
        partial, intents, objectives, completed, counts = self.advance(
            self.state,
            {"fight_id": 5, "original_breeds": [700], "completed_dungeon_id": None},
        )
        self.assertEqual([101, 401], objectives)
        self.assertEqual([], intents)
        self.assertEqual([40], completed)
        done, intents, objectives, completed, counts = self.advance(
            partial,
            {"fight_id": 6, "original_breeds": [], "completed_dungeon_id": 88},
            counts,
        )
        self.assertEqual(
            ([201, 102], [20, 10], [(20, {"d": 502}), (10, {"d": 501})]),
            (objectives, completed, intents),
        )
        self.assertEqual([101, 102, 201, 401], done["objectives"])

    def test_matching_boss_auto_accepts_once_and_native_level_condition_gates_it(self):
        definition = self.definitions[10]
        definition.update(cjP=100, cjL=0, cjU=0)
        empty = copy.deepcopy(self.state)
        empty["running"] = []
        empty["tracking"] = []
        event = {"fight_id": 7, "original_breeds": [700], "completed_dungeon_id": None}
        with patch("wakfu_server.dungeon_criteria.evaluate", return_value=True):
            accepted, started = combat_mission_activation.auto_accept(
                empty,
                event,
                [self.rules[0]],
                self.definitions,
                character=self.character,
                store=object(),
                now_ms=1000,
            )
            replay, replay_started = combat_mission_activation.auto_accept(
                accepted,
                event,
                [self.rules[0]],
                self.definitions,
                character=self.character,
                store=object(),
                now_ms=2000,
            )
            under_level, blocked = combat_mission_activation.auto_accept(
                empty,
                event,
                [self.rules[0]],
                self.definitions,
                character={**self.character, "level": 99},
                store=object(),
                now_ms=3000,
            )
        self.assertEqual(([10], [10]), (started, accepted["running"]))
        self.assertIn(10, accepted["tracking"])
        self.assertEqual(([], accepted), (replay_started, replay))
        self.assertEqual(([], empty), (blocked, under_level))

    def test_boss_binding_requires_both_original_breed_and_completed_dungeon(self):
        self.definitions[50].update(cjP=1, cjL=0, cjU=0)
        rule = self.rules[-1]
        wrong_dungeon = {
            "fight_id": 10,
            "original_breeds": [800],
            "completed_dungeon_id": 99,
        }
        accepted, started = combat_mission_activation.auto_accept(
            {**copy.deepcopy(self.state), "running": [], "tracking": []},
            wrong_dungeon,
            [rule],
            self.definitions,
            character=self.character,
            store=object(),
            now_ms=1000,
        )
        self.assertEqual([], started)
        self.assertNotIn(50, accepted["running"])

        correct = {**wrong_dungeon, "completed_dungeon_id": 88}
        with patch("wakfu_server.dungeon_criteria.evaluate", return_value=True):
            accepted, started = combat_mission_activation.auto_accept(
                {**copy.deepcopy(self.state), "running": [], "tracking": []},
                correct,
                [rule],
                self.definitions,
                character=self.character,
                store=object(),
                now_ms=1000,
            )
        self.assertEqual([50], started)
        updated, intents, objectives, completed, counts = self.advance(
            accepted, correct
        )
        self.assertEqual(
            ([501], [50], [(50, {"d": 504})]), (objectives, completed, intents)
        )


if __name__ == "__main__":
    unittest.main()
