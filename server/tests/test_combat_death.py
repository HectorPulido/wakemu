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
    def test_raw_new_deaths_finalize_state_without_allocating_native_actions(self):
        from wakfu_server.combat_death import newly_registered_death_messages

        fight, runtime, _ = test_combat_results.FightResultTests().state()
        fight.events = [dict(sequence=1, kind="death", actor_id=-200)]
        packets = newly_registered_death_messages(
            runtime, after_sequence=0, prepare_delivery=False
        )
        self.assertEqual(runtime.native_action_id, 0)
        self.assertEqual(
            [struct.unpack(">iiiqB", body)[3:] for op, body in packets if op == 12727],
            [(-200, 0), (-200, 2)],
        )
        self.assertEqual(
            fight.actors[-200].native_death_status["last_writer"], "owned.aTS.F.type2"
        )
        prepared = runtime.prepare_delivery(packets)
        self.assertEqual(runtime.native_action_id, 2)
        self.assertIs(runtime.prepare_delivery(prepared), prepared)
        self.assertEqual(newly_registered_death_messages(runtime, after_sequence=0), [])

    def test_action_death_delivery_is_unique_and_excludes_old_or_revived_deaths(self):
        from wakfu_server.combat_death import newly_registered_death_messages

        fight, runtime, _ = test_combat_results.FightResultTests().state()
        fight.events = [
            dict(sequence=1, kind="death", actor_id=100),
            dict(sequence=2, kind="death", actor_id=-200),
            dict(sequence=3, kind="death", actor_id=-200),
            dict(sequence=4, kind="death", actor_id=100),
        ]
        packets = newly_registered_death_messages(runtime, after_sequence=1)
        deaths = [
            struct.unpack(">iiiqB", body)[3:] for op, body in packets if op == 12727
        ]
        self.assertEqual(deaths, [(-200, 0), (-200, 2)])
        self.assertEqual(newly_registered_death_messages(runtime, after_sequence=1), [])
        for invalid in (-1, True, None):
            with self.assertRaises(ValueError):
                newly_registered_death_messages(runtime, after_sequence=invalid)

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
        self.assertEqual([op for op, body in death], [12727, 12727, 13420])
        self.assertEqual(death[0][1], struct.pack(">iiiqB", 7, 1, -1, -200, 0))
        self.assertEqual(death[1][1], struct.pack(">iiiqB", 7, 1, -1, -200, 2))
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

    def test_multiple_npc_deaths_publish_ko_before_next_surviving_turn(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        actors = [Actor(100, 0, (0, 0, 0), 60, 6, 3, 30, 1, 1, True)]
        actors.extend(
            Actor(-200 - n, 1, (n + 1, 0, 0), 20, 6, 3, 20 - n, 1) for n in range(3)
        )
        fight = Fight(
            7,
            actors,
            {actor.position for actor in actors},
            {0: {actors[0].position}, 1: {actor.position for actor in actors[1:]}},
        )
        fight.ready(1)
        runtime = RuntimeMessages(fight)
        # A single owned AoE preview removes two upcoming timeline members.
        with fight.effect_resolution():
            fight.actors[-200].hp = 0
            fight.actors[-201].hp = 0
        self.assertEqual(fight.order, [100, -202])
        packets = []
        for identity in (-200, -201):
            packets.extend(runtime.prepare_delivery(death_messages(runtime, identity)))
        packets.extend(runtime.end_turn(1, 100, 1))
        packets.extend(runtime.acknowledge_turn(struct.pack(">i", 1)))
        deaths = [
            (index, struct.unpack(">iiiqB", payload))
            for index, (opcode, payload) in enumerate(packets)
            if opcode == 12727
        ]
        self.assertEqual(
            [(row[3], row[4]) for _, row in deaths],
            [(-200, 0), (-200, 2), (-201, 0), (-201, 2)],
        )
        start = next(
            index for index, (opcode, _) in enumerate(packets) if opcode == 12502
        )
        self.assertTrue(all(index < start for index, _ in deaths))
        self.assertEqual(fight.current.id, -202)
        ids = [row[1] for _, row in deaths]
        self.assertEqual(len(set(ids)), 4)
        self.assertEqual(ids, sorted(ids))

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
