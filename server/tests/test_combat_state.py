import unittest
from wakfu_server.combat_state import Actor, Fight


class FightStateTests(unittest.TestCase):
    def fight(self, multiple=False):
        actors = [
            Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
            Actor(200, 1, (3, 0, 0), 20, 4, 2, 20, 1),
        ]
        if multiple:
            actors.extend(
                [
                    Actor(-7, 0, (0, 1, 0), 10, 3, 2, 80, 1, 1, True),
                    Actor(201, 1, (3, 1, 0), 20, 4, 2, 10, 1),
                ]
            )
        return Fight(
            7,
            actors,
            {(x, y, 0) for x in range(4) for y in range(2)},
            {0: {(0, 0, 0), (0, 1, 0)}, 1: {(3, 0, 0), (3, 1, 0)}},
        )

    def test_owned_placement_ready_and_current_turn(self):
        f = self.fight()
        with self.assertRaises(ValueError):
            f.ready(9)
        with self.assertRaises(ValueError):
            f.place(9, 100, (0, 1, 0))
        with self.assertRaises(ValueError):
            f.place(1, 100, (2, 0, 0))
        f.place(1, 100, (0, 1, 0))
        f.ready(1)
        self.assertEqual(f.current.id, 100)
        with self.assertRaises(ValueError):
            f.place(1, 100, (0, 0, 0))
        with self.assertRaises(ValueError):
            f.end_turn(1, 100, 9)
        with self.assertRaises(ValueError):
            f.end_turn(9, 100, 1)
        f.end_turn(1, 100, 1)
        self.assertEqual(f.current.id, 200)
        with self.assertRaises(ValueError):
            f.move(1, 100, [(1, 1, 0)])
        f.end_server_turn(200, 2)
        self.assertEqual(f.current.id, 100)

    def test_negative_controlled_actor_and_multiunit_death_order(self):
        f = self.fight(True)
        f.ready(1)
        self.assertEqual(f.order, [100, 200, -7, 201])
        f.apply_damage(100, 200, 50)
        self.assertEqual(f.order, [100, -7, 201])
        self.assertEqual(f.current.id, 100)
        f.end_turn(1, 100, 1)
        self.assertEqual(f.current.id, -7)
        f.move(1, -7, [(1, 1, 0)])
        f.apply_damage(-7, 201, 20)
        self.assertEqual((f.phase, f.winner), ("finished", 0))
        self.assertIsNone(f.current)
        with self.assertRaises(ValueError):
            f.end_turn(1, -7, 2)

    def test_movement_atomicity_resources_and_terrain(self):
        f = self.fight()
        f.ready(1)
        with self.assertRaises(ValueError):
            f.move(1, 100, [(1, 0, 0), (3, 0, 0)])
        self.assertEqual((f.current.position, f.current.mp), ((0, 0, 0), 3))
        with self.assertRaises(ValueError):
            f.move(1, 100, [(1, 1, 0)])
        f.move(1, 100, [(1, 0, 0), (2, 0, 0)])
        self.assertEqual(f.current.mp, 1)
        with self.assertRaises(ValueError):
            f.move(1, 100, [(2, 1, 0), (1, 1, 0)])
        f.spend(1, 100, ap=4)
        with self.assertRaises(ValueError):
            f.spend(1, 100, ap=3)
        f.end_turn(1, 100, 1)
        f.end_server_turn(200, 2)
        self.assertEqual((f.current.ap, f.current.mp), (6, 3))

    def test_death_current_actor_advances_without_skipping(self):
        f = self.fight(True)
        f.ready(1)
        f.apply_damage(100, 100, 60)
        self.assertEqual(f.current.id, 200)
        self.assertEqual(f.turn_id, 2)

    def test_wounded_actor_preserves_max_hp_and_per_actor_turn_number(self):
        wounded = Actor(9, 0, (0, 0, 0), 56, 6, 3, 100, 1, 1, True, max_hp=60)
        self.assertEqual((wounded.hp, wounded.max_hp), (56, 60))
        f = self.fight()
        f.ready(1)
        f.end_turn(1, 100, 1)
        f.end_server_turn(200, 2)
        self.assertEqual((f.turn_id, f.current.turn_count), (3, 2))
        with self.assertRaises(ValueError):
            f.end_turn(1, 100, 3)
        f.end_turn(1, 100, 2)

    def test_trigger_damage_outside_casters_turn_keeps_request_guard(self):
        f = self.fight(True)
        f.ready(1)
        with self.assertRaises(ValueError):
            f.apply_damage(200, 100, 5)
        self.assertEqual(f.apply_effect_damage(200, 100, 5), 5)
        self.assertEqual((f.actors[100].hp, f.current.id), (55, 100))
        f.apply_effect_damage(200, 100, 55)
        self.assertEqual(f.current.id, 200)
        self.assertEqual(f.order, [200, -7, 201])
        self.assertEqual(sum(e["kind"] == "death" for e in f.events), 1)

    def test_trigger_damage_rejects_unknown_source_and_inactive_fight(self):
        f = self.fight()
        with self.assertRaises(ValueError):
            f.apply_effect_damage(100, 200, 1)
        f.ready(1)
        with self.assertRaises(ValueError):
            f.apply_effect_damage(999, 200, 1)
        self.assertEqual(f.actors[200].hp, 20)

    def test_healing_reaction_clamps_to_maximum_without_turn_change(self):
        f = self.fight(True)
        f.ready(1)
        f.apply_effect_damage(200, 100, 25)
        self.assertEqual(f.apply_effect_healing(-7, 100, 40), 25)
        self.assertEqual((f.actors[100].hp, f.current.id), (60, 100))
        self.assertEqual(f.events[-1]["kind"], "healing")
        self.assertEqual(f.events[-1]["amount"], 25)
        with self.assertRaises(ValueError):
            f.apply_effect_healing(-7, 100, -1)
        f.apply_effect_damage(200, 100, 60)
        with self.assertRaises(ValueError):
            f.apply_effect_healing(-7, 100, 10)
