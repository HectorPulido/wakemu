"""Deterministic synthetic transition contracts, not native spell semantics.

These fixtures exercise real search, scoring and rival forecasting. The small
providers explicitly define legal transitions; they do not model Wakfu portals.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_jondo_search_hybrid import ThreeStepPreparationSession, scenario_candidates
from test_query_search import make_graph, run_search
from test_query_threat import FakeProvider, run_forecast


ORIGIN, SAFE, TRAP, END = (0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0)


class ForkPreparationSession(ThreeStepPreparationSession):
    def __init__(self, *, safe_available=True, hp_toll=0, ap_toll=0, mp=2):
        super().__init__()
        self.safe_available, self.hp_toll, self.ap_toll = (
            safe_available,
            hp_toll,
            ap_toll,
        )
        self.edges = [(ORIGIN, SAFE), (SAFE, END), (ORIGIN, TRAP), (TRAP, END)]
        self.cells = [ORIGIN, SAFE, TRAP, END]
        self.root_state["nativeContext"] = self.store.put_json(
            make_graph(self.cells, self.edges)
        )
        self.root_state["actors"][0]["mp"] = mp
        self.envelope["policy"]["limits"].update(depth=3, beam=2, nodes=32)
        self.transitions = []

    def request(self, query):
        if query["operation"] != "preview":
            return super().request(query)
        action = query["action"]
        prior = self.states[query["state"]]["public"]
        mover = prior["actors"][0]
        if action["type"] == "move":
            path = [tuple(cell) for cell in action["path"]]
            origin = tuple(mover["position"])
            valid = all(edge in self.edges for edge in zip([origin] + path, path))
            if (
                not valid
                or len(path) > mover["mp"]
                or not self.safe_available
                and SAFE in path
            ):
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["synthetic_route_unavailable"],
                )
            public = deepcopy(prior)
            public.update(key="state-" + str(len(self.states)), stage="moved")
            actor = public["actors"][0]
            actor.update(
                position=list(path[-1]),
                mp=actor["mp"] - len(path),
                ap=max(0, actor["ap"] - self.ap_toll),
            )
            if TRAP in path:
                actor["hp"] = max(0, actor["hp"] - self.hp_toll)
            if not actor["hp"]:
                public.update(phase="finished", currentId=None)
            self.states[public["key"]] = dict(public=public, used=False)
            self.transitions.append((deepcopy(action), deepcopy(public)))
            return dict(id=query["id"], supported=True, result=public)
        if action.get("spellId") == 51 and mover["ap"] <= 0:
            return dict(
                id=query["id"],
                supported=False,
                unknownDependencies=["synthetic_ap_exhausted"],
            )
        response = super().request(query)
        self.transitions.append((deepcopy(action), deepcopy(response["result"])))
        return response


def fork_candidates(graph, state, repertoire, actor_id, *args, **kwargs):
    if state["phase"] != "active":
        return
    if state["stage"] == "prepared":
        # Adversarial order: harmful route is offered before the safe route.
        yield dict(type="move", path=[list(TRAP), list(END)])
        yield dict(type="move", path=[list(SAFE), list(END)])
    elif state["stage"] == "moved":
        yield dict(type="cast", spellId=51, level=1, targetId=9, target=[9, 0, 0])
    else:
        yield from scenario_candidates(graph, state, repertoire, actor_id)


class PreparedRivalProvider(FakeProvider):
    """Five weak attacks crowd a neutral setup before its 20-HP followup."""

    def query(self, query):
        if query["operation"] != "preview" or query["action"]["type"] == "end_turn":
            return super().query(query)
        current = self.states[query["state"]]
        public = deepcopy(current["public"])
        action = query["action"]
        self.preview_log.append((query["state"], deepcopy(action)))
        public.update(key="synthetic-rival-" + str(len(self.states)))
        rival = next(actor for actor in public["actors"] if actor["id"] == 9)
        rival["ap"] -= 1
        if action["spellId"] == 50:
            public["stage"] = "prepared"
            # Certified resource preparation: the actual public AP increases
            # from six to eight, while no damage has happened yet.
            rival["ap"] += 3
        else:
            next(actor for actor in public["actors"] if actor["id"] == 1)["hp"] -= (
                20 if action["spellId"] == 51 else 2
            )
            public["stage"] = "spent"
        self.states[public["key"]] = dict(public=public, rival=9, used=False)
        return dict(id=query["id"], supported=True, result=public)


def rival_candidates(graph, state, repertoire, actor_id, *args, **kwargs):
    if state.get("stage") == "spent":
        return
    identities = (
        [51] if state.get("stage") == "prepared" else [700, 701, 702, 703, 704, 50]
    )
    for identity in identities:
        yield dict(type="cast", spellId=identity, level=1, targetId=1, target=[0, 0, 0])


class WeakFinisherRivalProvider(PreparedRivalProvider):
    def query(self, query):
        response = super().query(query)
        if query["operation"] == "preview":
            if query["action"].get("spellId") == 703:
                response["result"]["stage"] = "finisher-ready"
            if query["action"].get("spellId") == 52:
                next(
                    actor for actor in response["result"]["actors"] if actor["id"] == 1
                )["hp"] -= 25
        return response


def finisher_candidates(graph, state, repertoire, actor_id, *args, **kwargs):
    if state.get("stage") == "finisher-ready":
        yield dict(type="cast", spellId=52, level=1, targetId=1, target=[0, 0, 0])
    else:
        yield from rival_candidates(graph, state, repertoire, actor_id)


class AdversarialTacticalSequenceTests(unittest.TestCase):
    def run_fork(self, **kwargs):
        session = ForkPreparationSession(**kwargs)
        with patch("wakfu_ai.planning.query_search.candidates", fork_candidates):
            result = run_search(session, clock=lambda: 0)
        self.assertLessEqual(result["expanded"], 32)
        self.assertLessEqual(
            result["searchBudgetEvidence"]["peakContinuationFrames"], 2
        )
        return session, result

    def test_preparation_move_attack_chooses_safe_path_despite_harmful_first_order(
        self,
    ):
        for toll in (1, 10, 30):
            with self.subTest(hp_toll=toll):
                session, result = self.run_fork(hp_toll=toll)
                self.assertEqual(
                    [action["type"] for action in result["plan"]],
                    ["cast", "move", "cast"],
                )
                self.assertEqual(result["plan"][1]["path"], [list(SAFE), list(END)])
                self.assertEqual(result["components"]["damage"], 20)
                self.assertTrue(
                    any(
                        action["type"] == "move" and state["actors"][0]["hp"] < 30
                        for action, state in session.transitions
                    )
                )

    def test_unavoidable_small_toll_keeps_combo_but_costly_toll_keeps_direct_attack(
        self,
    ):
        _, cheap = self.run_fork(safe_available=False, hp_toll=1)
        _, costly = self.run_fork(safe_available=False, hp_toll=25)
        self.assertEqual(
            [action["type"] for action in cheap["plan"]], ["cast", "move", "cast"]
        )
        self.assertEqual(cheap["plan"][1]["path"], [list(TRAP), list(END)])
        self.assertEqual(costly["components"]["damage"], 2)
        self.assertEqual(len(costly["plan"]), 1)

    def test_ap_or_mp_exhaustion_cannot_publish_uncertified_combo(self):
        for resources in (dict(mp=1), dict(ap_toll=6)):
            with self.subTest(resources=resources):
                _, result = self.run_fork(**resources)
                self.assertEqual(result["components"]["damage"], 2)
                self.assertEqual(len(result["plan"]), 1)
                self.assertIn(result["action"]["spellId"], (9, 10, 11))

    def test_rival_setup_can_be_pruned_under_same_hard_node_budget(self):
        results = []
        for beam in (4, 6):
            provider = PreparedRivalProvider()
            with patch("wakfu_ai.planning.query_search.candidates", rival_candidates):
                result = run_forecast(
                    provider, depth=2, nodes=16, beam=beam, clock=lambda: 0
                )
            self.assertLessEqual(result["rivals"][0]["expanded"], 16)
            results.append(result)
        self.assertEqual(results[0]["knownLowerBound"], 2)
        self.assertEqual(results[1]["knownLowerBound"], 20)
        # This is a documented search limitation, not a false safety claim.
        self.assertFalse(results[0]["complete"])
        self.assertIn("rival_response_beam_pruned", results[0]["unknownDependencies"])

    def test_small_rival_attack_can_hide_a_stronger_continuation_than_setup(self):
        provider = WeakFinisherRivalProvider()
        with patch("wakfu_ai.planning.query_search.candidates", finisher_candidates):
            result = run_forecast(provider, depth=2, nodes=16, beam=4, clock=lambda: 0)
        # Reserving the last slot for setup discards this branch in the private
        # experiment. Its actual 29-HP outcome exceeds the setup's 20-HP attack.
        self.assertEqual(result["knownLowerBound"], 29)
        self.assertLessEqual(result["rivals"][0]["expanded"], 16)
        self.assertTrue(
            any(action.get("spellId") == 52 for _, action in provider.preview_log)
        )


if __name__ == "__main__":
    unittest.main()
