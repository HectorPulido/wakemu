"""Focused unit contracts for deterministic administrative population plans."""

import unittest
import types
import random
from collections import Counter
from unittest.mock import patch

from wakfu_server import ecology_admin_planner


class EcologyAdminPlannerTests(unittest.TestCase):
    def setUp(self):
        self.region = {
            "monster_capacity": 64,
            "monster_families": [{"family_id": 10}, {"family_id": 20}],
        }
        self.catalog = {
            "families": [
                {
                    "family_id": 10,
                    "tiers": [
                        {
                            "rank": 1,
                            "candidates": [
                                {
                                    "reference": 100,
                                    "min_level": 3,
                                    "boss_classification": "regular",
                                },
                                {
                                    "reference": 101,
                                    "min_level": 4,
                                    "boss_classification": "boss",
                                },
                            ],
                        },
                        {
                            "rank": 2,
                            "candidates": [
                                {
                                    "reference": 102,
                                    "min_level": 8,
                                    "boss_classification": "regular",
                                },
                                {
                                    "reference": 103,
                                    "min_level": 8,
                                    "boss_classification": "regular",
                                },
                                {
                                    "reference": 104,
                                    "min_level": 8,
                                    "boss_classification": "regular",
                                },
                                {
                                    "reference": 105,
                                    "min_level": 8,
                                    "boss_classification": "regular",
                                },
                                {
                                    "reference": 106,
                                    "min_level": 8,
                                    "boss_classification": "regular",
                                },
                                {
                                    "reference": 107,
                                    "min_level": 8,
                                    "boss_classification": "boss",
                                },
                            ],
                        },
                    ],
                },
                {
                    "family_id": 20,
                    "tiers": [
                        {
                            "rank": 1,
                            "candidates": [
                                {
                                    "reference": 200,
                                    "min_level": 5,
                                    "boss_classification": "regular",
                                },
                            ],
                        },
                        {
                            "rank": 2,
                            "candidates": [
                                {
                                    "reference": 201,
                                    "min_level": 9,
                                    "boss_classification": "regular",
                                },
                            ],
                        },
                    ],
                },
                {
                    "family_id": 30,
                    "tiers": [
                        {
                            "rank": 1,
                            "candidates": [
                                {
                                    "reference": 300,
                                    "min_level": 5,
                                    "boss_classification": "regular",
                                },
                            ],
                        }
                    ],
                },
            ]
        }
        positions = [(x, y, 0) for x in range(20) for y in range(20)]
        edges = []
        for x in range(20):
            for y in range(20):
                if x + 1 < 20:
                    edges.extend(
                        [((x, y, 0), (x + 1, y, 0)), ((x + 1, y, 0), (x, y, 0))]
                    )
                if y + 1 < 20:
                    edges.extend(
                        [((x, y, 0), (x, y + 1, 0)), ((x, y + 1, 0), (x, y, 0))]
                    )
        cells = {
            (x, y): [{"z": 0, "region_id": 7}] for x in range(20) for y in range(20)
        }

        def owned_instance(reference, *_args, **_kwargs):
            if reference == 106:
                raise ValueError("invalid native statistics")

        names = {
            100: "Native A",
            101: "Boss A",
            102: "Native A tier two",
            103: None,
            104: "x" * 65536,
            105: "\ud800",
            106: "Stats missing",
            107: "Boss tier two",
            200: "Native B",
            201: "Native B tier two",
            300: "Unsupported family",
        }
        modules = {
            "wakfu_server.native_catalog": types.SimpleNamespace(
                release=lambda: "ecology-planner-test"
            ),
            "wakfu_server.monster_initial_population": types.SimpleNamespace(
                REGIONS={(1000, 7): self.region}
            ),
            "wakfu_server.monster_maturation": types.SimpleNamespace(
                CATALOG=self.catalog
            ),
            "wakfu_server.monsters": types.SimpleNamespace(
                owned_instance=owned_instance,
                reference=lambda reference: {"name": names.get(reference)},
            ),
            "wakfu_server.combat_terrain": types.SimpleNamespace(
                map_geometry=lambda _map: {
                    "cells": positions,
                    "edges": edges,
                }
            ),
            "wakfu_server.planting_cells": types.SimpleNamespace(
                cells=lambda _map: cells
            ),
        }
        self.module_patch = patch.dict("sys.modules", modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        # from wakfu_server import native_catalog may reuse a package attribute
        # cached by preceding suites even when sys.modules is patched.
        self.package_patch = patch.object(
            __import__("wakfu_server"),
            "native_catalog",
            modules["wakfu_server.native_catalog"],
        )
        self.package_patch.start()
        self.addCleanup(self.package_patch.stop)
        self.addCleanup(ecology_admin_planner._prepare.cache_clear)
        ecology_admin_planner._prepare.cache_clear()

    def plan(self, **kwargs):
        return ecology_admin_planner.plan(
            1000,
            7,
            kwargs.pop("counts", {}),
            kwargs.pop("occupied", set()),
            target=kwargs.pop("target", 4),
            capacity=kwargs.pop("capacity", 8),
        )

    def test_round_robin_uses_only_supported_regular_families(self):
        proposals = self.plan()
        self.assertEqual([row["reference"] for row in proposals], [100, 200, 100, 200])
        self.assertEqual(len({(row["x"], row["y"], row["z"]) for row in proposals}), 4)
        self.assertNotIn(101, [row["reference"] for row in proposals])
        self.assertNotIn(300, [row["reference"] for row in proposals])

    def test_existing_regional_counts_and_occupied_cells_reduce_plan(self):
        proposals = self.plan(
            counts=Counter({10: 2}), occupied={(0, 0, 0)}, target=5, capacity=5
        )
        self.assertEqual(len(proposals), 3)
        self.assertEqual([row["reference"] for row in proposals], [100, 200, 200])
        self.assertNotIn(
            (0, 0, 0), {(row["x"], row["y"], row["z"]) for row in proposals}
        )

    def test_total_capacity_and_free_native_cells_bound_output(self):
        self.assertEqual(len(self.plan(counts={10: 4, 20: 3}, target=8, capacity=8)), 1)
        self.assertEqual(len(self.plan(target=8, capacity=3)), 3)
        self.assertEqual(
            self.plan(occupied={(x, y, 0) for x in range(20) for y in range(20)}), []
        )

    def test_invalid_scope_fails_closed(self):
        with self.assertRaises(ValueError):
            ecology_admin_planner.plan(0, 7, {}, set(), target=4, capacity=8)
        with self.assertRaises(ValueError):
            ecology_admin_planner.plan(1000, 7, {10: -1}, set(), target=4, capacity=8)

    def test_prepared_catalog_is_cached_and_immutable(self):
        prepared = ecology_admin_planner.prepare(1000, 7)
        self.assertIs(prepared, ecology_admin_planner.prepare(1000, 7))
        self.assertEqual(prepared["revision"], "ecology-planner-test")
        self.assertEqual(
            {
                family: {row["reference"] for row in refs}
                for family, refs in prepared["all_candidates"].items()
            },
            {10: {100, 102}, 20: {200, 201}},
        )
        with self.assertRaises(TypeError):
            prepared["capacity"] = 1
        proposals = ecology_admin_planner.plan(
            1000, 7, Counter(), set(), target=2, capacity=8, prepared=prepared
        )
        self.assertEqual(len(proposals), 2)

    def test_genesis_builds_fair_connected_multiform_groups_with_spatial_spread(self):
        from wakfu_server.ecology_admin_planner import plan_groups

        prepared = ecology_admin_planner.prepare(1000, 7)
        planned = plan_groups(
            1000,
            7,
            Counter(),
            set(),
            group_counts={},
            target_groups=10,
            min_members=2,
            max_members=5,
            capacity=64,
            max_groups=100,
            member_budget=500,
            prepared=prepared,
            rng=random.Random(41),
        )
        self.assertEqual(len(planned), 10)
        sizes = [len(group) for group in planned]
        self.assertTrue(all(2 <= size <= 5 for size in sizes), sizes)
        self.assertGreater(len(set(sizes)), 1, sizes)

        family_by_reference = {
            row["reference"]: family
            for family, refs in prepared["all_candidates"].items()
            for row in refs
        }
        seen_references = set()
        centers = []
        occupied = set()
        group_counts = Counter()
        member_counts = Counter()
        for group in planned:
            families = {family_by_reference[member["reference"]] for member in group}
            self.assertEqual(len(families), 1)
            family = next(iter(families))
            group_counts[family] += 1
            member_counts[family] += len(group)
            refs = {member["reference"] for member in group}
            seen_references.update(refs)
            self.assertTrue(refs <= {100, 102, 200, 201})
            points = {(member["x"], member["y"], member["z"]) for member in group}
            self.assertEqual(len(points), len(group))
            self.assertFalse(points & occupied)
            occupied.update(points)
            for start in points:
                reachable = {start}
                frontier = [start]
                while frontier:
                    current = frontier.pop()
                    for neighbor in prepared["adjacency"].get(current, ()):
                        if neighbor in points and neighbor not in reachable:
                            reachable.add(neighbor)
                            frontier.append(neighbor)
                self.assertEqual(reachable, points)
            centers.append(
                (
                    sum(p[0] for p in points) / len(points),
                    sum(p[1] for p in points) / len(points),
                )
            )

        self.assertEqual(group_counts, Counter({10: 5, 20: 5}))
        self.assertTrue({100, 102, 200, 201} <= seen_references, seen_references)
        self.assertGreater(max(x for x, _ in centers) - min(x for x, _ in centers), 10)
        self.assertGreater(max(y for _, y in centers) - min(y for _, y in centers), 10)
        self.assertEqual(
            plan_groups(
                1000,
                7,
                member_counts,
                occupied,
                group_counts=group_counts,
                target_groups=10,
                min_members=2,
                max_members=5,
                capacity=64,
                max_groups=100,
                member_budget=500,
                prepared=prepared,
                rng=random.Random(41),
            ),
            [],
        )

    def test_member_budgets_reserve_minimums_without_singleton_groups(self):
        from wakfu_server.ecology_admin_planner import plan_groups

        prepared = ecology_admin_planner.prepare(1000, 7)
        arguments = dict(
            map_id=1000,
            region_id=7,
            counts=Counter(),
            occupied=set(),
            group_counts={},
            target_groups=10,
            min_members=2,
            max_members=5,
            capacity=64,
            max_groups=100,
            prepared=prepared,
        )
        minimum = plan_groups(**arguments, member_budget=20, rng=random.Random(9))
        self.assertEqual(len(minimum), 10)
        self.assertEqual([len(group) for group in minimum], [2] * 10)

        partial = plan_groups(**arguments, member_budget=25, rng=random.Random(9))
        self.assertEqual(len(partial), 10)
        self.assertTrue(all(2 <= len(group) <= 5 for group in partial))
        self.assertLessEqual(sum(map(len, partial)), 25)

        constrained = plan_groups(
            **{**arguments, "capacity": 3}, member_budget=500, rng=random.Random(9)
        )
        self.assertEqual(len(constrained), 1)
        self.assertIn(len(constrained[0]), (2, 3))
