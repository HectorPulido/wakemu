"""Three elemental native branches before/after Contra Natura, including criticals.

Expected values pin the actual level200 native branch outputs with the ordinary
fixture modifiers, recipient healing received and Contra Natura healing modifier.
Contra Natura does not reverse ally/enemy allegiance in the current catalog.
"""
import os
import random
import struct
import unittest

import test_combat_aptitude_healing_runtime as allied_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaContraNaturaMatrixTests(unittest.TestCase):
    fixture = allied_fixture.AptitudeHealingRuntimeTests.fixture
    setUpClass = allied_fixture.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    def cast(self, fixture, spell, target, *, critical=False, granted=False, rng=None):
        from wakfu_server.combat_server_spell import prepare_server_spell

        fight, characters, monster, decks = fixture
        return prepare_server_spell(
            struct.pack(
                ">qqiih",
                7,
                spell if granted else (7 << 32) | spell,
                *fight.actors[target].position
            ),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=critical,
            rng=rng or random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        )

    def test_natural_and_contra_natura_all_elements_self_ally_enemy_normal_critical(
        self,
    ):
        from wakfu_server.fight_checkpoint_store import snapshot

        for spell in (779, 630, 645):
            for target in (7, 8, -7):
                for converted in (False, True):
                    for critical in (False, True):
                        with self.subTest(
                            spell=spell,
                            target=target,
                            converted=converted,
                            critical=critical,
                        ):
                            fixture = self.fixture(
                                active_spells=(spell,),
                                level=200,
                                injury=300,
                                enemy_position=(-8, -9, -1),
                            )
                            if converted:
                                toggle = self.cast(fixture, 7977, 7, granted=True)
                                fixture = (toggle.fight, *fixture[1:])
                            fight = fixture[0]
                            states = {
                                s.reference
                                for s in fight.actors[7].state_ledger.entries
                            }
                            self.assertEqual({3867, 8020} <= states, converted)
                            original = snapshot(fight)
                            rng = random.Random(0)
                            rng_before = rng.getstate()
                            if target == 7 and spell in (630, 645):
                                with self.assertRaisesRegex(
                                    ValueError, "casting eligibility"
                                ):
                                    self.cast(
                                        fixture,
                                        spell,
                                        target,
                                        critical=critical,
                                        rng=rng,
                                    )
                                self.assertEqual(snapshot(fight), original)
                                self.assertEqual(rng.getstate(), rng_before)
                                continue
                            hp = fight.actors[target].hp
                            ap, wp = fight.actors[7].ap, fight.actors[7].effect_stats[4]
                            result = self.cast(
                                fixture, spell, target, critical=critical, rng=rng
                            )
                            recipient = result.fight.actors[target]
                            if spell == 779:
                                if target == -7:
                                    delta = -(116 if critical else 93)
                                elif target == 7:
                                    delta = (
                                        (26 if critical else 21)
                                        if converted
                                        else (52 if critical else 42)
                                    )
                                else:
                                    delta = (
                                        (32 if critical else 26)
                                        if converted
                                        else (58 if critical else 47)
                                    )
                                self.assertEqual(recipient.hp, hp + delta)
                                self.assertEqual(
                                    any(
                                        s.reference == 3901
                                        for s in recipient.state_ledger.entries
                                    ),
                                    target != -7,
                                )
                            elif spell == 630:
                                self.assertEqual(
                                    recipient.hp, hp - (195 if critical else 156)
                                )
                            else:
                                self.assertEqual(
                                    recipient.hp,
                                    hp
                                    - (
                                        (107 if critical else 86) if target == -7 else 0
                                    ),
                                )
                                marks = [
                                    s
                                    for s in recipient.state_ledger.entries
                                    if s.reference == 3882
                                ]
                                self.assertEqual(len(marks), int(target == -7))
                                if marks:
                                    self.assertEqual(
                                        marks[0].level, 115 if critical else 92
                                    )
                            self.assertEqual(
                                result.fight.actors[7].ap,
                                ap - result.plan["costs"]["ap"],
                            )
                            self.assertEqual(
                                result.fight.actors[7].effect_stats[4],
                                wp - result.plan["costs"]["wp"],
                            )
                            self.assertEqual(snapshot(fight), original)
