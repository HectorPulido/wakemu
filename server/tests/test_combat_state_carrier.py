import struct
import unittest
from wakfu_server.combat_effect_removal import running_effect_removal
from wakfu_server.combat_state_carrier import (
    state_carrier_payload,
    state_carrier_application,
)


class StateCarrierTests(unittest.TestCase):
    def test_parent_container_is_serialized_and_scope_does_not_leak(self):
        from wakfu_server.combat_running_container import running_container_scope
        from wakfu_server.combat_effect_removal import _identity_fields

        plain = state_carrier_payload(**self.parameters())
        with running_container_scope(
            {"container_present": True, "container_type": 11}, (4807 << 16) | 200
        ):
            payload = state_carrier_payload(**self.parameters())
        fields = _identity_fields(payload, integer_fields=(9, 10))
        self.assertEqual(fields, {9: 11, 10: (4807 << 16) | 200})
        self.assertEqual(state_carrier_payload(**self.parameters()), plain)

    def parameters(self):
        return dict(
            uid=2345,
            base_uid=1234,
            caster_id=22,
            target_id=-33,
            state_id=3442,
            level=1,
            native_turn_clock=-1,
            native_realtime_remaining=0,
        )

    def test_native_serialization_identity_fields_and_additional(self):
        payload = state_carrier_payload(**self.parameters())
        # Native ProbeStateCarrier output: omit its optional Position5/TimeDatas11.
        expected = bytes.fromhex(
            "08a91210d20918ffffffffffffffffff01208180c86b301638dfffffffffffffffff014223508180c86b68a912880100900100980100a801ffffffffffffffffff01b00100900300"
        )
        self.assertEqual(payload, expected)
        applied = state_carrier_application(
            7, 8, uid=2345, target_id=-33, running_effect_payload=payload
        )
        self.assertEqual(
            struct.unpack(">iiiBih", applied[:19]), (7, 8, -1, 0, 310, len(payload))
        )
        self.assertEqual(applied[19:], payload)
        removed = running_effect_removal(
            7,
            9,
            uid=2345,
            target_id=-33,
            effect_class=310,
            running_effect_payload=payload,
        )
        from wakfu_server.combat_effect_removal import state_unapplication_payload

        self.assertEqual(removed[18:-16], state_unapplication_payload(payload))
        self.assertTrue(removed[18:-16].endswith(b"\x5a\x02\x08\x01"))

    def test_removal_forces_notification_only_and_preserves_native_timing(self):
        from wakfu_server.combat_effect_removal import state_unapplication_payload

        timing = bytes.fromhex("080010ff011a0608091001180020132801")
        payload = state_carrier_payload(
            **dict(self.parameters(), timing_payload=timing)
        )
        removed = state_unapplication_payload(payload)
        expected_timing = b"\x08\x01" + timing[2:]
        self.assertEqual(removed, payload[: -len(timing)] + expected_timing)
        self.assertEqual(state_unapplication_payload(removed), removed)
        applied = state_carrier_application(
            7, 8, uid=2345, target_id=-33, running_effect_payload=payload
        )
        self.assertEqual(applied[19:], payload)

    def test_distinct_parent_uid_and_explicit_clocks(self):
        params = self.parameters()
        for overrides in [
            dict(related_uid=2345),
            dict(uid=True),
            dict(native_turn_clock=None),
            dict(native_realtime_remaining=-(1 << 63) - 1),
            dict(level=32768),
        ]:
            with self.assertRaises(ValueError):
                state_carrier_payload(**dict(params, **overrides))
        from wakfu_server.combat_effect_removal import _identity_fields

        fields = _identity_fields(state_carrier_payload(**dict(params, base_uid=None)))
        self.assertEqual((fields[1], fields[2]), (2345, 2345))

    def test_native_permanent_sacrier_realtime_value_is_not_normalized(self):
        from wakfu_server.combat_effects import _integer

        payload = state_carrier_payload(
            **dict(self.parameters(), state_id=3702, native_realtime_remaining=-1000)
        )
        self.assertIn(_integer(22, -1000), payload)
