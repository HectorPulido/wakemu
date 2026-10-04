import struct
import unittest

from protocol_codec import decode_appearance, decode_body


class CreationProtocolTests(unittest.TestCase):
    def test_remote_route_preserves_stair_height_and_has_no_movement_mode(self):
        body = struct.pack(">qiihB", 42, 8, 32, -1, 2) + bytes([97, 64])
        route = decode_body("in", 13852, body)
        self.assertEqual(route["actor_id"], 42)
        self.assertEqual(route["start_position"], {"x": 8, "y": 32, "z": -1})
        self.assertEqual(route["end_position"], {"x": 9, "y": 34, "z": 0})
        self.assertEqual(route["step_count"], 2)
        self.assertNotIn("mode_id", route)
        for invalid in (body[:-1], body + b"\x00"):
            with self.assertRaises(ValueError):
                decode_body("in", 13852, invalid)

    def test_craft_request_keeps_station_recipe_and_quantity(self):
        body = struct.pack(">qii", 1234567890123, 123, 5)
        self.assertEqual(
            decode_body("out", 12231, body),
            {"craft_station_id": 1234567890123, "recipe_id": 123, "quantity": 5},
        )
        for invalid in (body[:-1], body + b"\x00"):
            with self.assertRaises(ValueError):
                decode_body("out", 12231, invalid)

    def test_creation_response_status_and_exact_length(self):
        self.assertEqual(
            decode_body("in", 22025, b"\x00"),
            {"status": 0, "success": True, "reason": "success"},
        )
        self.assertEqual(
            decode_body("in", 22025, b"\xff"),
            {"status": -1, "success": False, "reason": "unspecified_error"},
        )
        for status, reason in [
            (102, "existing_name"),
            (103, "invalid_name"),
            (104, "too_many_characters"),
            (105, "pending_migration_request"),
            (106, "character_class_disabled"),
        ]:
            self.assertEqual(
                decode_body("in", 22025, bytes([status]))["reason"], reason
            )
        for body in (b"", b"\x00\x00"):
            with self.assertRaises(ValueError):
                decode_body("in", 22025, body)

    def test_creation_preserves_signed_argb_and_unicode_name(self):
        # Protobuf int32 -1 is encoded as a ten-byte sign-extended varint.
        appearance = b"\x08" + b"\xff" * 9 + b"\x01" + b"\x50\x00\x58\x03\x60\x01"
        name = "Prueba ñ".encode("utf-8")
        body = struct.pack(">qhB", -1, 2, len(name)) + name
        body += b"\x01" + struct.pack(">H", len(appearance)) + appearance
        result = decode_body("out", 22296, body)
        self.assertEqual(result["character_name"], "Prueba ñ")
        self.assertEqual(
            result["appearance"],
            {"skinColor": -1, "clothIndex": 0, "faceIndex": 3, "sex": 1},
        )
        with self.assertRaises(ValueError):
            decode_body("out", 22296, body[:-1])

    def test_malformed_appearance_is_rejected(self):
        for body in (b"\x08\x80", b"\x08" + b"\x80" * 10, b"\x0a\x00", b"\x00\x00"):
            with self.assertRaises(ValueError):
                decode_appearance(body)
