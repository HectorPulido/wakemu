import struct
import unittest

from wakfu_server.items.socket_enchantment_wire import (
    bonus_installation_packets,
    encode_failure,
    encode_success,
    packets,
)
from wakfu_server.wire import proto_field, proto_fields
from wakfu_server.inventory_shards import initialized_wire_state


class SocketEnchantmentWireTests(unittest.TestCase):
    def test_action_results_match_native_opcode_enum_pairs(self):
        state = proto_field(10, proto_field(80, 0) + proto_field(96, 3)) + proto_field(
            72, 2
        )
        expected_state = initialized_wire_state(state)
        cases = {
            "add_charges": (13703, 0),
            "add_slot": (13703, 1),
            "change_slot_color": (13703, 2),
            "increase_count": (12920, 0),
            "change_colors": (12920, 1),
            "change_order": (12920, 2),
        }
        for operation, (expected_opcode, expected_action) in cases.items():
            with self.subTest(operation=operation):
                opcode, body = encode_success(
                    123, {"uid": 456, "operation": operation, "shard_state": state}
                )
                self.assertEqual(opcode, expected_opcode)
                status, character_id, uid, length = struct.unpack(">BqqH", body[:19])
                self.assertEqual(
                    (status, character_id, uid, length),
                    (0, 123, 456, len(expected_state)),
                )
                self.assertEqual(body[19:-1], expected_state)
                self.assertEqual(body[-1], expected_action)

    def test_sublimation_replacement_responses_have_no_action_suffix(self):
        state = proto_field(10, proto_field(80, 0) + proto_field(96, 1))
        for operation, expected_opcode in (
            ("apply_sublimation", 13983),
            ("remove_sublimation", 13793),
        ):
            with self.subTest(operation=operation):
                opcode, body = encode_success(
                    12, {"uid": 34, "operation": operation, "shard_state": state}
                )
                self.assertEqual(opcode, expected_opcode)
                self.assertEqual(body[19:], initialized_wire_state(state))

    def test_native_failure_is_one_status_byte_and_maps_to_matching_response_class(
        self,
    ):
        for request, response in (
            (12365, 13703),
            (13257, 12920),
            (12221, 13983),
            (12364, 13793),
        ):
            self.assertEqual(encode_failure(request, 1), (response, b"\x01"))
        with self.assertRaisesRegex(ValueError, "status"):
            encode_failure(12365, 0)
        with self.assertRaisesRegex(ValueError, "opcode"):
            encode_failure(13269, 6)

    def test_rejects_invalid_ids_and_oversized_native_signed_short(self):
        state = proto_field(10, proto_field(80, 0) + proto_field(96, 1))
        with self.assertRaisesRegex(ValueError, "character ID"):
            encode_success(
                0, {"uid": 2, "operation": "add_charges", "shard_state": state}
            )
        with self.assertRaisesRegex(ValueError, "item"):
            encode_success(
                1, {"uid": 0, "operation": "add_charges", "shard_state": state}
            )
        with self.assertRaisesRegex(ValueError, "item"):
            encode_success(
                1,
                {"uid": 2, "operation": "add_charges", "shard_state": b"\x00" * 32768},
            )

    def test_packet_sequence_refreshes_bags_and_wallet_after_response(self):
        state = proto_field(10, proto_field(80, 0) + proto_field(96, 1))
        result = {
            "uid": 2,
            "operation": "add_charges",
            "shard_state": state,
            "inventory_packet": (13713, struct.pack(">qB", 1, 35) + b"bags"),
            "cost_kamas": 5,
            "wallet_kamas": 95,
        }
        output = packets(1, result)
        self.assertEqual([opcode for opcode, _ in output], [13703, 13713, 12753])
        self.assertEqual(output[1][1], result["inventory_packet"][1])
        self.assertEqual(len(output[2][1]), 8)

    def test_13269_refreshes_reserve_then_native_socket_window_without_action_enum(
        self,
    ):
        bag = (13713, struct.pack(">qB", 123, 35) + b"authoritative-bags")
        state = proto_field(
            10,
            proto_field(80, 0)
            + proto_field(96, 3)
            + proto_field(88, 27094)
            + proto_field(112, 1),
        )
        result = {
            "uid": 456,
            "shard_state": state,
            "elements": bytes((2, 0)),
            "inventory_packet": bag,
            "cost_kamas": 0,
            "wallet_kamas": 100,
        }
        output = bonus_installation_packets(123, result)
        self.assertEqual([opcode for opcode, _ in output], [13713, 13766])
        self.assertEqual(output[0], bag)
        self.assertEqual(struct.unpack(">iqBI", output[1][1][:17]), (0, 456, 0, 2))
        self.assertEqual(output[1][1][17:19], bytes((2, 0)))
        state_length = struct.unpack(">I", output[1][1][19:23])[0]
        self.assertEqual(output[1][1][23:], initialized_wire_state(state))
        self.assertEqual(state_length, len(output[1][1][23:]))
        result["cost_kamas"] = 5
        result["wallet_kamas"] = 95
        self.assertEqual(
            [opcode for opcode, _ in bonus_installation_packets(123, result)],
            [13713, 13766, 12753],
        )


if __name__ == "__main__":
    unittest.main()
