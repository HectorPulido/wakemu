import struct
import unittest

from wakfu_server import dungeon_transport


class DungeonTransportResolutionTests(unittest.TestCase):
    def test_resolves_only_exact_configured_normal_dungeon_choice(self):
        body = struct.pack(">qiBi", 26842, 2504, 0, 2)
        resolved = dungeon_transport.resolve_request(527, body)
        self.assertEqual(resolved["route"].key, "jalato_normal")
        self.assertEqual(resolved["route"].template_id, 91)
        self.assertEqual(resolved["route"].definition_id, 90)
        self.assertEqual(
            resolved["destination"],
            {"map_id": 1086, "x": 4, "y": -12, "z": 0, "direction": 7},
        )
        self.assertNotIn("instance_id", resolved["destination"])

    def test_neo_alternative_and_nonconfigured_choice_are_not_intercepted(self):
        neo_body = struct.pack(">qiBi", 26842, 4759, 0, 2)
        other_teleporter = struct.pack(">qiBi", 26842, 2504, 0, 2)
        self.assertIsNone(dungeon_transport.resolve_request(527, neo_body))
        self.assertIsNone(dungeon_transport.resolve_request(1134, other_teleporter))

    def test_transport_service_does_not_claim_unconfigured_generic_destinations(self):
        body = struct.pack(">qiBi", 26842, 4759, 0, 2)
        self.assertIsNone(
            dungeon_transport.enter(
                None,
                1,
                "generation",
                1,
                527,
                body,
                criterion_allowed=None,
                source_allowed=None,
            )
        )

    def test_malformed_or_unsupported_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "request length"):
            dungeon_transport.resolve_request(527, b"short")
        with self.assertRaisesRegex(ValueError, "teleporter mode"):
            dungeon_transport.resolve_request(
                527, struct.pack(">qiBi", 26842, 2504, 1, 2)
            )
        with self.assertRaisesRegex(ValueError, "teleporter mode"):
            dungeon_transport.resolve_request(
                527, struct.pack(">qiBi", 26842, 2504, 0, 1)
            )


if __name__ == "__main__":
    unittest.main()
