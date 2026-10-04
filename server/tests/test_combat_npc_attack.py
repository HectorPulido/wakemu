import unittest, struct
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_npc_attack import ability, execute


class NativeNpcAttackTests(unittest.TestCase):
    def setUp(self):
        self.pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 1, owner_id=9, controlled=True)
        self.npc = Actor(-200, 1, (1, 0, 0), 20, 3, 3, 10, 1)
        self.fight = Fight(
            1,
            [self.pc, self.npc],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.fight.ready(9)
        self.monster = dict(id=-200, ref=5525, level=1, map_id=1134, wp=6)
        self.character = dict(id=7, account_id=9, breed=15, level=1, map_id=1134)

    def run_attack(self, **changes):
        kwargs = dict(
            action_id=1,
            effect_uid=1,
            player_wp_current=6,
            player_wp_maximum=6,
            critical_chance=0,
            caster_running_effects=[],
            target_running_effects=[],
            caster_bonuses={},
            target_bonuses={},
            mitigate=lambda damage, *args: damage,
        )
        kwargs.update(changes)
        with patch("wakfu_server.combat_npc_attack.static_visible", return_value=True):
            return execute(self.monster, self.character, self.fight, 7, **kwargs)

    def test_native_wonejo_reference_and_transacted_attack(self):
        rule = ability(self.monster)
        self.assertEqual((rule["spell_id"], rule["ap"], rule["damage"]), (7962, 0, 5))
        result = self.run_attack()
        self.assertEqual((self.pc.hp, self.npc.ap), (55, 3))
        wire = result["packets"][0][1]
        self.assertEqual(struct.unpack_from(">qih", wire, 20), (7962, 7962, 1))
        self.assertEqual(struct.unpack_from(">i", result["packets"][1][1], 20)[0], 7962)
        self.assertEqual(result["snapshots"][-200][19], 3)
        with self.assertRaises(ValueError):
            self.run_attack()

    def test_codec_failure_no_mutation(self):
        before = len(self.fight.events)
        with self.assertRaises(ValueError):
            self.run_attack(effect_uid=0)
        self.assertEqual(
            (self.pc.hp, self.npc.ap, len(self.fight.events)), (60, 3, before)
        )

    def test_unknown_actor_effects_rejected(self):
        with self.assertRaises(ValueError):
            self.run_attack(target_running_effects=None)
        with self.assertRaises(ValueError):
            ability(dict(ref=2, level=4))
