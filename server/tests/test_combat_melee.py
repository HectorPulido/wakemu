import struct
import unittest
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_melee import execute_unarmed, decode_request


class UnarmedTests(unittest.TestCase):
    def setUp(self):
        self.pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, owner_id=9, controlled=True)
        self.npc = Actor(-7, 1, (1, 0, 0), 20, 3, 3, 0, 1)
        self.fight = Fight(
            1,
            [self.pc, self.npc],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.fight.ready(9)
        self.character = dict(id=7, account_id=9, breed=15, level=1, map_id=1134)
        self.monster = dict(id=-7, ref=5525, level=1, map_id=1134, wp=6)
        self.body = struct.pack(">qqbiih", 7, -1, 15, 1, 0, 0)

    def run_attack(self, **changes):
        options = dict(
            unarmed=True,
            wp_current=6,
            wp_maximum=6,
            action_id=1,
            effect_uid=1,
            critical_chance=0,
            caster_running_effects=[],
            target_running_effects=[],
            caster_bonuses={},
            target_bonuses={},
            mitigate=lambda d, *a: d,
        )
        options.update(changes)
        with patch("wakfu_server.combat_execute.static_visible", return_value=True):
            return execute_unarmed(
                self.body, self.character, [self.monster], self.fight, 9, **options
            )

    def test_native_fists_cost_and_damage(self):
        result = self.run_attack()
        self.assertEqual((self.pc.ap, self.pc.mp, self.npc.hp), (3, 3, 17))
        self.assertEqual([p for p, _ in result["packets"]], [13509, 12613])
        self.assertEqual(set(result["snapshots"]), {7, -7})

    def test_failed_encoding_rolls_back(self):
        before = (self.pc.ap, self.npc.hp, len(self.fight.events))
        with self.assertRaises(ValueError):
            self.run_attack(effect_uid=0)
        self.assertEqual((self.pc.ap, self.npc.hp, len(self.fight.events)), before)

    def test_equipment_unknown_effects_and_short_request_rejected(self):
        for values in (
            dict(unarmed=False),
            dict(critical_chance=1),
            dict(target_running_effects=None),
        ):
            with self.assertRaises(ValueError):
                self.run_attack(**values)
        with self.assertRaises(ValueError):
            decode_request(self.body[:-1])
        self.assertEqual(self.pc.ap, 6)

    def test_insufficient_ap_does_not_damage(self):
        self.pc.ap = 2
        with self.assertRaises(ValueError):
            self.run_attack()
        self.assertEqual(self.npc.hp, 20)
