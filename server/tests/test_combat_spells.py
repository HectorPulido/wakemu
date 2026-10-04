import struct
import unittest
from wakfu_server.combat_spells import base_costs, cast_animation, cast_notification
from wakfu_server.combat_effects import direct_damage


class CombatSpellWireTests(unittest.TestCase):
    character = dict(id=7, breed=15, level=1)

    def test_native_owned_costs_and_ownership(self):
        self.assertEqual(
            base_costs(self.character, 6260),
            dict(ap=3, mp=0, wp=0, conditional_rules=0),
        )
        with self.assertRaises(ValueError):
            base_costs(self.character, 4778)

    def test_distinct_native_cast_layouts(self):
        animation = cast_animation(1, 2, self.character, 6260, (3, 4, 0))
        notification = cast_notification(1, 2, self.character, 6260, (3, 4, 0))
        self.assertEqual(len(animation), 50)
        self.assertEqual(len(notification), 50)
        self.assertEqual(
            struct.unpack_from(">qih", animation, 20), ((7 << 32) | 6260, 6260, 1)
        )
        self.assertEqual(
            struct.unpack_from(">qih", notification, 26), ((7 << 32) | 6260, 6260, 1)
        )
        self.assertEqual(animation[-10:], struct.pack(">iih", 3, 4, 0))
        self.assertEqual(notification[-10:], animation[-10:])
        self.assertEqual(struct.unpack_from(">i", notification, 20)[0], 6260)

    def test_owned_damage_native_header_and_reject_invalid_state(self):
        wire = direct_damage(
            1,
            2,
            uid=1,
            generic_effect=339483,
            element=4,
            caster_id=7,
            target_id=-7,
            damage=3,
        )
        fight, action, sequence, flag, element, size = struct.unpack_from(
            ">iiiBih", wire
        )
        self.assertEqual((fight, action, sequence, flag, element), (1, 2, -1, 0, 4))
        self.assertEqual(size, len(wire) - 19)
        for damage in (-1, 1 << 31):
            with self.assertRaises(ValueError):
                direct_damage(
                    1,
                    2,
                    uid=1,
                    generic_effect=339483,
                    element=4,
                    caster_id=7,
                    target_id=-7,
                    damage=damage,
                )

    def test_absorption_packet_matches_native_resource_result(self):
        from wakfu_server.combat_damage_healing import consume_damage
        from wakfu_server.combat_effect_removal import _identity_fields

        result = consume_damage(
            101,
            source_barrier=15,
            target_armor=20,
            target_virtual_hp=30,
            target_hp=100,
            blocked=False,
            bypass_armor_and_barrier=False,
            frozen_stats=(),
        )
        wire = direct_damage(
            1,
            2,
            uid=3,
            generic_effect=339483,
            element=4,
            caster_id=7,
            target_id=-7,
            damage=result["value"],
            armor_absorbed=result["armor_absorbed"],
            barrier_absorbed=result["barrier_absorbed"],
        )
        messages = {}
        _identity_fields(wire[19:], messages=messages)
        fields = _identity_fields(messages[8], integer_fields=(10, 19, 25))
        self.assertEqual(fields, {10: 20, 19: 15})
        for invalid in (-1, True, 1 << 31):
            with self.assertRaises(ValueError):
                direct_damage(
                    1,
                    2,
                    uid=3,
                    generic_effect=339483,
                    element=4,
                    caster_id=7,
                    target_id=-7,
                    damage=101,
                    barrier_absorbed=invalid,
                )
