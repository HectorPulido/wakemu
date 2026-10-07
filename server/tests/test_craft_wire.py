import struct
import unittest

from wakfu_server import craft_wire


class CraftWireTests(unittest.TestCase):
    def test_native_ordinary_recipe_fixture_decodes_exactly(self):
        # CraftRequestProbe: table UID 31515, recipe 123, quantity 2.
        body = bytes.fromhex("0000000000007b1b0000007b00000002")
        self.assertEqual(16, len(body))
        self.assertEqual(
            {"table_id": 31515, "recipe_id": 123, "quantity": 2},
            craft_wire.request(12231, body),
        )
        self.assertEqual(body, struct.pack(">qii", 31515, 123, 2))

    def test_exact_integer_boundaries_are_decoded_without_narrowing(self):
        body = struct.pack(">qii", (1 << 63) - 1, (1 << 31) - 1, (1 << 31) - 1)
        self.assertEqual(
            {
                "table_id": (1 << 63) - 1,
                "recipe_id": (1 << 31) - 1,
                "quantity": (1 << 31) - 1,
            },
            craft_wire.request(12231, body),
        )

    def test_truncated_and_trailing_bytes_are_rejected(self):
        valid = struct.pack(">qii", 31515, 123, 2)
        for body in (valid[:-1], valid + b"\x00"):
            with self.subTest(length=len(body)):
                with self.assertRaisesRegex(ValueError, "length"):
                    craft_wire.request(12231, body)

    def test_non_bytes_body_types_are_rejected(self):
        valid = struct.pack(">qii", 31515, 123, 2)
        for body in (bytearray(valid), memoryview(valid), list(valid), None):
            with self.subTest(body_type=type(body).__name__):
                with self.assertRaisesRegex(ValueError, "length"):
                    craft_wire.request(12231, body)

    def test_nonpositive_table_recipe_or_quantity_are_rejected(self):
        for values in (
            (0, 123, 2),
            (-1, 123, 2),
            (31515, 0, 2),
            (31515, -1, 2),
            (31515, 123, 0),
            (31515, 123, -1),
        ):
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, "identity or quantity"):
                    craft_wire.request(12231, struct.pack(">qii", *values))

    def test_only_verified_ordinary_recipe_opcode_is_supported(self):
        body = struct.pack(">qii", 31515, 123, 2)
        for opcode in (12230, 12232, 13515, 0, True, "12231"):
            with self.subTest(opcode=opcode):
                with self.assertRaisesRegex(
                    ValueError, "Unsupported crafting request mode"
                ):
                    craft_wire.request(opcode, body)

    def test_native_occupation_request_preserves_component_map_and_mode(self):
        body = struct.pack(">qibihih", 31517, 3600, 0, 2504, 10, 11451, 10)
        self.assertEqual(
            {
                "table_id": 31517,
                "recipe_id": 3600,
                "mode": 0,
                "components": {2504: 10, 11451: 10},
            },
            craft_wire.occupation_request(body),
        )

    def test_native_occupation_request_rejects_malformed_or_duplicate_components(self):
        valid = struct.pack(">qibih", 31517, 3600, 0, 2504, 5)
        for body in (valid[:-1], valid + b"\x00", bytearray(valid), memoryview(valid)):
            with self.subTest(body_type=type(body).__name__, length=len(body)):
                with self.assertRaisesRegex(ValueError, "occupation request length"):
                    craft_wire.occupation_request(body)
        duplicate = struct.pack(">qibihih", 31517, 3600, 0, 2504, 5, 2504, 5)
        with self.assertRaisesRegex(ValueError, "occupation component"):
            craft_wire.occupation_request(duplicate)

    def test_native_occupation_start_packet_uses_duration_and_opaque_final_i64(self):
        self.assertEqual(
            (13989, struct.pack(">qibqq", 31517, 3600, 0, 1500, 0)),
            craft_wire.occupation_started(31517, 3600, 0, 1500),
        )

    def test_native_completion_and_cancellation_statuses_are_distinct(self):
        self.assertEqual(
            {"result": 2, "occupation_type": 8},
            craft_wire.completion_request(bytes.fromhex("020008")),
        )
        with self.assertRaisesRegex(
            ValueError, "Unsupported crafting occupation result"
        ):
            craft_wire.completion_request(bytes.fromhex("030008"))

    def test_native_result_layout_and_boundaries_are_byte_exact(self):
        self.assertEqual(
            (13479, bytes.fromhex("00000000000000")),
            craft_wire.result(0, 0, 0),
        )
        self.assertEqual(
            (13479, bytes.fromhex("167fffffff7fff")),
            craft_wire.result(22, (1 << 31) - 1, 32767),
        )
        self.assertEqual(
            (13479, bytes.fromhex("00800000000000")),
            craft_wire.result(0, -(1 << 31), 0),
        )

    def test_native_result_rejects_invalid_enum_auxiliary_and_count_types(self):
        for status in (-1, len(craft_wire.RESULTS), True):
            with self.subTest(status=status):
                with self.assertRaisesRegex(ValueError, "native crafting result"):
                    craft_wire.result(status, 0, 1)
        for auxiliary in (-(1 << 31) - 1, 1 << 31, True):
            with self.subTest(auxiliary=auxiliary):
                with self.assertRaisesRegex(ValueError, "auxiliary field"):
                    craft_wire.result(0, auxiliary, 1)
        for count in (-1, 32768, True):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "processed count"):
                    craft_wire.result(0, 0, count)

    def test_native_crafting_cancellation_fixture_is_exactly_three_bytes(self):
        body = bytes.fromhex("030008")
        self.assertEqual(
            {"result": 3, "occupation_type": 8},
            craft_wire.cancellation(body),
        )

    def test_cancellation_rejects_completion_and_other_occupation_kinds(self):
        for body in (
            bytes.fromhex("020008"),  # Completion result is not cancellation.
            bytes.fromhex("030007"),
            bytes.fromhex("030009"),
            bytes.fromhex("0300ff"),
        ):
            with self.subTest(body=body.hex()):
                with self.assertRaisesRegex(
                    ValueError, "Unsupported crafting occupation result"
                ):
                    craft_wire.cancellation(body)

    def test_cancellation_rejects_truncated_trailing_and_nonbyte_payloads(self):
        valid = bytes.fromhex("030008")
        for body in (valid[:-1], valid + b"\x00", bytearray(valid), memoryview(valid)):
            with self.subTest(body_type=type(body).__name__, length=len(body)):
                with self.assertRaisesRegex(ValueError, "cancellation length"):
                    craft_wire.cancellation(body)


if __name__ == "__main__":
    unittest.main()
