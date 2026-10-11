"""Every Sadida doll profile is acquired by actual granted/elemental casts."""
import os
import unittest

import test_sadida_grant_pipeline as grants


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaDollBooksPipelineTests(unittest.TestCase):
    fixture = grants.SadidaGrantPipelineTests.fixture
    cast = grants.SadidaGrantPipelineTests.cast

    @staticmethod
    def adopt(data, fight):
        return (*data[:2], fight, *data[3:])

    def test_superpoderosa_grant_creates_exact_seven_action_book(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_summon import fresh_summon_slot_owned

        data = self.fixture()
        seeded = self.cast(data, 8137)
        data = self.adopt(data, seeded.fight)
        seed_cell = next(
            a["cell"]
            for a in seeded.fight.native_effect_areas.values()
            if a["reference"] == 1835
        )
        doll = self.cast(data, 925, target=seed_cell, action_id=11)
        data = self.adopt(data, doll.fight)
        # Native911 requires an existing owned doll, excluding Voodoll.
        import test_aniripsa_grant_summon_pipeline as turns

        turns.AniripsaGrantSummonPipelineTests().next_player_turn(data[2], data[:5])
        tx = self.cast(data, 911, action_id=12)
        actors = [
            a
            for a in tx.fight.actors.values()
            if getattr(a, "native_summon_source", None)
            and a.hp > 0
            and actor_action_book(a)["profile"] == 3746
        ]
        self.assertEqual(len(actors), 1)
        actor = actors[0]
        book = actor_action_book(actor)
        self.assertEqual(book["profile"], 3746)
        self.assertEqual(
            {a["reference"] for a in book["actions"]},
            {5153, 5023, 5021, 5026, 5024, 5025, 5356},
        )
        self.assertTrue(fresh_summon_slot_owned(tx.fight, actor))
        self.assertEqual(actor.team, tx.fight.actors[7].team)

    def test_five_elemental_seed_transformations_preserve_exact_books_and_qi(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_summon import fresh_summon_slot_owned
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_server_spell import prepare_server_initialization
        import test_combat_spell_transaction as native_fixture
        import random

        for spell, profile, abilities in (
            (925, 3747, {5024, 8138}),
            (921, 3748, {5023, 8138}),
            (918, 3749, {5021, 8138}),
            (932, 3750, {5026, 8138}),
            (930, 3751, {5025, 5356, 8138}),
        ):
            with self.subTest(spell=spell, profile=profile):
                (
                    character,
                    monster,
                    fight,
                ) = native_fixture.SpellTransactionTests().native_server_fixture(
                    10, 200, native_qi=True, target_hp=20000, variation_seed=17
                )
                deck = encode_deck((spell,))
                rng = random.Random(17)
                fight, packets = prepare_server_initialization(
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=1,
                    rng=rng,
                    fight_start=True,
                )
                data = (character, monster, fight, deck, rng, packets)
                seeded = self.cast(data, 8137)
                data = self.adopt(data, seeded.fight)
                areas = [
                    a
                    for a in seeded.fight.native_effect_areas.values()
                    if a["reference"] == 1835
                ]
                self.assertEqual(len(areas), 1)
                area = areas[0]
                cell = area.get("position", area.get("cell"))
                self.assertIsNotNone(cell, sorted(area))
                tx = self.cast(data, spell, target=cell, action_id=11)
                actors = [
                    a
                    for a in tx.fight.actors.values()
                    if getattr(a, "native_summon_source", None) and a.hp > 0
                ]
                self.assertEqual(len(actors), 1)
                actor = actors[0]
                book = actor_action_book(actor)
                self.assertEqual(book["profile"], profile)
                self.assertEqual({a["reference"] for a in book["actions"]}, abilities)
                self.assertTrue(fresh_summon_slot_owned(tx.fight, actor))
                self.assertEqual(actor.team, tx.fight.actors[7].team)
                current_registry(tx.fight)
