"""ANI-02 original Ready healing/link roots with owned player snapshots.

Initial wounds are persisted character HP, installed by the production snapshot
builder before Ready; no combat PA/HP authority is edited by these tests.
"""
import os
import random
import struct
import unittest

import test_combat_aptitude_healing_runtime as healing_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaAlliedHealingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wakfu_server.combat_retained_runtime import native_retained_metadata

        cls.active_retained_metadata = native_retained_metadata()

    fixture = healing_fixture.AptitudeHealingRuntimeTests.fixture
    cast_heal = healing_fixture.AptitudeHealingRuntimeTests.cast_heal

    def cast(self, fight, characters, monster, decks, spell, target):
        from wakfu_server.combat_server_spell import prepare_server_spell

        return prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | spell, *fight.actors[target].position),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        )

    def test_injured_self_and_ally_heal_pay_once_and_preserve_source(self):
        for target in (7, 8):
            with self.subTest(target=target):
                fight, characters, monster, decks = self.fixture()
                before = (
                    fight.actors[target].hp,
                    fight.actors[7].ap,
                    fight.actors[7].effect_stats[4],
                )
                result = self.cast(fight, characters, monster, decks, 779, target)
                recipient = result.fight.actors[target]
                self.assertGreater(recipient.hp, before[0])
                self.assertLessEqual(recipient.hp, recipient.max_hp)
                self.assertEqual(result.fight.actors[7].ap, before[1] - 3)
                self.assertEqual(result.fight.actors[7].effect_stats[4], before[2])
                self.assertEqual(fight.actors[target].hp, before[0])
                self.assertEqual(fight.actors[7].ap, before[1])

    def test_full_hp_heal_cannot_overflow_and_still_pays_native_cost(self):
        fight, characters, monster, decks = self.fixture(injury=0)
        before = fight.actors[7].ap
        result = self.cast(fight, characters, monster, decks, 779, 8)
        self.assertEqual(result.fight.actors[8].hp, fight.actors[8].max_hp)
        self.assertEqual(result.fight.actors[7].ap, before - 3)

    def test_link_allied_state_cost_and_enemy_rejection_are_atomic(self):
        fight, characters, monster, decks = self.fixture(active_spells=(779, 781))
        before = (fight.actors[7].ap, fight.actors[7].effect_stats[4])
        result = self.cast(fight, characters, monster, decks, 781, 8)
        states = [row.reference for row in result.fight.actors[8].state_ledger.entries]
        self.assertIn(3864, states)
        self.assertNotIn(
            3864, [row.reference for row in fight.actors[8].state_ledger.entries]
        )
        self.assertEqual(result.fight.actors[7].ap, before[0] - 2)
        self.assertEqual(result.fight.actors[7].effect_stats[4], before[1] - 1)
        events = list(fight.events)
        with self.assertRaises(ValueError):
            self.cast(fight, characters, monster, decks, 781, -7)
        self.assertEqual((fight.actors[7].ap, fight.actors[7].effect_stats[4]), before)
        self.assertEqual(fight.events, events)


class HealingNumericBoundaryTests(unittest.TestCase):
    def test_hp_then_virtual_hp_saturates_without_integer_overflow(self):
        from wakfu_server.combat_damage_healing import consume_healing

        result = consume_healing(
            (1 << 31) - 1,
            target_hp=90,
            target_max_hp=100,
            target_virtual_hp=3,
            target_max_virtual_hp=8,
            undead=False,
            bypass_undead=False,
            frozen_stats=(),
        )
        self.assertEqual(
            result,
            dict(
                value=15,
                hp_gain=10,
                virtual_hp_gain=5,
                target_hp=100,
                target_virtual_hp=8,
            ),
        )

    def test_frozen_hp_preserves_hp_and_allows_only_virtual_capacity(self):
        from wakfu_server.combat_damage_healing import consume_healing

        result = consume_healing(
            50,
            target_hp=90,
            target_max_hp=100,
            target_virtual_hp=3,
            target_max_virtual_hp=8,
            undead=False,
            bypass_undead=False,
            frozen_stats=(("target", 1),),
        )
        self.assertEqual(
            (result["target_hp"], result["target_virtual_hp"], result["value"]),
            (90, 8, 5),
        )

    def test_healing_resistance_saturates_at_actual_pa_bounds(self):
        from wakfu_server.combat_damage_healing import healing_resistance_after

        values = dict(
            target_max_hp=100,
            current=99,
            enabled=True,
            frozen=False,
            minimum=0,
            maximum=100,
        )
        self.assertEqual(healing_resistance_after(100, **values), 100)
        self.assertEqual(healing_resistance_after(100, **dict(values, frozen=True)), 99)
        self.assertEqual(
            healing_resistance_after(100, **dict(values, enabled=False)), 99
        )
