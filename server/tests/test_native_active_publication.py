"""Native journal publication keeps activation independent of completion."""
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

from wakfu_server import quest_npc
from wakfu_server.dungeon_achievement_authority import queries_from_state
from wakfu_server.achievements import service, wire


def state(*, running=(), completed=(), active=(), periods=None):
    return dict(
        variables={},
        objectives=[],
        running=list(running),
        completed=list(completed),
        active=list(active),
        active_periods={} if periods is None else periods,
        tracking=[],
        recent=[],
        completion_dates={str(q): 1000 for q in completed},
    )


def flags(raw):
    if raw[-1] != 0:
        raise AssertionError("Unexpected compressed small fixture")
    body = raw[2:-1]
    position = 5 + 12 * body[4]
    variables = struct.unpack_from(">i", body, position)[0]
    position += 4 + 12 * variables
    count = struct.unpack_from(">i", body, position)[0]
    position += 4
    records = {}
    for _ in range(count):
        identity, active, completed, _date1, date2 = struct.unpack_from(
            ">iBBBB", body, position
        )
        position += 8 + (8 if date2 else 0) + 1
        records[identity] = (active, completed)
    return records


class JournalDb:
    def __init__(self):
        self.queries = []

    def execute(self, sql, args):
        self.queries.append(sql)
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class NativeActivePublicationTests(unittest.TestCase):
    def test_initial_flags_distinguish_completed_active_from_completed_inactive(self):
        current = state(completed=[2160, 2161], active=[2160])
        self.assertEqual(flags(wire.section(current)), {2160: (1, 1), 2161: (0, 1)})
        authority = queries_from_state(current)
        self.assertTrue(authority["IsAchievementActive"](2160))
        self.assertFalse(authority["IsAchievementRunning"](2160))

    def test_expired_and_unknown_period_clocks_cannot_publish_active_flags(self):
        proof = dict(anchor_ms=1000, period_seconds=2, accepted_at_ms=1000)
        current = state(completed=[2160], active=[2160], periods={"2160": proof})
        with patch(
            "wakfu_server.achievements.lifecycle.time.time_ns",
            return_value=10_000_000_000,
        ):
            self.assertEqual(flags(wire.section(current))[2160], (0, 1))
            current["active_periods"]["2160"]["accepted_at_ms"] = None
            self.assertEqual(flags(wire.section(current))[2160], (0, 1))
        self.assertEqual(current["active"], [2160])

    def test_preview_changes_only_wire_bytes_not_independent_authority(self):
        current = state(completed=[2160], active=[])
        before = deepcopy(current)
        self.assertEqual(
            flags(wire.section(current, preview_active=[2160]))[2160], (1, 1)
        )
        self.assertFalse(queries_from_state(current)["IsAchievementActive"](2160))
        self.assertEqual(current, before)

    def test_journal_uses_generic_active_flags_without_per_quest_metadata_inference(
        self,
    ):
        current = state(completed=[424242], active=[424242])
        db = JournalDb()
        actual = service._journal_section(db, current, {}, 20)
        self.assertEqual(flags(actual)[424242], (1, 1))
        self.assertFalse(any("native_quest_metadata" in sql for sql in db.queries))

    def test_catalog_admission_projection_preserves_active_without_mutating_input(self):
        current = state(completed=[2160], active=[])
        before = deepcopy(current)
        with patch.object(
            service.catalog, "load", return_value={"definitions": {99: {}}}
        ):
            actual = service.project_section(current, None, db=JournalDb())
        self.assertEqual(flags(actual), {99: (1, 0), 2160: (0, 1)})
        self.assertEqual(current, before)

    def test_npc_running_root_uses_native_running_and_unknown_clock_keeps_greeting(
        self,
    ):
        item = dict(quest_id=1721, running_root=12, row={"dialogue_root": 10})
        completed = state(completed=[1721], active=[1721])
        self.assertEqual(quest_npc._running_root(None, {}, item, completed), 10)
        current = state(
            running=[1721],
            active=[1721],
            periods={
                "1721": dict(anchor_ms=1000, period_seconds=2, accepted_at_ms=None)
            },
        )
        with patch(
            "wakfu_server.achievements.lifecycle.time.time_ns",
            return_value=10_000_000_000,
        ):
            self.assertEqual(quest_npc._running_root(None, {}, item, current), 10)
            current["active_periods"]["1721"]["accepted_at_ms"] = 9500
            self.assertEqual(quest_npc._running_root(None, {}, item, current), 12)


if __name__ == "__main__":
    unittest.main()
