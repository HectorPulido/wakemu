"""Reconnect projections retain independently completed native mission flags."""
import struct
import unittest

from wakfu_server.achievements import service


def _native(identity, *, duration=0, period=0):
    return {
        "d": identity,
        "native_class": "aJM",
        "aqb": False,
        "getDuration": duration,
        "cjU": period,
    }


class Db:
    def __init__(self, guardian=None):
        self.guardian = _native(5146) if guardian is None else guardian

    def execute(self, query, args):
        self.query = query
        self.args = args
        return self

    def fetchall(self):
        if "native_quest_metadata_definitions" not in self.query:
            return []
        return [{"definition_id": 5146, "data": {"native": self.guardian}}]

    def fetchone(self):
        return None


class CompletedMissionVisibilityTests(unittest.TestCase):
    def test_nonperiodic_completion_retains_active_after_reconnect(self):
        state = dict(
            variables={},
            objectives=[],
            running=[],
            completed=[5146, 7000, 7001, 7002],
            tracking=[],
            recent=[],
            completion_dates={"5146": 1, "7000": 1, "7001": 1},
        )
        packet = service._journal_section(Db(), state, {}, 5)
        body = packet[2:-1]
        self.assertEqual(struct.unpack_from(">i", body, 9)[0], 4)
        rows = [struct.unpack_from(">iBBBBB", body, 13 + 9 * i) for i in range(4)]
        self.assertEqual(
            rows,
            [
                (5146, 1, 1, 0, 0, 0),
                (7000, 0, 1, 0, 0, 0),
                (7001, 0, 1, 0, 0, 0),
                (7002, 0, 1, 0, 0, 0),
            ],
        )
        self.assertEqual(state["running"], [])

    def test_changed_timed_or_periodic_definition_is_not_retained(self):
        state = dict(
            variables={},
            objectives=[],
            running=[],
            completed=[5146],
            tracking=[],
            recent=[],
            completion_dates={"5146": 1},
        )
        for definition in (_native(5146, duration=60), _native(5146, period=1)):
            packet = service._journal_section(Db(definition), state, {}, 5)
            self.assertEqual(
                struct.unpack_from(">iBBBBB", packet, 15), (5146, 0, 1, 0, 0, 0)
            )


if __name__ == "__main__":
    unittest.main()
