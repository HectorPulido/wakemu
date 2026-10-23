"""One resumable candidate cursor per exact search node, including warm reuse."""
from collections import Counter, deque
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import json

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_jondo_search_hybrid import PreparationSession, scenario_candidates
from test_query_search import run_search
from test_query_warm_start import hint, cast
from wakfu_ai.planning.query_search import _prune_frontier


def node(identity="a", score=1):
    return dict(
        score=score,
        actions=[{}],
        key=identity,
        intent="position",
        target=None,
        state={"key": identity},
    )


class FrontierReuseTests(unittest.TestCase):
    def test_alias_frames_cannot_exceed_beam_width(self):
        selected = node()
        frames = deque(
            [
                dict(node=selected, depth=1, stream=None),
                dict(node=selected, depth=1, stream=None),
                dict(node=node("b", 0), depth=1, stream=None),
            ]
        )
        retained = _prune_frontier(frames, 1, 1)
        self.assertEqual(len(retained), 1)
        self.assertIs(retained[0]["node"], selected)

    def test_existing_initialized_cursor_survives_new_alias_at_front(self):
        selected = node()
        stream = iter(["already-consumed", "next-unexplored"])
        self.assertEqual(next(stream), "already-consumed")
        advanced = dict(node=selected, depth=1, stream=stream)
        fresh = dict(node=selected, depth=1, stream=None)
        root = dict(node=node("root"), depth=0, stream=iter(()))
        retained = _prune_frontier(deque([fresh, root, advanced]), 1, 1)
        self.assertEqual(len(retained), 2)
        self.assertIn(root, retained)
        branch = next(frame for frame in retained if frame["depth"] != 0)
        self.assertIs(branch, advanced)
        self.assertEqual(next(branch["stream"]), "next-unexplored")

    def test_repeated_frame_reference_is_retained_once(self):
        frame = dict(node=node(), depth=1, stream=iter(["remaining"]))
        retained = _prune_frontier(deque([frame, frame]), 1, 1)
        self.assertEqual(len(retained), 1)
        self.assertIs(retained[0], frame)
        self.assertEqual(next(retained[0]["stream"]), "remaining")

    def test_nonhostile_warm_seed_keeps_plan_without_duplicate_descendant_queries(self):
        samples = []
        for warm in (False, True):
            session = PreparationSession()
            if warm:
                hint(session, [cast(50, 1)])
            previews, repertoires, counts = Counter(), Counter(), Counter()
            original = session.request

            def request(query):
                counts[query["operation"]] += 1
                if query["operation"] == "preview":
                    previews[
                        (query["state"], json.dumps(query["action"], sort_keys=True))
                    ] += 1
                elif query["operation"] == "repertoire":
                    repertoires[query["state"]] += 1
                return original(query)

            session.request = request
            with patch(
                "wakfu_ai.planning.query_search.candidates", scenario_candidates
            ):
                result = run_search(session)
            samples.append((result, counts))
            with self.subTest(warm=warm):
                self.assertTrue(
                    all(count == 1 for count in previews.values()), previews
                )
                self.assertTrue(
                    all(count == 1 for count in repertoires.values()), repertoires
                )
                self.assertLessEqual(
                    result["searchBudgetEvidence"]["peakContinuationFrames"], 2
                )
                self.assertEqual([step["spellId"] for step in result["plan"]], [50, 51])
        self.assertEqual(samples[0][1], samples[1][1])
        self.assertEqual(samples[0][0]["score"], samples[1][0]["score"])


if __name__ == "__main__":
    unittest.main()
