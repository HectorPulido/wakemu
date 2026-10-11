"""Prototype witness: existing eYQ serialization needs no global Qs registration."""
import unittest
from wakfu_server.combat.combat_effect_area_codec import area_payload
from wakfu_server.combat.combat_target_aura import target_aura_additional
from wakfu_server.wire import proto_fields


class ConstructorPrivateAreaCodecTests(unittest.TestCase):
    def fields(self, payload):
        return {tag >> 3: value for tag, value in proto_fields(payload)}

    def payload(self, **changes):
        values = dict(
            uid=101,
            base_uid=100,
            effect_reference=256225,
            area_reference=314,
            area_uid=102,
            level=1,
            keep_after=False,
            direction=None,
            caster_id=-200,
            target_id=-200,
            cell=(0, 0, 0),
            timing_payload=b"",
            status=-1,
            container_type=None,
            container_id=None,
        )
        values.update(changes)
        return self.fields(area_payload(**values))

    def test_private_area_identity_serializes_without_fight_or_global_manager(self):
        fields = self.payload()
        extra = self.fields(fields[8])
        self.assertEqual(extra[21], 102)
        self.assertEqual(extra[14], 1)
        self.assertEqual(extra[17], 0)
        self.assertEqual(extra[16], (1 << 64) - 1)
        timing = self.fields(fields[11])
        self.assertEqual(timing[2], (1 << 64) - 1)

    def test_private_shape_preserves_runner_status_and_constructor_options(self):
        fields = self.payload(level=3, keep_after=True, direction=4, status=7)
        extra = self.fields(fields[8])
        self.assertEqual((extra[14], extra[16], extra[17], extra[21]), (3, 4, 1, 102))
        self.assertEqual(self.fields(fields[11])[2], 7)

    def test_target_aura_extra_is_distinct_from_configured_area_extra(self):
        self.assertEqual(self.fields(target_aura_additional(102)), {21: 102})
        self.assertEqual(set(self.fields(self.payload()[8])), {14, 16, 17, 21})
