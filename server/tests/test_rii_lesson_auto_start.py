import unittest
from unittest.mock import Mock

from wakfu_server.achievements import rii_lesson_auto_start as auto


class RiiLessonAutoStartTests(unittest.TestCase):
    def test_all_lessons_select_only_the_players_owned_sack(self):
        for objective, (prefix, kind) in auto.KEYS.items():
            with self.subTest(objective=objective):
                sack = {"id": -11, "ref": 5466, "x": 0, "y": -16, "z": 0}
                groups = Mock()
                groups.available.return_value = [
                    {"key": (1388, 0, 1), "members": [sack]}
                ]
                db = Mock()
                db.execute.return_value.fetchone.return_value = {
                    "payload": {"kind": kind, "owner": 7, "actor_id": -11, "ref": 5466}
                }
                self.assertEqual(auto.target(db, groups, 7, objective), sack)
                db.execute.assert_called_once_with(
                    "SELECT payload FROM character_achievement_events "
                    "WHERE character_id=%s AND event_key=%s",
                    (7, prefix + "11"),
                )
                db.execute.return_value.fetchone.return_value["payload"]["owner"] = 8
                with self.assertRaises(ValueError):
                    auto.target(db, groups, 7, objective)

    def test_multiple_owned_encounters_are_rejected(self):
        groups = Mock()
        groups.available.return_value = [
            {"key": (1388, 0, 1), "members": [{"id": -11, "ref": 5466}]},
            {"key": (1388, 0, 2), "members": [{"id": -12, "ref": 5466}]},
        ]
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            {
                "payload": {
                    "kind": auto.KEYS[10574][1],
                    "owner": 7,
                    "actor_id": actor,
                    "ref": 5466,
                }
            }
            for actor in (-11, -12)
        ]
        with self.assertRaises(ValueError):
            auto.target(db, groups, 7, 10574)


if __name__ == "__main__":
    unittest.main()
