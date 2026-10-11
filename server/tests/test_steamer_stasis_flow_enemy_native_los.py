"""Stasis Flow's distinct enemy selector on a registered native obstacle."""
import os
import struct
import unittest
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerStasisFlowEnemyNativeLosTests(unittest.TestCase):
    def test_registered_enemy_receives_enemy_state_not_ally_state(self):
        helper = helpers.SteamerRuntimeTests()
        data = helper.fixture(actives=(6922,))
        enemy = data[2].actors[-7]
        self.assertGreaterEqual(enemy.native_obstacle_id, 0)
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monster, fight, deck, rng = data
        before = snapshot(fight)

        def native_los(origin, destination, current):
            return authoritative_visible(
                character["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    actor.id: {actor.position[:2]}
                    for actor in current.actors.values()
                    if actor.hp > 0
                },
            )

        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 6922, *enemy.position),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=10,
            line_of_sight=native_los,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(tx.outcomes))
        states = {s.reference for s in tx.fight.actors[-7].state_ledger.entries}
        self.assertIn(7669, states)
        self.assertNotIn(7668, states)
        self.assertEqual(tx.fight.actors[7].effect_stats[123], 0)
        self.assertEqual(data[2].actors[7].effect_stats[123], 3)
