import struct
import unittest
from tests import test_combat_results
from wakfu_server.combat_death import (
    death_messages,
    despawn_monster,
    dead_world_removals,
)
from wakfu_server.combat_results import finish_messages


class DeathTests(unittest.TestCase):
    def test_group_removal_is_independent_of_registry_finish_and_validates_all(self):
        f, runtime, metadata = test_combat_results.FightResultTests().state()
        self.assertEqual(dead_world_removals(f, [-200]), [despawn_monster(f, -200)])
        for roster in ([-200, 100], [-200, -999], [-200, -200], []):
            with self.assertRaises(ValueError):
                dead_world_removals(f, roster)
        f.actors[-200].hp = 1
        self.assertEqual(dead_world_removals(f, [-200]), [])
        f.phase = "active"
        with self.assertRaises(ValueError):
            dead_world_removals(f, [-200])

    def test_dead_owned_npc_animation_precedes_normal_results(self):
        f, runtime, metadata = test_combat_results.FightResultTests().state()
        death = death_messages(runtime, -200)
        self.assertEqual([op for op, body in death], [12727, 13420])
        self.assertEqual(death[0][1], struct.pack(">iiiqB", 7, 1, -1, -200, 2))
        results = finish_messages(
            runtime, metadata, duration_ms=1000, fight_instance_id=8, initiator_id=100
        )
        self.assertEqual(struct.unpack_from(">i", results[0][1], 4)[0], 2)
        with self.assertRaises(ValueError):
            death_messages(runtime, -200)

    def test_alive_and_foreign_actors_rejected_without_action_mutation(self):
        f, runtime, metadata = test_combat_results.FightResultTests().state()
        for identity in (100, -999):
            with self.assertRaises(ValueError):
                death_messages(runtime, identity)
        self.assertEqual(runtime.action_id, 0)

    def test_corpse_removal_uses_actor_opcode_and_type_not_interactive_objects(self):
        f, runtime, metadata = test_combat_results.FightResultTests().state()
        self.assertEqual(
            despawn_monster(f, -200), (12304, b"\0\0\1\1" + struct.pack(">q", -200))
        )
        for identity in (100, -999):
            with self.assertRaises(ValueError):
                despawn_monster(f, identity)
        f.phase = "active"
        with self.assertRaises(ValueError):
            despawn_monster(f, -200)
