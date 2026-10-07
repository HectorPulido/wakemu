import struct
import unittest

from wakfu_server.items import recycling_wire


class RecyclingWireTests(unittest.TestCase):
    def test_native_recycle_request_has_short_count_then_uid_longs(self):
        # cnz.aWH writes count with ayq.aH(short), then each Long with aJ(long).
        fixture = bytes.fromhex("0002 0102030405060708 0000000000010932")
        expected = {"uids": [0x0102030405060708, 67890]}
        self.assertEqual(recycling_wire.decode_request(12787, fixture), expected)
        self.assertEqual(recycling_wire.request(expected["uids"]), (12787, fixture))

    def test_native_recycle_request_rejects_bad_count_length_and_opcode(self):
        cases = (
            b"",
            bytes.fromhex("0000"),
            bytes.fromhex("ffff"),
            bytes.fromhex("0002 0000000000000001"),
            bytes.fromhex("0001 0000000000000001 00"),
        )
        for body in cases:
            with self.subTest(body=body.hex()), self.assertRaises(ValueError):
                recycling_wire.decode_request(12787, body)
        with self.assertRaisesRegex(ValueError, "opcode"):
            recycling_wire.decode_request(12786, bytes.fromhex("0001 0000000000000001"))
        with self.assertRaisesRegex(ValueError, "length"):
            recycling_wire.decode_request(
                12787, bytearray.fromhex("0001 0000000000000001")
            )

    def test_recycle_request_rejects_invalid_or_duplicate_uids(self):
        bad_bodies = (
            struct.pack(">hQ", 1, 0),
            struct.pack(">hq", 1, -1),
            struct.pack(">hq", 1, -(2**63)),
            struct.pack(">hqq", 2, 12, 12),
        )
        for body in bad_bodies:
            with self.subTest(body=body.hex()), self.assertRaises(ValueError):
                recycling_wire.decode_request(12787, body)
        for uids in ([], [0], [-1], [1 << 63], [True], [42, 42], None):
            with self.subTest(uids=uids), self.assertRaises(ValueError):
                recycling_wire.request(uids)

    def test_request_count_uses_native_signed_short_limit(self):
        maximum = list(range(1, 32768))
        opcode, body = recycling_wire.request(maximum)
        self.assertEqual(opcode, 12787)
        self.assertEqual(len(body), 2 + 32767 * 8)
        self.assertEqual(struct.unpack_from(">h", body)[0], 32767)
        self.assertEqual(recycling_wire.decode_request(opcode, body)["uids"], maximum)
        with self.assertRaisesRegex(ValueError, "count"):
            recycling_wire.request(list(range(1, 32769)))

    def test_result_is_two_signed_i32_values_without_assumed_domain_meaning(self):
        # cwS.dp reads two ByteBuffer.getInt() fields, in network byte order.
        fixture = bytes.fromhex("00000002 00000007")
        self.assertEqual(
            recycling_wire.decode_result(12890, fixture),
            {
                "first": 2,
                "second": 7,
            },
        )
        self.assertEqual(recycling_wire.result(2, 7), (12890, fixture))
        self.assertEqual(
            recycling_wire.decode_result(12890, bytes.fromhex("ffffffff 80000000")),
            {
                "first": -1,
                "second": -(2**31),
            },
        )
        for value in (True, -(2**31) - 1, 2**31, 1.0):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "fields"
            ):
                recycling_wire.result(value, 0)
        for body in (b"", bytes(7), bytes(9), bytearray(8)):
            with self.subTest(body=bytes(body).hex()), self.assertRaises(ValueError):
                recycling_wire.decode_result(12890, body)
        with self.assertRaisesRegex(ValueError, "opcode"):
            recycling_wire.decode_result(12891, fixture)


if __name__ == "__main__":
    unittest.main()
