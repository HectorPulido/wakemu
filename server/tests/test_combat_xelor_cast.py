import struct
import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spells import encode_deck
from wakfu_server.combat_xelor_cast import execute_xelor754


class BareXelorCastTests(unittest.TestCase):
    def setUp(self):
        self.pc = Actor(7, 0, (0, 0, 0), 240, 6, 3, 10, 19, owner_id=9, controlled=True)
        self.npc = Actor(-7, 1, (2, 0, 0), 30, 3, 3, 0, 1)
        self.fight = Fight(
            1,
            [self.pc, self.npc],
            {(0, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )
        self.fight.ready(9)
        self.character = dict(id=7, account_id=9, breed=5, level=19, map_id=1134)
        self.monster = dict(id=-7, ref=5525, level=1, map_id=1134, wp=6)
        self.body = struct.pack(">qqiih", 7, (7 << 32) | 754, 2, 0, 0)

    def cast(self, **changes):
        options = dict(
            wp_current=6,
            wp_maximum=6,
            action_id=1,
            effect_uid=1,
            critical_chance=0,
            caster_running_effects=[],
            target_running_effects=[],
            caster_bonuses={},
            target_bonuses={},
            line_of_sight=lambda *a: True,
            mitigate=lambda d, *a: d,
        )
        options.update(changes)
        return execute_xelor754(
            self.body,
            self.character,
            [self.monster],
            self.fight,
            9,
            encode_deck([754]),
            **options
        )

    def test_native_point_fire_damage_and_ap4(self):
        result = self.cast()
        self.assertEqual((self.pc.ap, self.pc.mp, self.npc.hp), (2, 3, 18))
        self.assertEqual(
            [opcode for opcode, _ in result["packets"]], [12588, 12678, 12613]
        )

    def test_conditional_ap_and_state_unknown_are_rejected(self):
        self.pc.ap = 3
        with self.assertRaises(ValueError):
            self.cast()
        self.pc.ap = 6
        with self.assertRaises(ValueError):
            self.cast(caster_running_effects=[6759])
        self.assertEqual((self.pc.ap, self.npc.hp), (6, 30))

    def test_dynamic_los_and_failed_encoding_roll_back(self):
        for options in (dict(line_of_sight=lambda *a: False), dict(effect_uid=0)):
            with self.assertRaises(ValueError):
                self.cast(**options)
        self.assertEqual((self.pc.ap, self.npc.hp), (6, 30))
