"""eZC/eZD owner redirection only applies to an actual Qq recipient."""
import unittest
from wakfu_server.combat_displacement import displacement_geometry


class TeleportOwnerParameterTests(unittest.TestCase):
    def test_proven_fighter_recipient_is_unchanged_for_both_teleports(self):
        source, target = object(), object()
        for family, expected in ((302, source), (340, target)):
            with self.subTest(family=family):
                result = displacement_geometry(
                    dict(effect_class=family, parameters=[1, 0]),
                    1,
                    source=source,
                    target=target,
                    cell=(2, 3, 0),
                    teleport_recipient_is_fighter=True,
                )
                self.assertIs(result["actor"], expected)
                self.assertEqual(result["destination"], (2, 3, 0))

    def test_unknown_or_non_fighter_owner_context_still_rejects(self):
        for authority in (None, False, 1):
            with self.subTest(authority=authority), self.assertRaises(ValueError):
                displacement_geometry(
                    dict(effect_class=302, parameters=[1, 0]),
                    1,
                    source=object(),
                    target=object(),
                    cell=(2, 3, 0),
                    teleport_recipient_is_fighter=authority,
                )
