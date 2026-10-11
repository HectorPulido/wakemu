"""Actual AP/MP theft must survive the target's next turn boundary."""
import random
import struct
import unittest

import test_aniripsa_grant_summon_pipeline as turn_helpers
import test_combat_spell_transaction as fixture_helpers
import test_xelor_runtime_pipeline as xelor_helpers
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_start,
)
from wakfu_server.spells import encode_deck


class ResourceLossTurnBoundaryTests(unittest.TestCase):
    @staticmethod
    def states(actor):
        return {entry.reference: entry.level for entry in actor.state_ledger.entries}

    def cra_fixture(self):
        (
            character,
            monster,
            fight,
        ) = fixture_helpers.SpellTransactionTests().native_server_fixture(
            9, 200, native_qi=True, target_hp=20000
        )
        deck = encode_deck([4816])
        rng = random.Random(4816)
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
        fight, _ = prepare_server_turn_start(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=fight.current.id,
            action_id=2,
            rng=rng,
            area_callbacks=True,
        )
        fixture = character, monster, fight, deck, rng
        for _ in range(8):
            if fight.current.id == 7:
                break
            turn_helpers.AniripsaGrantSummonPipelineTests().end_current_turn(
                fight, fixture
            )
        else:
            self.fail("Cra did not receive a turn after native initialization")
        return character, monster, fight, deck, rng

    def test_azotadora_mp_loss_survives_victim_turn_and_refills_after_expiry(self):
        character, monster, fight, deck, rng = self.cra_fixture()
        caster = fight.actors[7]
        target = fight.actors[-7]
        target_mp_before = target.mp
        target_mp_max = target.max_mp
        target_hp_before = target.hp
        self.assertEqual(target_mp_before, target_mp_max)

        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 4816, *target.position),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=3,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        after_cast = transaction.fight.actors[-7]
        actual_mp_loss = target_mp_before - after_cast.mp
        self.assertGreater(actual_mp_loss, 0)
        self.assertLess(after_cast.hp, target_hp_before)
        self.assertEqual(after_cast.max_mp, target_mp_max)
        self.assertEqual(self.states(after_cast).get(5227), actual_mp_loss * 10)

        fixture = (character, monster, transaction.fight, deck, rng)
        turn_helpers.AniripsaGrantSummonPipelineTests().end_current_turn(
            transaction.fight, fixture
        )
        victim_turn = transaction.fight.actors[-7]
        self.assertEqual(transaction.fight.current.id, -7)
        self.assertEqual(victim_turn.mp, target_mp_before - actual_mp_loss)
        self.assertEqual(victim_turn.max_mp, target_mp_max)
        hp_after_cast = after_cast.hp
        self.assertEqual(victim_turn.hp, hp_after_cast)

        turn_helpers.AniripsaGrantSummonPipelineTests().end_current_turn(
            transaction.fight, fixture
        )
        self.assertEqual(transaction.fight.current.id, 7)
        self.assertEqual(transaction.fight.actors[-7].mp, target_mp_max)
        self.assertEqual(transaction.fight.actors[-7].hp, hp_after_cast)
        turn_helpers.AniripsaGrantSummonPipelineTests().end_current_turn(
            transaction.fight, fixture
        )
        self.assertEqual(transaction.fight.current.id, -7)
        self.assertEqual(transaction.fight.actors[-7].mp, target_mp_max)
        self.assertEqual(transaction.fight.actors[-7].hp, hp_after_cast)

    def test_slowdown_ap_loss_survives_victim_turn_with_paid_wp_unchanged(self):
        data = xelor_helpers.XelorRuntimePipelineTests().fixture()
        fight = data[2]
        target = fight.actors[-7]
        target_ap_before = target.ap
        target_ap_max = target.max_ap
        target_hp_before = target.hp
        caster_wp_before = fight.actors[7].effect_stats[4]
        self.assertEqual(target_ap_before, target_ap_max)

        transaction = xelor_helpers.XelorRuntimePipelineTests().cast(
            data, 775, target.position, action_id=30
        )
        caster_wp_after_payment = transaction.fight.actors[7].effect_stats[4]
        self.assertEqual(caster_wp_after_payment, caster_wp_before - 1)
        after_cast = transaction.fight.actors[-7]
        actual_ap_loss = target_ap_before - after_cast.ap
        self.assertGreater(actual_ap_loss, 0)
        self.assertLess(after_cast.hp, target_hp_before)
        hp_after_cast = after_cast.hp
        self.assertEqual(after_cast.max_ap, target_ap_max)
        self.assertEqual(self.states(after_cast).get(5227), actual_ap_loss * 10)
        self.assertEqual(
            transaction.fight.actors[7].effect_stats[4], caster_wp_after_payment
        )

        helper = turn_helpers.AniripsaGrantSummonPipelineTests()
        fixture = xelor_helpers.XelorRuntimePipelineTests().adopt(
            data, transaction.fight
        )
        helper.end_current_turn(transaction.fight, fixture)
        victim_turn = transaction.fight.actors[-7]
        self.assertEqual(transaction.fight.current.id, -7)
        self.assertEqual(victim_turn.ap, target_ap_before - actual_ap_loss)
        self.assertEqual(victim_turn.max_ap, target_ap_max)
        self.assertEqual(victim_turn.hp, hp_after_cast)
        self.assertEqual(transaction.fight.actors[7].effect_stats[4], caster_wp_before)

        helper.end_current_turn(transaction.fight, fixture)
        self.assertEqual(transaction.fight.current.id, 7)
        self.assertEqual(transaction.fight.actors[-7].ap, target_ap_max)
        self.assertEqual(transaction.fight.actors[-7].hp, hp_after_cast)
        self.assertEqual(transaction.fight.actors[7].effect_stats[4], caster_wp_before)
        helper.end_current_turn(transaction.fight, fixture)
        self.assertEqual(transaction.fight.current.id, -7)
        self.assertEqual(transaction.fight.actors[-7].ap, target_ap_max)
        self.assertEqual(transaction.fight.actors[-7].hp, hp_after_cast)
        self.assertEqual(transaction.fight.actors[7].effect_stats[4], caster_wp_before)

    def test_actual_ready_maximum_penalty_is_not_erased_on_first_owned_turn(self):
        helper = xelor_helpers.XelorRuntimePipelineTests()
        baseline = helper.fixture(passives=())[2].actors[7]
        selected_fight = helper.fixture(passives=(756,))[2]
        selected = selected_fight.actors[7]
        self.assertEqual(selected_fight.current.id, 7)
        self.assertEqual(selected.max_mp, baseline.max_mp - 2)
        self.assertEqual(selected.mp, baseline.mp - 2)

    def test_native_companion_resources_survive_its_first_actual_turn_start(self):
        import test_enutrof_runtime as enutrof_helpers

        fixture = enutrof_helpers.EnutrofRuntimeTests().fixture(
            passives=(8279,), actives=(8240,)
        )
        fight = fixture[2]
        companion = next(
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        initial = (companion.ap, companion.max_ap, companion.mp, companion.max_mp)
        helper = turn_helpers.AniripsaGrantSummonPipelineTests()
        for _ in range(24):
            if fight.current.id == companion.id:
                break
            helper.end_current_turn(fight, fixture)
        self.assertEqual(fight.current.id, companion.id)
        self.assertEqual(
            (companion.ap, companion.max_ap, companion.mp, companion.max_mp),
            initial,
        )


if __name__ == "__main__":
    unittest.main()
