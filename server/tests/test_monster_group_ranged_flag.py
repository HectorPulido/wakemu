"""Flag24 has damage/range consumers, but no group registration branch."""
import unittest

from wakfu_server.combat_native_events import validate_group_registration_flags


class GroupRangedFlagTests(unittest.TestCase):
    def test_ranged_flag_preserves_authenticated_constructor_context(self):
        validate_group_registration_flags([24], active=False, constructor=True)
        validate_group_registration_flags([1, 16, 24], active=True)

    def test_ranged_flag_does_not_grant_placement_authority(self):
        with self.assertRaisesRegex(ValueError, "requires active combat"):
            validate_group_registration_flags([24], active=False)

    def test_health_ordering_and_unknown_flags_remain_rejected(self):
        for flags in ([8], [24, 8], [24, 999]):
            with self.subTest(flags=flags), self.assertRaisesRegex(
                ValueError, "Unaudited"
            ):
                validate_group_registration_flags(flags, active=True)
