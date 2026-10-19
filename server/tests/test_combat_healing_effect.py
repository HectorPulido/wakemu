import struct
import unittest
from wakfu_server.combat_healing_effect import direct_healing
from wakfu_server.combat_damage_healing import consume_healing, HEAL_ELEMENTS
from wakfu_server.combat_effect_removal import _identity_fields


class HealingEffectTests(unittest.TestCase):
    def test_packet_uses_actual_heal_including_virtual_hp_without_overflow(self):
        result = consume_healing(
            30,
            target_hp=90,
            target_max_hp=100,
            target_virtual_hp=5,
            target_max_virtual_hp=20,
            undead=False,
            bypass_undead=False,
            frozen_stats=(),
        )
        for kind in HEAL_ELEMENTS:
            packet = direct_healing(
                77,
                1,
                uid=100,
                base_uid=99,
                generic_effect=123,
                effect_class=kind,
                caster_id=7,
                target_id=-7,
                restored=result["value"],
            )
            header = struct.unpack(">iiiBih", packet[:19])
            self.assertEqual(header[:5], (77, 1, -1, 0, kind))
            messages = {}
            fields = _identity_fields(packet[19:], messages=messages)
            self.assertEqual((fields[1], fields[2], fields[4]), (100, 99, 25))
            self.assertEqual(messages, {})
            self.assertEqual(header[5], len(packet) - 19)

    def test_invalid_healing_values_and_ids_rejected(self):
        args = dict(
            fight_id=77,
            action_id=1,
            uid=100,
            generic_effect=123,
            effect_class=25,
            caster_id=7,
            target_id=-7,
            restored=25,
        )
        for overrides in (
            dict(restored=-(1 << 31) - 1),
            dict(restored=1 << 31),
            dict(restored=True),
            dict(uid=0),
            dict(effect_class=1),
            dict(target_id=0),
            dict(base_uid=-1),
        ):
            with self.assertRaises(ValueError):
                direct_healing(**dict(args, **overrides))

    def test_signed_actual_healing_boundaries_round_trip_native_int32(self):
        from wakfu_server.wire import proto_fields

        for value in (-(1 << 31), -65, -1, 0, 1, (1 << 31) - 1):
            with self.subTest(value=value):
                packet = direct_healing(
                    77,
                    1,
                    uid=100,
                    generic_effect=123,
                    effect_class=25,
                    caster_id=7,
                    target_id=-7,
                    restored=value,
                )
                encoded = next(v for tag, v in proto_fields(packet[19:]) if tag == 32)
                actual = (encoded + (1 << 31)) % (1 << 32) - (1 << 31)
                self.assertEqual(actual, value)
