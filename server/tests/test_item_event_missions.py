"""Reviewed missions started by successful native item conversions."""
import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from wakfu_server.achievements import item_event_missions


class FakeDB:
    def __init__(self, definition):
        self.definition = definition
        self.queries = []

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        return self

    def fetchone(self):
        return {"data": {"native": self.definition}}


class FakeStore:
    def now(self):
        return datetime.fromtimestamp(42, timezone.utc)


class ItemEventMissionTests(unittest.TestCase):
    def setUp(self):
        self.definition = {
            "native_class": "aJM",
            "d": 1217,
            "aqb": False,
            "cjI": "GetRealLevel() >= 105",
            "cjJ": [{"d": 2178}],
        }
        self.character = {"id": 7, "account_id": 8, "level": 105}
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [],
            "completed": [],
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }

    def invoke(
        self,
        *,
        native_class="bHS",
        action_id=3614,
        source_reference=15985,
        output_reference=15986,
        character=None,
        state=None
    ):
        db = FakeDB(self.definition)
        with patch(
            "wakfu_server.achievements.item_event_missions._owner"
        ) as owner, patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value=copy.deepcopy(self.state if state is None else state),
        ) as load, patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ) as record, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist, patch(
            "wakfu_server.achievements.wire.changes", return_value=[b"mission-start"]
        ) as changes:
            packets = item_event_missions.activate_for_output(
                db,
                FakeStore(),
                self.character if character is None else character,
                native_class=native_class,
                action_id=action_id,
                source_reference=source_reference,
                output_reference=output_reference,
                source_uid=9001,
            )
        return packets, db, owner, load, record, persist, changes

    def test_fragment_conversion_starts_and_tracks_mission_1217_once(self):
        packets, db, owner, load, record, persist, changes = self.invoke()
        self.assertEqual(packets, [b"mission-start"])
        owner.assert_called_once_with(db, self.character)
        self.assertEqual(
            db.queries[0][1],
            (
                1217,
                item_event_missions.BINDINGS[("bHS", 3614, 15985, 15986)]["revision"],
            ),
        )
        load.assert_called_once_with(db, 7)
        record.assert_called_once_with(
            db,
            7,
            "item-action-mission:1217",
            {
                "kind": "reconstructed_item_action_mission_v1",
                "mission_id": 1217,
                "action_id": 3614,
                "source_reference": 15985,
                "source_uid": 9001,
                "output_reference": 15986,
                "reconstruction": "reconstructed_item_description_and_quest_text_v1",
            },
        )
        updated = persist.call_args.args[2]
        self.assertEqual(updated["running"], [1217])
        self.assertEqual(updated["tracking"], [1217])
        changes.assert_called_once_with(7, self.state, updated, [], [], 42000)

    def test_repeat_activation_and_unmapped_conversion_do_not_create_progress(self):
        running = copy.deepcopy(self.state)
        running["running"] = [1217]
        running["tracking"] = [1217]
        packets, _, _, _, record, persist, changes = self.invoke(state=running)
        self.assertEqual(packets, [])
        record.assert_not_called()
        persist.assert_not_called()
        changes.assert_not_called()

        packets, _, _, _, record, persist, changes = self.invoke(output_reference=15987)
        self.assertEqual(packets, [])
        record.assert_not_called()
        persist.assert_not_called()
        changes.assert_not_called()

    def test_metadata_or_level_drift_rejects_activation(self):
        self.definition["cjI"] = "GetRealLevel() >= 104"
        with self.assertRaisesRegex(ValueError, "definition changed"):
            self.invoke()
        self.definition["cjI"] = "GetRealLevel() >= 105"
        with self.assertRaisesRegex(ValueError, "definition changed"):
            self.invoke(character={**self.character, "level": 104})


if __name__ == "__main__":
    unittest.main()
