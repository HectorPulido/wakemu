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


class DungeonLegacyTransportGuardTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server.dungeon_instances import EntryRoute

        self.route = EntryRoute(
            key="legacy",
            template_id=1000312,
            definition_id=1000312,
            entry_map_id=527,
            entry_object_id=1,
            destination_id=10,
            start_map_id=312,
            criterion="",
            native_template_id=-1,
        )
        self.destination = dict(
            destination_id=10,
            map_id=312,
            criterion="",
            cyZ=-1,
            x=1,
            y=2,
            z=3,
            direction=0,
            native_altitude_walkable=True,
            item_reference=0,
            cyW=0,
            cyX=0,
        )

    def resolve(self):
        from unittest.mock import patch

        with patch.object(
            dungeon_transport.dungeon_instances,
            "route_for_entry",
            return_value=self.route,
        ), patch.object(
            dungeon_transport.generic_transports,
            "source",
            return_value={"destinations": [self.destination]},
        ):
            return dungeon_transport.resolve_request(
                527, struct.pack(">qiBi", 1, 10, 0, 2)
            )

    def test_native_template_is_separate_from_local_run_template(self):
        self.assertEqual(self.resolve()["route"].template_id, 1000312)
        self.destination["cyZ"] = 0
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            self.resolve()

    def test_item_and_kama_requirements_are_not_waived(self):
        self.destination.update(item_reference=7, cyW=1)
        with self.assertRaisesRegex(ValueError, "item transaction"):
            self.resolve()
        self.destination.update(item_reference=0, cyW=0, cyX=10)
        with self.assertRaisesRegex(ValueError, "kama transaction"):
            self.resolve()
