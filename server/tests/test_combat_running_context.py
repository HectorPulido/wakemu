import unittest
from wakfu_server.combat_running_context import running_context_payload
from wakfu_server.combat_retained_runtime import group_payload
from wakfu_server.combat_summon_codec import summon_payload
from wakfu_server.combat_summon import SummonSpecification
from wakfu_server.wire import proto_fields

CONTEXT = bytes.fromhex("0801100020ffffffffffffffffff0128013000380040004800")
TIME = bytes.fromhex(
    "080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012801"
)


class NativeRunningContextTests(unittest.TestCase):
    def test_native_eYg_eVt_canonical_namespace(self):
        actual = group_payload(
            uid=901,
            base_uid=None,
            generic_effect=123,
            caster_id=7,
            target_id=-7,
            cell=(2, -3, 4),
            container_type=11,
            container_id=22,
            timing_payload=TIME,
            context_payload=CONTEXT,
        )
        # ProbeNativeRunningContext actual Qe.bca/eZR.c/eVt.fLV.
        self.assertEqual(
            actual.hex(),
            "088507108507187b20002a0f080210fdffffffffffffffff0118043007"
            "38f9ffffffffffffffff01480b50165a2b080010ffffffffffffffffff01"
            "1a0f080010ffffffffffffffffff01180020ffffffffffffffffff012801"
            "6a190801100020ffffffffffffffffff0128013000380040004800",
        )
        fields = dict(proto_fields(actual))
        self.assertEqual(fields[106], CONTEXT)
        self.assertNotIn(98, fields)

    def test_summon_uid_and_context_are_distinct_and_owner_paired(self):
        body = summon_payload(
            uid=902,
            base_uid=None,
            effect_reference=123,
            caster_id=7,
            cell=(2, -3, 4),
            specification=SummonSpecification(3251, 6, True, 3, 1, "current", -2),
            actor_id=901,
            obstacle_index=-1,
            properties=(),
            timing_payload=b"",
            container_type=11,
            container_id=22,
            context_payload=CONTEXT,
        )
        fields = dict(proto_fields(body))
        self.assertEqual(fields[98], bytes.fromhex("208507"))
        self.assertEqual(fields[106], CONTEXT)
        self.assertEqual((fields[72], fields[80]), (11, 22))
        with self.assertRaises(ValueError):
            running_context_payload(container_type=11)
