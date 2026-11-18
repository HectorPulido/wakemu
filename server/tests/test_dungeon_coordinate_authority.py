"""Native position predicates require an owned, typed current character pose."""

import unittest

from wakfu_server import dungeon_criteria


class NativeCoordinateAuthorityTests(unittest.TestCase):
    def test_original_signed_bounds_and_invalid_coordinate_authority(self):
        character = dict(
            id=7, account_id=3, map_id=1017, instance_id=0, x=0, y=-1, z=-77
        )
        region = "GetX() > -4 and GetX() < 4 and GetY() > -4 and GetY() < 4"
        self.assertTrue(dungeon_criteria.evaluate(None, region, character=character))
        self.assertFalse(
            dungeon_criteria.evaluate(None, region, character=dict(character, x=4))
        )
        self.assertTrue(
            dungeon_criteria.evaluate(None, "GetZ() == -77", character=character)
        )
        for bad in (
            dict(character, x=True),
            dict(character, x=2**31),
            dict(character, z=2**15),
            dict(character, account_id=0),
            dict(character, instance_id=-1),
            {key: value for key, value in character.items() if key != "y"},
        ):
            with self.subTest(character=bad), self.assertRaises(ValueError):
                dungeon_criteria.evaluate(
                    None,
                    "not (GetX() == 0 and GetY() == 0 and GetZ() == 0)",
                    character=bad,
                )
        for expression in (
            "GetX(7) == 0",
            "GetY(owner=7) == 0",
            "GetUnknownPosition() == 0",
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                dungeon_criteria.evaluate(None, expression, character=character)
