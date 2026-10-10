"""Actual Columnata area damage and its declared SELF armor recipient."""
import random
import struct
import unittest

import audit_active_spells as native
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class SacrierColumnataPipelineTests(unittest.TestCase):
    def test_self_centered_lethal_and_surviving_targets_preserve_atomic_cast(self):
        origin, enemy = (-23, -143, 70), (-22, -143, 70)
        terrain = native.bounded_arena(
            native.map_geometry(1134), origin, [enemy], radius=12
        )
        for level in (20, 200):
            for reference, monster_level in ((5525, 1), (3646, 12)):
                with self.subTest(level=level, reference=reference):
                    character, monster, fight = native.fixture(
                        11,
                        level,
                        enemy,
                        terrain,
                        origin,
                        monster_reference=reference,
                        monster_level=monster_level,
                    )
                    deck = encode_deck([5037], [])
                    rng = random.Random(7)
                    initialized, _ = prepare_server_initialization(
                        character,
                        {-7: monster},
                        fight,
                        3,
                        deck,
                        action_id=1,
                        rng=rng,
                        fight_start=True,
                    )
                    while initialized.current.id != 7:
                        initialized.end_server_turn(
                            initialized.current.id, initialized.turn_id
                        )
                    before = snapshot(initialized)
                    result = prepare_server_spell(
                        struct.pack(">qqiih", 7, (7 << 32) | 5037, *origin),
                        character,
                        {-7: monster},
                        initialized,
                        3,
                        deck,
                        action_id=2,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=rng,
                    )
                    self.assertEqual(snapshot(initialized), before)
                    target = result.fight.actors[-7]
                    self.assertLess(target.hp, initialized.actors[-7].hp)
                    # Original child416131 declares fcE8194 (SELF2 + flag8192).
                    # The group's enemy PV is not the armor recipient.
                    self.assertGreater(result.fight.actors[7].effect_stats[97], 0)
                    self.assertEqual(target.effect_stats[97], 0)
                    if reference == 5525:
                        self.assertEqual(target.hp, 0)
                        self.assertEqual(target.effect_stats[97], 0)
                        self.assertFalse(
                            any(
                                row.get("target_id") == -7
                                and row.get("effect_class") == 1013
                                for row in result.fight.owned_stat_effects.values()
                            )
                        )
                    else:
                        self.assertGreater(target.hp, 0)
                    self.assertLess(result.fight.actors[7].ap, initialized.actors[7].ap)
