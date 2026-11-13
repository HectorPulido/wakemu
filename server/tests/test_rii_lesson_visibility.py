import unittest
from unittest.mock import Mock

from wakfu_server.achievements import rii_lesson_visibility


class RiiLessonVisibilityTests(unittest.TestCase):
    def test_foreign_training_groups_are_hidden_but_native_groups_remain(self):
        actor = {"id": -11, "ref": 5466}
        groups = [
            {"key": (1388, 0, 1), "members": [actor]},
            {"key": (1388, 0, 2), "members": [{"id": -12, "ref": 5466}]},
            {"key": (1388, 0, 3), "members": [{"id": -13, "ref": 777}]},
        ]
        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            {
                "character_id": 200,
                "event_key": "rii-orientation-sack:11",
                "payload": {
                    "kind": "reconstructed_rii_orientation_sack",
                    "owner": 200,
                    "actor_id": -11,
                    "ref": 5466,
                },
            }
        ]
        self.assertEqual(
            rii_lesson_visibility.visible_groups(db, groups, 222), groups[1:]
        )
        self.assertEqual(
            rii_lesson_visibility.visible_groups(db, groups, 200), groups[1:]
        )
        self.assertEqual(
            rii_lesson_visibility.group_owners(db, groups), {(1388, 0, 1): 200}
        )

    def test_unrelated_or_forged_receipts_do_not_hide_native_groups(self):
        groups = [{"key": (1388, 0, 1), "members": [{"id": -11, "ref": 5466}]}]
        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            {
                "character_id": 200,
                "event_key": "rii-orientation-sack:11",
                "payload": {
                    "kind": "incorrect",
                    "owner": 200,
                    "actor_id": -11,
                    "ref": 5466,
                },
            }
        ]
        self.assertEqual(rii_lesson_visibility.visible_groups(db, groups, 222), groups)

    def test_return_removes_only_the_owners_receipted_sack(self):
        actors = [
            {"id": -11, "ref": 5466},
            {"id": -12, "ref": 5466},
            {"id": -13, "ref": 777},
        ]
        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            {
                "character_id": 222,
                "event_key": "rii-orientation-sack:11",
                "payload": {
                    "kind": "reconstructed_rii_orientation_sack",
                    "owner": 222,
                    "actor_id": -11,
                    "ref": 5466,
                },
            },
            {
                "character_id": 200,
                "event_key": "rii-orientation-sack:12",
                "payload": {
                    "kind": "reconstructed_rii_orientation_sack",
                    "owner": 200,
                    "actor_id": -12,
                    "ref": 5466,
                },
            },
        ]
        self.assertEqual(rii_lesson_visibility.owned_actor_ids(db, actors, 222), [-11])
