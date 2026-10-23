"""Fixed-work decision quality across representative continuation families.

Synthetic native outcomes are explicit. The paired private search variants
change reuse only, with identical utility, RNG-free outcomes and budgets.
"""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession
from test_query_warm_start import hint, cast
from test_jondo_search_hybrid import (
    PreparationSession,
    ThreeStepPreparationSession,
    scenario_candidates,
    three_step_candidates,
)
from wakfu_ai.context.native_context import encode


FAMILIES = (
    "ready_attack",
    "immediate_competing",
    "rejected_competing",
    "setup_attack",
    "setup_move_attack",
    "stale_hint",
    "after_attack_retreat",
)


class RejectSpellSession(FakeNativeSession):
    rejected_spell = 1

    def request(self, query):
        if (
            query["operation"] == "preview"
            and query["action"].get("spellId") == self.rejected_spell
        ):
            return dict(
                id=query["id"],
                supported=False,
                unknownDependencies=["fixture_fresh_native_rejection"],
            )
        return super().request(query)


def make_case(family, *, nodes=16, depth=None, beam=2, quantum=8):
    """Return a fresh native-API fixture and optional synthetic candidate stream."""
    factory = None
    if family in (
        "ready_attack",
        "immediate_competing",
        "rejected_competing",
        "stale_hint",
    ):
        identities = (1,) if family == "ready_attack" else (1, 2, 3, 4)
        effects = {identity: "safe_damage" for identity in identities}
        effects[identities[-1]] = "damage"
        cls = (
            RejectSpellSession
            if family in ("rejected_competing", "stale_hint")
            else FakeNativeSession
        )
        session = cls(
            spells=[dict(spellId=identity, level=1) for identity in identities],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects=effects,
        )
        if family == "stale_hint":
            session.rejected_spell = 99
        hint(session, [cast(99 if family == "stale_hint" else 1)])
        depth = 1 if depth is None else depth
    elif family in ("setup_attack", "setup_move_attack"):
        session = (
            PreparationSession()
            if family == "setup_attack"
            else ThreeStepPreparationSession()
        )
        # Unlike the old allocation-only fixture, export its owned spells too:
        # an empty book correctly activates movement-only wall budgeting.
        session.spells = [
            dict(spellId=identity, level=1) for identity in (9, 10, 11, 50, 51)
        ]
        factory = (
            scenario_candidates if family == "setup_attack" else three_step_candidates
        )
        hint(session, [cast(50, 1)])
        depth = (2 if family == "setup_attack" else 3) if depth is None else depth
    elif family == "after_attack_retreat":
        cells = [(x, 0, 0) for x in range(-1, 4)]
        edges = [(a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1]
        session = FakeNativeSession(spells=[], cells=cells, edges=edges)
        session.root_graph = encode(
            dict(
                runtime=SimpleNamespace(
                    fight=SimpleNamespace(
                        walkable=frozenset(cells),
                        edges=frozenset(edges),
                        turn_id=4,
                        events=[
                            dict(kind="damage", source_id=1, target_id=9, amount=1),
                            dict(kind="npc_cast", actor_id=1, turn_id=4),
                        ],
                    )
                )
            )
        )
        session.root_state["nativeContext"] = session.store.put_json(session.root_graph)
        hint(session, [dict(type="move", path=[[1, 0, 0]])])
        depth = 2 if depth is None else depth
    else:
        raise ValueError("Unknown efficiency family")
    session.envelope["policy"]["limits"].update(
        nodes=nodes, depth=depth, beam=beam, probeQuantum=quantum
    )
    return session, factory


def paired_case(family, *, nodes=16, depth=None, beam=2, quantum=8, query_budget=None):
    from query_efficiency_harness import make_search, measure

    paired = []
    for enabled in (False, True):
        session, factory = make_case(
            family, nodes=nodes, depth=depth, beam=beam, quantum=quantum
        )
        search = make_search(
            preview_reuse=enabled, frontier_reuse=enabled, candidate_factory=factory
        )
        paired.append(measure(session, search, query_budget=query_budget))
    return paired


class EfficiencyQualityTests(unittest.TestCase):
    def test_fixed_four_preview_budget_improves_competing_fresh_attack(self):
        before, after = paired_case("immediate_competing", nodes=4)
        self.assertEqual(before["result"]["components"]["damage"], 2)
        self.assertEqual(after["result"]["components"]["damage"], 5)
        self.assertEqual(before["result"]["expanded"], after["result"]["expanded"])
        self.assertGreater(after["uniquePreviews"], before["uniquePreviews"])
        self.assertEqual(after["result"]["action"]["spellId"], 4)

    def test_fixed_five_preview_budget_preserves_complete_setup_sequence(self):
        before, after = paired_case("setup_attack", nodes=5)
        self.assertEqual(before["result"]["components"].get("damage", 0), 2)
        self.assertEqual(after["result"]["components"]["damage"], 20)
        self.assertEqual(
            [action["spellId"] for action in after["result"]["plan"]], [50, 51]
        )
        self.assertEqual(before["result"]["expanded"], after["result"]["expanded"])

    def test_matrix_records_neutral_cases_and_preserves_certified_incumbent(self):
        for family in FAMILIES:
            for nodes in (4, 5, 6, 8, 12, 16):
                with self.subTest(family=family, nodes=nodes):
                    before, after = paired_case(family, nodes=nodes)
                    for sample in (before, after):
                        self.assertLessEqual(sample["result"]["expanded"], nodes)
                        self.assertAlmostEqual(
                            sample["result"]["score"],
                            sum(sample["result"]["components"].values()),
                        )
                    self.assertGreaterEqual(
                        after["result"]["score"], before["result"]["score"]
                    )
                    self.assertEqual(after["duplicatePreviews"], 0)

    def test_setup_move_attack_completes_when_budget_covers_useful_continuation(self):
        before, after = paired_case("setup_move_attack", nodes=16)
        self.assertEqual(
            [step["type"] for step in after["result"]["plan"]], ["cast", "move", "cast"]
        )
        self.assertEqual(after["result"]["components"]["damage"], 20)
        self.assertLessEqual(after["totalQueries"], before["totalQueries"])

    def test_eight_total_queries_find_setup_attack_instead_of_duplicate_work(self):
        before, after = paired_case("setup_attack", nodes=16, query_budget=8)
        self.assertEqual(before["totalQueries"], 8)
        self.assertEqual(after["totalQueries"], 8)
        self.assertEqual(before["result"]["components"]["damage"], 2)
        self.assertEqual(after["result"]["components"]["damage"], 20)
        self.assertGreater(after["uniquePreviews"], before["uniquePreviews"])
        self.assertEqual(after["duplicatePreviews"], 0)

    def test_total_query_cap_matrix_includes_tight_neutral_and_exhausted_cases(self):
        for family in FAMILIES:
            for budget in range(3, 25):
                with self.subTest(family=family, query_budget=budget):
                    before, after = paired_case(family, nodes=16, query_budget=budget)
                    self.assertLessEqual(before["totalQueries"], budget)
                    self.assertLessEqual(after["totalQueries"], budget)
                    self.assertGreaterEqual(
                        after["result"]["score"], before["result"]["score"]
                    )


if __name__ == "__main__":
    unittest.main()
