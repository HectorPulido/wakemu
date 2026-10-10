"""Owned healing branches on wounded allies and hostile targets."""
import os
import random
import struct
import unittest

import test_combat_aptitude_healing_runtime as healing_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaHealingBranchTests(unittest.TestCase):
    fixture = healing_fixture.AptitudeHealingRuntimeTests.fixture
    setUpClass = healing_fixture.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    def cast(self, fixture, spell, target, *, critical=False):
        from wakfu_server.combat_server_spell import prepare_server_spell

        fight, characters, monster, decks = fixture
        return prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | spell, *fight.actors[target].position),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=critical,
            rng=random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        )

    def test_water_spells_heal_allies_and_damage_enemies_with_exact_once_payment(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        for spell in (779, 780, 625):
            for target in (8, -7):
                for critical in (False, True):
                    with self.subTest(spell=spell, target=target, critical=critical):
                        fixture = self.fixture(
                            active_spells=(spell,), level=200, injury=300
                        )
                        fight = fixture[0]
                        if target == -7:
                            from wakfu_server.combat_qi_fight import (
                                move_registered_actor,
                            )

                            move_registered_actor(fight, fight.actors[-7], (-8, -9, -1))
                        before = snapshot(fight)
                        hp, ap, wp = (
                            fight.actors[target].hp,
                            fight.actors[7].ap,
                            fight.actors[7].effect_stats[4],
                        )
                        result = self.cast(fixture, spell, target, critical=critical)
                        after = result.fight.actors[target]
                        if target == 8:
                            self.assertGreater(after.hp, hp)
                            self.assertLessEqual(after.hp, after.max_hp)
                        else:
                            self.assertLess(after.hp, hp)
                        self.assertEqual(
                            result.fight.actors[7].ap, ap - result.plan["costs"]["ap"]
                        )
                        self.assertEqual(
                            result.fight.actors[7].effect_stats[4],
                            wp - result.plan["costs"]["wp"],
                        )
                        self.assertEqual(snapshot(fight), before)

    def test_juventud_installs_scaled_carrier_on_ally_and_enemy(self):
        for target in (7,):
            with self.subTest(target=target):
                fixture = self.fixture(active_spells=(782,), level=200, injury=300)
                result = self.cast(fixture, 782, target)
                entries = [
                    s
                    for s in result.fight.actors[target].state_ledger.entries
                    if s.reference == 3870
                ]
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0].level, 600)
                self.assertFalse(
                    any(
                        s.reference == 3870
                        for s in fixture[0].actors[target].state_ledger.entries
                    )
                )
