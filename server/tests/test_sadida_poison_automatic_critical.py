"""Actual automatic critical poison uses the same paid branch and shared RNG."""
import random
import struct
import unittest
import test_sadida_semantic_qualification as semantics
import test_aniripsa_grant_summon_pipeline as turns
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.fight_checkpoint_store import snapshot


class SadidaPoisonAutomaticCriticalTests(unittest.TestCase):
    def test_automatic_critical_poison_matches_explicit_branch_and_delayed_rng(self):
        observations = []
        for automatic in (True, False):
            with self.subTest(automatic=automatic):
                data = semantics.SadidaSemanticQualificationTests().fixture_at_distance(
                    3
                )
                character, monster, fight, deck, _, packets = data
                chance = fight.actors[7].effect_stats[9]
                self.assertGreater(chance, 0)
                self.assertLess(chance, 100)
                seed = next(
                    seed
                    for seed in range(10000)
                    if random.Random(seed).randint(1, 100) <= chance
                )
                rng = random.Random(seed)
                roll = random.Random(seed).randint(1, 100)
                if not automatic:
                    self.assertEqual(rng.randint(1, 100), roll)
                before = snapshot(fight)
                target = fight.actors[-7]

                def los(origin, destination, current):
                    return authoritative_visible(
                        character["map_id"],
                        origin,
                        destination,
                        current,
                        blocking_footprints={
                            a.id: {a.position[:2]}
                            for a in current.actors.values()
                            if a.hp > 0
                        },
                    )

                tx = prepare_server_spell(
                    struct.pack(">qqiih", 7, (7 << 32) | 914, *target.position),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=10,
                    line_of_sight=los,
                    critical=None if automatic else True,
                    rng=rng,
                )
                self.assertEqual(snapshot(fight), before)
                self.assertTrue(tx.plan["critical_decision"]["critical"])
                if automatic:
                    self.assertEqual(
                        tx.plan["critical_decision"]["critical_roll"], roll
                    )
                poisoned = tx.fight.actors[-7]
                self.assertEqual(
                    next(
                        s.level
                        for s in poisoned.state_ledger.entries
                        if s.reference == 3617
                    ),
                    125,
                )
                self.assertEqual(poisoned.hp, target.hp)
                resources = (
                    fight.actors[7].ap - tx.fight.actors[7].ap,
                    fight.actors[7].mp - tx.fight.actors[7].mp,
                    fight.actors[7].effect_stats[4]
                    - tx.fight.actors[7].effect_stats[4],
                )
                cast_rng = rng.getstate()
                data = (character, monster, tx.fight, deck, rng, packets)
                turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                    tx.fight, data[:5]
                )
                self.assertEqual(tx.fight.current.id, -7)
                damage = target.hp - tx.fight.actors[-7].hp
                self.assertGreater(damage, 0)
                observations.append((resources, damage, cast_rng, rng.getstate()))
        self.assertGreater(observations[0][0][0], 0)
        self.assertEqual(observations[0], observations[1])
