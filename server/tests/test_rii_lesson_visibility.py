import unittest
from unittest.mock import Mock
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_lesson_visibility


class RiiLessonVisibilityTests(unittest.TestCase):
    def test_native_guardian_receipt_hides_private_actor_from_every_world_view(self):
        group = {
            "key": (1387, 0, 1),
            "members": [{"id": -11, "ref": 5458}],
        }
        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            {
                "character_id": 200,
                "event_key": "rii-guardian-actor:11",
                "payload": {
                    "kind": "reconstructed_rii_guardian_actor",
                    "owner": 200,
                    "actor_id": -11,
                    "ref": 5458,
                },
            }
        ]
        self.assertEqual(
            rii_lesson_visibility.group_owners(db, [group]), {group["key"]: 200}
        )
        self.assertEqual(rii_lesson_visibility.visible_groups(db, [group], 200), [])
        self.assertEqual(rii_lesson_visibility.visible_groups(db, [group], 999), [])

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

    def test_scene_cleanup_retires_all_exact_historical_owners_only(self):
        groups = [
            {"members": [{"id": -11, "ref": 5466, "status": "dead"}]},
            {"members": [{"id": -12, "ref": 5466, "status": "available"}]},
            {"members": [{"id": -13, "ref": 5466, "status": "dead"}]},
            {"members": [{"id": -14, "ref": 777, "status": "available"}]},
        ]
        receipts = [
            {
                "character_id": 200,
                "event_key": "rii-orientation-sack:11",
                "payload": {
                    "kind": "reconstructed_rii_orientation_sack",
                    "owner": 200,
                    "actor_id": -11,
                    "ref": 5466,
                },
            },
            {
                "character_id": 300,
                "event_key": "rii-orientation-sack:12",
                "payload": {
                    "kind": "reconstructed_rii_orientation_sack",
                    "owner": 300,
                    "actor_id": -12,
                    "ref": 5466,
                },
            },
            {
                "character_id": 400,
                "event_key": "rii-orientation-sack:13",
                "payload": {
                    "kind": "forged",
                    "owner": 400,
                    "actor_id": -13,
                    "ref": 5466,
                },
            },
        ]
        calls = []

        def execute(query, args=()):
            calls.append((query, args))
            rows = groups if "FROM combat_groups" in query else receipts
            return SimpleNamespace(fetchall=lambda: rows)

        db = SimpleNamespace(execute=execute)
        with patch(
            "wakfu_server.combat_monster_world.remove_message",
            side_effect=lambda ids: (12304, tuple(ids)),
        ) as remove:
            self.assertEqual(
                rii_lesson_visibility.scene_cleanup(db, 1388, 0),
                ((12304, (-12, -11)),),
            )
        self.assertEqual(remove.call_args.args, ([-12, -11],))
        self.assertEqual(len(calls), 2)
        self.assertNotIn("status", calls[0][0].lower())

        db.execute = Mock()
        self.assertEqual(rii_lesson_visibility.scene_cleanup(db, 1385, 0), ())
        db.execute.assert_not_called()
