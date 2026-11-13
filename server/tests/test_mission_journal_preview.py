import struct
import unittest
from wakfu_server.achievements.wire import section
from unittest.mock import patch
from wakfu_server.achievements import service


class MissionJournalPreviewTests(unittest.TestCase):
    def test_preview_projects_completed_as_active_without_mutating_authority(self):
        state = dict(
            variables={},
            objectives=[],
            running=[1],
            completed=[2],
            tracking=[],
            recent=[],
            completion_dates={},
        )
        raw = section(state, preview_active=[2], preview_completed=[5165])
        body = raw[2:-1]
        self.assertEqual(raw[-1], 0)
        count = struct.unpack_from(">i", body, 9)[0]
        self.assertEqual(count, 3)
        rows = [struct.unpack_from(">iBBBBB", body, 13 + i * 9) for i in range(count)]
        self.assertEqual(
            rows, [(1, 1, 0, 0, 0, 0), (2, 1, 1, 0, 0, 0), (5165, 0, 1, 0, 0, 0)]
        )
        self.assertEqual(state["running"], [1])
        self.assertEqual(state["completed"], [2])
        with self.assertRaises(ValueError):
            section(state, preview_active=[3])

    def test_character_projection_uses_preview_only_for_requested_character(self):
        class Db:
            def execute(self, query, args):
                self.query = query
                return self

            def fetchall(self):
                return []

            def fetchone(self):
                return {
                    "value": {
                        "schema": "mission_journal_preview_v1",
                        "character_id": 40,
                        "active": [2],
                        "completed": [5165],
                    }
                }

        state = dict(
            variables={},
            objectives=[],
            running=[1],
            completed=[2],
            tracking=[],
            recent=[],
            completion_dates={},
        )
        with patch.object(
            service.catalog, "load", return_value={"definitions": {}}
        ), patch(
            "wakfu_server.objectives.environmental_recurring_storage.activation_dates",
            return_value={},
        ):
            preview = service.project_section(state, None, db=Db(), character_id=40)
            normal = service.project_section(state, None, db=Db(), character_id=41)
        self.assertEqual(
            struct.unpack_from(">iBBBBB", preview, 15 + 9), (2, 1, 1, 0, 0, 0)
        )
        self.assertEqual(
            struct.unpack_from(">iBBBBB", normal, 15 + 9), (2, 0, 1, 0, 0, 0)
        )
        self.assertEqual(state["completed"], [2])

    def test_character_projection_preserves_recurring_activation_date(self):
        class Db:
            def execute(self, query, args):
                return self

            def fetchall(self):
                return []

            def fetchone(self):
                return None

        state = dict(
            variables={},
            objectives=[],
            running=[4100],
            completed=[],
            tracking=[4100],
            recent=[],
            completion_dates={},
        )
        accepted_at = 1794421094367
        with patch.object(
            service.catalog, "load", return_value={"definitions": {}}
        ), patch(
            "wakfu_server.objectives.environmental_recurring_storage.activation_dates",
            return_value={4100: accepted_at},
        ) as dates:
            raw = service.project_section(state, None, db=Db(), character_id=16)
        dates.assert_called_once_with(unittest.mock.ANY, 16)
        body = raw[2:-1]
        self.assertEqual(struct.unpack_from(">iBBBB", body, 13), (4100, 1, 0, 0, 1))
        self.assertEqual(struct.unpack_from(">q", body, 21)[0], accepted_at)


if __name__ == "__main__":
    unittest.main()
