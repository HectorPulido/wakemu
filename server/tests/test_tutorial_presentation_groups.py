"""Focused persistence tests for mixed native tutorial presentation groups."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server.achievements import storage, tutorial_presentation_once as once


class _MemoryDB:
    def __init__(self):
        self.rows = {}

    def execute(self, query, params):
        class Result:
            def __init__(self, row):
                self.row = row

            def fetchone(self):
                return self.row

        char_id = params[0]
        if "ORDER BY (payload->>'order_ns')" in query:
            prefix = params[2]
            rows = [
                (key, value)
                for (owner, key), value in self.rows.items()
                if owner == char_id and key.startswith(prefix)
            ]
            rows.sort(key=lambda pair: int(pair[1]["order_ns"]), reverse=True)
            return Result(None if not rows else {"payload": rows[0][1]})
        key = params[1]
        return Result(
            None
            if (char_id, key) not in self.rows
            else {"payload": self.rows[(char_id, key)]}
        )


def _record(db, character_id, key, payload):
    identity = (character_id, key)
    if identity in db.rows:
        return False
    db.rows[identity] = deepcopy(payload)
    return True


class TutorialPresentationGroupTests(unittest.TestCase):
    def setUp(self):
        self.db = _MemoryDB()
        self.character = dict(id=77, instance_id=1001)
        self.group = dict(
            id="native-tutorial",
            start_event=15992,
            initializers={"2015": 15992, "2018": 16007, "2016": 15998},
            events=[15992, 15998, 16007, 16008, 16009],
        )

    def _context(self, character, token, order):
        with patch.object(storage, "_lock"), patch.object(
            storage, "record_event", side_effect=_record
        ):
            with patch(
                "wakfu_server.achievements.tutorial_presentation_once.time.time_ns",
                return_value=order,
            ):
                once.register_context(self.db, character, token)

    def _claim(self, character, scenario, event):
        with patch.object(storage, "_lock"), patch.object(
            storage, "record_event", side_effect=_record
        ):
            return once.claim_group_event(
                self.db, character, self.group, scenario, event
            )

    def test_group_start_order_dedup_phase_and_context_are_pinned(self):
        self._context(self.character, "a" * 32, 1)
        # Crew dialogue cannot bootstrap the native program on its own.
        self.assertFalse(self._claim(self.character, 2015, 15998))
        self.assertTrue(self._claim(self.character, 2015, 15992))
        self.assertFalse(self._claim(self.character, 2015, 15992))
        self.assertTrue(self._claim(self.character, 2015, 15998))
        self.assertFalse(self._claim(self.character, 2018, 16008))
        self.assertTrue(self._claim(self.character, 2018, 16007))
        self.assertTrue(self._claim(self.character, 2018, 16008))
        self.assertTrue(self._claim(self.character, 2016, 15998))

        # A later loaded context (reconnect or another instance) cannot replay
        # the group or capture actors owned by the earlier native run.
        self._context(self.character, "b" * 32, 2)
        self.assertFalse(self._claim(self.character, 2016, 15998))
        self.assertFalse(
            self._claim(dict(self.character, instance_id=1002), 2015, 15992)
        )
        other = dict(self.character, id=78)
        self._context(other, "d" * 32, 3)
        self.assertTrue(self._claim(other, 2015, 15992))

    def test_invalid_group_rejected_before_claim(self):
        self._context(self.character, "c" * 32, 1)
        invalid = dict(self.group, initializers={"2015": 12345})
        with patch.object(storage, "_lock"), patch.object(
            storage, "record_event", side_effect=_record
        ):
            with self.assertRaisesRegex(
                ValueError, "Invalid native presentation group"
            ):
                once.claim_group_event(self.db, self.character, invalid, 2015, 15992)


if __name__ == "__main__":
    unittest.main()
