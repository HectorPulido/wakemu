import unittest
from dataclasses import replace
from pathlib import Path
from wakfu_server.combat_captured_summon import CapturedSummonPlan
from wakfu_server.combat_captured_summon_codec import (
    CapturedDescriptor,
    captured_descriptor_blob,
    captured_summon_application,
)
from wakfu_server.combat_summon import SummonSpecification
from wakfu_server.characters.captured_roster import CapturedCreature


class CapturedSummonCodecTests(unittest.TestCase):
    def plan(self, name="owned"):
        entry = CapturedCreature(0, 5347, name)
        spec = SummonSpecification(5347, 200, False, 1, 0, "caster", -2)
        return CapturedSummonPlan(spec, 7, 0, 12345, name, entry, 0.75, 1.25, True)

    def test_original_ezs_vj_differential_all_nine_rows(self):
        rows = (
            (Path(__file__).parent / "fixtures/native-captured-summon-codec.txt")
            .read_text()
            .splitlines()
        )
        index = 0
        for name in ("", "owned", "Baliza é"):
            for hp in (1, -1, 32768):
                actual = captured_descriptor_blob(
                    self.plan(name),
                    CapturedDescriptor(hp, 7, -1, True),
                    obstacle_index=17,
                    caster_id=7,
                )
                self.assertEqual(actual.hex(), rows[index].split()[1])
                index += 1

    def test_family324_envelope_and_selected_slot_are_separate(self):
        plan = replace(self.plan(), selected_slot=9)
        blob = captured_descriptor_blob(
            plan, CapturedDescriptor(1, 7, -1, True), obstacle_index=17, caster_id=7
        )
        self.assertEqual(blob[-14], 9)
        number, body = captured_summon_application(
            1,
            2,
            plan=plan,
            descriptor=CapturedDescriptor(1, 7, -1, True),
            uid=3,
            base_uid=None,
            effect_reference=4,
            caster_id=7,
            cell=(1, 0, 0),
            obstacle_index=17,
            timing_payload=b"",
        )
        self.assertEqual(number, 12613)
        self.assertEqual(body[12], 1)
        self.assertEqual(int.from_bytes(body[13:17], "big"), 324)
        self.assertIn(blob, body)

    def test_missing_source_fields_and_owner_mismatch_reject(self):
        for descriptor in (
            None,
            CapturedDescriptor(1, 9, -1, True),
            CapturedDescriptor(1, 7, -1, None),
        ):
            with self.assertRaises(ValueError):
                captured_descriptor_blob(
                    self.plan(), descriptor, obstacle_index=17, caster_id=7
                )
