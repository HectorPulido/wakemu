import unittest
from types import SimpleNamespace
from wakfu_server.combat_cast import _validate_target


class NativeSelfCastLosTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(id=7, position=(0, 0, 0), hp=100, ap=6, mp=3)
        self.fight = SimpleNamespace(
            walkable={(0, 0, 0), (1, 0, 0)}, actors={7: self.actor}
        )
        self.rule = dict(
            minimum=0, maximum=1, linear=False, line_of_sight=True, free_cell=False
        )
        self.calls = []

    def validate(self, cell):
        return _validate_target(
            dict(target=cell),
            self.actor,
            self.fight,
            6,
            dict(ap=1, mp=0, wp=0),
            self.rule,
            [123],
            20,
            lambda *args: self.calls.append(args) or False,
            123,
        )

    def test_native_same_xyz_does_not_use_bare_ray_catalog(self):
        self.assertEqual(self.validate((0, 0, 0))["target_id"], 7)
        self.assertEqual(self.calls, [])

    def test_different_cell_still_requires_verified_los(self):
        with self.assertRaisesRegex(ValueError, "line of sight"):
            self.validate((1, 0, 0))
        self.assertEqual(len(self.calls), 1)

    def test_self_keeps_range_resources_and_free_cell_guards(self):
        self.rule["minimum"] = 1
        with self.assertRaisesRegex(ValueError, "native range"):
            self.validate((0, 0, 0))
        self.rule["minimum"] = 0
        self.rule["free_cell"] = True
        with self.assertRaisesRegex(ValueError, "unoccupied"):
            self.validate((0, 0, 0))
        self.actor.ap = 0
        with self.assertRaisesRegex(ValueError, "resources"):
            self.validate((0, 0, 0))
