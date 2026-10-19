import unittest
from contextlib import contextmanager
from datetime import datetime, timezone

from wakfu_server.maps import (
    dungeon_criteria,
    dungeon_entry_access,
    seasonal_access,
    transport_criteria,
)


HALOUINE = (
    '@("event.halouine.date.expired") ('
    + seasonal_access.EVENT_WINDOWS[443]
    + ")@ and #HasState(1536)#"
)
MADRAGUE = (
    '@("quest.Madrague.event.termine") ('
    + seasonal_access.EVENT_WINDOWS[1075]
    + ')@ and @("quest.Madrague.boussole") GetItemQuantity(20389) > 0@'
)
SUMMER = "(GetRealLevel() >= 51 and (" + seasonal_access.EVENT_WINDOWS[146] + "))"


class ClockStore:
    def clock(self):
        return datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp()

    @contextmanager
    def connection(self):
        yield self

    def execute(self, query, params):
        if params != (dungeon_entry_access.SETTING,):
            raise AssertionError(params)
        return self

    def fetchone(self):
        return {"value": dict(dungeon_entry_access.DEFAULT)}


class SeasonalAccessTests(unittest.TestCase):
    def rewrite(self, criterion, map_id):
        return seasonal_access.open_event_calendar(criterion, destination_map_id=map_id)

    def test_halouine_opens_outside_calendar_without_waiving_state(self):
        opened = self.rewrite(HALOUINE, 443)
        for state, expected in ((False, False), (True, True)):
            with self.subTest(state=state):
                self.assertEqual(
                    expected,
                    dungeon_criteria.evaluate(
                        ClockStore(),
                        opened,
                        queries={"HasState": lambda identity: state},
                    ),
                )
        self.assertFalse(
            dungeon_criteria.evaluate(
                ClockStore(), HALOUINE, queries={"HasState": lambda identity: True}
            )
        )

    def test_bound_dungeon_entry_uses_existing_mission_policy(self):
        self.assertTrue(
            dungeon_entry_access.evaluate(
                ClockStore(), HALOUINE, character={"id": 1}, destination_map_id=443
            )
        )
        self.assertFalse(
            dungeon_entry_access.evaluate(ClockStore(), HALOUINE, character={"id": 1})
        )

    def test_madrague_retains_item_predicate(self):
        opened = self.rewrite(MADRAGUE, 1075)
        self.assertIn("GetItemQuantity(20389) > 0", opened)
        self.assertNotIn("IsAfter", opened)
        self.assertNotIn("IsBefore", opened)

    def test_summer_retains_required_level(self):
        opened = self.rewrite(SUMMER, 146)
        for level, expected in ((50, False), (51, True)):
            with self.subTest(level=level):
                self.assertEqual(
                    expected,
                    transport_criteria.evaluate(
                        opened,
                        {"level": level},
                        now_ms=int(ClockStore().clock() * 1000),
                    ),
                )

    def test_missing_wrong_or_unknown_map_keeps_calendar(self):
        self.assertEqual(HALOUINE, seasonal_access.open_event_calendar(HALOUINE))
        for map_id in (527, 472, 1075, 99999):
            with self.subTest(map_id=map_id):
                self.assertEqual(HALOUINE, self.rewrite(HALOUINE, map_id))

    def test_other_dates_release_gates_and_unreviewed_windows_stay_intact(self):
        changed = HALOUINE.replace("2026", "2027")
        self.assertEqual(changed, self.rewrite(changed, 443))
        release = 'not GetBooleanSystemConfiguration("beta.mode") and IsAfter(13,12,2016,20,00,00)'
        self.assertEqual(release, self.rewrite(release, 443))
        extra = HALOUINE + " and IsAfter(01,01,2040,00,00,00)"
        self.assertIn("IsAfter(01,01,2040,00,00,00)", self.rewrite(extra, 443))

    def test_duplicate_window_and_malformed_map_are_not_waived(self):
        duplicate = HALOUINE + " and (" + seasonal_access.EVENT_WINDOWS[443] + ")"
        self.assertEqual(duplicate, self.rewrite(duplicate, 443))
        for map_id in (True, 0, -1, "443"):
            with self.subTest(map_id=map_id), self.assertRaises(ValueError):
                self.rewrite(HALOUINE, map_id)

    def test_unknown_extra_predicate_remains_rejected(self):
        with self.assertRaises(ValueError):
            dungeon_criteria.evaluate(
                ClockStore(),
                self.rewrite(HALOUINE + " and IsAdmin()", 443),
                queries={"HasState": lambda identity: True},
            )


if __name__ == "__main__":
    unittest.main()
