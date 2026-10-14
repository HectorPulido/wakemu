"""Superpoderosa inherits roles through actual doll absorption before acting."""
import os
import random
import unittest

import test_aniripsa_grant_summon_pipeline as turns
import test_combat_spell_transaction as fixtures
import test_sadida_grant_pipeline as grants
import test_sadida_super_voodoll_actions_pipeline as actions


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaSuperActionConsequencesTests(unittest.TestCase):
    def inherited_role(self, spell, profile, role, *, distance=2):
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_qi_fight import current_registry

        (
            character,
            monster,
            fight,
        ) = fixtures.SpellTransactionTests().native_server_fixture(
            10,
            200,
            native_qi=True,
            target_hp=20000,
            variation_seed=17,
            target_distance=distance,
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
        data = character, monster, fight, deck, rng, packets
        helper = grants.SadidaGrantPipelineTests()
        tx = helper.cast(data, 8137, target=(-8, -6, -1))
        data = (*data[:2], tx.fight, *data[3:])
        tx = helper.cast(data, spell, target=(-8, -6, -1), action_id=11)
        data = (*data[:2], tx.fight, *data[3:])
        ordinary = next(
            actor
            for actor in tx.fight.actors.values()
            if getattr(actor, "native_summon_source", None)
            and actor.hp > 0
            and actor_action_book(actor)["profile"] == profile
        )
        self.assertIn(
            role, {state.reference for state in ordinary.state_ledger.entries}
        )
        turns.AniripsaGrantSummonPipelineTests().next_player_turn(data[2], data[:5])
        tx = helper.cast(data, 911, target=(-7, -7, -1), action_id=12)
        data = (*data[:2], tx.fight, *data[3:])
        super_doll = next(
            actor
            for actor in tx.fight.actors.values()
            if getattr(actor, "native_summon_source", None)
            and actor.hp > 0
            and actor_action_book(actor)["profile"] == 3746
        )
        self.assertIn(
            role, {state.reference for state in super_doll.state_ledger.entries}
        )
        self.assertEqual(tx.fight.actors[ordinary.id].hp, 0)
        self.assertFalse(
            any(
                row and row["identity"] == ["actor", ordinary.id]
                for row in tx.fight.native_qi_slots
            )
        )
        current_registry(tx.fight)
        return data, super_doll.id

    def action(self, data, identity, reference, target_id):
        from wakfu_server.combat_qi_fight import current_registry

        helper = turns.AniripsaGrantSummonPipelineTests()
        fight = data[2]
        for _ in range(30):
            if fight.current.id == identity:
                break
            helper.end_current_turn(fight, data[:5])
        self.assertEqual(fight.current.id, identity)
        actor = fight.actors[identity]
        resources = actor.ap, actor.mp, actor.effect_stats[4]
        tx = actions.SadidaSuperVoodollActionsPipelineTests().summon_cast(
            data, identity, reference, fight.actors[target_id].position
        )
        after = tx.fight.actors[identity]
        # Native casting table: each of these six acquired actions costs3AP,
        # zeroMP and zeroWP (5025 additionally caps its evaluation level at6).
        self.assertEqual(
            tuple(tx.plan["costs"][key] for key in ("ap", "mp", "wp")),
            (3, 0, 0),
        )
        if after.hp > 0:
            self.assertEqual(after.ap, resources[0] - tx.plan["costs"]["ap"])
            self.assertEqual(after.mp, resources[1] - tx.plan["costs"]["mp"])
            self.assertEqual(
                after.effect_stats[4], resources[2] - tx.plan["costs"]["wp"]
            )
        current_registry(tx.fight)
        return tx

    def test_inherited_5023_damages_only_selected_enemy(self):
        data, identity = self.inherited_role(921, 3748, 8187)
        hp = {key: actor.hp for key, actor in data[2].actors.items()}
        tx = self.action(data, identity, 5023, -7)
        self.assertGreater(hp[-7] - tx.fight.actors[-7].hp, 0)
        self.assertEqual(tx.fight.actors[7].hp, hp[7])
        self.assertEqual(tx.fight.actors[identity].hp, hp[identity])

    def test_inherited_5021_heals_wounded_owner_without_healing_enemy(self):
        from wakfu_server.combat_hp_raw import set_hp_raw_current

        data, identity = self.inherited_role(918, 3749, 8191)
        owner = data[2].actors[7]
        set_hp_raw_current(owner, owner.max_hp // 2)
        hp, enemy_hp = owner.hp, data[2].actors[-7].hp
        tx = self.action(data, identity, 5021, 7)
        self.assertGreater(tx.fight.actors[7].hp - hp, 0)
        self.assertLessEqual(tx.fight.actors[7].hp, owner.max_hp)
        self.assertEqual(tx.fight.actors[-7].hp, enemy_hp)

    def test_inherited_5026_carriers_produce_real_poison_and_mp_loss(self):
        data, identity = self.inherited_role(932, 3750, 8195)
        tx = self.action(data, identity, 5026, -7)
        enemy = tx.fight.actors[-7]
        self.assertTrue(
            {3617, 3309, 8259}
            <= {state.reference for state in enemy.state_ledger.entries}
        )
        hp, maximum = enemy.hp, enemy.max_mp
        next_data = (*data[:2], tx.fight, *data[3:])
        for _ in range(30):
            if tx.fight.current.id == -7:
                break
            turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                tx.fight, next_data[:5]
            )
        self.assertEqual(tx.fight.current.id, -7)
        self.assertLess(tx.fight.actors[-7].hp, hp)
        self.assertLess(tx.fight.actors[-7].mp, maximum)
        self.assertGreater(tx.fight.actors[7].hp, 0)

    def test_inherited_5024_explosion_retires_source_and_preserves_bystanders(self):
        data, identity = self.inherited_role(925, 3747, 8193)
        hp = data[2].actors[-7].hp
        owner_hp = data[2].actors[7].hp
        tx = self.action(data, identity, 5024, identity)
        self.assertGreater(hp - tx.fight.actors[-7].hp, 0)
        self.assertEqual(tx.fight.actors[identity].hp, 0)
        self.assertEqual(tx.fight.actors[identity].native_obstacle_id, -1)
        self.assertEqual(tx.fight.actors[7].hp, owner_hp)
        for key in (7, -7):
            self.assertTrue(
                any(
                    row and row["identity"] == ["actor", key]
                    for row in tx.fight.native_qi_slots
                )
            )
        self.assertFalse(
            any(
                row and row["identity"] == ["actor", identity]
                for row in tx.fight.native_qi_slots
            )
        )

    def test_inherited_5025_pulls_enemy_to_adjacent_native_cell(self):
        data, identity = self.inherited_role(930, 3751, 8189, distance=3)
        source, target = data[2].actors[identity], data[2].actors[-7]
        before = target.position
        tx = self.action(data, identity, 5025, -7)
        after = tx.fight.actors[-7].position
        self.assertEqual(after[1:], before[1:])
        self.assertEqual(
            after, (source.position[0] + 1, source.position[1], source.position[2])
        )
        self.assertEqual(before[0] - after[0], 1)
        self.assertEqual(tx.fight.actors[identity].position, source.position)

    def test_inherited_5356_links_actual_owner_and_source(self):
        data, identity = self.inherited_role(934, 3751, 8190)
        tx = self.action(data, identity, 5356, 7)
        target_states = [
            s for s in tx.fight.actors[7].state_ledger.entries if s.reference == 3681
        ]
        source_states = [
            s
            for s in tx.fight.actors[identity].state_ledger.entries
            if s.reference == 3682
        ]
        self.assertEqual(len(target_states), 1)
        self.assertEqual(len(source_states), 1)
        self.assertEqual(target_states[0].level, 1)
        self.assertEqual(source_states[0].level, 1)
        self.assertNotIn(
            3681, {s.reference for s in tx.fight.actors[-7].state_ledger.entries}
        )
