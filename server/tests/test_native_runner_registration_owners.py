"""Contracts credited by original registry and literal-return bytecode audit."""
import json
from pathlib import Path
import unittest


class NativeRunnerRegistrationOwnersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = json.loads(
            (
                Path(__file__).parents[1]
                / "protocol/native-runner-registration-owners.json"
            ).read_text()
        )["effects"]

    def test_stat_armor_and_maximum_owners_are_target_owned(self):
        for family in (
            20,
            31,
            41,
            191,
            56,
            57,
            192,
            193,
            986,
            1013,
            1201,
            1202,
            400,
            649,
            877,
        ):
            row = self.effects[str(family)]
            self.assertTrue(row["literal_constants_verified"])
            self.assertEqual((row["bbA"], row["bbB"]), (True, False))

    def test_copy_and_352_have_native_caster_registration_shape(self):
        for family in (402, 352):
            row = self.effects[str(family)]
            self.assertTrue(row["literal_constants_verified"])
            self.assertEqual((row["bbA"], row["bbB"]), (False, True))

    def test_dynamic_groups_remain_unknown_until_context_resolution(self):
        for family in (330, 341, 1103):
            row = self.effects[str(family)]
            self.assertFalse(row["literal_constants_verified"])
            self.assertIsNone(row["bbA"])
            self.assertIsNone(row["bbB"])
