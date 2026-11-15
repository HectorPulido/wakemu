import unittest
from unittest.mock import patch

from wakfu_server.maps.npc_objective_facts import (
    ObjectiveFacts,
    evaluate,
    load,
    supported,
)
from wakfu_server.maps.dungeon_achievement_authority import queries_from_snapshot


class NativeObjectiveBooleanFactsTests(unittest.TestCase):
    criterion = (
        "GetInstanceId() == 1385\r\n and "
        "(IsAchievementObjectiveComplete(10596) or IsAchievementComplete(5154))"
    )

    def test_native_boolean_criterion_uses_world_objective_and_quest_authority(self):
        self.assertTrue(supported(self.criterion, {10596}))
        objective_branch = ObjectiveFacts(
            {10596: True},
            achievement_queries=queries_from_snapshot(
                {"running": [], "completed": [], "objectives": []}
            ),
        )
        self.assertTrue(
            evaluate(self.criterion, {"map_id": 1385}, objective_branch, {10596})
        )
        completed_quest = ObjectiveFacts(
            achievement_queries=queries_from_snapshot(
                {"running": [], "completed": [5154], "objectives": []}
            )
        )
        self.assertTrue(
            evaluate(self.criterion, {"map_id": 1385}, completed_quest, {10596})
        )
        self.assertFalse(evaluate(self.criterion, {"map_id": 1385}, {}, {10596}))
        # Even a true objective cannot stand in for absent quest authority.
        self.assertFalse(
            evaluate(
                self.criterion,
                {"map_id": 1385},
                {10596: True},
                {10596},
            )
        )
        self.assertFalse(
            evaluate(self.criterion, {"map_id": 1388}, {10596: True}, {10596})
        )

    def test_legacy_objectives_do_not_imply_quest_completion(self):
        self.assertTrue(
            evaluate(
                "IsAchievementObjectiveComplete(10596)",
                {},
                {10596: True},
                {10596},
            )
        )
        self.assertFalse(
            evaluate("IsAchievementComplete(5154)", {}, {5154: True}, {10596})
        )
        self.assertFalse(evaluate("IsAchievementComplete(5154)", {}, {}, {10596}))

    def test_caster_real_level_criteria_use_owned_character_level(self):
        self.assertTrue(
            evaluate('GetRealLevel("caster") >= 6', {"level": 6}, {}, {10596})
        )
        self.assertFalse(
            evaluate('GetRealLevel("caster") >= 6', {"level": 5}, {}, {10596})
        )
        self.assertFalse(
            evaluate('GetRealLevel("caster") >= 6', {"level": True}, {}, {10596})
        )
        self.assertTrue(
            evaluate("GetRealLevel('caster') <= 30", {"level": 30}, {}, {10596})
        )
        self.assertFalse(
            evaluate("GetRealLevel('caster') <= 30", {"level": 31}, {}, {10596})
        )
        self.assertFalse(
            evaluate("GetRealLevel('target') >= 6", {"level": 6}, {}, {10596})
        )

    def test_unknown_malformed_or_unsupported_boolean_facts_fail_closed(self):
        for criterion in (
            "IsUnknownPredicate(1) or IsAchievementObjectiveComplete(10596)",
            "IsAchievementObjectiveComplete(999999) or IsAchievementObjectiveComplete(10596)",
            "IsAchievementComplete(5154)",
        ):
            with self.subTest(criterion=criterion):
                self.assertFalse(evaluate(criterion, {}, {10596: True}, {10596}))
        self.assertFalse(
            evaluate(
                "IsAchievementObjectiveComplete(10596)",
                {},
                {10596: 1},
                {10596},
            )
        )
        self.assertFalse(evaluate("IsAchievementComplete(5154)", {}, {}, {10596}))

    def test_load_preserves_legacy_facts_and_projects_validated_snapshot_queries(self):
        class FakeDb:
            def __init__(self):
                self.calls = 0

            def execute(self, query, params):
                self.calls += 1
                if self.calls == 1:
                    return _Result({"id": 9})
                if self.calls == 2:
                    return _Result(
                        [
                            {"objective_id": 10596, "completed": True},
                            {"objective_id": 10595, "completed": False},
                        ]
                    )
                return _Result(
                    {
                        "snapshot": {
                            "running": [42],
                            "completed": [5154],
                            "objectives": [10595],
                        }
                    }
                )

        with patch(
            "wakfu_server.dungeon_achievement_authority.queries_from_snapshot",
            wraps=__import__(
                "wakfu_server.dungeon_achievement_authority",
                fromlist=["queries_from_snapshot"],
            ).queries_from_snapshot,
        ) as snapshot_projection:
            facts = load(FakeDb(), 7, 9)

        self.assertTrue(facts[10596])
        self.assertTrue(facts[10595])
        self.assertEqual(snapshot_projection.call_count, 1)
        self.assertTrue(facts.achievement_queries["IsAchievementRunning"](42))
        self.assertTrue(facts.achievement_queries["IsAchievementComplete"](5154))
        self.assertTrue(
            facts.achievement_queries["IsAchievementObjectiveComplete"](10595)
        )
        self.assertTrue(evaluate("IsAchievementComplete(5154)", {}, facts, {10596}))


class _Result:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value if isinstance(self.value, dict) else None

    def fetchall(self):
        return self.value if isinstance(self.value, list) else []


if __name__ == "__main__":
    unittest.main()
