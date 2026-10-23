"""Deterministic property and full-search checks for advisory opportunities.

The forecast sessions below are explicit synthetic native-API doubles. These
checks exercise allocation/authority contracts, not Wakfu spell correctness.
"""
from copy import deepcopy
from itertools import product
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession, run_search
from test_query_attack_opportunities import LinearSession, linear_spell
from wakfu_ai.context.native_context import NativeGraph
from wakfu_ai.planning.attack_opportunities import attack_opportunity_routes
from wakfu_ai.planning.query_search import (
    _fight,
    _movement_candidates,
    _movement_orders,
    _native_range_hints,
)


def row(identity, team, position, hp=20, maximum=20):
    return dict(
        id=identity,
        team=team,
        position=position,
        hp=hp,
        max_hp=maximum,
        ap=6,
        mp=3,
        wp=2,
        armor=0,
        controlled=team == 1,
    )


def spell(minimum, maximum, *, tags=("damage",), linear=False, diagonal=False):
    value = linear_spell()
    value["casting"].update(
        levels=[[minimum, maximum, [1]]], linear=linear, diagonal=diagonal
    )
    value["advisoryCapabilities"]["tags"] = list(tags)
    return value


def offers(routes, actors, spells, priority=None, evidence=None):
    return attack_opportunity_routes(
        routes,
        actors,
        1,
        spells,
        range_hints=_native_range_hints,
        route_priority=priority or (lambda route: (0, len(route), route)),
        capability_evidence=evidence,
    )


def matches(start, target, minimum, maximum, linear, diagonal):
    """Independent hint-contract oracle, with no claim of native legality."""
    horizontal, vertical = abs(start[0] - target[0]), abs(start[1] - target[1])
    in_range = minimum <= horizontal + vertical <= maximum
    aligned = (
        not (linear or diagonal)
        or (linear and (horizontal == 0 or vertical == 0))
        or (diagonal and horizontal == vertical)
    )
    return in_range and aligned


class OpportunityPropertyTests(unittest.TestCase):
    def test_600_generated_layouts_preserve_route_authority_and_minimal_exposure(self):
        rng = random.Random(20261022)
        for case in range(600):
            minimum = rng.randrange(0, 5)
            maximum = minimum + rng.randrange(0, 6)
            linear, diagonal = rng.choice(
                ((False, False), (True, False), (False, True), (True, True))
            )
            actors = {1: row(1, 1, (0, 0, rng.randrange(-2, 3)))}
            for identity in range(2, 7):
                actors[identity] = row(
                    identity,
                    0,
                    (rng.randrange(-5, 6), rng.randrange(-5, 6), rng.randrange(-2, 3)),
                    hp=rng.choice((0, 5, 20)),
                )
            endpoints = {
                (rng.randrange(-5, 6), rng.randrange(-5, 6), rng.randrange(-2, 3))
                for _ in range(20)
            }
            routes = [(end,) for end in sorted(endpoints)]
            exposure = {route: rng.randrange(0, 3) for route in routes}
            priority = lambda route: (exposure[route], len(route), route)
            before = deepcopy((routes, actors))
            selected = offers(
                routes,
                actors,
                [spell(minimum, maximum, linear=linear, diagonal=diagonal)],
                priority,
            )
            with self.subTest(case=case):
                self.assertEqual((routes, actors), before)
                self.assertLessEqual(len(selected), 8)
                self.assertEqual(len(selected), len(set(selected)))
                self.assertEqual(list(selected), sorted(selected, key=priority))
                for route in selected:
                    self.assertIn(route, routes)
                    self.assertEqual(exposure[route], min(exposure.values()))
                    self.assertTrue(
                        any(
                            target["hp"] > 0
                            and not matches(
                                actors[1]["position"],
                                target["position"],
                                minimum,
                                maximum,
                                linear,
                                diagonal,
                            )
                            and matches(
                                route[-1],
                                target["position"],
                                minimum,
                                maximum,
                                linear,
                                diagonal,
                            )
                            for identity, target in actors.items()
                            if identity != 1
                        )
                    )

    def test_coordinate_translation_and_altitude_do_not_fabricate_geometry(self):
        actors = {1: row(1, 1, (0, 0, 0)), 2: row(2, 0, (2, 3, 0))}
        routes = [((0, 1, 0), (0, 2, 0)), ((1, 0, 0), (2, 0, 0))]
        expected = offers(routes, actors, [spell(1, 3, linear=True)])
        for dx, dy, dz in ((10, -20, 5), (-7, 6, -3), (0, 0, 100)):
            transform = lambda cell: (cell[0] + dx, cell[1] + dy, cell[2] + dz)
            shifted = {
                identity: dict(actor, position=transform(actor["position"]))
                for identity, actor in actors.items()
            }
            translated = [tuple(map(transform, route)) for route in routes]
            self.assertEqual(
                offers(translated, shifted, [spell(1, 3, linear=True)]),
                tuple(tuple(map(transform, route)) for route in expected),
            )

    def test_input_order_changes_do_not_change_small_complete_opportunities(self):
        actors = {
            1: row(1, 1, (0, 0, 0)),
            2: row(2, 0, (2, 3, 0)),
            3: row(3, 0, (-2, -3, 0)),
        }
        routes = [((x, y, 0),) for x, y in product(range(-2, 3), repeat=2)]
        value = spell(1, 3, linear=True)
        expected = offers(routes, actors, [value])
        rng = random.Random(983)
        for _ in range(25):
            rng.shuffle(routes)
            shuffled = list(actors.items())
            rng.shuffle(shuffled)
            self.assertEqual(offers(routes, dict(shuffled), [value]), expected)

    def test_support_control_and_dead_target_matrix(self):
        origin, endpoint, target = (0, 0, 0), (2, 0, 0), (2, 3, 0)
        route = (endpoint,)
        for tag, team, health in product(
            ("damage", "control", "healing", "heal", "protection", "armor", "unknown"),
            (0, 1),
            (0, 10, 20),
        ):
            actors = {1: row(1, 1, origin), 2: row(2, team, target, hp=health)}
            useful = health > 0 and (
                team == 0
                and tag in ("damage", "control")
                or team == 1
                and (
                    tag in ("protection", "armor")
                    or tag in ("healing", "heal")
                    and health < 20
                )
            )
            with self.subTest(tag=tag, team=team, health=health):
                selected = offers(
                    [route], actors, [spell(1, 3, tags=(tag,), linear=True)]
                )
                self.assertEqual(bool(selected), useful)

    def test_conditionals_keep_each_range_alignment_branch(self):
        actors = {1: row(1, 1, (0, 0, 0)), 2: row(2, 0, (3, 3, 0))}
        diagonal_route, line_route = ((1, 1, 0),), ((0, 3, 0),)
        value = spell(1, 2, linear=True)
        value["casting"]["conditional"] = [
            dict(ranges=[[4, 4]], linear=False, diagonal=True)
        ]
        self.assertEqual(
            offers([diagonal_route, line_route], actors, [value]), (diagonal_route,)
        )
        value["casting"]["conditional"][0]["unknown_future_gate"] = True
        self.assertEqual(offers([diagonal_route, line_route], actors, [value]), ())

    def test_eight_route_cap_and_32_unique_profile_limit_leave_inputs_intact(self):
        routes = [((identity, 0, 0),) for identity in range(1, 13)]
        actors = {1: row(1, 1, (0, 0, 0))}
        actors.update(
            {
                100 + identity: row(100 + identity, 0, (identity, 3, 0))
                for identity in range(1, 13)
            }
        )
        self.assertEqual(len(offers(routes, actors, [spell(3, 3, linear=True)])), 8)
        profiles = [spell(100 + index, 100 + index) for index in range(32)]
        self.assertEqual(
            offers(routes, actors, profiles + [spell(3, 3, linear=True)]), ()
        )
        self.assertEqual(len(routes), 12)
        self.assertEqual(len(profiles), 32)


class OpportunityStreamTests(unittest.TestCase):
    def test_120_directed_xyz_layouts_keep_every_original_route_after_promotion(self):
        rng = random.Random(9947)
        for case in range(120):
            cells = [(x, y, (x + y) % 2) for x, y in product(range(4), repeat=2)]
            edges = [
                (start, end)
                for start in cells
                for end in cells
                if abs(start[0] - end[0]) + abs(start[1] - end[1]) == 1
                and rng.random() > 0.25
            ]
            actors = {1: row(1, 1, cells[0]), 9: row(9, 0, cells[-1])}
            actors[1]["mp"] = rng.randrange(0, 5)
            hazard = frozenset(cell for cell in cells if rng.random() < 0.1)
            kwargs = dict(hazard_cells=hazard, spells=[spell(1, 3, linear=True)])
            streams = _movement_orders(edges, cells, actors, 1, **kwargs)
            promoted = {route for stream in streams for route in stream}
            with patch(
                "wakfu_ai.planning.query_search.attack_opportunity_routes",
                return_value=(),
            ):
                base = {
                    route
                    for stream in _movement_orders(edges, cells, actors, 1, **kwargs)
                    for route in stream
                }
            with self.subTest(case=case):
                self.assertEqual(promoted, base)
                for route in promoted:
                    self.assertLessEqual(len(route), actors[1]["mp"])
                    previous = tuple(actors[1]["position"])
                    for cell in route:
                        self.assertIn((previous, cell), edges)
                        self.assertNotEqual(cell, tuple(actors[9]["position"]))
                        previous = cell

    def test_actual_candidate_stream_deduplicates_routes_without_losing_prefixes(self):
        session = LinearSession()
        graph = NativeGraph(session.root_graph)
        actors = {row["id"]: row for row in session.root_state["actors"]}
        cells = [tuple(cell) for cell in session.cells]
        kwargs = dict(spells=[linear_spell()])
        fight = _fight(graph)
        actual = list(
            _movement_candidates(
                graph, graph.field(fight, "edges"), cells, actors, 1, **kwargs
            )
        )
        keys = [tuple(map(tuple, action["path"])) for action in actual]
        base = {
            route
            for stream in _movement_orders(session.edges, cells, actors, 1, **kwargs)
            for route in stream
        }
        self.assertEqual(set(keys), base)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(any(len(route) == 1 for route in keys))
        self.assertTrue(any(len(route) == 2 for route in keys))

    def test_native_rejection_cannot_turn_advisory_opportunity_into_damage(self):
        session = LinearSession()
        session.envelope["policy"]["limits"].update(nodes=32)
        original = session.request

        def request(query):
            if query["operation"] == "preview" and query["action"]["type"] == "cast":
                session.preview_actions.append(deepcopy(query["action"]))
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["native_line_of_sight_blocked"],
                )
            return original(query)

        session.request = request
        result = run_search(session)
        self.assertEqual(result["components"].get("damage", 0), 0)
        self.assertFalse(any(action["type"] == "cast" for action in result["plan"]))
        self.assertIn("native_line_of_sight_blocked", result["unknownDependencies"])
        self.assertLessEqual(result["expanded"], 32)

    def test_full_search_rejects_harmful_friendly_fire_despite_promoted_position(self):
        session = LinearSession()
        session.effects[1] = "friendly_fire"
        session.envelope["policy"]["limits"].update(nodes=32)
        result = run_search(session)
        self.assertFalse(any(action["type"] == "cast" for action in result["plan"]))
        self.assertGreaterEqual(result["score"], 0)

    def test_full_search_control_uses_certified_resource_outcome(self):
        session = LinearSession()
        session.spells[0]["advisoryCapabilities"]["tags"] = ["control"]
        session.effects[1] = "none"
        original = session.request

        def request(query):
            response = original(query)
            if (
                query["operation"] == "preview"
                and query["action"]["type"] == "cast"
                and query["action"].get("targetId") == 9
                and response["supported"]
            ):
                target = next(
                    actor for actor in response["result"]["actors"] if actor["id"] == 9
                )
                target["ap"] = max(0, target["ap"] - 4)
            return response

        session.request = request
        result = run_search(session)
        self.assertEqual(
            [action["type"] for action in result["plan"]], ["move", "cast"]
        )
        self.assertEqual(result["components"]["control"], 2)
        self.assertEqual(result["components"]["damage"], 0)

    def test_full_search_healing_promotion_requires_real_wounded_ally_outcome(self):
        session = LinearSession()
        session.spells[0]["advisoryCapabilities"]["tags"] = ["heal"]
        session.effects[1] = "heal"
        session.envelope["policy"]["limits"].update(nodes=16)
        ally = next(actor for actor in session.root_state["actors"] if actor["id"] == 2)
        ally.update(position=[2, 3, 0], hp=10)
        enemy = next(
            actor for actor in session.root_state["actors"] if actor["id"] == 9
        )
        enemy["position"] = [3, 0, 0]
        result = run_search(session)
        self.assertEqual(result["components"]["healing"], 8)
        self.assertEqual(result["components"]["damage"], 0)
        self.assertEqual(result["plan"][-1]["targetId"], 2)


if __name__ == "__main__":
    unittest.main()
