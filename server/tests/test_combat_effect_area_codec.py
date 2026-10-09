import unittest
from wakfu_server.combat_effect_area_codec import area_payload, area_application
from wakfu_server.wire import proto_fields

TIME = bytes.fromhex("08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01")


class NativeEffectAreaCodecTests(unittest.TestCase):
    def test_actual_eYW_inherits_eYQ_packet_layout(self):
        args = dict(
            uid=902,
            base_uid=None,
            effect_reference=160582,
            area_reference=778,
            area_uid=901,
            level=1,
            keep_after=True,
            direction=None,
            caster_id=7,
            cell=(2, -3, 4),
            timing_payload=TIME,
        )
        trap = area_application(1, 2, effect_class=308, **args)
        baseline = area_application(1, 2, effect_class=315, **args)
        import struct

        self.assertEqual(trap[0], baseline[0])
        self.assertEqual(
            struct.unpack(">iiiih", trap[1][:18]), (1, 2, -1, 308, len(trap[1]) - 18)
        )
        self.assertEqual(
            struct.unpack(">iiiih", baseline[1][:18]),
            (1, 2, -1, 315, len(baseline[1]) - 18),
        )
        self.assertEqual(trap[1][18:], baseline[1][18:])

    def test_actual_eYQ_canonical_bytes(self):
        body = area_payload(
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
            timing_payload=TIME,
        )
        self.assertEqual(
            body.hex(),
            "088607108607187b208a0c2a0f080210fdffffffffffffffff0118043007421570018001ffffffffffffffffff01880101a80185075a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012801",
        )
        self.assertNotIn(98, dict(proto_fields(body)))

    def test_area_and_context_namespaces_are_separate(self):
        args = dict(
            uid=902,
            base_uid=None,
            effect_reference=123,
            area_reference=1546,
            area_uid=901,
            level=0,
            keep_after=True,
            direction=3,
            caster_id=7,
            cell=(2, -3, 4),
            timing_payload=TIME,
        )
        fields = dict(proto_fields(area_payload(**args, context_payload=b"\x08\x01")))
        self.assertEqual(fields[106], b"\x08\x01")
        with self.assertRaises(ValueError):
            area_payload(**dict(args, direction=8))


class OwnedHourAreaTests(unittest.TestCase):
    def test_manager_removal_does_not_invoke_owner_cleanup(self):
        from types import SimpleNamespace
        from wakfu_server.combat_effect_area import remove_owned_hour_area

        fight = SimpleNamespace(
            native_effect_areas={
                1: dict(uid=1, cell=(2, 3, 0), owner_id=7, native_hour_contract=True),
                2: dict(uid=2, cell=(2, 3, 0), owner_id=7, native_hour_contract=True),
                3: dict(uid=3, cell=(2, 3, 1), owner_id=7, native_hour_contract=True),
                4: dict(uid=4, cell=(2, 3, 0), owner_id=8, native_hour_contract=True),
            }
        )
        removed = remove_owned_hour_area(fight, 1)
        self.assertEqual({r["uid"] for r in removed}, {1})
        self.assertEqual(set(fight.native_effect_areas), {2, 3, 4})
        self.assertEqual(remove_owned_hour_area(fight, 1), ())

    def test_unaudited_primary_removal_keeps_original(self):
        from types import SimpleNamespace
        from wakfu_server.combat_effect_area import remove_owned_hour_area

        fight = SimpleNamespace(
            native_effect_areas={
                1: dict(uid=1, cell=(2, 3, 0), owner_id=7, native_hour_contract=True),
                2: dict(uid=2, cell=(2, 3, 0), owner_id=7, native_hour_contract=False),
            }
        )
        with self.assertRaises(ValueError):
            remove_owned_hour_area(fight, 2)
        self.assertEqual(set(fight.native_effect_areas), {1, 2})
