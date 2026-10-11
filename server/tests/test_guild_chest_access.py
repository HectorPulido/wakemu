"""Offline checks for physical guild storage authority boundaries."""
import struct
import unittest

from wakfu_server.characters.guild_chest_dispatch import validate_access


class GuildChestAccessTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(id=5, map_id=1134, instance_id=0, x=1, y=-69, z=30)
        self.object = dict(
            id=31504, type="GuildStorageBox", map_id=1134, x=1, y=-69, z=30
        )
        self.point = dict(
            map_id=1134,
            object_id=31504,
            action_id=12,
            parameter=0,
            compartment_ids=[0, 1],
        )
        self.body = struct.pack(">qHH", 31504, 12, 0)

    def validate(self, **kwargs):
        return validate_access(
            self.character, self.body, [self.object], [self.point], **kwargs
        )

    def test_installed_object_and_explicit_policy_grant_detached_context(self):
        result = self.validate()
        self.point["compartment_ids"].append(2)
        self.assertEqual(result["compartment_ids"], (0, 1))

    def test_private_instance_and_active_activity_are_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(blocked=True)
        self.character["instance_id"] = 7
        with self.assertRaises(ValueError):
            self.validate()

    def test_account_chest_never_grants_guild_storage(self):
        self.object["type"] = "AccountChest"
        with self.assertRaises(ValueError):
            self.validate()

    def test_distance_and_elevation_are_checked(self):
        self.character["x"] = 5
        with self.assertRaises(ValueError):
            self.validate()
        self.character["x"] = 1
        self.character["z"] = 33
        with self.assertRaises(ValueError):
            self.validate()

    def test_action_parameter_map_and_ambiguous_policy_are_rejected(self):
        for key, value in (("action_id", 13), ("parameter", 1), ("map_id", 9)):
            original = self.point[key]
            self.point[key] = value
            with self.assertRaises(ValueError):
                self.validate()
            self.point[key] = original
        with self.assertRaises(ValueError):
            validate_access(
                self.character, self.body, [self.object], [self.point, self.point]
            )

    def test_unbounded_policy_and_duplicate_compartments_are_rejected(self):
        for key, value in (
            ("max_distance", 4),
            ("max_z_distance", True),
            ("compartment_ids", [0, 0]),
            ("compartment_ids", []),
        ):
            point = dict(self.point, **{key: value})
            with self.assertRaises(ValueError):
                validate_access(self.character, self.body, [self.object], [point])

    def test_packet_truncation_and_trailing_bytes_are_rejected(self):
        for body in (self.body[:-1], self.body + b"\x00", bytearray(self.body)):
            with self.assertRaises(ValueError):
                validate_access(self.character, body, [self.object], [self.point])


if __name__ == "__main__":
    unittest.main()
