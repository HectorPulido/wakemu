"""Source custody and chosen-action transaction tests for the new adapter."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

import wakfu_ai.bridge

_STAGE = Path(__file__).resolve().parents[1] / "wakfu_ai" / "bridge"
if str(_STAGE) not in wakfu_ai.bridge.__path__:
    wakfu_ai.bridge.__path__.insert(0, str(_STAGE))
from wakfu_ai.bridge import jondo_entry
from wakfu_ai.bridge.jondo_snapshot import (
    summarize,
    usage_rows,
    portal_edges,
    _reachable,
    semantic_rows,
    utility_targets,
)


class Runtime:
    def __init__(self):
        self.fight = SimpleNamespace(
            phase="active", current=SimpleNamespace(id=-7), turn_id=1
        )
        self.awaiting_ack, self.pending, self.ends = None, [], 0

    def end_server_turn(self, actor, turn):
        self.ends += 1
        self.awaiting_ack = turn
        return [(9000, b"end")]


class Oracle:
    def __init__(self, runtime):
        self.runtime, self.identity, self.calls = runtime, "native-source", []

    def state_identity(self, runtime):
        return self.identity

    def commit(self, action, *, stats_serializer):
        self.calls.append(deepcopy(action))
        if action.get("spellId") == 99:
            raise ValueError("Native casting rejects missing WP")
        if action["type"] == "end_turn":
            return self.runtime.end_server_turn(-7, 1)
        self.identity += "-committed"
        return [(12588, b"native")]

    def preview(self, *args):
        raise AssertionError("The bridge must not run speculative native candidates")


class Transport:
    def __init__(self, callback):
        self.callback, self.requests = callback, []

    def request(self, endpoint, request, *, deadline):
        self.assert_endpoint = endpoint
        self.requests.append(deepcopy(request))
        return 200, self.callback(request, len(self.requests))


def request_fixture(oracle, *, excluded_actions, budget_ms):
    return dict(
        protocol=1,
        requestId="request-" + str(len(excluded_actions)),
        source={"nativeIdentity": oracle.identity},
        excludedActions=list(excluded_actions),
    )


def reply(request, action, alternatives=()):
    return dict(
        protocol=1,
        requestId=request["requestId"],
        source=deepcopy(request["source"]),
        action=action,
        alternatives=list(alternatives),
    )


class JondoBridgeTests(unittest.TestCase):
    def drive(self, oracle, callback, **kwargs):
        transport = Transport(callback)
        with patch.object(jondo_entry, "build_snapshot", request_fixture):
            deliveries = list(
                jondo_entry.run_prepared_turn(
                    oracle.runtime,
                    oracle,
                    object(),
                    transport,
                    deadline=time.monotonic() + 10,
                    max_actions=1,
                    **kwargs
                )
            )
        return deliveries, transport

    def test_rejected_choice_rolls_back_and_a_native_alternative_still_executes(self):
        oracle = Oracle(Runtime())
        bad = dict(type="cast", spellId=99, level=1, target=[1, 0, 0])
        good = dict(type="cast", spellId=7, level=1, target=[1, 0, 0])
        deliveries, transport = self.drive(
            oracle, lambda req, count: reply(req, bad, [good])
        )
        self.assertEqual(oracle.calls[:2], [bad, good])
        self.assertEqual(transport.assert_endpoint, "/jondo/decide")
        self.assertEqual(deliveries[0][0], [(12588, b"native")])
        self.assertEqual(len(deliveries[0][1]["rejectedActions"]), 1)
        self.assertEqual(oracle.runtime.ends, 1)

    def test_rejection_feedback_requeries_the_same_unmutated_source(self):
        oracle = Oracle(Runtime())
        bad = dict(type="cast", spellId=99, level=1, target=[1, 0, 0])
        good = dict(type="move", path=[[1, 0, 0]])

        def callback(req, count):
            return reply(req, bad, [] if count == 1 else [good])

        deliveries, transport = self.drive(oracle, callback)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(
            transport.requests[1]["excludedActions"], [jondo_entry.action_key(bad)]
        )
        self.assertEqual(
            transport.requests[0]["source"], transport.requests[1]["source"]
        )
        self.assertEqual(deliveries[0][1]["action"], good)

    def test_foreign_source_is_never_committed(self):
        oracle = Oracle(Runtime())

        def callback(req, count):
            result = reply(req, dict(type="end_turn"))
            result["source"]["nativeIdentity"] = "different-fight"
            return result

        with self.assertRaisesRegex(ValueError, "foreign native source"):
            self.drive(oracle, callback)
        self.assertEqual(oracle.calls, [])

    def test_source_changed_during_transport_is_rejected(self):
        oracle = Oracle(Runtime())

        def callback(req, count):
            oracle.identity = "concurrent-native-transition"
            return reply(req, dict(type="end_turn"))

        with self.assertRaisesRegex(ValueError, "source changed"):
            self.drive(oracle, callback)
        self.assertEqual(oracle.calls, [])

    def test_valid_end_turn_keeps_the_original_jondo_choice(self):
        oracle = Oracle(Runtime())
        deliveries, transport = self.drive(
            oracle,
            lambda req, count: reply(
                req, dict(type="end_turn"), [dict(type="move", path=[[1, 0, 0]])]
            ),
        )
        self.assertEqual(oracle.calls, [dict(type="end_turn")])
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(oracle.runtime.awaiting_ack, 1)

    def test_pending_presentation_prevents_network_and_turn_advance(self):
        oracle = Oracle(Runtime())
        oracle.runtime.pending = ["native-fifo-delivery"]
        deliveries, transport = self.drive(
            oracle, lambda req, count: self.fail("unexpected request")
        )
        self.assertEqual(deliveries, [])
        self.assertEqual(transport.requests, [])
        self.assertEqual(oracle.runtime.ends, 0)

    def test_invalid_boolean_protocol_is_not_accepted_as_version_one(self):
        request = dict(requestId="native", source={"nativeIdentity": "source"})
        invalid = dict(
            protocol=True,
            requestId="native",
            source=request["source"],
            action={"type": "end_turn"},
        )
        with self.assertRaises(ValueError):
            list(jondo_entry.checked_actions(invalid, request))

    def test_summary_does_not_multiply_damage_for_three_disjoint_relations(self):
        rows = [
            dict(
                kind="damage",
                amount=12,
                target=relation,
                nativeReference=77,
                element="fire",
            )
            for relation in ("self", "ally", "enemy")
        ]
        result = summarize(rows, [])
        self.assertEqual(result["damage"], 12)
        self.assertTrue(result["hurtsAllies"])
        self.assertEqual(result["element"], "fire")
        self.assertEqual(summarize([], ["unknown_native_mechanic"])["utility"], 1)

    def test_native_normal_variant_does_not_add_critical_branch_or_its_children(self):
        def effect(amount, variant, **extras):
            return dict(
                effect_class=2,
                variant=variant,
                minimum_level=0,
                maximum_level=100,
                parameters=[amount, 0],
                parameter_count=1,
                probability_base=100,
                probability_per_level=0,
                native_target_selector=None,
                area_class="anD",
                area_native="point",
                children=(),
                **extras
            )

        critical = effect(12, 1)
        critical["children"] = [4]
        compiled = SimpleNamespace(
            effects={
                "1": critical,
                "2": effect(10, 0),
                "3": effect(999, 0, criteria="unresolved"),
                "4": effect(500, 0),
            }
        )
        with patch(
            "wakfu_server.combat_static_catalogs.characteristic_registry",
            return_value={"effects": {}},
        ):
            rows, unknown = semantic_rows(compiled, [1, 2], 10)
        self.assertEqual(summarize(rows, unknown)["damage"], 10)
        self.assertEqual({row["nativeReference"] for row in rows}, {2})

    def test_unknown_mechanic_uses_native_enemy_selector_without_fake_damage(self):
        compiled = SimpleNamespace(
            effects={
                "1": dict(
                    variant=0,
                    native_target_selector=dict(**{"class": "fcE"}, mask=8),
                    children=(),
                )
            }
        )
        fact = utility_targets(
            compiled, [1], 10, rule=dict(maximum=5, allow_self=False)
        )
        self.assertTrue(fact["utilityOnEnemies"])
        self.assertEqual(fact["utilityTargets"], ["enemy"])
        self.assertEqual(fact["utilityTargetBasis"], "exclusive_enemy")
        self.assertEqual(
            summarize([], ["percent_hp_requires_target_context"])["damage"], 0
        )

    def test_null_selector_stays_ambiguous_and_zero_range_enemy_aura_aims_at_self(self):
        compiled = SimpleNamespace(
            effects={"1": dict(variant=0, native_target_selector=None, children=())}
        )
        fact = utility_targets(compiled, [1], 10, rule=dict(maximum=5, allow_self=True))
        self.assertFalse(fact["utilityOnEnemies"])
        self.assertEqual(fact["utilityTargets"], ["ally", "enemy", "self"])
        self.assertEqual(fact["utilityTargetBasis"], "mixed_or_unknown")
        compiled.effects["1"]["native_target_selector"] = dict(
            **{"class": "fcE"}, mask=8
        )
        aura = utility_targets(compiled, [1], 10, rule=dict(maximum=0, allow_self=True))
        self.assertFalse(aura["utilityOnEnemies"])
        self.assertEqual(aura["utilityTargets"], ["self"])
        self.assertEqual(aura["utilityEffectRelations"], ["enemy"])
        self.assertEqual(aura["utilityTargetBasis"], "self_aim_zero_range")

    def test_unknown_selector_does_not_certify_enemy_only_or_reuse_critical_relations(
        self,
    ):
        compiled = SimpleNamespace(
            effects={
                "1": dict(variant=0, children=()),
                "2": dict(
                    variant=1,
                    native_target_selector=dict(**{"class": "fcE"}, mask=8),
                    children=(),
                ),
            }
        )
        fact = utility_targets(compiled, [1, 2], 10)
        self.assertFalse(fact["utilityOnEnemies"])
        self.assertTrue(fact["utilityTargetUnknown"])
        self.assertEqual(fact["utilityTargets"], [])

    def test_usage_is_current_caster_turn_and_cooldown_not_another_actor_book(self):
        fight = SimpleNamespace(
            turn_id=44,
            native_table_turn=8,
            native_spell_usage={
                "-7": dict(
                    turn=2,
                    casts={"17": 2},
                    targets={"17": {"('actor', 40)": 1}},
                    last={"17": 7},
                ),
                "-8": dict(turn=2, casts={"99": 5}),
            },
        )
        actor = SimpleNamespace(id=-7, turn_count=2)
        rows = usage_rows(fight, actor, [dict(id=17, interval=3)])
        self.assertEqual(
            rows,
            [
                dict(spellId=17, count=2, remainingCooldown=2),
                dict(
                    spellId=17, count=2, remainingCooldown=2, targetId=40, targetCount=1
                ),
            ],
        )
        actor.turn_count = 3
        self.assertEqual(
            usage_rows(fight, actor, [dict(id=17, interval=3)]),
            [dict(spellId=17, count=0, remainingCooldown=2)],
        )

    def test_unlimited_native_spell_events_still_supply_jondo_support_usage(self):
        actor = SimpleNamespace(id=-7, turn_count=3)
        fight = SimpleNamespace(
            turn_id=44,
            native_table_turn=8,
            native_spell_usage={},
            events=[
                dict(kind="npc_cast", actor_id=-7, turn_id=44, spell_id=17),
                dict(kind="npc_cast", actor_id=-7, turn_id=43, spell_id=17),
                dict(kind="npc_cast", actor_id=-8, turn_id=44, spell_id=17),
            ],
        )
        self.assertEqual(
            usage_rows(fight, actor, [dict(id=17, interval=0)]),
            [dict(spellId=17, count=1, remainingCooldown=0)],
        )

    def portal_fixture(self):
        a, b, c = (0, 0, 0), (9, 0, 1), (10, 0, 1)
        gates = {
            uid: dict(
                uid=uid,
                native_type_id=19,
                native_cells_xy=(cell[:2],),
                native_fight_affiliation=1,
                native_fight_affiliation_source="faV.j(PV).bcM",
            )
            for uid, cell in ((11, a), (12, b))
        }
        actor = SimpleNamespace(id=-7, hp=20, mp=2, position=a)
        fight = SimpleNamespace(
            current=actor, native_effect_areas=gates, actors={-7: actor}, edges={(b, c)}
        )
        runtime = SimpleNamespace(fight=fight)
        oracle = SimpleNamespace(
            runtime=runtime, fork=lambda **kwargs: deepcopy(runtime)
        )
        return oracle, {a: 0, b: 1, c: 2}

    def test_registered_native_portals_are_labelled_and_count_one_movement_point(self):
        oracle, indices = self.portal_fixture()
        before = deepcopy(oracle.runtime.fight.native_effect_areas)
        with patch(
            "wakfu_ai.native.native_portal_travel._visible_gates",
            side_effect=lambda owner, private: tuple(
                private.fight.native_effect_areas.values()
            ),
        ):
            rows = portal_edges(oracle, indices, frozenset())
        self.assertEqual(
            rows,
            [
                dict(fromCell=0, toCell=1, entryUid=11, exitUid=12),
                dict(fromCell=1, toCell=0, entryUid=12, exitUid=11),
            ],
        )
        self.assertEqual(oracle.runtime.fight.native_effect_areas, before)
        a, b, c = indices
        reachable, _ = _reachable(
            oracle.runtime.fight, oracle.runtime.fight.current, [(a, b), (b, a)]
        )
        self.assertEqual(reachable[c], 2)
        self.assertNotIn((a, b), oracle.runtime.fight.edges)

    def test_closed_unusable_and_different_network_gates_are_not_advised(self):
        oracle, indices = self.portal_fixture()
        with patch(
            "wakfu_ai.native.native_portal_travel._visible_gates",
            side_effect=lambda owner, private: tuple(
                private.fight.native_effect_areas.values()
            ),
        ):
            self.assertEqual(portal_edges(oracle, indices, frozenset({105})), [])
            oracle.runtime.fight.native_effect_areas[12]["native_fight_affiliation"] = 0
            self.assertEqual(portal_edges(oracle, indices, frozenset()), [])
            del oracle.runtime.fight.native_effect_areas[12]
            self.assertEqual(portal_edges(oracle, indices, frozenset()), [])


class JondoSnapshotLosTests(unittest.TestCase):
    def fixture(self):
        def actor(identity, team, position, hp=20):
            return SimpleNamespace(
                id=identity,
                team=team,
                position=position,
                hp=hp,
                max_hp=20,
                ap=6,
                max_ap=6,
                mp=1 if identity == 1 else 3,
                max_mp=3,
                effect_stats={4: 0, 97: 0},
                effect_maxima={4: 0, 92: 0},
                physical_radius=0,
                effective_level=10,
                direction=0,
                controlled=False,
                native_los_height=identity + 2,
                native_obstacle_id=identity,
                turn_count=1,
                state_ledger=SimpleNamespace(entries=[]),
            )

        active = actor(1, 1, (0, 0, 0))
        enemy = actor(2, 0, (3, 0, 2))
        ally = actor(3, 1, (0, 2, 0))
        dead = actor(4, 0, (2, 2, 0), hp=0)
        hidden = actor(5, 0, (4, 0, 0))
        candidate = (1, 0, 1)
        unused = (7, 7, 3)
        fight = SimpleNamespace(
            id=7,
            current=active,
            actors={a.id: a for a in (active, enemy, ally, dead, hidden)},
            turn_id=1,
            sequence=1,
            native_table_turn=1,
            native_qi_visibility_ignored_slots=[],
            walkable={a.position for a in (active, enemy, ally, dead, hidden)}
            | {candidate, unused},
            edges={(active.position, candidate)},
        )
        runtime = SimpleNamespace(fight=fight, action_id=1)
        oracle = SimpleNamespace(
            runtime=runtime,
            identity="source",
            factory=lambda *args: (
                SimpleNamespace(native_rail_movement_authority=object()),
                SimpleNamespace(
                    actor_authority=SimpleNamespace(
                        properties=lambda f, a: frozenset({5})
                        if a.id == 5
                        else frozenset()
                    )
                ),
            ),
            descriptor=lambda *args: dict(map_id=546, ref=1),
            owned_spells=lambda f: {},
        )
        oracle.state_identity = lambda r: oracle.identity
        return oracle, candidate, unused

    def build(self, oracle, visible):
        from wakfu_ai.bridge.jondo_snapshot import build_snapshot

        with patch(
            "wakfu_ai.bridge.jondo_snapshot.source",
            return_value=dict(nativeIdentity="source", catalogRevision="a" * 64),
        ), patch(
            "wakfu_ai.bridge.jondo_snapshot.effective_affiliation",
            side_effect=lambda fight, actor: actor.team,
        ), patch(
            "wakfu_server.combat_los.authoritative_visible", side_effect=visible
        ), patch(
            "wakfu_server.combat_tackle_movement.movement_tackle_cost",
            return_value=(0, 0),
        ):
            return build_snapshot(oracle)

    def test_reposition_measures_actual_reverse_los_in_relocated_actor_context(self):
        oracle, candidate, unused = self.fixture()
        fight = oracle.runtime.fight
        positions = {
            identity: actor.position for identity, actor in fight.actors.items()
        }
        calls = []

        def visible(
            map_id,
            origin,
            target,
            private,
            *,
            blocking_footprints,
            prepared_geometry=None
        ):
            moved = private.actors[1]
            calls.append((origin, target, moved.position))
            self.assertEqual(map_id, 546)
            self.assertIsNot(private, fight)
            self.assertIsNot(moved, fight.actors[1])
            self.assertEqual(
                set(blocking_footprints[1]),
                set() if origin == moved.position else {moved.position[:2]},
            )
            self.assertEqual(
                private.actors[2].native_los_height, fight.actors[2].native_los_height
            )
            self.assertEqual(private.actors[2].position, positions[2])
            if origin == positions[2]:
                self.assertEqual(target, moved.position)
                return True
            self.assertEqual(origin, moved.position)
            return False

        snapshot = self.build(oracle, visible)
        indices = {
            tuple(cell["xyz"]): cell["id"] for cell in snapshot["board"]["cells"]
        }
        rays = {
            (start, end): value
            for start, end, value in snapshot["board"]["lineOfSight"]
        }
        self.assertFalse(rays[indices[candidate], indices[positions[2]]])
        self.assertTrue(rays[indices[positions[2]], indices[candidate]])
        self.assertTrue(rays[indices[positions[2]], indices[positions[1]]])
        self.assertNotIn((indices[positions[3]], indices[candidate]), rays)
        self.assertFalse(any(unused in (start, end) for start, end, _ in calls))
        self.assertFalse(
            any(
                positions[4] in (start, end) or positions[5] in (start, end)
                for start, end, _ in calls
            )
        )
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(len(rays), len(snapshot["board"]["lineOfSight"]))
        self.assertEqual(
            {identity: actor.position for identity, actor in fight.actors.items()},
            positions,
        )

    def test_missing_reverse_native_evidence_is_omitted_not_false_or_symmetric(self):
        oracle, candidate, _ = self.fixture()
        enemy = oracle.runtime.fight.actors[2].position

        def visible(map_id, origin, target, private, **kwargs):
            if origin == enemy:
                raise ValueError("No native evidence for reverse ray")
            return True

        snapshot = self.build(oracle, visible)
        indices = {
            tuple(cell["xyz"]): cell["id"] for cell in snapshot["board"]["cells"]
        }
        rays = {
            (start, end): value
            for start, end, value in snapshot["board"]["lineOfSight"]
        }
        self.assertTrue(rays[indices[candidate], indices[enemy]])
        self.assertNotIn((indices[enemy], indices[candidate]), rays)

    def test_native_deadline_is_checked_between_forward_and_reverse_queries(self):
        from wakfu_ai.native.native_deadline import bounded

        oracle, _, _ = self.fixture()
        now, calls = [0], []

        def visible(*args, **kwargs):
            calls.append(args)
            now[0] = 2
            return False

        with bounded(1, clock=lambda: now[0]):
            with self.assertRaises(TimeoutError):
                self.build(oracle, visible)
        self.assertEqual(len(calls), 1)

    def test_reverse_queries_preserve_the_native_source_guard(self):
        oracle, _, _ = self.fixture()

        def visible(*args, **kwargs):
            oracle.identity = "changed"
            return True

        with self.assertRaisesRegex(ValueError, "Native source changed"):
            self.build(oracle, visible)


if __name__ == "__main__":
    unittest.main()
