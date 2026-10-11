"""Owned Steamer class actions through native Ready, grants and cast transactions."""
import os
import random
import unittest
import test_combat_pandawa_runtime as pandawa_helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerRuntimeTests(unittest.TestCase):
    cast = pandawa_helpers.PandawaRuntimeTests.cast
    adopt = pandawa_helpers.PandawaRuntimeTests.adopt
    next_owned_turn = pandawa_helpers.PandawaRuntimeTests.next_owned_turn

    def fixture(self, passives=(), *, actives=()):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            16,
            200,
            target_hp=2000,
            native_qi=True,
            target_distance=3,
            variation_seed=17,
        )
        deck = encode_deck(list(actives), passives)
        rng = random.Random(0)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, fight, deck, rng

    def test_ready_installs_actual_resources_and_four_owned_grants(self):
        from wakfu_server.combat_spell_grant import granted_spells

        fixture = self.fixture()
        actor = fixture[2].actors[7]
        self.assertTrue({7008, 7700, 6923, 6924} <= set(granted_spells(fixture[2], 7)))
        self.assertEqual(actor.effect_stats[4], 3)
        self.assertEqual(actor.effect_stats[123], 3)

    def test_actual_microbot_cast_registers_nonfighter_owned_network(self):
        fixture = self.fixture()
        result = self.cast(fixture, 7008)
        areas = [
            row
            for row in result.fight.native_effect_areas.values()
            if row["reference"] == 978
        ]
        self.assertEqual(len(areas), 1)
        row = areas[0]
        self.assertEqual(row["owner_id"], 7)
        self.assertNotIn(row["uid"], result.fight.actors)
        self.assertIn(
            row["uid"], result.fight.native_microbot_networks[7]["microbot_ids"]
        )
        self.assertGreater(len(result.packets), 0)

    def test_actual_turret_cast_preserves_native_creator_and_registration(self):
        from wakfu_server.combat_qi_fight import current_registry

        fixture = self.fixture()
        result = self.cast(fixture, 7700)
        summons = [
            actor
            for actor in result.fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        ]
        self.assertEqual(len(summons), 1)
        turret = summons[0]
        self.assertEqual(turret.native_controller_id, 7)
        self.assertEqual(turret.team, result.fight.actors[7].team)
        self.assertGreaterEqual(turret.native_obstacle_id, 0)
        # Native profile PB114 excludes this stationary machine from turns.
        self.assertIn(114, turret.native_fight_properties)
        self.assertNotIn(turret.id, result.fight.order)
        current_registry(result.fight)

    def test_both_owned_forms_apply_real_state_and_preserve_source(self):
        for spell, state in ((6923, 7647), (6924, 7648)):
            with self.subTest(spell=spell):
                fixture = self.fixture()
                if spell == 6924:
                    from wakfu_server.combat_server_spell import server_runtime
                    from wakfu_server.combat_spell_grant import granted_spells
                    from tools.class_spell_eligible_targets import eligible_cast_targets

                    character, monster, fight, deck, rng = fixture
                    _, adapter = server_runtime(
                        character,
                        {-7: monster},
                        deck,
                        action_id=2,
                        critical=False,
                        rng=rng,
                    )
                    targets = eligible_cast_targets(
                        fight,
                        character,
                        deck,
                        granted_spells(fight, 7)[7008]["uid"],
                        adapter=adapter,
                        line_of_sight=lambda *args: True,
                        actor_id=7,
                        limit=128,
                        maximum_eligible=16,
                    )
                    adjacent = [
                        row
                        for row in targets["eligible"]
                        if sum(
                            abs(row["target"][i] - fight.actors[7].position[i])
                            for i in (0, 1)
                        )
                        == 1
                    ]
                    self.assertTrue(adjacent, targets)
                    born = self.cast(fixture, 7008, target=adjacent[0]["target"])
                    fixture = self.adopt(fixture, born.fight)
                    fixture[2].move(3, 7, [adjacent[0]["target"]])
                result = self.cast(
                    fixture, spell, target=fixture[2].actors[7].position, action_id=3
                )
                self.assertIn(
                    state,
                    {
                        entry.reference
                        for entry in result.fight.actors[7].state_ledger.entries
                    },
                )
                self.assertNotIn(
                    state,
                    {
                        entry.reference
                        for entry in fixture[2].actors[7].state_ledger.entries
                    },
                )
                self.assertTrue(result.packets)
