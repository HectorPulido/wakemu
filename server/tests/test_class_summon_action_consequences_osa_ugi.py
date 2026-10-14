"""Actual owned Wauwau casts assert gameplay consequences, not only book entries."""
import os
import unittest
from random import Random
from unittest.mock import patch

import test_combat_uginak_wauwau_lifecycle as lifecycle
from wakfu_server.combat_server_spell import prepare_server_initialization


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
@patch.dict(
    os.environ, {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"}
)
class WauwauActionConsequencesTests(unittest.TestCase):
    def controlled_summon(self):
        fixture = lifecycle.WauwauLifecycleTests()
        characters, decks, fight = fixture.fixture()
        for actor_id in (7, 8):
            fight, _ = prepare_server_initialization(
                characters[actor_id],
                {},
                fight,
                characters[actor_id]["account_id"],
                decks[actor_id],
                action_id=actor_id,
                rng=Random(7),
                fight_start=(actor_id == 8),
                player_characters=characters,
                deck_blobs=decks,
            )
        for action in range(10, 30):
            if fight.current.id == 7:
                break
            fight, _ = fixture.finish_current(characters, decks, fight, action)
        self.assertEqual(fight.current.id, 7)
        summoned = fixture.cast(characters, decks, fight, 7, 6286, (-3, -18, 0), 31)
        summon_id = next(iter(set(summoned.fight.actors) - set(fight.actors)))
        fight = summoned.fight
        for action in range(32, 52):
            if fight.current.id == summon_id:
                break
            fight, _ = fixture.finish_current(characters, decks, fight, action)
        self.assertEqual(fight.current.id, summon_id)
        return fixture, characters, decks, fight, summon_id

    def test_6291_transfers_health_and_pays_once_without_mutating_source(self):
        fixture, characters, decks, fight, summon_id = self.controlled_summon()
        before = (
            fight.actors[summon_id].hp,
            fight.actors[summon_id].ap,
            fight.actors[summon_id].effect_stats[4],
            fight.actors[7].hp,
        )
        result = fixture.cast(
            characters, decks, fight, summon_id, 6291, fight.actors[7].position, 60
        )
        summon = result.fight.actors[summon_id]
        self.assertLess(summon.hp, before[0])
        self.assertEqual(summon.ap, before[1] - 2)
        self.assertEqual(summon.effect_stats[4], before[2] - 1)
        self.assertEqual(result.fight.actors[7].hp, result.fight.actors[7].max_hp)
        self.assertEqual(
            (
                fight.actors[summon_id].hp,
                fight.actors[summon_id].ap,
                fight.actors[summon_id].effect_stats[4],
                fight.actors[7].hp,
            ),
            before,
        )

    def test_6292_native_seeded_owner_loss_and_resistance_preserve_source(self):
        from wakfu_server import combat_resource_loss_handler as loss_handler
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        fixture, characters, decks, fight, summon_id = self.controlled_summon()
        before_mp = fight.actors[8].mp
        before_ap = fight.actors[summon_id].ap
        owner_hp = fight.actors[7].hp
        original_calculation = loss_handler.resolve_resource_loss
        outcomes = set()
        observations = []
        chain_trace = []

        def observe_calculation(**kwargs):
            plan = original_calculation(**kwargs)
            observations.append(plan)
            return plan

        def observe_chain(**row):
            if row.get("effect_reference") in {341570, 341572}:
                chain_trace.append(row)

        # Real seeded native transactions preserve the original Fight. The dog
        # cancels its original loss and reapplies it through its actual owner;
        # the owner-attributed calculation can independently be resisted.
        for seed in range(16):
            with self.subTest(seed=seed):
                observations.clear()
                chain_trace.clear()
                with patch.object(
                    lifecycle, "Random", lambda _: Random(seed)
                ), patch.object(
                    loss_handler, "resolve_resource_loss", observe_calculation
                ), combat_diagnostic_scope(
                    observe_chain, limit=4096
                ):
                    result = fixture.cast(
                        characters,
                        decks,
                        fight,
                        summon_id,
                        6292,
                        fight.actors[8].position,
                        60,
                    )
                loss = before_mp - result.fight.actors[8].mp
                self.assertIn(loss, (0, 1))
                outcomes.add(loss)
                self.assertTrue(observations)
                self.assertEqual(observations[0].requested, 1)
                if observations[0].calculated > 0:
                    self.assertTrue(
                        any(
                            row.get("effect_reference") == 341572
                            and row.get("caster_id") == 7
                            and row.get("target_id") == 8
                            and row.get("status") in {"completed", "no_effect"}
                            for row in chain_trace
                        ),
                        chain_trace,
                    )
                    self.assertGreaterEqual(len(observations), 2)
                    self.assertEqual(loss, observations[-1].actual)
                else:
                    self.assertEqual(loss, 0)
                self.assertEqual(result.fight.actors[summon_id].ap, before_ap - 2)
                self.assertEqual(result.fight.actors[7].hp, owner_hp)
                self.assertEqual(fight.actors[8].mp, before_mp)
                self.assertEqual(fight.actors[summon_id].ap, before_ap)
                if outcomes == {0, 1}:
                    break
        self.assertEqual(outcomes, {0, 1}, "Need actual resisted and successful casts")

    def test_6293_creates_one_owned_area_at_selected_cell(self):
        fixture, characters, decks, fight, summon_id = self.controlled_summon()
        target = (-3, -16, 0)
        old_ids = set(getattr(fight, "native_effect_areas", {}))
        before_ap = fight.actors[summon_id].ap
        result = fixture.cast(characters, decks, fight, summon_id, 6293, target, 60)
        areas = result.fight.native_effect_areas
        fresh = [areas[uid] for uid in set(areas) - old_ids]
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh[0]["reference"], 1268)
        self.assertEqual(fresh[0]["owner_id"], summon_id)
        self.assertEqual(tuple(fresh[0]["cell"]), target)
        self.assertEqual(result.fight.actors[summon_id].ap, before_ap - 4)
        self.assertEqual(set(getattr(fight, "native_effect_areas", {})), old_ids)

    def test_6294_stabilizes_selected_recipient_and_pays_once(self):
        fixture, characters, decks, fight, summon_id = self.controlled_summon()
        before_ap = fight.actors[summon_id].ap
        before_wp = fight.actors[summon_id].effect_stats[4]
        result = fixture.cast(
            characters,
            decks,
            fight,
            summon_id,
            6294,
            fight.actors[summon_id].position,
            60,
        )
        states = {
            entry.reference
            for entry in result.fight.actors[summon_id].state_ledger.entries
        }
        self.assertIn(3434, states)
        self.assertNotIn(
            3434,
            {entry.reference for entry in result.fight.actors[8].state_ledger.entries},
        )
        self.assertEqual(result.fight.actors[summon_id].ap, before_ap - 2)
        self.assertEqual(result.fight.actors[summon_id].effect_stats[4], before_wp - 1)
        self.assertNotIn(
            3434,
            {entry.reference for entry in fight.actors[summon_id].state_ledger.entries},
        )
