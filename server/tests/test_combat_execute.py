import struct, unittest
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spells import encode_deck
from wakfu_server.combat_execute import execute_adjacent_cast


class TransactionalCastTests(unittest.TestCase):
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
        for actor in self.fight.actors.values():
            # Bare fresh combat fixture: no native AP-cost modifiers installed.
            actor.spell_ap_cost_modifiers = {}
        self.character = dict(id=7, account_id=9, breed=15, level=1, map_id=1134)
        self.monster = dict(id=-7, ref=5525, level=1, map_id=1134, wp=6)
        self.body = struct.pack(">qqiih", 7, (7 << 32) | 6266, 1, 0, 0)

    def execute(self, **kwargs):
        options = dict(
            wp_current=6,
            wp_maximum=6,
            action_id=1,
            effect_uid=1,
            critical_chance=0,
            running_effects=[],
            summons=[],
            bonuses={},
            mitigate=lambda damage, *a: damage,
        )
        options.update(kwargs)
        with patch("wakfu_server.combat_execute.static_visible", return_value=True):
            return execute_adjacent_cast(
                self.body,
                self.character,
                self.monster,
                self.fight,
                9,
                encode_deck([6266]),
                **options
            )

    def test_commit_resources_damage_and_owned_packets(self):
        result = self.execute()
        self.assertEqual((self.pc.ap, self.pc.mp, self.npc.hp), (2, 3, 15))
        self.assertEqual(
            [opcode for opcode, _ in result["packets"]], [12588, 12678, 12613]
        )
        self.assertEqual(result["damage"], 5)
        self.assertEqual(set(result["snapshots"]), {7, -7})

    def test_encoding_error_leaves_entire_fight_untouched(self):
        before = (
            self.pc.ap,
            self.pc.mp,
            self.npc.hp,
            len(self.fight.events),
            self.fight.phase,
        )
        with self.assertRaises(ValueError):
            self.execute(effect_uid=0)
        self.assertEqual(
            (
                self.pc.ap,
                self.pc.mp,
                self.npc.hp,
                len(self.fight.events),
                self.fight.phase,
            ),
            before,
        )

    def test_unknown_bonus_or_crit_rejects_before_mutation(self):
        for options in (dict(bonuses={"damage": 1}), dict(critical_chance=1)):
            with self.assertRaises(ValueError):
                self.execute(**options)
        self.assertEqual((self.pc.ap, self.npc.hp), (6, 20))

    def test_mp_loss_native_zero_resistance_complete_and_unknown_rejected(self):
        self.body = struct.pack(">qqiih", 7, (7 << 32) | 6261, 1, 0, 0)
        kwargs = dict(
            wp_current=6,
            wp_maximum=6,
            action_id=1,
            effect_uid=1,
            critical_chance=0,
            running_effects=[],
            summons=[],
            bonuses={},
            mitigate=lambda damage, *a: damage,
        )
        with patch("wakfu_server.combat_execute.static_visible", return_value=True):
            with self.assertRaises(ValueError):
                execute_adjacent_cast(
                    self.body,
                    self.character,
                    self.monster,
                    self.fight,
                    9,
                    encode_deck([6261]),
                    **kwargs
                )
            result = execute_adjacent_cast(
                self.body,
                self.character,
                self.monster,
                self.fight,
                9,
                encode_deck([6261]),
                mp_resistance_caster=0,
                mp_resistance_target=0,
                mp_immune=False,
                **kwargs
            )
        self.assertEqual(
            (self.pc.ap, self.npc.hp, self.npc.mp, self.npc.max_mp), (4, 18, 2, 3)
        )
        self.assertTrue(result["plan"]["complete"])
        self.assertEqual(len(result["packets"]), 4)

    def test_multiple_owned_npcs_selects_requested_target(self):
        from wakfu_server.combat_execute import selected_monster

        second = dict(self.monster, id=-201)
        self.assertIs(selected_monster([self.monster, second], -201), second)
        self.assertIs(
            selected_monster({-200: self.monster, -201: second}, self.monster["id"]),
            self.monster,
        )
        with self.assertRaises(ValueError):
            selected_monster([self.monster, self.monster], self.monster["id"])
        with self.assertRaises(ValueError):
            selected_monster([self.monster], -333)
