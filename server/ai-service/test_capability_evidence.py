from copy import deepcopy
import unittest

from capability_evidence import observed
from native_context import NativeGraph
from query_search import candidates, _diverse_beam
from test_query_search import (
    ACTOR_ID,
    ALLY_ID,
    ENEMY_ID,
    fixture,
    run_search,
    FakeNativeSession,
)
from topology_distance import measure


class CapabilityEvidenceTests(unittest.TestCase):
    def support_fixture(self, *, healing):
        origin, stair, support, ally = (0, 0, 0), (-1, 0, 0), (-2, 0, 1), (-3, 0, 1)
        cells = [origin, stair, support, ally, (1, 0, 0), (2, 0, 0), (3, 0, 0)]
        edges = [
            (origin, stair),
            (stair, support),
            (support, ally),
            (origin, (1, 0, 0)),
            ((1, 0, 0), (2, 0, 0)),
            ((2, 0, 0), (3, 0, 0)),
        ]
        session = FakeNativeSession(
            spells=[dict(spellId=987654, level=1)],
            cells=cells,
            edges=edges,
            effects={987654: "heal" if healing else "none"},
        )
        session.root_state["actors"][1].update(position=list(ally), hp=10)
        session.root_state.update(
            measure(cells, edges, session.root_state["actors"], actor_id=ACTOR_ID)
        )
        session.envelope["policy"]["limits"].update(depth=2, beam=2, nodes=40)
        original = session.request

        def request(query):
            state = session.states[query["state"]]["public"]
            if query["operation"] == "preview":
                action = query["action"]
                caster = next(
                    actor for actor in state["actors"] if actor["id"] == ACTOR_ID
                )
                if (
                    action["type"] == "cast"
                    and action.get("targetId") == ALLY_ID
                    and tuple(caster["position"]) != support
                ):
                    return dict(
                        id=query["id"],
                        supported=False,
                        unknownDependencies=["native_support_out_of_range"],
                    )
            response = original(query)
            if query["operation"] == "preview" and response["supported"]:
                public = response["result"]
                public.update(
                    measure(cells, edges, public["actors"], actor_id=ACTOR_ID)
                )
            return response

        session.request = request
        return session

    def test_unknown_heal_out_of_root_range_survives_enemy_approach_with_beam_two(self):
        session = self.support_fixture(healing=True)
        result = run_search(session)
        self.assertEqual(
            result["plan"][0], dict(type="move", path=[[-1, 0, 0], [-2, 0, 1]])
        )
        self.assertEqual(result["plan"][1]["targetId"], ALLY_ID)
        self.assertEqual(result["components"]["healing"], 8)
        self.assertLess(result["components"]["position"], 0)
        self.assertEqual(session.root_state["actors"][1]["hp"], 10)

    def test_support_exploration_without_effect_does_not_reward_support_position(self):
        session = self.support_fixture(healing=False)
        result = run_search(session)
        self.assertEqual(result["components"]["healing"], 0)
        self.assertNotIn([-2, 0, 1], result["action"].get("path", []))
        self.assertTrue(
            any(
                action.get("path", [])[-1:] == [[-2, 0, 1]]
                for action in session.preview_actions
            )
        )

    def test_support_order_keeps_every_route_and_spell_candidate(self):
        session = self.support_fixture(healing=False)
        graph = NativeGraph(session.root_graph)
        state = deepcopy(session.root_state)
        wounded = list(candidates(graph, state, {"spells": session.spells}, ACTOR_ID))
        state["actors"][1]["hp"] = state["actors"][1]["max_hp"]
        healthy = list(candidates(graph, state, {"spells": session.spells}, ACTOR_ID))
        self.assertEqual(sorted(map(repr, wounded)), sorted(map(repr, healthy)))
        moves = [action for action in wounded if action["type"] == "move"]
        self.assertEqual(len(moves), len({repr(action) for action in moves}))
        self.assertEqual(moves[1]["path"][-1], [-2, 0, 1])

    def test_support_beam_rejects_foreign_or_unknown_facts_without_changing_scores(
        self,
    ):
        def option(key, score, distance, *, actor_id=ACTOR_ID, targets=None):
            return dict(
                key=key,
                score=score,
                intent="position",
                target=None,
                actions=[{}],
                state=dict(
                    key=key,
                    nativeSupportApproach=dict(
                        actorId=actor_id,
                        targetIds=[ALLY_ID] if targets is None else targets,
                        distance=distance,
                    ),
                ),
            )

        best = option("attack-position", 10, 4)
        alternative = option("other-position", 9, 3)
        reference = dict(actorId=ACTOR_ID, targetIds=[ALLY_ID], distance=3)
        for candidate in (
            option("support", -2, None),
            option("support", -2, 1, actor_id=99),
            option("support", -2, 1, targets=[88]),
        ):
            with self.subTest(candidate=candidate):
                self.assertEqual(
                    _diverse_beam(
                        [best, alternative, candidate], 2, ACTOR_ID, reference
                    ),
                    [best, alternative],
                )
        support = option("support", -2, 1)
        self.assertEqual(
            _diverse_beam([best, alternative, support], 2, ACTOR_ID, reference),
            [best, support],
        )
        self.assertEqual(support["score"], -2)
        self.assertEqual(_diverse_beam([best, support], 1, ACTOR_ID, reference), [best])

    def test_receipt_variants_of_same_runtime_do_not_consume_distinct_beam_slots(self):
        def option(key, score, intent, target, identity):
            return dict(
                key=key,
                score=score,
                intent=intent,
                target=target,
                actions=[{}],
                state=dict(key=key, runtimeIdentity=identity * 64),
            )

        options = [
            option("receipt-a", 10, "damage", 9, "a"),
            option("receipt-b", 9, "damage", 10, "a"),
            option("support", 8, "heal", 2, "b"),
        ]
        self.assertEqual(
            [node["key"] for node in _diverse_beam(options, 2)],
            ["receipt-a", "support"],
        )

    def test_observed_attack_orders_enemy_before_wounded_ally_without_filtering(self):
        session = fixture([dict(spellId=987654, level=2)], edges=[])
        session.root_state["actors"][1]["hp"] = 10
        graph = NativeGraph(session.root_graph)
        baseline = list(
            candidates(graph, session.root_state, {"spells": session.spells}, ACTOR_ID)
        )
        ranked = list(
            candidates(
                graph,
                session.root_state,
                {"spells": session.spells},
                ACTOR_ID,
                {(987654, 2): {"damage"}},
            )
        )
        self.assertEqual(baseline[0]["targetId"], ALLY_ID)
        self.assertEqual(ranked[0]["targetId"], ENEMY_ID)
        self.assertEqual(sorted(map(repr, baseline)), sorted(map(repr, ranked)))

    def test_multi_role_spell_keeps_wounded_ally_and_enemy_high_priority(self):
        session = fixture([dict(spellId=100, level=1)], edges=[])
        session.root_state["actors"][1]["hp"] = 10
        actions = list(
            candidates(
                NativeGraph(session.root_graph),
                session.root_state,
                {"spells": session.spells},
                ACTOR_ID,
                {(100, 1): {"damage", "healing"}},
            )
        )
        self.assertEqual([a.get("targetId") for a in actions[:2]], [ALLY_ID, ENEMY_ID])
        self.assertEqual(len(actions), len(session.cells))

    def test_beam_retains_support_branch_among_repeated_damage_options(self):
        def option(key, score, intent, target):
            return dict(
                key=key, score=score, intent=intent, target=target, actions=[{}]
            )

        options = [
            option("attack-a", 10, "damage", ENEMY_ID),
            option("attack-b", 9, "damage", ENEMY_ID),
            option("heal", 3, "heal", ALLY_ID),
        ]
        beam = _diverse_beam(options, 2)
        self.assertEqual([node["key"] for node in beam], ["attack-a", "heal"])
        self.assertEqual(beam[1]["score"], 3)
        self.assertEqual(_diverse_beam(options, 1), [options[0]])
        self.assertEqual(
            [node["key"] for node in _diverse_beam(options, 3)],
            ["attack-a", "heal", "attack-b"],
        )

    def test_support_branch_can_win_only_after_a_certified_continuation(self):
        session = fixture(
            [dict(spellId=i, level=1) for i in (100, 101, 200)],
            effects={100: "damage", 101: "damage", 200: "heal"},
            edges=[],
        )
        session.root_state["actors"][1]["hp"] = 20
        session.envelope["policy"]["weights"] = {"damage": 2}
        session.envelope["policy"]["limits"].update(depth=2, beam=2)
        native_request = session.request

        def request(query):
            parent = session.states[query["state"]]
            ally = next(a for a in parent["public"]["actors"] if a["id"] == ALLY_ID)
            enemy = next(a for a in parent["public"]["actors"] if a["id"] == ENEMY_ID)
            support_ready = ally["hp"] == 28 and enemy["hp"] == 30
            if query["operation"] == "repertoire" and support_ready:
                parent["used"] = False
            response = native_request(query)
            if (
                query["operation"] == "preview"
                and support_ready
                and response["supported"]
            ):
                action = query["action"]
                if (
                    action.get("spellId") in (100, 101)
                    and action.get("targetId") == ENEMY_ID
                ):
                    child = response["result"]
                    next(a for a in child["actors"] if a["id"] == ENEMY_ID)["hp"] = 10
            return response

        session.request = request
        result = run_search(session)
        self.assertEqual([a["spellId"] for a in result["plan"]], [200, 100])
        self.assertEqual(result["components"]["healing"], 8)
        self.assertEqual(result["components"]["damage"], 40)

    def test_one_spell_can_have_multiple_observed_capabilities(self):
        session = fixture([])
        before = {row["id"]: dict(row) for row in session.root_actors}
        before[ALLY_ID]["hp"] = 20
        after = deepcopy(before)
        after[ENEMY_ID]["hp"] -= 3
        after[ENEMY_ID]["ap"] -= 1
        after[ENEMY_ID]["position"] = [4, 0, 0]
        after[ALLY_ID]["hp"] += 2
        after[ALLY_ID]["armor"] += 4
        after[88] = dict(after[ALLY_ID], id=88, registeredSummon=True)
        self.assertEqual(
            observed(before, after, ACTOR_ID),
            ["control", "damage", "displacement", "healing", "protection", "summoning"],
        )

    def test_self_movement_and_friendly_damage_do_not_imply_damage_role(self):
        session = fixture([])
        before = {row["id"]: dict(row) for row in session.root_actors}
        after = deepcopy(before)
        after[ACTOR_ID]["position"] = [1, 0, 0]
        after[ALLY_ID]["hp"] -= 5
        after[88] = dict(after[ALLY_ID], id=88)
        self.assertEqual(observed(before, after, ACTOR_ID), [])

    def test_search_reports_actual_damage_for_arbitrary_spell_id(self):
        session = fixture([dict(spellId=987654, level=2)], effects={987654: "damage"})
        result = run_search(session)
        self.assertEqual(
            result["capabilityEvidence"],
            [
                dict(
                    spellId=987654,
                    level=2,
                    observedCapabilities=["damage"],
                    basis="certified_native_transition",
                )
            ],
        )
        self.assertFalse(result["capabilitySurveyComplete"])

    def test_rejected_spell_does_not_acquire_capability_evidence(self):
        session = fixture([dict(spellId=7962, level=1)])
        session.reject_all = True
        self.assertEqual(run_search(session)["capabilityEvidence"], [])
