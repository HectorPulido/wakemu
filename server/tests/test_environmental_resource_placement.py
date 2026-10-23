"""Reachable zone-wide placement on native terrain and bounded sparse controls."""
from collections import defaultdict, deque
import unittest

from wakfu_server.objectives.environmental_resource_placement import plan


class EnvironmentalResourcePlacementTests(unittest.TestCase):
    def test_native_zone_spread_preserves_access_and_caps_disconnected_sparse_capacity(
        self,
    ):
        from wakfu_server.planting_cells import cells
        from wakfu_server.combat_terrain import map_geometry

        surfaces = cells(327)
        geometry = map_geometry(327)
        floor = {tuple(p) for p in geometry["cells"]}
        edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
        neighbors = defaultdict(set)
        for a, b in edges:
            if a in floor and b in floor and (b, a) in edges:
                neighbors[a].add(b)
        remaining, components = set(floor), []
        while remaining:
            root = min(remaining)
            reached, queue = {root}, deque([root])
            while queue:
                for neighbor in neighbors[queue.popleft()]:
                    if neighbor not in reached:
                        reached.add(neighbor)
                        queue.append(neighbor)
            remaining.difference_update(reached)
            components.append(reached)
        original = {
            (x, y, row["z"])
            for (x, y), rows in surfaces.items()
            for row in rows
            if row["region_id"] == 56601
        }
        connected = max(components, key=lambda component: len(component & original))
        origin = min(connected & original)
        kwargs = dict(
            region_id=56601,
            origins=[origin],
            taken=set(),
            quantity=200,
            seed="native-map327-zone-spread",
            reserve=0,
        )
        rows = plan(surfaces, geometry, **kwargs)
        self.assertEqual(len(rows), 200)
        self.assertEqual(rows, plan(surfaces, geometry, **kwargs))
        self.assertNotEqual(
            rows, plan(surfaces, geometry, **dict(kwargs, seed="another-event"))
        )
        positions = {(row["x"], row["y"], row["z"]) for row in rows}
        xy = {point[:2] for point in positions}
        self.assertEqual(len(xy), 200)
        self.assertTrue(positions <= original & connected)
        for row in rows:
            point = (row["x"], row["y"], row["z"])
            route = tuple(map(tuple, row["path"]))
            approach = tuple(row["approach"])
            self.assertEqual(route[0], origin)
            self.assertEqual(route[-1], approach)
            self.assertTrue(all(p[:2] not in xy for p in route))
            for a, b in zip(route, route[1:]):
                self.assertIn((a, b), edges)
                self.assertIn((b, a), edges)
            self.assertIn((approach, point), edges)
            self.assertIn((point, approach), edges)
        for a in positions:
            for b in positions:
                if a != b:
                    self.assertGreaterEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 3)
        # Independent extent check catches sorted-prefix or near-player clustering.
        available = original & connected
        for axis in (0, 1):
            extent = max(p[axis] for p in available) - min(p[axis] for p in available)
            selected_extent = max(p[axis] for p in positions) - min(
                p[axis] for p in positions
            )
            self.assertGreaterEqual(selected_extent, extent * 0.7)

        # Declared synthetic control: upper floor is disconnected, an occupied
        # bridge blocks its far component, and sparse capacity must not fill gaps.
        ground = [(x, 0, 0) for x in range(18)]
        upper = [(x, 0, 9) for x in range(18)]
        control_edges = []
        for level in (ground, upper):
            for a, b in zip(level, level[1:]):
                control_edges.extend(((a, b), (b, a)))
        control_surfaces = {
            (x, 0): [dict(z=z, region_id=1) for z in (0, 9)] for x in range(18)
        }
        control = plan(
            control_surfaces,
            dict(cells=ground + upper, edges=control_edges),
            region_id=1,
            origins=[ground[0]],
            taken={(9, 0)},
            quantity=200,
            reserve=0,
            seed="sparse-native-contract",
        )
        self.assertGreater(len(control), 0)
        self.assertLess(len(control), 200)
        self.assertTrue(all(row["z"] == 0 and row["x"] < 9 for row in control))
        self.assertEqual(
            plan(
                control_surfaces,
                dict(cells=ground + upper, edges=control_edges),
                region_id=1,
                origins=[(99, 99, 0)],
                taken=set(),
                quantity=200,
                reserve=0,
                seed="absent-origin",
            ),
            (),
        )
