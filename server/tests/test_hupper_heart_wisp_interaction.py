"""Paid Hupper utility lifetime and LIGHT tie resolution at the real handler."""
from copy import deepcopy
import struct
import unittest


class HupperHeartWispInteractionTests(unittest.TestCase):
    def test_paid_light_heals_only_injured_ally_and_full_health_still_pays(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_los import authoritative_visible

        for injury in (500, 0):
            with self.subTest(injury=injury):
                fight, characters, monster, decks = TwoXelorFixture().fixture(
                    caster_breed=19,
                    active_spells=(5590,),
                    second_player_breed=5,
                    level=200,
                    injury=injury,
                    native_target_ref=4168,
                    native_target_level=190,
                )
                caster, ally, enemy = fight.actors[7], fight.actors[8], fight.actors[-7]
                before = snapshot(fight)
                tx = prepare_server_spell(
                    struct.pack(">qqiih", 7, (7 << 32) | 5590, *ally.position),
                    characters[7],
                    {-7: monster},
                    fight,
                    3,
                    decks[7],
                    action_id=10,
                    critical=False,
                    line_of_sight=lambda a, b, p: authoritative_visible(1134, a, b, p),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                self.assertEqual(snapshot(fight), before)
                healed = tx.fight.actors[8]
                if injury:
                    self.assertGreater(healed.hp, ally.hp)
                else:
                    self.assertEqual(healed.hp, ally.hp)
                self.assertLessEqual(healed.hp, healed.max_hp)
                self.assertEqual(tx.fight.actors[7].hp, caster.hp)
                self.assertEqual(tx.fight.actors[-7].hp, enemy.hp)
                self.assertGreater(tx.plan["costs"]["ap"], 0)
                self.assertEqual(
                    tx.fight.actors[7].ap, caster.ap - tx.plan["costs"]["ap"]
                )
                qb_debit = sum(
                    row["actual_delta"]
                    for row in tx.plan["extra_resource_payment"]
                    if row["stat_id"] == 111
                )
                self.assertLess(qb_debit, 0)
                self.assertEqual(
                    tx.fight.actors[7].effect_stats[111],
                    caster.effect_stats[111] + qb_debit,
                )

    def test_paid_heart_wisp_survive_ongoing_recovery_then_owned_recall(self):
        import test_combat_huppermage_runtime as fixtures
        import test_aniripsa_grant_summon_pipeline as turns
        from durable_native_fixture import hupper_constructor, assert_native_enemy
        from tools.class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_los import authoritative_visible

        with hupper_constructor():
            (
                character,
                monster,
                fight,
                deck,
                rng,
            ) = fixtures.HuppermageRuntimeTests().fixture((5562, 5590))
        assert_native_enemy(self, fight, monster)
        action_id = 10

        def cast(spell, target, *, granted=False):
            nonlocal fight, action_id
            action_id += 1
            uid = (
                granted_spells(fight, 7)[spell]["uid"] if granted else (7 << 32) | spell
            )
            before = snapshot(fight)
            tx = prepare_server_spell(
                struct.pack(">qqiih", 7, uid, *target),
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=action_id,
                line_of_sight=lambda a, b, p: authoritative_visible(1134, a, b, p),
                critical=False,
                rng=rng,
            )
            self.assertEqual(snapshot(fight), before)
            self.assertTrue(any(tx.outcomes))
            fight = tx.fight
            return tx

        cast(5562, fight.actors[-7].position)
        self.assertIn(
            4064, {entry.reference for entry in fight.actors[7].state_ledger.entries}
        )
        self.assertTrue({5573, 5574} <= set(granted_spells(fight, 7)))
        cast(5573, fight.actors[7].position, granted=True)
        self.assertIn(
            4121, {entry.reference for entry in fight.actors[7].state_ledger.entries}
        )
        _, adapter = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=action_id + 1,
            critical=False,
            rng=rng,
        )
        selection = eligible_cast_targets(
            fight,
            character,
            deck,
            granted_spells(fight, 7)[5574]["uid"],
            adapter=adapter,
            actor_id=7,
            limit=64,
            maximum_eligible=1,
            line_of_sight=lambda a, b, p: authoritative_visible(1134, a, b, p),
        )
        self.assertTrue(selection["eligible"], selection)
        cell = selection["eligible"][0]["target"]
        placed = cast(5574, cell, granted=True)
        self.assertEqual(placed.plan["costs"]["ap"], 1)
        areas = [
            row
            for row in fight.native_effect_areas.values()
            if row["reference"] == 1049
        ]
        self.assertEqual(len(areas), 1)
        source = deepcopy(areas[0])
        self.assertEqual(source["owner_id"], 7)
        self.assertEqual(tuple(source["cell"]), tuple(cell))
        from wakfu_server.combat_turn_duration import current_turn_duration

        runtime = RuntimeMessages(fight)
        current_turn_duration(fight, runtime.duration)
        before = snapshot(fight)
        resources = (
            fight.actors[7].effect_stats[111],
            fight.actors[7].effect_maxima[111],
        )
        packets = runtime.recover(3, struct.pack(">i", fight.id), now_ms=20000)
        self.assertTrue(any(opcode == 12053 for opcode, _ in packets))
        self.assertEqual(snapshot(fight), before)
        current_source = fight.native_effect_areas[source["uid"]]
        for key in ("uid", "owner_id", "reference", "cell", "native_cells_xy"):
            self.assertEqual(current_source[key], source[key])
        self.assertEqual(
            (fight.actors[7].effect_stats[111], fight.actors[7].effect_maxima[111]),
            resources,
        )
        turns.AniripsaGrantSummonPipelineTests().next_player_turn(
            fight, (character, monster, fight, deck, rng)
        )
        self.assertEqual(fight.current.id, 7)
        self.assertIn(source["uid"], fight.native_effect_areas)
        cast(5574, tuple(source["cell"]), granted=True)
        self.assertNotIn(source["uid"], fight.native_effect_areas)
        self.assertFalse(
            any(row["reference"] == 1049 for row in fight.native_effect_areas.values())
        )


class LightTieHandlerInteractionTests(unittest.TestCase):
    def damage(self, family, source_masteries):
        from test_combat_damage_handler import DamageHandlerTests
        from wakfu_server.combat_effect_removal import _identity_fields

        fixture = DamageHandlerTests()
        fixture.setUp()
        caster, target = fixture.fight.actors[7], fixture.fight.actors[-7]
        caster.effect_stats.update(source_masteries)
        caster.effect_stats[100] = 0
        target.hp = target.max_hp = 10000
        target.effect_stats.update({97: 0, 92: 0, 28: 100, 29: 0, 30: 200, 31: 300})
        fixture.effect["effect_class"] = family
        self.assertTrue(fixture.handler(fixture.effect, {}, fixture.invocation))
        value = _identity_fields(fixture.packets[0][1][19:])[4]
        self.assertEqual(target.hp, 10000 - value)
        return value

    def test_light_ties_choose_native_element_and_its_resistance_at_handler(self):
        for masteries, expected_family, alternate in (
            ({21: 100, 22: 100, 23: 100, 24: 100}, 2, 4),
            ({21: 0, 22: 100, 23: 100, 24: 100}, 4, 3),
            ({21: 0, 22: 0, 23: 100, 24: 100}, 3, 5),
        ):
            with self.subTest(masteries=masteries):
                actual = self.damage(1083, masteries)
                self.assertEqual(actual, self.damage(expected_family, masteries))
                self.assertNotEqual(actual, self.damage(alternate, masteries))


if __name__ == "__main__":
    unittest.main()
