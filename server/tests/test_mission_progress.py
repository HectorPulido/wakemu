import copy
import unittest
from unittest.mock import patch

from wakfu_server.achievements import conversation, mission_progress


class MissionProgressTests(unittest.TestCase):
    def setUp(self):
        self.definition = {
            "d": 91,
            "native_class": "aJM",
            "aqb": False,
            "cjI": {"always": True},
            "cjJ": [
                {"d": 901, "ckc": {"always": True}, "cke": {"always": True}},
                {"d": 902, "ckc": {"always": True}, "cke": {"always": True}},
            ],
            "cjK": [{"d": 77}],
        }
        self.character = {"id": 5, "account_id": 6}
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [91],
            "completed": [],
            "tracking": [91],
            "recent": [],
            "completion_dates": {},
        }
        self.criteria = patch(
            "wakfu_server.dungeon_criteria.evaluate", return_value=True
        )
        self.criteria.start()
        self.addCleanup(self.criteria.stop)

    def test_two_objectives_complete_once_and_replay_is_idempotent(self):
        first, rewards, added, completed = mission_progress.advance_objective(
            self.state,
            self.definition,
            901,
            character=self.character,
            store=object(),
            now_ms=100,
        )
        self.assertEqual(
            ([901], [], [901], []), (first["objectives"], rewards, added, completed)
        )
        second, rewards, added, completed = mission_progress.advance_objective(
            first,
            self.definition,
            902,
            character=self.character,
            store=object(),
            now_ms=200,
        )
        self.assertEqual([901, 902], second["objectives"])
        self.assertEqual(([(91, {"d": 77})], [902], [91]), (rewards, added, completed))
        self.assertEqual([], second["running"])
        self.assertEqual([91], second["completed"])
        self.assertEqual({"91": 200}, second["completion_dates"])
        replay = mission_progress.advance_objective(
            second,
            self.definition,
            902,
            character=self.character,
            store=object(),
            now_ms=300,
        )
        self.assertEqual((second, [], [], []), replay)

    def test_criteria_failure_and_inactive_quest_do_not_advance(self):
        with patch("wakfu_server.dungeon_criteria.evaluate", return_value=False):
            with self.assertRaisesRegex(ValueError, "prerequisite"):
                mission_progress.advance_objective(
                    self.state,
                    self.definition,
                    901,
                    character=self.character,
                    store=object(),
                    now_ms=100,
                )
        inactive = copy.deepcopy(self.state)
        inactive["running"] = []
        with self.assertRaisesRegex(ValueError, "not running"):
            mission_progress.advance_objective(
                inactive,
                self.definition,
                901,
                character=self.character,
                store=object(),
                now_ms=100,
            )

    def test_conversation_adapter_preserves_qualified_fact_checks(self):
        fact = {
            "kind": "qualified_native_quest_conversation_v1",
            "character_id": 5,
            "account_id": 6,
            "quest_id": 91,
            "objective_id": 901,
            "native_definition_sha256": conversation._digest(self.definition),
        }
        with patch.object(
            mission_progress,
            "advance_objective",
            return_value=(self.state, [], [901], []),
        ) as transition:
            result = conversation.advance(
                self.state,
                fact,
                self.definition,
                character=self.character,
                store=object(),
                now_ms=100,
            )
        self.assertEqual((self.state, [], [901], []), result)
        self.assertEqual(901, transition.call_args.args[2])
        fact["account_id"] = 999
        with self.assertRaisesRegex(ValueError, "Invalid native conversation"):
            conversation.advance(
                self.state,
                fact,
                self.definition,
                character=self.character,
                store=object(),
                now_ms=100,
            )


if __name__ == "__main__":
    unittest.main()
