"""Native Deathburn counter data binds only the reviewed public family fights."""

import json
from pathlib import Path
import unittest

from test_mission_toolkit_core import state
from wakfu_server.achievements import mission_toolkit_contract as contract
from wakfu_server.achievements import mission_toolkit_planner as planner


ROOT = Path(__file__).parents[1]


class EreboriaDeathburnIntroductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads(
            (
                ROOT
                / "wakfu_server/achievements/mission_profiles/ereboria-deathburn-introduction.json"
            ).read_text()
        )
        cls.definition = json.loads(
            (ROOT / "tests/fixtures/native_ereboria_goomy_definition.json").read_text()
        )
        cls.definitions = [cls.definition]

    def test_native_counter_accepts_only_running_public_family_1100_deaths(self):
        checked = contract.validate(self.profile, {5047: self.definition})
        self.assertEqual(len(checked["bindings"]), 4)
        self.assertEqual(
            {row["event"]["reference"] for row in checked["bindings"]},
            {5379, 5380, 5381, 5383},
        )

        character = dict(id=369, map_id=1359, instance_id=0, level=36)
        current = state(running=[5047])
        self.assertNotIn(5046, current["completed"])
        for reference in (5379, 5380, 5381, 5383, 5379):
            current, intents, completed_objectives, completed = planner.plan(
                current,
                self.definitions,
                checked,
                dict(kind="monster_defeat", reference=reference, quantity=2),
                character=character,
                store=object(),
                now_ms=1,
            )
            self.assertEqual(intents, [])
            self.assertEqual(completed, [])
        self.assertEqual(current["variables"]["747"], 10)
        self.assertIn(10411, current["objectives"])
        self.assertNotIn(10412, current["objectives"])
        self.assertNotIn(5047, current["completed"])

        current, intents, _, completed = planner.plan(
            current,
            self.definitions,
            checked,
            dict(kind="monster_defeat", reference=5383, quantity=32767),
            character=character,
            store=object(),
            now_ms=2,
        )
        self.assertEqual(current["variables"]["747"], 10)
        self.assertEqual((intents, completed), ([], []))

        rejected = (
            ("wrong-reference", state(running=[5047]), character, 5399),
            ("wrong-map", state(running=[5047]), dict(character, map_id=1360), 5379),
            (
                "private-instance",
                state(running=[5047]),
                dict(character, instance_id=7),
                5379,
            ),
            ("unassigned", state(), character, 5379),
            ("completed", state(completed=[5047]), character, 5379),
        )
        for label, before, actor, reference in rejected:
            with self.subTest(case=label):
                after, intents, objectives, completions = planner.plan(
                    before,
                    self.definitions,
                    checked,
                    dict(kind="monster_defeat", reference=reference, quantity=1),
                    character=actor,
                    store=object(),
                    now_ms=3,
                )
                self.assertEqual(after, before)
                self.assertEqual((intents, objectives, completions), ([], [], []))


if __name__ == "__main__":
    unittest.main()
