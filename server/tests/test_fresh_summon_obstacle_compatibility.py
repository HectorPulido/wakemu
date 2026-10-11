"""Fresh constructor sentinels do not weaken registered QK validation."""
from types import SimpleNamespace
import unittest

from wakfu_server.combat_summon_creation import register_fresh_summon_obstacle


class FreshSummonObstacleCompatibilityTests(unittest.TestCase):
    def fixture(self, slot=-1):
        members = {
            7: SimpleNamespace(id=7, native_obstacle_id=0),
            -7: SimpleNamespace(id=-7, native_obstacle_id=1),
        }
        return (
            SimpleNamespace(actors=members, native_effect_areas={}),
            SimpleNamespace(id=901, native_obstacle_id=slot),
        )

    def test_native_fresh_minus_one_gets_first_free_actor_only_slot(self):
        fight, actor = self.fixture()
        register_fresh_summon_obstacle(fight, actor)
        self.assertEqual(actor.native_obstacle_id, 2)
        self.assertEqual([a.native_obstacle_id for a in fight.actors.values()], [0, 1])
        self.assertNotIn(actor.id, fight.actors)

    def test_registered_invalid_or_duplicate_slots_remain_rejected(self):
        for slot in (-1, 0):
            fight, actor = self.fixture()
            fight.actors[-7].native_obstacle_id = slot
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                register_fresh_summon_obstacle(fight, actor)
            self.assertEqual(actor.native_obstacle_id, -1)

    def test_existing_actor_cannot_be_reallocated_as_fresh(self):
        fight, actor = self.fixture()
        fight.actors[actor.id] = actor
        with self.assertRaisesRegex(ValueError, "already in the fighter roster"):
            register_fresh_summon_obstacle(fight, actor)
        self.assertEqual(actor.native_obstacle_id, -1)
