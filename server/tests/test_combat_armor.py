import unittest
from types import SimpleNamespace
from copy import deepcopy
from wakfu_server.combat_armor import armor_amount, NativeArmorHandler
from wakfu_server.combat_stat_handler import StatExecutionContext, NativeStatHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields


def actor(identity, position):
    return SimpleNamespace(
        id=identity,
        position=position,
        hp=100,
        max_hp=100,
        max_ap=6,
        max_mp=3,
        effect_stats={1: 100, 97: 10, 120: 50, 121: 20},
        effect_maxima={1: 100, 97: 1000000},
        effect_minima={97: 0},
        effect_frozen=frozenset(),
        physical_radius=0,
    )


class NativeArmorTests(unittest.TestCase):
    def setUp(self):
        self.source, self.target = actor(22, (0, 0, 0)), actor(-33, (1, 0, 0))
        self.effect = dict(
            effect_class=1013, parameters=[100, 0], variant=0, native_effect_flags=[]
        )

    def test_native_jar_coefficient_modes(self):
        for mode, expected in enumerate((100, 150, 120, 170)):
            effect = dict(self.effect, parameters=[100, 0, mode, 0])
            result = armor_amount(
                effect, 1, self.source, self.target, capped_player=False
            )
            self.assertEqual(result, dict(requested=expected, room=2147483637))
        self.assertEqual(
            armor_amount(self.effect, 1, self.source, self.source, capped_player=False)[
                "requested"
            ],
            120,
        )

    def test_player_cap_and_explicit_bypass(self):
        self.target.effect_stats[88] = 50
        self.assertEqual(
            armor_amount(self.effect, 1, self.source, self.target, capped_player=True),
            dict(requested=40, room=40),
        )
        bypass = dict(self.effect, parameters=[100, 0, 0, 0, 0, 0, 2, 0])
        self.assertEqual(
            armor_amount(bypass, 1, self.source, self.target, capped_player=True)[
                "requested"
            ],
            100,
        )

    def test_elemental_mastery_flags_and_negative_floor(self):
        self.source.effect_stats.update({21: 25, 20: 25, 102: 25, 103: 25})
        effect = dict(self.effect, parameters=[80, 0, 0, 0, 1, 0])
        self.assertEqual(
            armor_amount(effect, 1, self.source, self.target, capped_player=False)[
                "requested"
            ],
            160,
        )
        bad = dict(effect, native_effect_flags=[100])
        with self.assertRaises(ValueError):
            armor_amount(bad, 1, self.source, self.target, capped_player=False)

    def test_application_native_additional_and_owned_removal(self):
        fight = SimpleNamespace(
            id=1,
            actors={22: self.source, -33: self.target},
            phase="active",
            current=self.source,
            owned_stat_effects={},
            _event=lambda *a, **k: None,
        )
        packets = []
        context = StatExecutionContext(True, True, None, True, None)
        handler = NativeArmorHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 902,
            context=lambda *a: context,
            authority=lambda *a: SimpleNamespace(is_player=False),
        )
        inv = EffectInvocation(123456, 1, 22, -33, (1, 0, 0))
        self.effect["parameters"] = [100, 0, 0, 0]
        self.assertTrue(handler(self.effect, None, inv))
        self.assertEqual(self.target.effect_stats[97], 110)
        messages = {}
        _identity_fields(
            bytes.fromhex(fight.owned_stat_effects[902]["payload"]), messages=messages
        )
        self.assertEqual(messages[8].hex(), "60619801f5ffffff07c80164")
        stat = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=lambda: 903,
            context=lambda *a: context,
        )
        stat.remove(902)
        self.assertEqual(self.target.effect_stats[97], 10)
        self.assertEqual([opcode for opcode, _ in packets], [13497, 13560])
        self.effect["parameters"] = [0, 0]
        handler.allocate_uid = lambda: self.fail("Zero initial amount allocated UID")
        self.assertFalse(handler(self.effect, None, inv))
        self.assertEqual(len(packets), 2)
