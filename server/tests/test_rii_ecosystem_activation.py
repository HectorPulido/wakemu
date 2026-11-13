"""Kheperalia's reconstructed acceptance validates all three native quests."""
import unittest
from copy import deepcopy

from wakfu_server.achievements import rii_ecosystem_activation as activation


def native_definitions():
    return {
        identity: {
            "d": identity,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjJ": [{"d": item} for item in objectives],
        }
        for identity, objectives in activation.OBJECTIVES.items()
    }


def state():
    return {
        "running": [],
        "completed": [],
        "tracking": [],
        "objectives": [],
        "variables": {},
        "completion_dates": {},
        "recent": [],
    }


class RiiEcosystemAcceptanceTests(unittest.TestCase):
    def test_first_is_started_and_tracked_once_without_objectives(self):
        before = state()
        after, started = activation.plan(before, native_definitions())
        self.assertEqual(started, [5145])
        self.assertEqual(after["running"], [5145])
        self.assertEqual(after["tracking"], [5145])
        self.assertEqual(after["objectives"], [])
        self.assertEqual(before, state())
        self.assertEqual(activation.plan(after, native_definitions()), (after, []))

    def test_running_mission_blocks_next_until_complete(self):
        before = state()
        before["completed"] = [5145]
        before["running"] = [5155]
        before["tracking"] = [5155]
        after, started = activation.plan(before, native_definitions())
        self.assertEqual(started, [])
        self.assertEqual(after["completed"], [5145])
        self.assertEqual(after["running"], [5155])
        self.assertEqual(after["tracking"], [5155])
        before["running"] = []
        before["tracking"] = []
        before["completed"].append(5155)
        after, started = activation.plan(before, native_definitions())
        self.assertEqual(started, [5156])
        self.assertEqual(after["tracking"], [5156])

    def test_bad_native_definition_rejected_without_partial_mutation(self):
        before = state()
        definitions = native_definitions()
        definitions[5156]["cjJ"] = [{"d": 1}]
        original = deepcopy(before)
        with self.assertRaises(ValueError):
            activation.plan(before, definitions)
        self.assertEqual(before, original)


if __name__ == "__main__":
    unittest.main()
