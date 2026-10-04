import unittest
from wakfu_server.combat_placement_cells import generate
from wakfu_server.combat_wire import arena, topology, decode_topology


class PlacementCellTests(unittest.TestCase):
    def grid(self):
        cells = {(x, y, 0) for x in range(8) for y in range(4)}
        edges = {
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        }
        return cells, edges

    def test_multiple_owned_members_reserve_cells_and_native_wire_keeps_all_slots(self):
        cells, edges = self.grid()
        seeds = {0: {(0, 0, 0)}, 1: {(7, 0, 0), (7, 1, 0)}}
        placement = generate(cells, edges, seeds)
        self.assertEqual([len(placement[t]) for t in (0, 1)], [6, 6])
        self.assertTrue(all(seeds[t] <= placement[t] for t in (0, 1)))
        self.assertFalse(placement[0] & placement[1])
        data = arena(777, 1, sorted(cells), placement)
        decoded = decode_topology(topology(data))
        self.assertEqual(
            decoded["team_values"], []
        )  # No fake obstacles per placement cell.
        self.assertEqual(decoded["cell_flags"].count(0), 6)
        self.assertEqual(decoded["cell_flags"].count(1), 6)
        self.assertEqual(
            generate(reversed(sorted(cells)), reversed(sorted(edges)), seeds), placement
        )

    def test_native_staircase_and_separated_upper_floor_never_fabricate_connections(
        self,
    ):
        cells = {(0, 0, 0), (1, 0, 2), (2, 0, 4), (9, 9, 10), (9, 10, 10)}
        edges = {((0, 0, 0), (1, 0, 2)), ((9, 9, 10), (9, 10, 10))}
        placement = generate(cells, edges, {0: {(0, 0, 0)}, 1: {(9, 9, 10)}})
        self.assertEqual(placement[0], {(0, 0, 0), (1, 0, 2)})
        self.assertEqual(placement[1], {(9, 9, 10), (9, 10, 10)})
        self.assertNotIn((2, 0, 4), placement[0])

    def test_tiny_map_limits_capacity_and_enemy_actor_seed_blocks_passage(self):
        cells = {(x, 0, 0) for x in range(3)}
        edges = {((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (2, 0, 0))}
        placement = generate(cells, edges, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}})
        self.assertEqual(placement[0], {(0, 0, 0)})
        self.assertEqual(placement[1], {(1, 0, 0), (2, 0, 0)})

    def test_more_actors_than_policy_and_invalid_geometry(self):
        cells, edges = self.grid()
        seeds = {0: {(0, 0, 0)}, 1: {(7, y, 0) for y in range(4)}}
        placement = generate(cells, edges, seeds, slots_per_team=2)
        self.assertEqual(len(placement[1]), 4)
        with self.assertRaises(ValueError):
            generate(cells | {(0, 0, 10)}, edges, seeds)
        with self.assertRaises(ValueError):
            generate(cells, edges, {0: {(0, 0, 0)}, 1: {(0, 0, 0)}})
        with self.assertRaises(ValueError):
            generate(cells, edges, seeds, slots_per_team=True)

    def test_two_player_placement_and_readiness_share_generated_capacity(self):
        from wakfu_server.combat_state import Actor, Fight

        cells, edges = self.grid()
        first = Actor(1, 0, (0, 0, 0), 60, 6, 3, 10, 1, 7, True)
        second = Actor(2, 0, (0, 1, 0), 60, 6, 3, 5, 1, 8, True)
        monster = Actor(-3, 1, (7, 0, 0), 12, 6, 3, 0, 1)
        placement = generate(
            cells, edges, {0: {first.position, second.position}, 1: {monster.position}}
        )
        fight = Fight(9, [first, second, monster], cells, placement, edges)
        extra = min(placement[0] - {first.position, second.position})
        fight.place(7, first.id, extra)
        self.assertEqual(first.position, extra)
        with self.assertRaises(ValueError):
            fight.place(7, second.id, extra)
        with self.assertRaises(ValueError):
            fight.place(8, second.id, extra)
        fight.ready(7)
        self.assertEqual(fight.phase, "placement")
        fight.ready(8)
        self.assertEqual(fight.phase, "active")
