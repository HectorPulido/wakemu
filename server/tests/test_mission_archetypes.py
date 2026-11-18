"""Focused compiler regressions for reviewed generic mission archetypes."""

import copy
import unittest

from wakfu_server.achievements import mission_archetypes


def native_quest(identity, objectives):
    return {
        "d": identity,
        "native_class": "aJM",
        "aqb": False,
        "cjJ": objectives,
        "cjK": [],
        "cjU": 0,
        "cjL": 0,
        "getDuration": 0,
    }


class MissionArchetypeCompilerTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "schema": "mission-archetypes-v1",
            "id": "compiler-fixture",
            "evidence": ["reviewed test evidence"],
            "missions": [
                {
                    "quest_id": 101,
                    "activation": {
                        "mode": "event",
                        "event": {"kind": "craft_completed", "reference": 501},
                    },
                    "maps": [700, 701],
                    "objectives": [
                        {
                            "objective_id": 201,
                            "archetype": "craft",
                            "reference": 501,
                            "count": "operation",
                        },
                        {
                            "objective_id": 202,
                            "archetype": "defeat",
                            "reference": 502,
                            "count": "operation",
                            "maps": [701],
                        },
                    ],
                }
            ],
        }
        self.native = {
            101: native_quest(101, [{"d": 201, "ckf": []}, {"d": 202, "ckf": []}]),
        }

    def test_compiles_every_native_objective_and_keeps_declared_scopes(self):
        profile, summary = mission_archetypes.compile_profile(
            self.document, self.native
        )
        self.assertEqual(summary["missions"], 1)
        self.assertEqual(summary["objectives"], 2)
        self.assertEqual(profile["bindings"][0]["maps"], [700, 701])
        self.assertEqual(profile["bindings"][1]["maps"], [701])
        self.assertEqual(profile["activations"][0]["event"]["reference"], 501)

    def test_rejects_incomplete_or_duplicated_native_objective_coverage(self):
        incomplete = copy.deepcopy(self.document)
        incomplete["missions"][0]["objectives"].pop()
        with self.assertRaisesRegex(ValueError, "cover every native mission objective"):
            mission_archetypes.compile_profile(incomplete, self.native)

        duplicate = copy.deepcopy(self.document)
        duplicate["missions"][0]["objectives"][1]["objective_id"] = 201
        with self.assertRaisesRegex(ValueError, "cover every native mission objective"):
            mission_archetypes.compile_profile(duplicate, self.native)

    def test_rejects_recurring_missions_without_cycle_adapter(self):
        recurring = copy.deepcopy(self.native)
        recurring[101]["cjU"] = 1
        with self.assertRaisesRegex(ValueError, "Recurring/timed missions"):
            mission_archetypes.compile_profile(self.document, recurring)

    def test_rejects_unsupported_event_and_unreviewed_reference(self):
        invalid = copy.deepcopy(self.document)
        invalid["missions"][0]["objectives"][0]["archetype"] = "translated-text-guess"
        with self.assertRaisesRegex(ValueError, "Unsupported mission event archetype"):
            mission_archetypes.compile_profile(invalid, self.native)

        invalid = copy.deepcopy(self.document)
        invalid["missions"][0]["objectives"][0]["reference"] = True
        with self.assertRaisesRegex(ValueError, "reviewed producer reference"):
            mission_archetypes.compile_profile(invalid, self.native)


if __name__ == "__main__":
    unittest.main()
