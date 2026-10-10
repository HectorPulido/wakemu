"""Actual ENIRIPSA summon and mode passive consumers, not inert Ready markers."""
import os
import random
import struct
import unittest

import test_aniripsa_grant_summon_pipeline as grant_fixture
import test_aniripsa_contra_natura_matrix as allied_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaSummonPassivePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        allied_fixture.AniripsaContraNaturaMatrixTests.setUpClass()

    def test_transgression_resistance_and_healing_follow_mode_and_remove_on_toggle(
        self,
    ):
        helper = grant_fixture.AniripsaGrantSummonPipelineTests()
        for passive in ((), (7992,)):
            with self.subTest(passive=passive):
                fixture = helper.fixture(passives=passive)
                self.assertEqual(fixture[2].actors[7].effect_stats[27], 0)
                first = helper.cast(fixture, 7977)
                self.assertEqual(
                    first.fight.actors[7].effect_stats[27], 75 if passive else 0
                )
                self.assertEqual(first.fight.actors[7].effect_stats[114], -50)
                adopted = helper.adopt(fixture, first.fight)
                helper.next_player_turn(first.fight, adopted)
                second = helper.cast(adopted, 7977)
                self.assertEqual(second.fight.actors[7].effect_stats[27], 0)
                self.assertEqual(second.fight.actors[7].effect_stats[114], 0)
        allied = allied_fixture.AniripsaContraNaturaMatrixTests()
        for converted, expected in ((False, 47), (True, 26)):
            fixture = allied.fixture(
                active_spells=(779,), passive_spells=(7992,), level=200, injury=300
            )
            if converted:
                fixture = (
                    allied.cast(fixture, 7977, 7, granted=True).fight,
                    *fixture[1:],
                )
            hp = fixture[0].actors[8].hp
            result = allied.cast(fixture, 779, 8)
            self.assertEqual(result.fight.actors[8].hp - hp, expected)

    def test_ambivalence_allied_target_improves_healing_without_self_toggle(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        helper = allied_fixture.AniripsaContraNaturaMatrixTests()
        fixture = helper.fixture(
            active_spells=(779,), passive_spells=(7998,), level=200, injury=300
        )
        result = helper.cast(fixture, 7977, 8, granted=True)
        self.assertEqual(result.fight.actors[7].effect_stats[114], 30)
        self.assertNotIn(
            3867, {s.reference for s in result.fight.actors[7].state_ledger.entries}
        )
        self.assertEqual(result.fight.actors[8].effect_stats[32], 0)
        hp = result.fight.actors[8].hp
        healed = helper.cast((result.fight, *fixture[1:]), 779, 8)
        self.assertEqual(healed.fight.actors[8].hp - hp, 59)
        absent = helper.fixture(active_spells=(779,), level=200, injury=300)
        before = snapshot(absent[0])
        with self.assertRaisesRegex(ValueError, "casting eligibility"):
            helper.cast(absent, 7977, 8, granted=True)
        self.assertEqual(snapshot(absent[0]), before)

    def test_ambivalence_enemy_target_reacts_to_healing_not_direct_damage(self):
        helper = allied_fixture.AniripsaContraNaturaMatrixTests()
        for spell, target, expected_loss in (
            (779, 8, 9),
            (779, 7, 8),
            (779, -7, 93),
            (630, -7, 156),
        ):
            with self.subTest(spell=spell, target=target):
                fixture = helper.fixture(
                    active_spells=(779, 630),
                    passive_spells=(7998,),
                    level=200,
                    injury=300,
                    enemy_position=(-8, -9, -1),
                )
                marked = helper.cast(fixture, 7977, -7, granted=True)
                self.assertNotIn(
                    3867,
                    {s.reference for s in marked.fight.actors[7].state_ledger.entries},
                )
                hp = marked.fight.actors[-7].hp
                result = helper.cast((marked.fight, *fixture[1:]), spell, target)
                self.assertEqual(hp - result.fight.actors[-7].hp, expected_loss)
                damage = [
                    event
                    for event in result.fight.events
                    if event.get("kind") == "damage" and event.get("target_id") == -7
                ]
                self.assertEqual(len(damage), 1)
                if target in (7, 8):
                    self.assertTrue(
                        any(
                            event.get("kind") == "healing"
                            and event.get("target_id") == target
                            for event in result.fight.events
                        )
                    )

    def test_naturaleza_muerta_cost_and_actual_death_area_for_four_profiles(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_summon_retirement import retired_summon_ids
        from wakfu_server.fight_checkpoint_store import snapshot

        helper = grant_fixture.AniripsaGrantSummonPipelineTests()
        for dark, upgraded, nature in (
            (False, False, False),
            (False, False, True),
            (True, False, True),
            (False, True, True),
            (True, True, True),
        ):
            with self.subTest(dark=dark, upgraded=upgraded, nature=nature):
                passives = ((5455,) if nature else ()) + ((7991,) if upgraded else ())
                fixture = helper.fixture(passives=passives)
                if dark:
                    fixture = helper.adopt(fixture, helper.cast(fixture, 7977).fight)
                summon_tx = helper.cast(fixture, 7978, (-8, -6, -1))
                self.assertEqual(summon_tx.plan["costs"]["ap"], 3 if nature else 2)
                fixture = helper.adopt(fixture, summon_tx.fight)
                summon = next(
                    a
                    for a in fixture[2].actors.values()
                    if getattr(a, "native_summon_source", None) and a.hp > 0
                )
                self.assertFalse(getattr(fixture[2], "native_effect_areas", {}))
                for _ in range(35):
                    character, monster, fight, deck, rng = fixture
                    original = snapshot(fight)
                    try:
                        transaction = prepare_server_spell(
                            struct.pack(">qqiih", 7, (7 << 32) | 630, *summon.position),
                            character,
                            {-7: monster},
                            fight,
                            3,
                            deck,
                            action_id=50 + fight.turn_id,
                            line_of_sight=lambda *args: True,
                            critical=False,
                            rng=rng,
                        )
                    except ValueError as exc:
                        if "resources" not in str(exc) and "maximum casts" not in str(
                            exc
                        ):
                            raise
                        self.assertEqual(snapshot(fight), original)
                        helper.next_player_turn(fight, fixture)
                        continue
                    fixture = helper.adopt(fixture, transaction.fight)
                    summon = transaction.fight.actors[summon.id]
                    if summon.hp == 0:
                        break
                else:
                    self.fail("Actual Cunejo death did not occur within legal turns")
                self.assertIn(summon.id, retired_summon_ids(fixture[2]))
                areas = list(getattr(fixture[2], "native_effect_areas", {}).values())
                self.assertEqual(len(areas), int(nature))
                if nature:
                    self.assertEqual(areas[0]["reference"], 1814)
                    self.assertEqual(areas[0]["cell"], summon.position)
                    self.assertEqual(areas[0]["owner_id"], 7)
                    self.assertEqual(areas[0]["native_fight_affiliation"], 0)
