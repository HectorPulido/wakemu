"""Empty-scope distribution uses native area and preserves every owned monster."""
import random
import unittest
from copy import deepcopy

from wakfu_server.monster_idle_distribution import footprint_cells, plan


def grid(size):
    cells = [(x, y, 0) for x in range(size) for y in range(size)]
    edges = [
        (cell, (cell[0] + dx, cell[1] + dy, 0))
        for cell in cells
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if 0 <= cell[0] + dx < size and 0 <= cell[1] + dy < size
    ]
    return dict(cells=cells, edges=edges)


def group(identity, x, y, count=1, status="available"):
    return dict(
        group_id=identity,
        status=status,
        members=[
            dict(
                id=-identity * 10 - index,
                ref=4 + index,
                level=10 + index,
                hp=7 + index,
                max_hp=100 + index,
                map_id=999999,
                instance_id=0,
                team=1,
                x=x + index,
                y=y,
                z=0,
            )
            for index in range(count)
        ],
    )


class IdleDistributionPlannerTests(unittest.TestCase):
    def apply_moves(self, groups, moves):
        result = deepcopy(groups)
        for move in moves:
            original = next(g for g in result if g["group_id"] == move["group_id"])
            self.assertEqual(original["members"], move["expected_members"])
            self.assertEqual(
                [m["id"] for m in move["expected_members"]],
                [m["id"] for m in move["moved_members"]],
            )
            for before, after in zip(original["members"], move["moved_members"]):
                self.assertEqual(
                    {k: v for k, v in before.items() if k not in ("x", "y", "z")},
                    {k: v for k, v in after.items() if k not in ("x", "y", "z")},
                )
            original["members"] = move["moved_members"]
        return result

    def test_uniform_distribution_covers_map_area_without_corner_only_placement(self):
        geometry = grid(16)
        groups = [group(index + 1, index % 4, index // 4) for index in range(16)]
        initial = deepcopy(groups)
        moves = plan(groups, geometry, rng=random.Random(17), actor_radii={4: 0})
        final = self.apply_moves(groups, moves)
        self.assertEqual(groups, initial)
        points = [(g["members"][0]["x"], g["members"][0]["y"]) for g in final]
        self.assertEqual(len(set(points)), len(points))
        self.assertEqual(
            {(x // 8, y // 8) for x, y in points}, {(0, 0), (0, 1), (1, 0), (1, 1)}
        )
        self.assertTrue(any(3 <= x <= 12 and 3 <= y <= 12 for x, y in points))
        self.assertGreaterEqual(len({(x // 4, y // 4) for x, y in points}), 10)
        self.assertTrue(all((x, y, 0) in set(geometry["cells"]) for x, y in points))

    def test_multi_member_groups_preserve_health_stages_membership_and_reserved_actors(
        self,
    ):
        geometry = grid(24)
        groups = [
            group(index + 1, (index % 4) * 4, index // 4, count=4)
            for index in range(12)
        ]
        groups += [
            group(100, 12, 12, status="fighting"),
            group(101, 15, 15, status="defeated"),
        ]
        moves = plan(
            groups,
            geometry,
            occupied=[(23, 23, 0)],
            rng=random.Random(23),
            actor_radii={reference: 0 for reference in range(4, 8)},
        )
        self.assertNotIn(100, {move["group_id"] for move in moves})
        self.assertNotIn(101, {move["group_id"] for move in moves})
        final = self.apply_moves(groups, moves)
        cells = [
            tuple(m[k] for k in ("x", "y", "z"))
            for g in final
            if g["status"] != "defeated"
            for m in g["members"]
        ]
        self.assertEqual(len(cells), len(set(cells)))
        self.assertNotIn((23, 23, 0), cells)
        self.assertTrue(set(cells) <= set(geometry["cells"]))
        self.assertEqual(final[-2:], groups[-2:])

    def test_unplaceable_roster_waits_without_inventing_cells_or_losing_members(self):
        groups = [group(1, 0, 0, count=4)]
        initial = deepcopy(groups)
        moves = plan(
            groups,
            dict(cells=[(0, 0, 0)], edges=[]),
            rng=random.Random(3),
            actor_radii={reference: 0 for reference in range(4, 8)},
        )
        self.assertEqual(moves, [])
        self.assertEqual(groups, initial)

    def test_large_physical_footprints_fit_native_cells_and_never_intersect(self):
        geometry = grid(24)
        groups = [group(index + 1, 2 + 4 * index, 2) for index in range(4)]
        moves = plan(groups, geometry, rng=random.Random(11), actor_radii={4: 1})
        final = self.apply_moves(groups, moves)
        occupied = set()
        native = set(geometry["cells"])
        for item in final:
            physical = set(footprint_cells(item["members"][0], actor_radii={4: 1}))
            self.assertEqual(len(physical), 9)
            self.assertTrue(physical <= native)
            self.assertFalse(physical & occupied)
            occupied.update(physical)
