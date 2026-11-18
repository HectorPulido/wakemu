"""The reconstructed starter encounter retains native terrain, grades and gates."""

import copy
import json
from pathlib import Path
import unittest

from wakfu_server.combat_geometry import prepare_geometry, reachable
from wakfu_server.quest_instance_configuration import compile_profile


class SawmillConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parents[1]
        directory = root / "wakfu_server/maps/quest_encounter_profiles"
        cls.profile = json.loads((directory / "astrub-sawmill.json").read_text())
        cls.walking = json.loads(
            (directory / cls.profile["exploration_file"]).read_text()
        )
        cls.native = json.loads(
            (root / "tests/fixtures/native_astrub_sawmill_sources.json").read_text()
        )
        cls.sources = {(row["map_id"], row["id"]): row for row in cls.native["sources"]}

    def compile(self, sources=None):
        return compile_profile(
            self.profile,
            geometry=prepare_geometry(self.walking),
            exploration=self.walking,
            sources=sources or self.sources,
            monster=self.native["monster"],
        )

    def test_native_active_gate_roster_grade_and_reachable_exterior_are_preserved(self):
        config = self.compile()
        self.assertEqual(config["route"]["criterion"], "IsAchievementActive(2190)")
        roster = config["compiled_plan"]["rooms"][0]["monsters"][0]
        self.assertEqual(
            (
                roster["ref_id"],
                roster["count"],
                roster["native_min_level"],
                roster["native_max_level"],
            ),
            (1710, 3, 3, 3),
        )
        self.assertFalse(config["compiled_plan"]["official"])
        self.assertEqual(
            config["topology"]["owned_quest_encounter"]["entry_objective"], 4329
        )
        self.assertEqual(
            config["topology"]["owned_quest_encounter"]["victory_objective"], 4328
        )
        walking = prepare_geometry(config["topology"]["exploration_geometry"])
        origin = tuple(config["topology"]["rooms"][0]["anchor"])
        door = config["topology"]["physical_exit_objects"][0]
        self.assertIn(
            tuple(door["source_position"]),
            reachable(origin, walking.cells, walking.outgoing),
        )
        self.assertEqual(door["destination"], dict(map_id=527, x=-150, y=51, z=0))

    def test_completed_other_quest_and_compound_gates_cannot_be_substituted(self):
        for criterion in (
            "IsAchievementComplete(2190)",
            "IsAchievementActive(2158)",
            "IsAchievementActive(2190) or True",
            "",
        ):
            with self.subTest(criterion=criterion):
                sources = copy.deepcopy(self.sources)
                sources[(527, 19409)]["destinations"][0]["criterion"] = criterion
                with self.assertRaisesRegex(ValueError, "native running-quest gate"):
                    self.compile(sources)


if __name__ == "__main__":
    unittest.main()
