import struct
import unittest
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spells import encode_deck
from wakfu_server.combat_iop_cast import execute_iop4785, execute_iop_cast
from wakfu_server.combat_states import (
    plan_3425,
    state_packet,
    state8913_metadata,
    expire_8913,
)


class BareIopCastTests(unittest.TestCase):
    def setUp(self):
        self.pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, owner_id=9, controlled=True)
        # Native po.SX is part of the real player snapshot authority. This
        # bare cast fixture represents an owned player, not an unknown actor.
        self.pc.native_controlled_by_ai = False
        self.npc = Actor(-7, 1, (1, 0, 0), 30, 3, 3, 0, 1)
        self.npc.native_controlled_by_ai = True
        self.fight = Fight(
            1,
            [self.pc, self.npc],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.fight.ready(9)
        self.character = dict(id=7, account_id=9, breed=8, level=1, map_id=1134)
        self.monster = dict(id=-7, ref=5525, level=1, map_id=1134, wp=6)
        self.body = struct.pack(">qqiih", 7, (7 << 32) | 4785, 1, 0, 0)

    def cast(self, **changes):
        options = dict(
            wp_current=6,
            wp_maximum=6,
            action_id=1,
            effect_uid=1,
            critical_chance=0,
            caster_states=getattr(self.pc, "combat_states", {}),
            target_states={},
            caster_bonuses={},
            target_bonuses={},
            other_running_effects=[],
            mitigate=lambda d, *a: d,
        )
        options.update(changes)
        with patch("wakfu_server.combat_execute.static_visible", return_value=True):
            return execute_iop4785(
                self.body,
                self.character,
                [self.monster],
                self.fight,
                9,
                encode_deck([4785]),
                **options
            )

    def test_air_damage_state_and_native_ap_cost(self):
        result = self.cast()
        self.assertEqual((self.pc.ap, self.pc.mp, self.npc.hp), (3, 3, 27))
        self.assertEqual(result["states"], {3442: 25})
        self.assertEqual(
            [p for p, _ in result["packets"]], [12588, 12678, 12613, 12613]
        )
        self.assertEqual(self.pc.combat_states, {3442: 25})
        self.cast(effect_uid=3)
        self.assertEqual((self.pc.ap, self.pc.combat_states), (0, {3442: 50}))

    def test_unknown_combo_effect_and_encoding_failure_roll_back(self):
        for options in (
            dict(caster_states={3444: 3}),
            dict(target_states={3467: 1}),
            dict(other_running_effects=None),
            dict(effect_uid=0),
        ):
            with self.assertRaises(ValueError):
                self.cast(**options)
        self.assertEqual((self.pc.ap, self.npc.hp), (6, 30))
        self.assertFalse(hasattr(self.pc, "combat_states"))

    def test_native_additive_limit_and_expiry_unknown_explicit(self):
        self.assertEqual(plan_3425({3442: 390}, 25), {3442: 400})
        self.assertEqual(plan_3425({3442: 400}, 25), {3442: 400})
        self.assertFalse(state8913_metadata()["execution_verified"])
        with self.assertRaises(ValueError):
            state_packet(
                1,
                2,
                uid=0,
                generic_effect=150383,
                caster_id=7,
                target_id=7,
                state_id=3425,
                level=25,
            )

    def test_4780_requires_expiry_hook_and_zero_armor(self):
        body = struct.pack(">qqiih", 7, (7 << 32) | 4780, 1, 0, 0)
        options = dict(
            wp_current=6,
            wp_maximum=6,
            action_id=1,
            effect_uid=1,
            critical_chance=0,
            caster_states={},
            target_states={},
            caster_bonuses={},
            target_bonuses={},
            other_running_effects=[],
            mitigate=lambda d, *a: d,
        )
        with patch("wakfu_server.combat_execute.static_visible", return_value=True):
            for extra in ({}, {"state_expiry_enabled": True, "target_armor": 1}):
                with self.assertRaises(ValueError):
                    execute_iop_cast(
                        body,
                        self.character,
                        [self.monster],
                        self.fight,
                        9,
                        encode_deck([4780]),
                        **options,
                        **extra
                    )
            result = execute_iop_cast(
                body,
                self.character,
                [self.monster],
                self.fight,
                9,
                encode_deck([4780]),
                **options,
                state_expiry_enabled=True,
                target_armor=0
            )
        self.assertEqual(
            (self.pc.ap, self.npc.hp, self.pc.combat_states), (4, 28, {3442: 10})
        )
        self.assertEqual(len(result["packets"]), 5)
        self.assertEqual(self.npc.combat_states[8913]["expires_at_caster_start"], 2)
        self.assertIn(
            8913, expire_8913(self.npc.combat_states, caster_id=8, caster_turn=2)
        )
        self.assertEqual(
            expire_8913(self.npc.combat_states, caster_id=7, caster_turn=2), {}
        )
