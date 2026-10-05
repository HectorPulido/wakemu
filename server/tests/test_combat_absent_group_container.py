import unittest
from wakfu_server.combat_retained_runtime import group_payload
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.wire import proto_fields


class AbsentGroupContainerTests(unittest.TestCase):
    def payload(self, kind, identity):
        return group_payload(
            uid=901,
            base_uid=800,
            generic_effect=350552,
            caster_id=7,
            target_id=-7,
            cell=(4, 5, 0),
            container_type=kind,
            container_id=identity,
            timing_payload=native_time_payload(),
        )

    def test_absent_container_matches_native_y_g_y_w_y_m_bytes(self):
        actual = self.payload(None, None)
        self.assertEqual(
            actual.hex(),
            "08850710a00618d8b21520002a06080410051800300738f9ffffffffffffffff015a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800",
        )
        fields = dict(proto_fields(actual))
        self.assertNotIn(72, fields)
        self.assertNotIn(80, fields)

    def test_present_container_keeps_fields_and_partial_absence_rejects(self):
        fields = dict(proto_fields(self.payload(11, 6266)))
        self.assertEqual((fields[72], fields[80]), (11, 6266))
        for kind, identity in ((None, 6266), (11, None), (True, 6266)):
            with self.assertRaises(ValueError):
                self.payload(kind, identity)
