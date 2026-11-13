import unittest
from unittest.mock import MagicMock, patch
from wakfu_server.achievements.admin_missions import transition
from wakfu_server.command_permissions import ADMIN_ONLY_COMMANDS, canonical_command
from wakfu_server.test_console import HELP, execute, parse_target


class AdminMissionsTests(unittest.TestCase):
    def setUp(self):
        self.empty = dict(
            variables={},
            objectives=[],
            running=[],
            completed=[],
            tracking=[],
            recent=[],
            completion_dates={},
        )
        self.quest = dict(
            d=91,
            native_class="aJM",
            aqb=False,
            cjU=0,
            cjJ=[dict(d=3), dict(d=4)],
            cjK=[dict(d=1)],
        )

    def test_assign_complete_and_reject_replay(self):
        active, objectives, rewards = transition(self.empty, self.quest, "assign", 100)
        self.assertEqual(
            (active["running"], active["tracking"], objectives, rewards),
            ([91], [91], [], []),
        )
        self.assertEqual(self.empty["running"], [])
        done, objectives, rewards = transition(active, self.quest, "complete", 123)
        self.assertEqual(done["completed"], [91])
        self.assertEqual((done["running"], done["tracking"]), ([], []))
        self.assertEqual((objectives, rewards), ([3, 4], [dict(d=1)]))
        self.assertEqual(done["completion_dates"], {"91": 123})
        with self.assertRaises(ValueError):
            transition(done, self.quest, "complete", 124)
        with self.assertRaises(ValueError):
            transition(self.empty, self.quest, "complete", 124)

    def test_reject_periodic_and_admin_permission(self):
        with self.assertRaises(ValueError):
            transition(self.empty, dict(self.quest, cjU=86400), "assign", 100)
        self.assertTrue(
            {"!quests", "!quest-assign", "!quest-complete"} <= ADMIN_ONLY_COMMANDS
        )

    def test_english_commands_help_and_legacy_aliases(self):
        for syntax in (
            "!quests [text] [--page N]",
            "!quest-assign id [target]",
            "!quest-complete id [target]",
            "!chest depositall",
        ):
            self.assertIn(syntax, HELP)
        self.assertEqual(canonical_command("!misiones"), "!quests")
        self.assertEqual(
            parse_target('!quest-assign 1695 "Prueba Sacro"'),
            ("!quest-assign 1695", "Prueba Sacro"),
        )
        self.assertEqual(
            parse_target("!mision-completar 1695"), ("!quest-complete 1695", None)
        )

    def test_english_list_routes_query_and_page(self):
        store = MagicMock()
        character = {"id": 42}
        store.character.return_value = character
        with patch("wakfu_server.command_permissions.authorize_command"), patch(
            "wakfu_server.test_console._lease"
        ), patch(
            "wakfu_server.achievements.admin_missions.catalog", return_value="result"
        ) as catalog:
            result = execute(store, None, 1, 1, character, "!quests hunter --page 2")
        self.assertEqual(result["message"], "result")
        self.assertEqual(catalog.call_args.args[1:], ("hunter", 2))


if __name__ == "__main__":
    unittest.main()
