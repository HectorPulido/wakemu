"""Decision-wide navigation fallback, independent of native legality."""
import pathlib
import types
import unittest


def staged_module():
    path = pathlib.Path(__file__).parents[1] / "wakfu_ai/planning/query_search.py"
    module = types.ModuleType("wakfu_ai.planning._staged_query_search")
    module.__package__ = "wakfu_ai.planning"
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


class AllyRelaxedSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.search = staged_module()

    def raw(self, strict=None, relaxed=9):
        return dict(
            actors=[
                dict(
                    id=1,
                    team=1,
                    position=[0, 0, 0],
                    hp=10,
                    max_hp=10,
                    ap=6,
                    mp=3,
                    wp=0,
                    armor=0,
                )
            ],
            topologyDistances={"1": strict},
            topologyCellCount=20,
            allyRelaxedTopologyDistances={"1": relaxed},
        )

    def test_fallback_requires_known_disconnection_and_finite_navigation(self):
        self.assertEqual(
            self.search._approach_topology(self.raw(), 1),
            "allyRelaxedTopologyDistances",
        )
        for strict, relaxed in [(4, 9), (None, None), (None, True), (None, -1)]:
            self.assertIsNone(
                self.search._approach_topology(self.raw(strict, relaxed), 1)
            )
        self.assertIsNone(self.search._approach_topology(self.raw(), 1, retreat=True))

    def test_missing_strict_fact_is_rejected_instead_of_enabling_fallback(self):
        root = self.raw()
        root["topologyDistances"] = {}
        mode = self.search._approach_topology(root, 1)
        self.assertIsNone(mode)
        with self.assertRaisesRegex(ValueError, "Incomplete native topology distances"):
            self.search._metrics(root, 1, approach_topology=mode)

    def test_root_basis_stays_fixed_after_strict_route_opens(self):
        root = self.raw(None, 9)
        mode = self.search._approach_topology(root, 1)
        child = self.raw(3, 7)
        before = self.search._metrics(root, 1, approach_topology=mode)
        after = self.search._metrics(child, 1, approach_topology=mode)
        self.assertEqual(before["position_basis"], after["position_basis"])
        self.assertEqual(before["position"], -2.25)
        self.assertEqual(after["position"], -1.75)
        self.assertEqual(child["topologyDistances"]["1"], 3)

    def test_unknown_endpoint_cannot_gain_from_missing_relaxed_fact(self):
        child = self.raw(3, 7)
        del child["allyRelaxedTopologyDistances"]
        metrics = self.search._metrics(
            child, 1, approach_topology="allyRelaxedTopologyDistances"
        )
        self.assertEqual(metrics["position"], -21 * 0.25)

    def test_primary_target_keeps_primary_relaxed_scale(self):
        root = self.raw(2, 4)
        root.update(
            primaryTopologyDistances={"1": None},
            allyRelaxedPrimaryTopologyDistances={"1": 12},
        )
        mode = self.search._approach_topology(root, 1)
        self.assertEqual(mode, "allyRelaxedPrimaryTopologyDistances")
        self.assertEqual(
            self.search._metrics(root, 1, approach_topology=mode)["position"], -3
        )

    def test_candidate_order_promotes_progress_without_crossing_ally(self):
        edges = [((x, 0, 0), (x + 1, 0, 0)) for x in range(5)]
        edges += [(b, a) for a, b in edges]
        actors = {
            1: dict(id=1, team=1, position=(0, 0, 0), hp=10, max_hp=10, mp=3),
            2: dict(id=2, team=1, position=(3, 0, 0), hp=10, max_hp=10, mp=3),
            3: dict(id=3, team=0, position=(5, 0, 0), hp=10, max_hp=10, mp=3),
        }
        orders = self.search._movement_orders(
            edges, [(x, 0, 0) for x in range(6)], actors, 1
        )
        first = next(orders[0])
        self.assertEqual(first[-1], (2, 0, 0))
        for order in orders:
            for path in order:
                self.assertNotIn((3, 0, 0), path)

    def test_mandatory_border_navigation_keeps_actual_avoidable_exposure(self):
        # Main corridor 0-1-2-3-4, ally at3. The border at2 is mandatory.
        forward = {(x, 0, 0): {(x + 1, 0, 0)} for x in range(4)}
        forward[(0, 0, 0)].add((0, 1, 0))
        forward[(0, 1, 0)] = {(1, 0, 0)}
        reverse = {}
        for start, ends in forward.items():
            for end in ends:
                reverse.setdefault(end, set()).add(start)
        actors = {
            1: dict(id=1, team=1, position=(0, 0, 0), hp=10),
            2: dict(id=2, team=1, position=(3, 0, 0), hp=10),
            3: dict(id=3, team=0, position=(4, 0, 0), hp=10),
        }
        hazards = {(2, 0, 0), (0, 1, 0)}
        remaining = self.search._remaining_border_exposure
        self.assertIsNone(remaining(reverse, actors, 1, hazards))
        root = remaining(reverse, actors, 1, hazards, relax_allies=True)
        self.assertEqual(root, 1)
        actors[1] = dict(actors[1], position=(2, 0, 0))
        after = remaining(reverse, actors, 1, hazards, relax_allies=True)
        self.assertEqual(max(0, 1 + after - root), 0)
        # Taking the unnecessary side border adds a second hazardous entry.
        self.assertEqual(max(0, 2 + after - root), 1)


if __name__ == "__main__":
    unittest.main()
