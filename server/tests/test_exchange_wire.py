import copy
import struct
import unittest

from wakfu_server import exchange_wire


EXCHANGE = 0x1122334455667788
UID = 67890


class ExchangeWireTests(unittest.TestCase):
    def test_offer_and_quantity_update_keep_uid_before_exchange_id(self):
        # coA/13037 and coF/12203 native ByteBuffer.putLong UID, putLong
        # exchangeId, putShort quantity (trade-request-codecs javap fixture).
        fixture = bytes.fromhex("0000000000010932 00000000000001c8 0002")
        self.assertEqual(
            exchange_wire.request(13037, fixture),
            {"uid": UID, "exchange_id": 456, "quantity": 2},
        )
        self.assertEqual(
            exchange_wire.request(12203, fixture),
            {"uid": UID, "exchange_id": 456, "quantity": 2},
        )

    def test_item_quantities_are_signed_short_and_keep_wire_boundaries(self):
        for opcode in (13037, 12203):
            body = struct.pack(">qqh", UID, 456, 32767)
            self.assertEqual(exchange_wire.request(opcode, body)["quantity"], 32767)
            for quantity in (-32768, -1):
                with self.subTest(
                    opcode=opcode, quantity=quantity
                ), self.assertRaisesRegex(ValueError, "quantity"):
                    exchange_wire.request(
                        opcode, struct.pack(">qqh", UID, 456, quantity)
                    )

    def test_quantity_update_zero_is_a_valid_native_short_value(self):
        # The coF serializer stores the UI's dhK.coe() value with i2s and
        # ByteBuffer.putShort; it contains no positivity guard. Keep zero as a
        # decoded wire value so a later exchange-state layer can decide its
        # meaning rather than rejecting a value the native encoder can emit.
        fixture = bytes.fromhex("0000000000010932 00000000000001c8 0000")
        self.assertEqual(
            exchange_wire.request(12203, fixture),
            {"uid": UID, "exchange_id": 456, "quantity": 0},
        )

    def test_item_request_rejects_bad_ids_wrong_lengths_and_nonbytes(self):
        for opcode in (13037, 12203):
            for uid, exchange_id in ((0, 1), (-1, 1), (1, 0), (1, -1)):
                with self.subTest(
                    opcode=opcode, uid=uid, exchange_id=exchange_id
                ), self.assertRaises(ValueError):
                    exchange_wire.request(
                        opcode, struct.pack(">qqh", uid, exchange_id, 1)
                    )
            for body in (b"", bytes(17), bytes(19), bytearray(18)):
                with self.subTest(
                    opcode=opcode, body=bytes(body).hex()
                ), self.assertRaises(ValueError):
                    exchange_wire.request(opcode, body)

    def test_withdrawal_count_uids_and_duplicates_match_coB_layout(self):
        # coB writes exchange i64, list size i32, then each UID i64.
        body = bytes.fromhex(
            "00000000000001c8 00000002 0000000000010932 00000000000181cd"
        )
        self.assertEqual(
            exchange_wire.request(13113, body),
            {"exchange_id": 456, "uids": [67890, 98765]},
        )
        malformed = (
            struct.pack(">qi", 456, 0),
            struct.pack(">qi", 456, -1),
            struct.pack(">qiQQ", 456, 2, UID, UID),
            struct.pack(">qiQQ", 456, 2, UID, 0),
            struct.pack(">qiQ", 456, 1, UID) + b"\x00",
            struct.pack(">qiQ", 456, 2, UID),
            struct.pack(">qiQ", 0, 1, UID),
            struct.pack(">qiQ", -1, 1, UID),
        )
        for invalid in malformed:
            with self.subTest(body=invalid.hex()), self.assertRaises(ValueError):
                exchange_wire.request(13113, invalid)

    def test_bulk_offer_count_and_uid_list_match_coG_layout(self):
        # coG writes exchange i64, selected count i32, then full-stack UIDs i64.
        body = struct.pack(">qiqq", 456, 2, 67890, 98765)
        self.assertEqual(
            exchange_wire.request(12510, body),
            {"exchange_id": 456, "uids": [67890, 98765]},
        )
        malformed = (
            struct.pack(">qi", 456, 0),
            struct.pack(">qi", 456, -1),
            struct.pack(">qi", 456, 129),
            struct.pack(">qiQQ", 456, 2, UID, UID),
            struct.pack(">qiQQ", 456, 2, UID, 0),
            struct.pack(">qiQ", 456, 1, UID) + b"\x00",
            struct.pack(">qiQ", 456, 2, UID),
            struct.pack(">qiQ", 0, 1, UID),
            struct.pack(">qiQ", -1, 1, UID),
        )
        for invalid in malformed:
            with self.subTest(body=invalid.hex()), self.assertRaises(ValueError):
                exchange_wire.request(12510, invalid)

    def test_confirmation_has_only_exchange_id_and_no_revision(self):
        fixture = bytes.fromhex("1122334455667788")
        self.assertEqual(
            exchange_wire.request(13406, fixture), {"exchange_id": EXCHANGE}
        )
        for invalid in (
            fixture[:-1],
            fixture + b"\x00",
            bytes(8),
            struct.pack(">q", -1),
        ):
            with self.subTest(body=invalid.hex()), self.assertRaises(ValueError):
                exchange_wire.request(13406, invalid)

    def test_server_carriers_match_native_field_offsets_and_status_range(self):
        self.assertEqual(
            exchange_wire.proposed(EXCHANGE, 1234567890123456789),
            (12538, bytes.fromhex("1122334455667788 112210f47de98115")),
        )
        self.assertEqual(
            exchange_wire.status(EXCHANGE, 0, 1234567890123456789, 0x0102030405060708),
            (
                13535,
                bytes.fromhex("1122334455667788 00 112210f47de98115 0102030405060708"),
            ),
        )
        for status in range(5):
            packet = exchange_wire.status(EXCHANGE, status, 7, 8)
            self.assertEqual(packet[0], 13535)
            self.assertEqual(packet[1][8], status)
        for status in (-1, 5, True):
            with self.subTest(status=status), self.assertRaisesRegex(
                ValueError, "status"
            ):
                exchange_wire.status(EXCHANGE, status, 7, 8)
        for identity in (0, -1, 1 << 63, True):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                exchange_wire.proposed(EXCHANGE, identity)

    def test_native_ready_and_closed_carriers_are_byte_exact_and_strict(self):
        actor = 0x0102030405060708
        self.assertEqual(
            exchange_wire.ready(EXCHANGE, actor, True),
            (13486, bytes.fromhex("1122334455667788 0102030405060708 01")),
        )
        self.assertEqual(
            exchange_wire.ready(EXCHANGE, actor, False),
            (13486, bytes.fromhex("1122334455667788 0102030405060708 00")),
        )
        for confirmed in (0, 1, None, "true"):
            with self.subTest(confirmed=confirmed), self.assertRaisesRegex(
                ValueError, "readiness"
            ):
                exchange_wire.ready(EXCHANGE, actor, confirmed)
        for exchange_id, actor_id in (
            (0, actor),
            (-1, actor),
            (EXCHANGE, 0),
            (EXCHANGE, 1 << 63),
            (EXCHANGE, True),
        ):
            with self.subTest(
                exchange_id=exchange_id, actor_id=actor_id
            ), self.assertRaises(ValueError):
                exchange_wire.ready(exchange_id, actor_id, True)

        for result in range(4):
            self.assertEqual(
                exchange_wire.closed(EXCHANGE, result),
                (12235, struct.pack(">qB", EXCHANGE, result)),
            )
        for result in (-1, 4, True, 1.0):
            with self.subTest(result=result), self.assertRaisesRegex(
                ValueError, "closure"
            ):
                exchange_wire.closed(EXCHANGE, result)

    def test_invitation_result_maps_native_zero_one_and_rejects_other_branches(self):
        accepted = struct.pack(">qB", EXCHANGE, 0)
        declined = struct.pack(">qB", EXCHANGE, 1)
        self.assertEqual(
            exchange_wire.invitation_answer(accepted),
            {"exchange_id": EXCHANGE, "accepted": True},
        )
        self.assertEqual(
            exchange_wire.invitation_answer(declined),
            {"exchange_id": EXCHANGE, "accepted": False},
        )
        for result in (2, 3, 4, 255):
            with self.subTest(result=result), self.assertRaisesRegex(
                ValueError, "invitation"
            ):
                exchange_wire.invitation_answer(struct.pack(">qB", EXCHANGE, result))
        for invalid in (accepted[:-1], accepted + b"\0", struct.pack(">qB", 0, 0)):
            with self.subTest(body=invalid.hex()), self.assertRaises(ValueError):
                exchange_wire.invitation_answer(invalid)

    def test_invitation_action_result_one_depends_on_sender_role(self):
        self.assertEqual(
            exchange_wire.invitation_action(
                struct.pack(">qB", EXCHANGE, 0), actor_is_inviter=False
            ),
            {"exchange_id": EXCHANGE, "action": "accept"},
        )
        self.assertEqual(
            exchange_wire.invitation_action(
                struct.pack(">qB", EXCHANGE, 1), actor_is_inviter=False
            ),
            {"exchange_id": EXCHANGE, "action": "decline"},
        )
        # Captured inviter UI cancellation emits result1; another native
        # cancellation path (bup) emits result4. Both are role checked later.
        self.assertEqual(
            exchange_wire.invitation_action(
                struct.pack(">qB", EXCHANGE, 1), actor_is_inviter=True
            ),
            {"exchange_id": EXCHANGE, "action": "cancel"},
        )
        self.assertEqual(
            exchange_wire.invitation_action(
                struct.pack(">qB", EXCHANGE, 4), actor_is_inviter=True
            ),
            {"exchange_id": EXCHANGE, "action": "cancel"},
        )
        self.assertEqual(
            exchange_wire.invitation_action(
                struct.pack(">qB", EXCHANGE, 4), actor_is_inviter=False
            ),
            {"exchange_id": EXCHANGE, "action": "cancel"},
        )
        for result in (2, 3, 5, 255):
            with self.subTest(result=result), self.assertRaisesRegex(
                ValueError, "action"
            ):
                exchange_wire.invitation_action(
                    struct.pack(">qB", EXCHANGE, result), actor_is_inviter=True
                )
        for actor_is_inviter in (None, 0, 1):
            with self.subTest(
                actor_is_inviter=actor_is_inviter
            ), self.assertRaisesRegex(ValueError, "role"):
                exchange_wire.invitation_action(
                    struct.pack(">qB", EXCHANGE, 1), actor_is_inviter=actor_is_inviter
                )

    def test_captured_inviter_cancel_body_0901_keeps_exchange_id_variable(self):
        # Captured coD/12997 request: exchange ID 9 followed by result1.
        # The exchange identity is data, not a fixed opcode-specific constant.
        captured_body = bytes.fromhex("0000000000000009 01")
        self.assertEqual(
            exchange_wire.invitation_action(captured_body, actor_is_inviter=True),
            {"exchange_id": 9, "action": "cancel"},
        )
        other_exchange_id = 0x0102030405060708
        variable_body = struct.pack(">q", other_exchange_id) + captured_body[-1:]
        self.assertEqual(
            exchange_wire.invitation_action(variable_body, actor_is_inviter=True),
            {"exchange_id": other_exchange_id, "action": "cancel"},
        )

    def test_native_cash_and_plain_or_element_item_carriers(self):
        actor = 1234567890123
        self.assertEqual(
            exchange_wire.cash(EXCHANGE, actor, 987654321),
            (13412, struct.pack(">qqBq", EXCHANGE, actor, 0, 987654321)),
        )
        for result in (0, 1, 2, 3, 4, 5, 10):
            self.assertEqual(
                exchange_wire.cash(EXCHANGE, actor, 0, result=result)[1][16], result
            )
        for result in (-1, 6, 9, 11, True):
            with self.subTest(result=result), self.assertRaisesRegex(
                ValueError, "result"
            ):
                exchange_wire.cash(EXCHANGE, actor, 1, result=result)
        for amount in (-1, 1 << 63, True):
            with self.subTest(amount=amount), self.assertRaisesRegex(
                ValueError, "cash"
            ):
                exchange_wire.cash(EXCHANGE, actor, amount)

        unit = {"uid": UID, "reference": 12, "quantity": 2}
        plain = (
            struct.pack(">qqBh", EXCHANGE, actor, 0, 2)
            + struct.pack(">qih", UID, 12, 2)
            + bytes(8)
        )
        self.assertEqual(exchange_wire.item(EXCHANGE, actor, unit, 2), (13636, plain))
        self.assertEqual(
            exchange_wire.item(EXCHANGE, actor, unit, 2, removed=True), (13084, plain)
        )
        elements = {**unit, "damage_elements": 2, "resistance_elements": 16}
        element_form = (
            struct.pack(">qqBh", EXCHANGE, actor, 0, 2)
            + struct.pack(">qih", UID, 12, 2)
            + bytes.fromhex("00000000000102100000")
        )
        self.assertEqual(
            exchange_wire.item(EXCHANGE, actor, elements, 2), (13636, element_form)
        )
        self.assertEqual(
            exchange_wire.item(EXCHANGE, actor, elements, 1, result=10)[1][16], 10
        )
        for quantity in (0, -1, 32768, True):
            with self.subTest(quantity=quantity), self.assertRaisesRegex(
                ValueError, "quantity"
            ):
                exchange_wire.item(EXCHANGE, actor, unit, quantity)
        for item_unit in (
            None,
            {**unit, "mount": {}},
            {**unit, "damage_elements": 1, "resistance_elements": 0},
        ):
            with self.subTest(item_unit=item_unit), self.assertRaises(ValueError):
                exchange_wire.item(EXCHANGE, actor, item_unit, 1)

    def test_mount_uses_validated_basic_vj_carrier_and_keeps_full_state_unchanged(self):
        actor = 1234567890123
        mount = {
            "uid": UID,
            "reference": 14422,
            "quantity": 1,
            "mount": {
                "model_id": 88,
                "definition_id": 88,
                "name": "Exchange mount",
                "xp": 321,
                "health": 19,
                "color_item_ref": 8,
                "equipped_item_ref": 9,
                "sleep_item_ref": 0,
                "reskin_item_ref": 0,
                "last_meal_date": 123000,
                "last_hungry_date": 456000,
                "sleep_date": 0,
                "revision": 4,
            },
        }
        before = copy.deepcopy(mount)
        expected = (
            struct.pack(">qqBh", EXCHANGE, actor, 0, 1)
            + struct.pack(">qih", UID, 14422, 1)
            + bytes(8)
        )
        self.assertEqual(
            (13636, expected), exchange_wire.item(EXCHANGE, actor, mount, 1)
        )
        self.assertEqual(before, mount)
        with self.assertRaisesRegex(ValueError, "unstacked"):
            exchange_wire.item(EXCHANGE, actor, {**mount, "quantity": 2}, 2)


if __name__ == "__main__":
    unittest.main()
