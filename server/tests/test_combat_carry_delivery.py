import unittest
from itertools import product

from wakfu_server.combat_carry_delivery import (
    native_carry_gate,
    native_throw_additional,
)


class NativeCarryDeliveryTests(unittest.TestCase):
    def test_native_throw_bytes_include_false_and_signed_coordinates(self):
        self.assertEqual(
            native_throw_additional((0, 0, 0), False).hex(), "7a06080010001800880100"
        )
        self.assertEqual(
            native_throw_additional((7, -9, -1), True).hex(),
            "7a18080710f7ffffffffffffffff0118ffffffffffffffffff01880101",
        )
        self.assertEqual(
            native_throw_additional((-2147483648, 2147483647, -32768), False).hex(),
            "7a1c0880808080f8ffffffff0110ffffffff07188080feffffffffffff01880100",
        )

    def test_native_256_guard_combinations(self):
        for flags in product((False, True), repeat=8):
            cannot, stabilized, ce, te, ca, ta, bypass, same = flags
            actual = native_carry_gate(
                target_is_ehh=True,
                caster_is_ehg=True,
                both_are_ehg_affiliations=True,
                target_cannot_be_carried=cannot,
                target_stabilized=stabilized,
                bypass_stabilization=bypass,
                caster_enemy_stabilized=ce,
                target_enemy_stabilized=te,
                caster_ally_stabilized=ca,
                target_ally_stabilized=ta,
                same_affiliation=same,
            )
            expected = not cannot and (
                bypass or (not stabilized and not ((ca or ta) if same else (ce or te)))
            )
            with self.subTest(flags=flags):
                self.assertEqual(actual, expected)

    def test_unknown_qcl_and_coordinates_reject(self):
        with self.assertRaises(ValueError):
            native_throw_additional((0, 0, 0), None)
        with self.assertRaises(ValueError):
            native_throw_additional((0, 0, 32768), False)

    def test_nullable_throw_and_actual_carry_full_payload(self):
        import struct
        from wakfu_server.combat_carry_delivery import (
            native_carry_payload,
            native_carry_packet,
        )
        from wakfu_server.wire import proto_fields

        for family, target in ((333, None), (334, -7)):
            payload = native_carry_payload(
                uid=1,
                base_uid=0,
                reference=22,
                family=family,
                caster_id=7,
                target_id=target,
                cell=(2, -1, 3),
                value=0,
                qcl=False,
                timing_payload=b"",
                context_payload=None,
            )
            fields = {tag >> 3: value for tag, value in proto_fields(payload)}
            self.assertEqual(fields.get(1), 1)
            self.assertEqual(fields.get(2), 0)
            self.assertEqual(
                fields.get(7), None if target is None else target & ((1 << 64) - 1)
            )
            self.assertIsNotNone(fields.get(5))
            self.assertEqual(
                {tag >> 3: value for tag, value in proto_fields(fields[11])}[2],
                (1 << 64) - 1,
            )
            opcode, packet = native_carry_packet(99, 1, payload, family=family)
            self.assertEqual(opcode, 12613)
            self.assertEqual(
                struct.unpack_from(">iiiBih", packet),
                (99, 1, -1, 0, family, len(payload)),
            )
            self.assertEqual(packet[19:], payload)
