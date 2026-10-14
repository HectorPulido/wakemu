"""Structural forecasts retain native revival and zero-maximum dead records."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_ai.planning.tactical import _actors, _action


class NativeRetainedForecastContractTests(unittest.TestCase):
    def raw_actor(self, identity=1, hp=0, maximum=0):
        return dict(
            id=identity,
            hp=hp,
            max_hp=maximum,
            position=[0, 0, 0],
            team=1,
            controlled=False,
            armor=0,
            ap=6,
            mp=3,
            wp=0,
        )

    def test_native_dead_zero_maximum_record_remains_structurally_valid(self):
        result = _actors([self.raw_actor()], {(0, 0, 0)})
        self.assertEqual((result[1]["hp"], result[1]["max_hp"]), (0, 0))

    def test_positive_hp_still_cannot_exceed_zero_maximum(self):
        with self.assertRaisesRegex(ValueError, "Invalid forecast HP"):
            _actors([self.raw_actor(hp=1)], {(0, 0, 0)})

    def test_native_certified_cast_may_name_retained_ko_target(self):
        before = _actors([self.raw_actor(maximum=60)], {(0, 0, 0)})
        action = dict(type="cast", spellId=6169, level=1, targetId=1, target=[0, 0, 0])
        _action(action, before, before, 1, {(0, 0, 0)}, set())

    def test_unknown_retained_target_is_still_rejected(self):
        before = _actors([self.raw_actor(maximum=60)], {(0, 0, 0)})
        action = dict(type="cast", spellId=6169, level=1, targetId=2, target=[0, 0, 0])
        with self.assertRaisesRegex(ValueError, "Invalid forecast cast target"):
            _action(action, before, before, 1, {(0, 0, 0)}, set())


if __name__ == "__main__":
    unittest.main()
