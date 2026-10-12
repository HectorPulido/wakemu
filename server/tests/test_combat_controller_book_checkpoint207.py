"""Typed controller UI books remain exact checkpoint and transaction evidence."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from types import SimpleNamespace
import unittest

from wakfu_server.combat_character_copy_book import CopyBookAction
from wakfu_server.fight_checkpoint_store import _plain
from wakfu_server.combat_geometry_snapshot import source_snapshot


class ControllerBookCheckpoint207Tests(unittest.TestCase):
    def book(self):
        return CopyBookAction((7 << 32) | 6266, 6266, 20, False, True, False)

    def test_exact_uid_and_all_native_action_fields_survive_json_roundtrip(self):
        action = self.book()
        recovered = CopyBookAction(**json.loads(json.dumps(_plain(action))))
        recovered.validate()
        self.assertEqual(recovered, action)
        self.assertEqual(_plain(action), asdict(action))
        self.assertEqual(recovered.uid, (7 << 32) | 6266)

    def test_source_guard_preserves_book_source_runner_controller_and_uid(self):
        fight = SimpleNamespace(
            actors={},
            native_controller_action_books={
                7: {
                    "producer": "eWD207.eZd.fQM.actual",
                    "running_uid": 19,
                    "controller_id": -7,
                    "actions": (self.book(),),
                }
            },
        )
        before = source_snapshot(fight)
        clone = deepcopy(fight)
        self.assertEqual(source_snapshot(clone), before)
        self.assertIsInstance(
            clone.native_controller_action_books[7]["actions"][0], CopyBookAction
        )
        clone.native_controller_action_books[7]["actions"] = (
            replace(self.book(), uid=6266),
        )
        self.assertNotEqual(source_snapshot(clone), before)
        self.assertEqual(source_snapshot(fight), before)

    def test_invalid_typed_action_does_not_serialize_as_authority(self):
        with self.assertRaisesRegex(ValueError, "book action"):
            _plain(replace(self.book(), level=1 << 20))

    def test_unrelated_dataclasses_remain_unsupported(self):
        from dataclasses import dataclass

        @dataclass
        class Untrusted:
            uid: int

        with self.assertRaisesRegex(ValueError, "nonserializable"):
            _plain(Untrusted(7))

    def test_runtime_callback_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonserializable"):
            _plain({"actions": [lambda: None]})


if __name__ == "__main__":
    unittest.main()
