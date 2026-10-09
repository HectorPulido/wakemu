"""Configured eYQ actor and cell routing share the area serialization."""
import struct
import unittest
from wakfu_server.combat_effect_area_codec import area_application
from wakfu_server.wire import proto_fields


class ConfiguredAreaCodecTests(unittest.TestCase):
    def arguments(self):
        return dict(
            uid=902,
            base_uid=None,
            effect_reference=123,
            area_reference=1546,
            area_uid=901,
            level=1,
            keep_after=True,
            direction=None,
            caster_id=7,
            cell=(2, -3, 4),
            timing_payload=b"\x08\x00",
        )

    def test_actor_family_preserves_actual_target_and_cell(self):
        opcode, packet = area_application(
            1, 2, effect_class=314, target_id=8, **self.arguments()
        )
        self.assertEqual(opcode, 13497)
        self.assertEqual(struct.unpack(">iiiih", packet[:18])[3], 314)
        fields = dict(proto_fields(packet[18:]))
        self.assertEqual(fields[56], 8)
        self.assertIn(42, fields)

    def test_existing_cell_family_omits_target(self):
        _, packet = area_application(1, 2, **self.arguments())
        self.assertEqual(struct.unpack(">iiiih", packet[:18])[3], 315)
        self.assertNotIn(56, dict(proto_fields(packet[18:])))

    def test_cell_family_rejects_actor_recipient(self):
        with self.assertRaises(ValueError):
            area_application(1, 2, target_id=8, **self.arguments())

    def test_immediate_creation_executes_without_changing_retained_delivery(self):
        for family in (308, 315, 339, 1008):
            observed_opcode, observed = area_application(
                1, 2, effect_class=family, **self.arguments()
            )
            opcode, executed = area_application(
                1, 2, effect_class=family, execute_immediate=True, **self.arguments()
            )
            self.assertEqual(observed_opcode, 13497)
            self.assertEqual(opcode, 12613)
            self.assertEqual(executed[:12], observed[:12])
            self.assertEqual(executed[12], 1)
            self.assertEqual(executed[13:], observed[12:])
        with self.assertRaises(ValueError):
            area_application(1, 2, execute_immediate=None, **self.arguments())

    def test_other_runner_family_cannot_use_area_codec(self):
        with self.assertRaises(ValueError):
            area_application(1, 2, effect_class=307, **self.arguments())
