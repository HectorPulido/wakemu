"""Native movement/search/publication followed by a fresh remote continuation.

The transport is an in-memory substitute for HTTP only: QuerySessions runs the
real planner and NativeSession answers through the real NativeOracle. Combat
rules, resources, targeting, state transitions and Registry are not mocked.
"""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_native_oracle as native_fixtures
from wakfu_ai.bridge.world_bridge import _json_bytes, NativeSession
from wakfu_ai.bridge.world_shared import run_shared_turn
from wakfu_ai.context.native_context import NativeGraph
from wakfu_ai.native import native_turn
from wakfu_ai.native.native_stats import NativeStats
from wakfu_ai.planning.query_sessions import QuerySessions
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session


class NativeContinuationE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixtures.NativeOracleTests.setUpClass()

    def test_real_move_plan_is_published_then_fresh_cast_is_repreviewed(self):
        from wakfu_server.spells import default_deck

        fixture = native_fixtures.NativeOracleTests.wonejo_fixture(
            compact=True,
            monster_position=(-6, -7, -1),
        )
        fight = fixture.fight
        fight.order = [fixture.npc.id, fixture.pc.id]
        fight.turn_index = 0
        fixture.npc.turn_count = 1
        # This fixture supplies one movement point to expose move -> native
        # melee cast, without changing the spell or any spell rule.
        from wakfu_server.combat_resource_pa_notifications import set_resource_current

        set_resource_current(fight, fixture.npc, 3, 1)
        runtime = RuntimeMessages(fight)
        runtime.tactical_encounter_id = "native-continuation-e2e"
        participant = Session(
            fixture.character["account_id"],
            fixture.pc.id,
            "native-continuation-e2e",
            fixture.character["map_id"],
            0,
        )
        registry = Registry(lambda member: member == participant)
        shared = registry.register(fight, participant, runtime=runtime)
        sessions = QuerySessions()
        roots, decisions, queries, responses = [], [], [], []

        class Store:
            graphs = {}

            def seal_manifest(self, digest):
                return {"complete": digest == "c" * 64}

            def json(self, digest):
                return deepcopy(self.graphs[digest])

        store = Store()

        class Transport:
            def catalog(self, exporter):
                return "c" * 64

            def instance(self, graph):
                payload = _json_bytes(graph)
                digest = hashlib.sha256(payload).hexdigest()
                store.graphs[digest] = json.loads(payload)
                return digest

            def _retry_request(self, endpoint, payload):
                if endpoint != "/v3/decide":
                    raise AssertionError(endpoint)
                if "response" not in payload:
                    roots.append(deepcopy(payload))
                else:
                    responses.append(
                        (payload["requestId"], deepcopy(payload["response"]))
                    )
                response = sessions.decide(payload, store)
                if response["status"] == "query":
                    queries.extend(
                        (payload["requestId"], deepcopy(row))
                        for row in response["queries"]
                    )
                elif response["status"] == "decided":
                    decisions.append(deepcopy(response["decision"]))
                return response

            def request(self, endpoint, payload):
                if endpoint == "/v3/cancel":
                    return sessions.cancel(payload)
                return self._retry_request(endpoint, payload)

        # Threat search has independent native coverage. This test isolates
        # continuity of a two-action own-turn plan and publication custody.
        class OwnTurnSession(NativeSession):
            OPERATIONS = tuple(
                operation
                for operation in NativeSession.OPERATIONS
                if operation != "project_turn"
            )

        deck = default_deck(fixture.character)
        serializer = NativeStats(
            characters={fixture.pc.id: fixture.character},
            monsters={fixture.npc.id: fixture.monster},
            fight_id=fight.id,
        )
        policy = dict(limits=dict(depth=2, beam=4, nodes=48, budgetMs=10000))

        def runner(native):
            return native_turn.run_turn(
                native,
                characters={fixture.pc.id: fixture.character},
                monsters={fixture.npc.id: fixture.monster},
                decks={fixture.pc.id: deck},
                excluded_decks={fixture.pc.id: frozenset()},
                viewer_id=fixture.pc.id,
                flags={},
                transport=Transport(),
                exporter=object(),
                policy=policy,
                policy_version="native-continuation-e2e",
                stats_serializer=serializer,
                budget_seconds=120,
            )

        driver = run_shared_turn(
            runtime, SimpleNamespace(registry=registry), participant, runner
        )
        with patch.object(native_turn, "NativeSession", OwnTurnSession):
            try:
                first = next(driver)[1]
                self.assertEqual(first["action"]["type"], "move", first)
                self.assertGreaterEqual(len(first["plan"]), 2, first)
                self.assertEqual(first["plan"][1]["type"], "cast", first)
                self.assertEqual(shared.sequence, 1)
                published_position = shared.fight.actors[fixture.npc.id].position
                self.assertNotEqual(published_position, fixture.npc.position)
                health_before = shared.fight.actors[fixture.pc.id].hp
                caster_before = shared.fight.actors[fixture.npc.id]
                resources_before = dict(
                    ap=caster_before.ap,
                    mp=caster_before.mp,
                    wp=caster_before.effect_stats[4],
                )

                second = next(driver)[1]
                self.assertEqual(second["action"]["type"], "cast", second)
                self.assertEqual(shared.sequence, 2)
                self.assertLess(shared.fight.actors[fixture.pc.id].hp, health_before)
                self.assertNotEqual(roots[0]["sourceKey"], roots[1]["sourceKey"])
                self.assertNotEqual(roots[0]["rootState"], roots[1]["rootState"])
                self.assertNotIn("warmStart", roots[0])
                self.assertEqual(roots[1]["warmStart"]["actions"], first["plan"][1:4])
                self.assertEqual(second["searchBudgetEvidence"]["warmStartAccepted"], 1)
                second_previews = [
                    query
                    for request, query in queries
                    if request == roots[1]["requestId"]
                    and query["operation"] == "preview"
                ]
                self.assertEqual(second_previews[0]["state"], roots[1]["rootState"])
                self.assertEqual(second_previews[0]["action"], first["plan"][1])
                fresh_preview = next(
                    response["result"]
                    for request, response in responses
                    if request == roots[1]["requestId"]
                    and response["id"] == second_previews[0]["id"]
                )
                # Read costs from the native SpellTransaction that authorized
                # this fresh preview. Some owned attacks cost zero AP; verify
                # exact payment rather than inventing a positive AP charge.
                graph = NativeGraph(store.graphs[fresh_preview["nativeContext"]])
                transition = graph.field(graph.data["root"], "transition")
                transaction = graph.field(transition, "transaction")
                plan = graph.field(transaction, "plan")
                costs = graph.plain(graph.field(plan, "costs"))
                caster_after = shared.fight.actors[fixture.npc.id]
                resources_after = dict(
                    ap=caster_after.ap,
                    mp=caster_after.mp,
                    wp=caster_after.effect_stats[4],
                )
                for resource in ("ap", "mp", "wp"):
                    self.assertIs(type(costs[resource]), int)
                    self.assertEqual(
                        resources_before[resource] - resources_after[resource],
                        costs[resource],
                        (resource, costs, second["action"]),
                    )
                self.assertTrue(
                    any(
                        event.get("kind") == "npc_cast"
                        and event.get("spell_id") == second["action"]["spellId"]
                        and event.get("actor_id") == fixture.npc.id
                        for event in shared.fight.events
                    )
                )
                for batch in registry.drain(fight.id, participant):
                    self.assertTrue(batch.packets)
                self.assertEqual(len(decisions), 2)
            finally:
                driver.close()


if __name__ == "__main__":
    unittest.main()
