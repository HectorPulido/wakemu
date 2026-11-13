"""The captured Grougaloragran terminal advances only the active quest."""
import copy
import unittest
from unittest.mock import Mock, patch

from wakfu_server import npc_world, rii_conversation_progress as progress
from test_npc_observed_dialogue import captured_row
from test_rii_conversation_progress import RiiConversationTests


class RiiGuardianDialogueTests(RiiConversationTests):
    def guardian(self):
        row = captured_row(-1706442035962340, 5458, 1387, -12, 0, 2, 1, 5764, 1238)
        character, session, request = self.session(
            row, [(5764, 13343), (5790, 13345), (5791, 13347)]
        )
        return row, character, session, request

    def guardian_definition(self):
        return {
            "d": 5146,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [
                {"d": 10582, "ckc": "", "cke": ""},
                {"d": 10583, "ckc": "IsAchievementObjectiveComplete(10582)", "cke": ""},
                {"d": 10584, "ckc": "", "cke": ""},
            ],
            "cjK": [],
        }

    def test_terminal_advances_talk_but_does_not_complete_fight(self):
        self.state["running"].append(5146)
        self.state["objectives"].append(10582)
        self.db.execute.side_effect = lambda sql, args: Mock(
            fetchone=Mock(return_value={"data": {"native": self.guardian_definition()}})
        )
        row, character, session, request = self.guardian()
        with patch.object(progress.npc_world, "load_scene", return_value=[row]):
            result = progress.choose(self.store, 2, 1, character, session, request)
        self.assertIn(10583, self.state["objectives"])
        self.assertNotIn(10584, self.state["objectives"])
        self.assertIn(5146, self.state["running"])
        self.assertTrue(any(code == 13832 for code, _ in result["packets"]))

    def test_missing_entrance_does_not_advance_and_restores_session(self):
        self.state["running"].append(5146)
        self.db.execute.side_effect = lambda sql, args: Mock(
            fetchone=Mock(return_value={"data": {"native": self.guardian_definition()}})
        )
        row, character, session, request = self.guardian()
        old = copy.deepcopy(self.state)
        with patch.object(progress.npc_world, "load_scene", return_value=[row]):
            with self.assertRaises(ValueError):
                progress.choose(self.store, 2, 1, character, session, request)
        self.assertEqual(self.state, old)
        self.assertEqual(session.node_id, 5791)


if __name__ == "__main__":
    unittest.main()
