"""Explicit native morph spell level zero is distinct from actor level zero."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_ai.planning.tactical import _action
from wakfu_ai.planning.capabilities import validate_capabilities


class NativeZeroCastLevelTests(unittest.TestCase):
    def fixture(self):
        actors = {
            -200: dict(
                id=-200,
                hp=10,
                max_hp=10,
                level=1,
                controlled=False,
                team=1,
                ap=6,
                mp=3,
                wp=6,
                position=(0, 0, 0),
            ),
            7: dict(
                id=7,
                hp=60,
                max_hp=60,
                level=1,
                controlled=True,
                team=0,
                ap=6,
                mp=3,
                wp=6,
                position=(1, 0, 0),
            ),
        }
        return actors, dict(
            type="cast", spellId=7570, level=0, targetId=7, target=[1, 0, 0]
        )

    def test_explicit_zero_spell_level_preserves_positive_actor_and_resources(self):
        before, action = self.fixture()
        after = deepcopy(before)
        after[-200]["ap"] = 3
        checkpoint = deepcopy((before, after))
        _action(action, before, after, -200, {(0, 0, 0), (1, 0, 0)}, set())
        self.assertEqual((before, after), checkpoint)
        self.assertEqual(before[-200]["level"], 1)
        advisory = dict(
            spellId=7570,
            level=0,
            minimum=0,
            maximum=1,
            tags=["damage"],
            conditional=False,
        )
        self.assertEqual(validate_capabilities([advisory])[0]["level"], 0)

    def test_negative_level_and_unknown_target_remain_invalid(self):
        before, action = self.fixture()
        with self.assertRaisesRegex(ValueError, "Invalid spell level"):
            _action(
                dict(action, level=-1),
                before,
                before,
                -200,
                {(0, 0, 0), (1, 0, 0)},
                set(),
            )
        with self.assertRaisesRegex(ValueError, "Invalid forecast cast target"):
            _action(
                dict(action, targetId=999),
                before,
                before,
                -200,
                {(0, 0, 0), (1, 0, 0)},
                set(),
            )


if __name__ == "__main__":
    unittest.main()
