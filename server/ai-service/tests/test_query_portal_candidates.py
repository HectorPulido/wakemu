"""Native source-bound portal advice enters the ordinary query workflow."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession
from wakfu_ai.context.native_context import NativeGraph
from wakfu_ai.planning.query_search import candidates, _warm_start_actions


class PortalCandidateTests(unittest.TestCase):
    def fixture(self):
        session = FakeNativeSession(
            spells=[],
            cells=[(0, 0, 0), (1, 0, 0), (5, 0, 0), (6, 0, 0)],
            edges=[((0, 0, 0), (1, 0, 0)), ((5, 0, 0), (6, 0, 0))],
        )
        session.root_state["actors"][2]["position"] = [6, 0, 0]
        fact = dict(
            schema="native-portal-travel-v1",
            sourceState="root-state",
            stateRevision=97,
            actorId=1,
            destinations=[[5, 0, 0]],
        )
        return session, dict(spells=[], nativePortalTravel=fact)

    def offers(self, session, metadata):
        return list(
            candidates(NativeGraph(session.root_graph), session.root_state, metadata, 1)
        )

    def test_certified_endpoint_is_separate_from_adjacent_walking_and_does_not_mutate_edges(
        self,
    ):
        session, metadata = self.fixture()
        before = deepcopy(session.root_graph)
        self.assertEqual(
            self.offers(session, metadata),
            [
                dict(type="portal_travel", destination=[5, 0, 0]),
                dict(type="move", path=[[1, 0, 0]]),
            ],
        )
        self.assertEqual(session.root_graph, before)
        self.assertNotIn(((0, 0, 0), (5, 0, 0)), session.edges)

    def test_foreign_actor_revision_source_or_schema_cannot_supply_a_portal_candidate(
        self,
    ):
        for mutation in (
            dict(sourceState="foreign"),
            dict(stateRevision=98),
            dict(actorId=9),
            dict(actorId=True),
            dict(stateRevision=True),
            dict(schema="unknown"),
            dict(sourceState=None),
            dict(extra="unknown"),
        ):
            with self.subTest(mutation=mutation):
                session, metadata = self.fixture()
                metadata["nativePortalTravel"].update(mutation)
                self.assertEqual(
                    self.offers(session, metadata),
                    [dict(type="move", path=[[1, 0, 0]])],
                )

    def test_inactive_actor_cannot_use_another_actors_portal_advice(self):
        session, metadata = self.fixture()
        session.root_state["currentId"] = 9
        self.assertFalse(
            any(
                action["type"] == "portal_travel"
                for action in self.offers(session, metadata)
            )
        )

    def test_destinations_are_copied_deduplicated_and_limited_to_complete_xyz_terrain(
        self,
    ):
        session, metadata = self.fixture()
        metadata["nativePortalTravel"]["destinations"] = [
            [5, 0, 0],
            [5, 0, 0],
            [999, 0, 0],
            [True, 0, 0],
            [5, 0],
            "unknown",
        ]
        result = self.offers(session, metadata)
        portals = [action for action in result if action["type"] == "portal_travel"]
        self.assertEqual(portals, [dict(type="portal_travel", destination=[5, 0, 0])])
        metadata["nativePortalTravel"]["destinations"][0][0] = 99
        self.assertEqual(portals[0]["destination"], [5, 0, 0])

    def test_casts_and_ordinary_routes_remain_eligible_with_portal_advice(self):
        session, metadata = self.fixture()
        metadata["spells"] = [dict(spellId=1, level=1)]
        result = self.offers(session, metadata)
        self.assertTrue(any(action["type"] == "cast" for action in result))
        self.assertIn(dict(type="move", path=[[1, 0, 0]]), result)
        self.assertIn(dict(type="portal_travel", destination=[5, 0, 0]), result)

    def test_warm_portal_requires_exact_shape_and_is_a_defensive_copy(self):
        action = dict(type="portal_travel", destination=[5, 0, 0])
        hint = dict(schema="verified-turn-continuation-v1", actions=[action])
        accepted = _warm_start_actions(hint)
        action["destination"][0] = 99
        self.assertEqual(accepted, [dict(type="portal_travel", destination=[5, 0, 0])])
        for invalid in (
            dict(type="portal_travel", destination=[True, 0, 0]),
            dict(type="portal_travel", destination=[5, 0]),
            dict(type="portal_travel", destination=[5, 0, 0], authorized=True),
        ):
            self.assertEqual(
                _warm_start_actions(dict(schema=hint["schema"], actions=[invalid])), []
            )


if __name__ == "__main__":
    unittest.main()
