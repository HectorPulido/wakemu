"""Native advisory move/cast opportunities retain fresh preview authority."""
from pathlib import Path
from collections import Counter
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession, run_search
from wakfu_ai.planning.query_search import _movement_orders, _native_range_hints


def linear_spell():
    return dict(
        spellId=1,
        level=1,
        casting=dict(
            protected=False,
            maximum_level=1,
            line_of_sight=True,
            linear=True,
            free_cell=False,
            levels=[[1, 3, [1]]],
            costs=[[1, 0, 0]],
            categories=[],
            conditional=[],
            range_modifiable=False,
            path_option=False,
            diagonal=False,
            linear_path=False,
            allow_self=False,
            forbid_QI_P=False,
            cast_criterion_raw="",
            cast_criterion_native_present=False,
        ),
        advisoryCapabilities=dict(spellId=1, level=1, tags=["damage"]),
    )


class LinearSession(FakeNativeSession):
    def __init__(self):
        cells = [(x, y, 0) for x in range(3) for y in range(3)] + [(2, 3, 0)]
        edges = [
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        ]
        super().__init__(
            spells=[linear_spell()], cells=cells, edges=edges, effects={1: "damage"}
        )
        self.root_state["actors"][0]["mp"] = 2
        self.root_state["actors"][-1]["position"] = [2, 3, 0]
        self.envelope["policy"]["limits"].update(depth=2, nodes=4, beam=2)

    def request(self, query):
        if query["operation"] == "preview" and query["action"]["type"] == "cast":
            source = self.states[query["state"]]["public"]["actors"][0]["position"]
            target = query["action"]["target"]
            distance = abs(source[0] - target[0]) + abs(source[1] - target[1])
            if (
                source[0] != target[0] and source[1] != target[1]
            ) or not 1 <= distance <= 3:
                self.preview_actions.append(query["action"])
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["native_fixture_range_or_alignment"],
                )
        return super().request(query)


class QueryAttackOpportunityTests(unittest.TestCase):
    def test_current_native_metadata_shape_remains_advisory_range_hint(self):
        self.assertEqual(_native_range_hints(linear_spell()), ((1, 3),))
        spell = linear_spell()
        spell["casting"]["unrecognized_future_rule"] = True
        self.assertIsNone(_native_range_hints(spell))

    def test_route_order_preserves_hold_and_retreat_behavior(self):
        session = LinearSession()
        actors = {row["id"]: row for row in session.root_state["actors"]}
        with patch(
            "wakfu_ai.planning.query_search.attack_opportunity_routes",
            side_effect=AssertionError("Must not promote approach while retreating"),
        ):
            _movement_orders(
                session.edges,
                list(map(tuple, session.cells)),
                actors,
                1,
                retreat=True,
                spells=[linear_spell()],
            )
            with patch(
                "wakfu_ai.planning.query_search.decide_team_posture",
                return_value={"mode": "hold"},
            ):
                _movement_orders(
                    session.edges,
                    list(map(tuple, session.cells)),
                    actors,
                    1,
                    team_posture=True,
                    spells=[linear_spell()],
                )

    def test_same_preview_budget_can_reach_linear_cast_opportunity(self):
        results = []
        for enabled in (False, True):
            session = LinearSession()
            queries = Counter()
            original = session.request

            def request(query):
                queries[query["operation"]] += 1
                return original(query)

            session.request = request
            if enabled:
                result = run_search(session)
            else:
                with patch(
                    "wakfu_ai.planning.query_search.attack_opportunity_routes",
                    return_value=(),
                ):
                    result = run_search(session)
            results.append((result, queries))
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(results[1][1], dict(preview=4, repertoire=2))
        self.assertGreater(
            results[1][0]["components"].get("damage", 0),
            results[0][0]["components"].get("damage", 0),
        )
        self.assertEqual(
            [row["type"] for row in results[1][0]["plan"]], ["move", "cast"]
        )


if __name__ == "__main__":
    unittest.main()
