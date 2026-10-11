"""Unknown rival responses must not create a spurious safety advantage."""
import unittest
from unittest.mock import patch

from wakfu_ai.planning.risk_coverage import comparable_bounds


def forecast(bound, *, expanded=0, complete=False, identity=9):
    return dict(
        knownLowerBound=bound,
        complete=complete,
        rivals=[
            dict(
                actorId=identity,
                knownLowerBound=bound,
                expanded=expanded,
                complete=complete,
            )
        ],
    )


class NativeRiskCoverageTests(unittest.TestCase):
    def test_unevaluated_move_does_not_beat_known_baseline_risk(self):
        self.assertEqual(comparable_bounds([forecast(0.5), forecast(0)]), [0.5, 0.5])

    def test_certified_response_can_differentiate_alternatives(self):
        self.assertEqual(
            comparable_bounds([forecast(7, expanded=2), forecast(2, expanded=2)]),
            [7, 2],
        )

    def test_complete_zero_is_not_replaced_with_another_positions_risk(self):
        self.assertEqual(
            comparable_bounds([forecast(7), forecast(0, complete=True)]), [7, 0]
        )

    def test_different_rivals_are_not_conflated(self):
        self.assertEqual(
            comparable_bounds([forecast(7, identity=9), forecast(0, identity=10)]),
            [7, 0],
        )

    def test_all_unknown_zero_remains_unknown_zero(self):
        entries = [forecast(0), forecast(0)]
        self.assertEqual(comparable_bounds(entries), [0, 0])
        self.assertFalse(entries[0]["complete"])

    def test_search_does_not_spend_mp_for_an_unevaluated_safety_bonus(self):
        from test_query_search import ACTOR_ID, fixture, run_search

        session = fixture([])
        session.envelope["operations"] = ["project_turn"]
        session.envelope["policy"]["limits"]["depth"] = 1
        session.envelope["policy"]["weights"] = dict(position=0, resources=1)

        def incomplete_projection(state, *args, **kwargs):
            if False:
                yield
            current = next(a for a in state["actors"] if a["id"] == ACTOR_ID)
            result = forecast(2 if current["position"] == [0, 0, 0] else 0)
            result["unknownDependencies"] = ["rival_search_deadline_reached"]
            return result

        with patch("wakfu_ai.planning.query_threat.forecast", incomplete_projection):
            result = run_search(session)
        self.assertEqual(result["action"], {"type": "end_turn"})
        moves = [entry for entry in result["rivalForecasts"] if entry["actions"]]
        self.assertTrue(moves)
        self.assertTrue(all(entry["coverageImputation"] == 2 for entry in moves))
