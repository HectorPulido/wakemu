"""Every ecology movement branch obeys the actual birth territory, not species."""
import random
import unittest
from copy import deepcopy

from protocol_codec import decode_body
from test_monster_idle_distribution import grid, group
from wakfu_server import monster_wander as wander
from wakfu_server.monster_idle_distribution import footprint_cells, plan as idle_plan
from wakfu_server.monster_home_paths import homing_path


class BirthHomeMovementTests(unittest.TestCase):
    def test_every_visible_group_gets_an_attempt_under_one_group_time_budget(self):
        groups = [
            dict(
                group_id=identity,
                status="available",
                members=[dict(id=-identity, ref=4, x=0, y=0, z=0)],
            )
            for identity in range(1, 21)
        ]
        first_attempts = [
            wander.visible_groups(
                groups, [dict(x=0, y=1, z=0)], radius=20, tick=tick, batch_size=8
            )[0]["group_id"]
            for tick in range(20)
        ]
        self.assertEqual(set(first_attempts), set(range(1, 21)))
        self.assertEqual(len(first_attempts), len(set(first_attempts)))

    def test_split_group_keeps_roaming_inside_home_when_companion_cannot_return(self):
        class OneStepRng:
            def __init__(self):
                self.budgets = []

            def randint(self, low, high):
                self.budgets.append((low, high))
                return low

            def choice(self, candidates):
                return max(candidates, key=lambda cell: (cell[0], cell[1]))

        members = [
            dict(id=-1, ref=4, level=10, hp=17, x=0, y=1, z=0),
            dict(id=-2, ref=4, level=10, hp=23, x=2, y=0, z=0),
        ]
        initial = deepcopy(members)
        region = lambda cell: 11 if cell[0] <= 0 else 22
        inside_edges = [((0, y, 0), (0, y + 1, 0)) for y in range(1, 9)]
        inside_edges.append(((0, 1, 0), (1, 1, 0)))
        return_edges = [((2, 0, 0), (1, 0, 0)), ((1, 0, 0), (0, 0, 0))]
        for case, edges, occupied in (
            ("blocked", inside_edges + return_edges, [(1, 0, 0)]),
            ("disconnected", inside_edges, []),
            ("returning", inside_edges + return_edges, []),
        ):
            with self.subTest(case=case):
                indexed = wander.edge_index(edges)
                rng = OneStepRng()
                result = homing_path(
                    members,
                    [dict(x=3, y=3, z=0)],
                    indexed,
                    11,
                    region,
                    occupied=occupied,
                    min_steps=1,
                    max_steps=8,
                    rng=rng,
                )
                self.assertIsNotNone(result)
                self.assertEqual(rng.budgets, [(1, 8)])
                self.assertEqual(wander.point(result["members"][0]), (0, 2, 0))
                self.assertEqual(
                    wander.point(result["members"][1]),
                    (1, 0, 0) if case == "returning" else (2, 0, 0),
                )
                anchor = wander.point(result["members"][0])
                self.assertLessEqual(
                    max(
                        max(abs(member["x"] - anchor[0]), abs(member["y"] - anchor[1]))
                        for member in result["members"]
                    ),
                    2,
                )
                for opcode, payload in result["packets"]:
                    decoded = decode_body("in", opcode, payload)
                    self.assertEqual(decoded["step_count"], 1)
                    origin = tuple(
                        decoded["start_position"][k] for k in ("x", "y", "z")
                    )
                    endpoint = tuple(
                        decoded["end_position"][k] for k in ("x", "y", "z")
                    )
                    self.assertIn((origin, endpoint), indexed[0])
                    self.assertNotIn(endpoint, occupied)
                    if decoded["actor_id"] == -1:
                        self.assertEqual(region(endpoint), 11)
                for before, after in zip(members, result["members"]):
                    self.assertEqual(
                        {k: v for k, v in before.items() if k not in ("x", "y", "z")},
                        {k: v for k, v in after.items() if k not in ("x", "y", "z")},
                    )
                self.assertEqual(members, initial)

    def test_drifted_monster_returns_through_native_steps_without_teleporting_or_new_flags(
        self,
    ):
        member = dict(id=-1, ref=9999, level=10, hp=17, x=2, y=0, z=0)
        players = [dict(x=2, y=3, z=0)]
        indexed = wander.edge_index([((2, 0, 0), (1, 0, 0)), ((1, 0, 0), (0, 0, 0))])
        region = lambda cell: 11 if cell[0] <= 0 else 22
        result = homing_path(
            [member],
            players,
            indexed,
            11,
            region,
            min_steps=3,
            max_steps=3,
            rng=random.Random(3),
        )
        self.assertIsNotNone(result)
        self.assertEqual(set(result), {"members", "packets"})
        self.assertEqual(wander.point(result["members"][0]), (0, 0, 0))
        decoded = decode_body("in", *result["packets"][0])
        self.assertEqual(decoded["step_count"], 2)
        self.assertEqual(decoded["start_position"], dict(x=2, y=0, z=0))
        self.assertEqual(decoded["end_position"], dict(x=0, y=0, z=0))
        self.assertEqual(
            {k: v for k, v in member.items() if k not in ("x", "y", "z")},
            {k: v for k, v in result["members"][0].items() if k not in ("x", "y", "z")},
        )
        self.assertIsNone(
            homing_path(
                [member],
                players,
                indexed,
                11,
                region,
                occupied=[(1, 0, 0)],
                min_steps=3,
                max_steps=3,
                rng=random.Random(3),
            )
        )
        self.assertIsNone(
            homing_path(
                [member],
                players,
                wander.edge_index([]),
                11,
                region,
                min_steps=3,
                max_steps=3,
                rng=random.Random(3),
            )
        )

    def test_homing_keeps_home_members_in_place_while_drifted_companions_return(self):
        members = [dict(id=-1, ref=4, x=0, y=1, z=0), dict(id=-2, ref=4, x=2, y=0, z=0)]
        region = lambda cell: 11 if cell[0] <= 0 else 22
        indexed = wander.edge_index([((2, 0, 0), (1, 0, 0)), ((1, 0, 0), (0, 0, 0))])
        result = homing_path(
            members,
            [dict(x=2, y=3, z=0)],
            indexed,
            11,
            region,
            min_steps=3,
            max_steps=3,
            rng=random.Random(4),
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["members"][0], members[0])
        self.assertEqual(wander.point(result["members"][1]), (0, 0, 0))
        self.assertEqual(len(result["packets"]), 1)
        self.assertEqual(decode_body("in", *result["packets"][0])["actor_id"], -2)

    def test_roaming_dispersal_overlap_and_flexible_paths_cannot_leave_home(self):
        class Rng:
            def __init__(self, roll):
                self.roll = roll

            def random(self):
                return self.roll

            def randint(self, low, high):
                return high

            def choice(self, candidates):
                return candidates[0]

        def allowed(cell):
            return cell[0] <= 0

        edges = [
            ((0, 0, 0), (1, 0, 0)),
            ((0, 0, 0), (0, 1, 0)),
            ((0, 1, 0), (1, 1, 0)),
            ((0, 1, 0), (0, 2, 0)),
        ]
        threat = [
            dict(status="available", members=[dict(id=-2, ref=4, x=-1, y=0, z=0)])
        ]
        cases = [
            (0.9, False, False),
            (0.0, False, False),
            (0.9, True, False),
            (0.9, False, True),
        ]
        for roll, overlap, companion in cases:
            with self.subTest(roll=roll, overlap=overlap, companion=companion):
                members = [dict(id=-1, ref=9999, x=0, y=0, z=0)]
                if companion:
                    members.append(dict(id=-3, ref=9999, x=0, y=-1, z=0))
                players = [dict(x=0, y=0 if overlap else 3, z=0)]
                result = wander.plan_group_path(
                    members,
                    players,
                    edges,
                    destination_allowed=allowed,
                    other_groups=threat,
                    rng=Rng(roll),
                    min_steps=1,
                    max_steps=3,
                )
                self.assertIsNotNone(result)
                for opcode, payload in result["packets"]:
                    packet = decode_body("in", opcode, payload)
                    x, y, z = (packet["start_position"][k] for k in ("x", "y", "z"))
                    for step in packet["steps"]:
                        x, y, z = x + step["dx"], y + step["dy"], z + step["dz"]
                        self.assertTrue(allowed((x, y, z)))
                for old, new in zip(members, result["members"]):
                    self.assertEqual(
                        {k: v for k, v in old.items() if k not in ("x", "y", "z")},
                        {k: v for k, v in new.items() if k not in ("x", "y", "z")},
                    )

    def test_idle_distribution_uses_each_home_and_full_footprints_after_prior_drift(
        self,
    ):
        geometry = grid(24)
        groups = [
            group(1, 18, 2, count=3),
            group(2, 2, 18, count=3),
            group(3, 20, 20, status="fighting"),
        ]
        initial = deepcopy(groups)
        homes = {1: 11, 2: 22, 3: 22}
        region = lambda cell: 11 if cell[0] < 12 else 22
        moves = idle_plan(
            groups,
            geometry,
            home_regions=homes,
            region_at=region,
            actor_radii={4: 0, 5: 0, 6: 0},
            rng=random.Random(83),
        )
        self.assertEqual({move["group_id"] for move in moves}, {1, 2})
        self.assertEqual(groups, initial)
        claimed = set()
        for move in moves:
            for old, new in zip(move["expected_members"], move["moved_members"]):
                cells = set(footprint_cells(new, actor_radii={4: 0, 5: 0, 6: 0}))
                self.assertTrue(
                    all(region(cell) == homes[move["group_id"]] for cell in cells)
                )
                self.assertFalse(cells & claimed)
                claimed.update(cells)
                self.assertEqual(
                    {k: v for k, v in old.items() if k not in ("x", "y", "z")},
                    {k: v for k, v in new.items() if k not in ("x", "y", "z")},
                )

    def test_idle_large_footprint_cannot_straddle_its_birth_boundary(self):
        geometry = grid(16)
        groups = [group(1, 11, 3)]
        region = lambda cell: 11 if cell[0] < 8 else 22
        moves = idle_plan(
            groups,
            geometry,
            home_regions={1: 11},
            region_at=region,
            actor_radii={4: 1},
            rng=random.Random(61),
        )
        self.assertEqual(len(moves), 1)
        physical = footprint_cells(moves[0]["moved_members"][0], actor_radii={4: 1})
        self.assertTrue(all(region(cell) == 11 for cell in physical))
