import copy
import cProfile
from datetime import date, datetime, timezone
from decimal import Decimal
import io
import json
import pstats
import struct
import threading
import time
import unittest
import urllib.request

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import snapshot as fight_snapshot
from wakfu_server.combat_tactical_ai import (
    Preview,
    build_request,
    run_turn,
    step,
    validate_response,
)


class FakeNativeProvider:
    """Small deterministic provider for bridge and transaction boundary tests."""

    def __init__(self):
        self.context_key = "fixture-v1"
        self.preview_inputs = []
        self.commit_actions = []

    def roster(self, fight):
        return [
            dict(
                id=a.id,
                team=a.team,
                controlled=a.controlled,
                position=list(a.position),
                hp=a.hp,
                max_hp=a.max_hp,
                ap=a.ap,
                mp=a.mp,
                wp=6,
                armor=0,
            )
            for a in sorted(fight.actors.values(), key=lambda actor: actor.id)
        ]

    def outcome_features(self, fight):
        return {"positionValue": 0}

    def actions(self, fight):
        actor = fight.current
        dest = (actor.position[0] + 1, actor.position[1], actor.position[2])
        if dest in fight.walkable and (actor.position, dest) in fight.edges:
            yield {"type": "move", "path": [list(dest)]}

    def preview(self, fight, action, action_id, *, forecast):
        self.preview_inputs.append((fight, action_id, forecast))
        actor = fight.current
        candidate = copy.deepcopy(fight)
        candidate.server_move(actor.id, [tuple(action["path"][-1])])
        return Preview(candidate, ((9000, struct.pack(">i", action_id)),))

    def commit(self, runtime, action, stats_serializer):
        self.commit_actions.append(copy.deepcopy(action))
        actor = runtime.fight.current
        runtime.fight.server_move(actor.id, [tuple(action["path"][-1])])
        runtime.action_id += 1
        return [(9000, struct.pack(">i", runtime.action_id))]


class TacticalBridgeTests(unittest.TestCase):
    def make_runtime(self, fight_id=4):
        cells = {(x, 0, 0) for x in range(5)}
        edges = {(a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1}
        player = Actor(7, 0, (4, 0, 0), 60, 6, 3, 0, 1, 9, True)
        npc = Actor(-200, 1, (0, 0, 0), 20, 3, 3, 10, 1)
        fight = Fight(
            fight_id,
            [player, npc],
            cells,
            {0: {(4, 0, 0)}, 1: {(0, 0, 0)}},
            edges,
        )
        fight.ready(9)
        self.assertEqual(fight.current.id, -200)
        return RuntimeMessages(fight), FakeNativeProvider()

    @staticmethod
    def response(request, actions=None):
        return {
            "protocol": 2,
            **{
                key: request[key]
                for key in (
                    "requestId",
                    "stateKey",
                    "fightInstanceId",
                    "turnId",
                    "stateRevision",
                    "catalogVersion",
                    "policyVersion",
                )
            },
            "decision": {
                "actor_id": request["actor_id"],
                "actions": actions
                or [request["states"][0]["transitions"][0]["action"]],
            },
            "trace": {},
        }

    def test_forecasts_are_private_and_respect_preview_limit(self):
        runtime, provider = self.make_runtime()
        before = fight_snapshot(runtime.fight)

        request = build_request(runtime, provider, max_previews=1, depth=3)

        self.assertEqual(len(provider.preview_inputs), 1)
        self.assertTrue(provider.preview_inputs[0][2])
        self.assertIsNot(provider.preview_inputs[0][0], runtime.fight)
        self.assertEqual(fight_snapshot(runtime.fight), before)
        self.assertEqual(request["producerTrace"]["previews"], 1)
        self.assertLessEqual(
            sum(len(state["transitions"]) for state in request["states"]), 1
        )

    def test_forecast_deadline_stops_expansion_without_partial_preview(self):
        from unittest.mock import patch

        import wakfu_server.combat_tactical_ai as tactical

        runtime, provider = self.make_runtime()
        ticks = iter((0.0, 2.0))
        with patch.object(
            tactical.time, "monotonic", side_effect=lambda: next(ticks, 2.0)
        ):
            request = build_request(runtime, provider, budget_ms=1)

        self.assertEqual(request["producerTrace"]["previews"], 0)
        self.assertEqual(request["states"][0]["transitions"], [])
        self.assertEqual(provider.preview_inputs, [])

    def test_response_revalidation_rejects_stale_state_context_and_uncertified_action(
        self,
    ):
        runtime, provider = self.make_runtime()
        request = build_request(runtime, provider, max_previews=2)
        valid = self.response(request)

        for field, stale_value in (
            ("requestId", "old-request"),
            ("fightInstanceId", "old-fight"),
            ("turnId", request["turnId"] + 1),
            ("stateRevision", request["stateRevision"] + 1),
            ("catalogVersion", "old-catalog"),
            ("policyVersion", "old-policy"),
        ):
            response = copy.deepcopy(valid)
            response[field] = stale_value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_response(runtime, request, response, provider)

        provider.context_key = "changed-provider-context"
        with self.assertRaisesRegex(ValueError, "Combat changed"):
            validate_response(runtime, request, valid, provider)
        provider.context_key = "fixture-v1"

        forged = self.response(request, [{"type": "cast", "spellId": 1}])
        with self.assertRaisesRegex(ValueError, "certification"):
            validate_response(runtime, request, forged, provider)

        runtime.fight.server_move(-200, [(1, 0, 0)])
        with self.assertRaisesRegex(ValueError, "Combat changed"):
            validate_response(runtime, request, valid, provider)

    def test_build_and_step_refuse_to_cross_pending_turn_ack(self):
        runtime, provider = self.make_runtime()
        runtime.awaiting_ack = 0
        runtime.pending = [(123, b"next turn")]
        with self.assertRaisesRegex(ValueError, "not synchronized"):
            build_request(runtime, provider)
        with self.assertRaisesRegex(ValueError, "not synchronized"):
            step(runtime, provider, lambda *args: b"stats")

    def test_step_commits_one_certified_action_only(self):
        runtime, provider = self.make_runtime()
        calls = []

        def decide(request):
            calls.append(request)
            return self.response(request)

        packets, diagnostic = step(
            runtime, provider, lambda *args: b"stats", transport_call=decide
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(provider.commit_actions, [diagnostic["action"]])
        self.assertEqual(packets[0][0], 9000)
        self.assertEqual(runtime.fight.actors[-200].position, (1, 0, 0))
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(runtime.pending, [])

    def test_two_encounters_keep_distinct_checkpoints_and_private_state(self):
        first, provider = self.make_runtime(fight_id=40)
        second, _ = self.make_runtime(fight_id=41)
        second_before = fight_snapshot(second.fight)

        first_request = build_request(first, provider, max_previews=1, depth=1)
        second_request = build_request(second, provider, max_previews=1, depth=1)
        second_response = self.response(second_request)

        self.assertNotEqual(
            first_request["fightInstanceId"], second_request["fightInstanceId"]
        )
        self.assertNotEqual(first_request["stateKey"], second_request["stateKey"])
        first.fight.server_move(-200, [(1, 0, 0)])
        self.assertEqual(fight_snapshot(second.fight), second_before)
        self.assertEqual(second.fight.actors[-200].position, (0, 0, 0))
        self.assertEqual(
            validate_response(second, second_request, second_response, provider),
            second_request["states"][0]["transitions"][0]["action"],
        )

    def test_large_arena_cells_survive_native_snapshot_and_preview(self):
        from wakfu_server.combat_tactical_ai import state_key

        runtime, provider = self.make_runtime()
        cells = {(x, y, 0) for x in range(132) for y in range(132)}
        cells.update((132, y, 0) for y in range(28))
        runtime.fight.actors[-200].position = (59, 64, 0)
        runtime.fight.actors[7].position = (59, 65, 0)
        runtime.fight.walkable = cells
        runtime.fight.placement = {0: set(cells), 1: set(cells)}
        runtime.fight.edges = {
            ((59, 64, 0), (60, 64, 0)),
            ((60, 64, 0), (59, 64, 0)),
        }
        native_state = state_key(runtime.fight)

        request = build_request(
            runtime, provider, max_previews=1, budget_ms=1000, depth=1
        )

        self.assertEqual(request["terrainScope"], "certified_action_footprint")
        self.assertEqual(request["producerTrace"]["nativeCells"], 17452)
        self.assertEqual(
            request["producerTrace"]["decisionCells"], len(request["walkable"])
        )
        self.assertLess(
            len(request["walkable"]), request["producerTrace"]["nativeCells"]
        )
        self.assertIn([59, 64, 0], request["walkable"])
        self.assertIn([59, 65, 0], request["walkable"])
        self.assertIn([60, 64, 0], request["walkable"])
        self.assertEqual(request["producerTrace"]["previews"], 1)
        self.assertEqual(
            request["states"][0]["transitions"][0]["action"]["type"], "move"
        )
        self.assertEqual(
            request["edges"],
            [
                [[59, 64, 0], [60, 64, 0]],
                [[60, 64, 0], [59, 64, 0]],
            ],
        )
        runtime.fight.walkable.remove((132, 27, 0))
        self.assertNotEqual(state_key(runtime.fight), native_state)

    def test_transport_timeout_ends_turn_without_changing_actor_resources(self):
        runtime, provider = self.make_runtime()
        actor = runtime.fight.current
        before = (
            actor.hp,
            actor.ap,
            actor.mp,
            copy.deepcopy(actor.effect_stats),
            actor.position,
            runtime.action_id,
            runtime.native_action_id,
            copy.deepcopy(runtime.pending),
            len(runtime.fight.events),
        )

        def timeout(request):
            raise TimeoutError("test transport deadline")

        deliveries = run_turn(
            runtime, provider, lambda *args: b"stats", transport_call=timeout
        )
        packets, diagnostic = next(deliveries)

        self.assertEqual(packets, [])
        self.assertIn("TimeoutError", diagnostic["reason"])
        self.assertEqual((actor.hp, actor.ap, actor.mp), before[:3])
        self.assertEqual(actor.effect_stats, before[3])
        self.assertEqual(actor.position, before[4])
        self.assertEqual((runtime.action_id, runtime.native_action_id), before[5:7])
        self.assertEqual(runtime.pending, before[7])
        self.assertIsNone(runtime.awaiting_ack)
        end_packets, end_diagnostic = next(deliveries)
        self.assertTrue(end_packets)
        self.assertEqual(end_diagnostic["action"], {"type": "end_turn"})
        self.assertIsNotNone(runtime.awaiting_ack)
        self.assertEqual((actor.hp, actor.ap, actor.mp), before[:3])
        self.assertEqual(actor.effect_stats, before[3])
        self.assertEqual(actor.position, before[4])
        # The turn barrier is allowed to publish lifecycle packets; the timeout
        # yielded no action delivery and left the NPC's combat values intact.

    def test_turn_generator_redecides_after_each_delivery_then_uses_native_ack(self):
        runtime, provider = self.make_runtime()
        calls = []

        def decide(request):
            calls.append(request)
            return self.response(request)

        deliveries = run_turn(
            runtime,
            provider,
            lambda *args: b"stats",
            transport_call=decide,
            max_actions=2,
        )
        first_packets, _ = next(deliveries)
        self.assertEqual(first_packets[0][0], 9000)
        self.assertIsNone(runtime.awaiting_ack)
        second_packets, _ = next(deliveries)
        self.assertEqual(second_packets[0][0], 9000)
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0]["stateKey"], calls[1]["stateKey"])
        self.assertIsNone(runtime.awaiting_ack)

        end_packets, diagnostic = next(deliveries)
        self.assertEqual(diagnostic["action"], {"type": "end_turn"})
        self.assertEqual(runtime.awaiting_ack, 1)
        self.assertTrue(end_packets)
        with self.assertRaisesRegex(ValueError, "Invalid or stale"):
            runtime.acknowledge_turn(struct.pack(">i", 0))
        self.assertEqual(runtime.awaiting_ack, 1)
        runtime.acknowledge_turn(struct.pack(">i", 1))
        self.assertIsNone(runtime.awaiting_ack)

    def test_no_supported_candidate_preserves_producer_diagnostics_at_turn_barrier(
        self,
    ):
        runtime, provider = self.make_runtime()
        provider.actions = lambda fight: iter(())
        calls = []

        def decide(request):
            calls.append(request)
            return self.response(request, [{"type": "end_turn"}])

        deliveries = run_turn(
            runtime, provider, lambda *args: b"stats", transport_call=decide
        )
        packets, diagnostic = next(deliveries)

        self.assertTrue(packets)
        self.assertEqual(len(calls), 1)
        self.assertEqual(diagnostic["action"], {"type": "end_turn"})
        self.assertEqual(diagnostic["producer"]["previews"], 0)
        self.assertIn("requestId", diagnostic)
        self.assertIn("fightInstanceId", diagnostic)
        self.assertIn("sourceRevision", diagnostic)
        self.assertIn("policyVersion", diagnostic)
        self.assertIsNotNone(runtime.awaiting_ack)

    def test_native_provider_context_key_canonicalizes_database_value_types(self):
        from wakfu_server.combat_tactical_ai import NativeProvider

        character = {
            "id": 7,
            "created_at": datetime(2024, 5, 6, 7, 8, tzinfo=timezone.utc),
            "birth_date": date(1992, 3, 4),
            "native_blob": memoryview(b"\x00\xff"),
            "weight": Decimal("1.2500"),
            "flags": {"ready", "native"},
        }
        monster = {
            -200: {
                "id": -200,
                "ref": 1,
                "updated_at": date(2025, 1, 2),
                "binary": bytearray(b"npc"),
            }
        }
        provider = NativeProvider(character, monster, b"deck")
        duplicate = NativeProvider(
            {
                "flags": {"native", "ready"},
                "weight": Decimal("1.2500"),
                "native_blob": b"\x00\xff",
                "birth_date": date(1992, 3, 4),
                "created_at": datetime(2024, 5, 6, 7, 8, tzinfo=timezone.utc),
                "id": 7,
            },
            {
                -200: {
                    "binary": b"npc",
                    "updated_at": date(2025, 1, 2),
                    "ref": 1,
                    "id": -200,
                }
            },
            b"deck",
        )

        self.assertEqual(provider.context_key, duplicate.context_key)
        changed = NativeProvider(
            dict(character, native_blob=b"changed"), monster, b"deck"
        )
        self.assertNotEqual(provider.context_key, changed.context_key)

    def test_native_provider_context_key_includes_all_player_decks(self):
        from wakfu_server.combat_tactical_ai import NativeProvider

        base = NativeProvider(
            {"id": 7},
            {},
            b"main",
            player_characters={7: {"id": 7}, 8: {"id": 8}},
            deck_blobs={7: b"main", 8: b"ally"},
        )
        changed = NativeProvider(
            {"id": 7},
            {},
            b"main",
            player_characters={7: {"id": 7}, 8: {"id": 8}},
            deck_blobs={7: b"main", 8: b"changed"},
        )
        self.assertNotEqual(base.context_key, changed.context_key)


class NativeTacticalPreviewTests(unittest.TestCase):
    class _MovementAuthority:
        """Explicit ordinary actor facts for synthetic AI movement previews."""

        def __call__(self, fight, actor):
            from wakfu_server.combat_runtime_adapter import NativeActorAuthority

            if fight.actors.get(actor.id) is not actor:
                raise ValueError("Movement fixture actor is not in the current fight")
            return NativeActorAuthority(
                targeting=dict(
                    baF=True,
                    baG=False,
                    baK=False,
                    dpu_id=actor.id,
                ),
                is_player=actor.controlled,
                deck_spell_ids=frozenset(),
                excluded_deck_spell_ids=frozenset(),
                is_carried=False,
                breed_id=15 if actor.controlled else 0,
                summon_count=0,
                summon_counts_by_breed={},
                occupant_blocks=True,
            )

        def properties(self, fight, actor):
            return frozenset()

    @classmethod
    def setUpClass(cls):
        # The native compiled catalog is process cached and costly to build.
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_server_spell import prewarm_runtime_catalogs
        from tests.test_ai_service import service

        npc_runtime_catalog()
        prewarm_runtime_catalogs()
        cls.http = service.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        cls.http_thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.http_thread.start()
        cls.ai_url = "http://127.0.0.1:" + str(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.http_thread.join(2)

    def test_real_native_los_known_map_1134_adjacent_edge(self):
        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_los import authoritative_visible

        fixture = NativeNpcAttackTests()
        fixture.setUp()
        source, target = (-23, -143, 70), (-22, -143, 70)
        fixture.fight.walkable = {source, target}
        fixture.fight.actors[fixture.npc.id].position = source
        fixture.fight.actors[fixture.pc.id].position = target

        self.assertTrue(
            authoritative_visible(
                1134,
                source,
                target,
                fixture.fight,
                blocking_footprints={
                    fixture.npc.id: {source[:2]},
                    fixture.pc.id: {target[:2]},
                },
            )
        )

    def test_jalato_native_spell_rejection_keeps_certified_movement_candidate(self):
        from unittest.mock import patch

        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_npc_spell import owned_spells
        from wakfu_server.combat_tactical_ai import NativeProvider, build_request
        from wakfu_server.spells import default_deck

        fixture = NativeNpcAttackTests()
        fixture.setUp()
        fixture.monster.update(ref=1, level=8)
        fixture.npc.effective_level = 8
        fixture.fight.walkable = {(x, 0, 0) for x in range(7)}
        from wakfu_server.combat_qi_fight import move_registered_actor

        move_registered_actor(fixture.fight, fixture.npc, (0, 0, 0))
        move_registered_actor(fixture.fight, fixture.pc, (6, 0, 0))
        fixture.fight.placement = {
            0: set(fixture.fight.walkable),
            1: set(fixture.fight.walkable),
        }
        fixture.fight.edges = {
            (a, b)
            for a in fixture.fight.walkable
            for b in fixture.fight.walkable
            if abs(a[0] - b[0]) == 1
        }
        fixture.fight.native_rail_movement_authority = self._MovementAuthority()
        runtime = RuntimeMessages(fixture.fight)
        provider = NativeProvider(
            fixture.character,
            {fixture.npc.id: fixture.monster},
            default_deck(fixture.character),
        )
        before = fight_snapshot(runtime.fight, runtime=runtime)

        self.assertEqual(owned_spells(runtime.fight, provider.monsters), {5767: 8})
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            request = build_request(
                runtime, provider, max_previews=2, budget_ms=5000, depth=1
            )

        root = next(
            state for state in request["states"] if state["key"] == request["rootState"]
        )
        actions = [transition["action"] for transition in root["transitions"]]
        self.assertTrue(any(action["type"] == "move" for action in actions))
        self.assertFalse(any(action["type"] == "cast" for action in actions))
        self.assertGreater(request["producerTrace"]["rejected"], 0)
        self.assertTrue(
            any(
                reason.startswith("Unsupported native NPC effect roots:")
                for reason in request["producerTrace"]["rejectedReasons"]
            ),
            request["producerTrace"]["rejectedReasons"],
        )
        from tests.test_ai_service import planner

        result = planner.decide(request)
        first_action = result["decision"]["actions"][0]
        self.assertEqual(first_action["type"], "move")
        self.assertLess(abs(first_action["path"][-1][0] - 6), 6)
        self.assertEqual(fight_snapshot(runtime.fight, runtime=runtime), before)

    def test_wonejo_forecast_uses_native_los_and_commit_failure_rolls_back(self):
        from unittest.mock import patch

        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_tactical_ai import NativeProvider
        from wakfu_server.spells import default_deck

        fixture = NativeNpcAttackTests()
        fixture.setUp()
        fixture.fight.edges = {
            ((0, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (0, 0, 0)),
        }
        provider = NativeProvider(
            fixture.character,
            {fixture.npc.id: fixture.monster},
            default_deck(fixture.character),
        )
        runtime = RuntimeMessages(fixture.fight)
        action = {
            "type": "cast",
            "spellId": 7962,
            "level": 1,
            "targetId": fixture.pc.id,
            "target": list(fixture.pc.position),
        }
        original_fight = runtime.fight
        original_npc = runtime.fight.actors[fixture.npc.id]
        original_player = runtime.fight.actors[fixture.pc.id]
        before = fight_snapshot(runtime.fight)

        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            forecast = provider.preview(
                runtime.fight, action, runtime.action_id + 1, forecast=True
            )
            self.assertEqual(forecast.fight.actors[fixture.pc.id].hp, 55)
            self.assertEqual(runtime.fight.actors[fixture.pc.id].hp, 60)
            self.assertNotEqual(
                forecast.fight.native_spell_usage, runtime.fight.native_spell_usage
            )
            self.assertEqual(fight_snapshot(runtime.fight), before)

            def broken_serializer(actor, fight):
                raise ValueError("injected serializer failure")

            with self.assertRaisesRegex(ValueError, "serializer failure"):
                provider.commit(runtime, action, broken_serializer)

        self.assertIs(runtime.fight, original_fight)
        self.assertIs(runtime.fight.actors[fixture.npc.id], original_npc)
        self.assertIs(runtime.fight.actors[fixture.pc.id], original_player)
        self.assertEqual(fight_snapshot(runtime.fight), before)
        self.assertEqual((runtime.action_id, runtime.native_action_id), (0, 0))
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(runtime.pending, [])

    def test_native_wonejo_decides_over_http_executes_once_then_ends_by_usage_limit(
        self,
    ):
        from unittest.mock import patch

        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_tactical_ai import NativeProvider, step
        from wakfu_server.spells import default_deck
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        fixture = NativeNpcAttackTests()
        fixture.setUp()
        fixture.fight.edges = {
            ((0, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (0, 0, 0)),
        }
        runtime = RuntimeMessages(fixture.fight)
        provider = NativeProvider(
            fixture.character,
            {fixture.npc.id: fixture.monster},
            default_deck(fixture.character),
            forecast_limits={"budget_ms": 5000, "depth": 1, "max_previews": 16},
        )
        responses = []

        def post_to_local_ai(request):
            call = urllib.request.Request(
                self.ai_url + "/v2/decide",
                data=json.dumps(request, allow_nan=False).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(call, timeout=5) as reply:
                response = json.load(reply)
            responses.append((request, response))
            return response

        def actual_stats(actor, fight):
            wp_current = actor.effect_stats[4]
            wp_maximum = actor.effect_maxima[4]
            if actor.controlled:
                return actual_actor_stats(
                    fixture.character,
                    actor,
                    fight.id,
                    wp_current=wp_current,
                    wp_maximum=wp_maximum,
                )
            return actual_monster_actor_stats(
                fixture.monster,
                actor,
                fight.id,
                wp_current=wp_current,
                wp_maximum=wp_maximum,
                direction=3,
            )

        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            packets, diagnostic = step(
                runtime,
                provider,
                actual_stats,
                transport_call=post_to_local_ai,
            )
            self.assertEqual(diagnostic["action"]["type"], "cast")
            self.assertEqual(diagnostic["action"]["spellId"], 7962)
            self.assertEqual(runtime.fight.actors[fixture.pc.id].hp, 55)
            self.assertTrue(any(opcode == 12678 for opcode, _ in packets))
            self.assertEqual(runtime.action_id, 1)
            self.assertGreater(runtime.native_action_id, 0)
            usage = runtime.fight.native_spell_usage[str(fixture.npc.id)]
            self.assertEqual(usage["casts"]["7962"], 1)
            self.assertEqual(usage["targets"]["7962"][str(fixture.pc.id)], 1)

            packets, diagnostic = step(
                runtime,
                provider,
                actual_stats,
                transport_call=post_to_local_ai,
            )

        self.assertEqual(diagnostic["action"], {"type": "end_turn"})
        self.assertEqual(packets, [])
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0][1]["decision"]["actions"][0]["spellId"], 7962)
        self.assertEqual(
            responses[1][1]["decision"]["actions"][0], {"type": "end_turn"}
        )
        self.assertEqual(runtime.fight.actors[fixture.pc.id].hp, 55)
        self.assertEqual(runtime.action_id, 1)

    def test_wonejo_forecast_replay_matches_fresh_execution_effects(self):
        """A deterministic forecast replays, while only fresh commit spends live use."""
        from unittest.mock import patch

        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_tactical_ai import NativeProvider
        from wakfu_server.spells import default_deck

        fixture = NativeNpcAttackTests()
        fixture.setUp()
        fixture.fight.edges = {
            ((0, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (0, 0, 0)),
        }
        runtime = RuntimeMessages(fixture.fight)
        provider = NativeProvider(
            fixture.character,
            {fixture.npc.id: fixture.monster},
            default_deck(fixture.character),
        )
        action = {
            "type": "cast",
            "spellId": 7962,
            "level": 1,
            "targetId": fixture.pc.id,
            "target": list(fixture.pc.position),
        }
        live_fight, live_npc, live_pc = (
            runtime.fight,
            runtime.fight.actors[fixture.npc.id],
            runtime.fight.actors[fixture.pc.id],
        )
        source_snapshot = fight_snapshot(runtime.fight, runtime=runtime)
        source_usage = copy.deepcopy(runtime.fight.native_spell_usage)

        def effects(fight):
            return (
                fight.actors[fixture.pc.id].hp,
                fight.actors[fixture.pc.id].effect_stats.get(97),
                fight.actors[fixture.npc.id].hp,
                fight.actors[fixture.npc.id].ap,
                fight.actors[fixture.npc.id].mp,
                fight.actors[fixture.npc.id].effect_stats.get(4),
                copy.deepcopy(fight.native_spell_usage),
            )

        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            first = provider.preview(
                runtime.fight, action, runtime.action_id + 1, forecast=True
            )
            replay = provider.preview(
                runtime.fight, action, runtime.action_id + 1, forecast=True
            )
            self.assertIsNot(first.fight, runtime.fight)
            self.assertEqual(effects(first.fight), effects(replay.fight))
            self.assertEqual(effects(first.fight)[0], 55)
            self.assertEqual(runtime.fight.native_spell_usage, source_usage)
            self.assertEqual(
                fight_snapshot(runtime.fight, runtime=runtime), source_snapshot
            )
            self.assertIs(runtime.fight, live_fight)
            self.assertIs(runtime.fight.actors[fixture.npc.id], live_npc)
            self.assertIs(runtime.fight.actors[fixture.pc.id], live_pc)
            self.assertEqual(runtime.pending, [])

            def serializer(actor, fight):
                return b"valid-fixture-stats"

            packets = provider.commit(runtime, action, serializer)

        self.assertTrue(packets)
        self.assertEqual(runtime.fight.actors[fixture.pc.id].hp, 55)
        usage = runtime.fight.native_spell_usage[str(fixture.npc.id)]
        self.assertEqual(usage["casts"]["7962"], 1)
        self.assertEqual(usage["targets"]["7962"][str(fixture.pc.id)], 1)
        # Commit adopts authoritative values while preserving public Fight and
        # Actor identities held by the server's protocol/runtime callers.
        self.assertIs(runtime.fight, live_fight)
        self.assertIs(runtime.fight.actors[fixture.npc.id], live_npc)
        self.assertIs(runtime.fight.actors[fixture.pc.id], live_pc)
        self.assertEqual(live_pc.hp, 55)
        self.assertEqual(live_npc.hp, 20)

    def test_native_encounter_state_isolation_after_first_wonejo_commit(self):
        from unittest.mock import patch

        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_tactical_ai import NativeProvider, build_request
        from wakfu_server.spells import default_deck

        fixtures = [NativeNpcAttackTests(), NativeNpcAttackTests()]
        for fixture in fixtures:
            fixture.setUp()
            fixture.fight.edges = {
                ((0, 0, 0), (1, 0, 0)),
                ((1, 0, 0), (0, 0, 0)),
            }
        fixtures[1].fight.id = 2
        runtimes = [RuntimeMessages(f.fight) for f in fixtures]
        providers = [
            NativeProvider(
                f.character, {f.npc.id: f.monster}, default_deck(f.character)
            )
            for f in fixtures
        ]
        second_before = fight_snapshot(runtimes[1].fight, runtime=runtimes[1])
        second_usage = copy.deepcopy(runtimes[1].fight.native_spell_usage)
        first_request = build_request(
            runtimes[0], providers[0], max_previews=1, depth=1, budget_ms=5000
        )
        second_request = build_request(
            runtimes[1], providers[1], max_previews=1, depth=1, budget_ms=5000
        )
        self.assertNotEqual(
            first_request["fightInstanceId"], second_request["fightInstanceId"]
        )
        # Identical starting positions can have an identical content key;
        # encounter identity remains independently scoped by fightInstanceId.

        def serializer(actor, fight):
            return b"valid-fixture-stats"

        action = {
            "type": "cast",
            "spellId": 7962,
            "level": 1,
            "targetId": fixtures[0].pc.id,
            "target": list(fixtures[0].pc.position),
        }
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            providers[0].commit(runtimes[0], action, serializer)
        self.assertEqual(runtimes[1].fight.actors[fixtures[1].pc.id].hp, 60)
        self.assertEqual(runtimes[1].fight.native_spell_usage, second_usage)
        self.assertEqual(
            fight_snapshot(runtimes[1].fight, runtime=runtimes[1]), second_before
        )

    def test_native_build_request_warm_cost_on_small_position_corpus(self):
        """Record warm native forecast cost for multiple legal placements."""
        from unittest.mock import patch

        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_tactical_ai import NativeProvider, build_request
        from wakfu_server.spells import default_deck

        samples = []
        for label, npc_x in (("adjacent", 5), ("approach_then_cast", 0)):
            fixture = NativeNpcAttackTests()
            fixture.setUp()
            fixture.fight.walkable = {(x, 0, 0) for x in range(7)}
            fixture.fight.edges = {
                (a, b)
                for a in fixture.fight.walkable
                for b in fixture.fight.walkable
                if abs(a[0] - b[0]) == 1
            }
            from wakfu_server.combat_qi_fight import move_registered_actor

            player_x = 4 if label == "approach_then_cast" else 6
            move_registered_actor(fixture.fight, fixture.pc, (player_x, 0, 0))
            move_registered_actor(fixture.fight, fixture.npc, (npc_x, 0, 0))
            fixture.fight.placements = {
                0: set(fixture.fight.walkable),
                1: set(fixture.fight.walkable),
            }
            fixture.fight.native_rail_movement_authority = self._MovementAuthority()
            runtime = RuntimeMessages(fixture.fight)
            provider = NativeProvider(
                fixture.character,
                {fixture.npc.id: fixture.monster},
                default_deck(fixture.character),
            )
            # Warm the native metadata lookup and derived feature path before
            # timing build_request's default 150 ms forecast budget.
            provider.capabilities(runtime.fight)
            provider.outcome_features(runtime.fight)
            warm_fight = copy.deepcopy(runtime.fight)
            from wakfu_server.combat_qi_fight import move_registered_actor

            move_registered_actor(
                warm_fight, warm_fight.actors[fixture.npc.id], (5, 0, 0)
            )
            move_registered_actor(
                warm_fight, warm_fight.actors[fixture.pc.id], (6, 0, 0)
            )
            warm_action = next(
                action
                for action in provider.actions(warm_fight)
                if action["type"] == "cast"
            )
            with patch(
                "wakfu_server.combat_los.authoritative_visible", return_value=True
            ):
                provider.preview(
                    warm_fight, warm_action, runtime.action_id + 1, forecast=True
                )
            before = fight_snapshot(runtime.fight, runtime=runtime)
            start = time.perf_counter()
            with patch(
                "wakfu_server.combat_los.authoritative_visible", return_value=True
            ):
                request = build_request(runtime, provider)
            elapsed = time.perf_counter() - start
            samples.append((label, elapsed, request, runtime, provider))
            self.assertEqual(fight_snapshot(runtime.fight, runtime=runtime), before)

        report = []
        for label, elapsed, request, _, _ in samples:
            transitions = [
                t for state in request["states"] for t in state["transitions"]
            ]
            casts = sum(t["action"]["type"] == "cast" for t in transitions)
            dto_bytes = len(json.dumps(request, allow_nan=False).encode())
            report.append(
                f"{label}: wall={elapsed:.4f}s, producer={request['producerTrace']['elapsedMs']:.3f}ms, "
                f"previews={request['producerTrace']['previews']}, "
                f"transitions={len(transitions)}, casts={casts}, "
                f"nativeCells={request['producerTrace']['nativeCells']}, "
                f"decisionCells={request['producerTrace']['decisionCells']}, dto={dto_bytes}B"
            )
        self.warm_build_request_report = report
        print(
            "warm native build_request defaults (48/150ms/depth2):", "; ".join(report)
        )
        self.assertEqual(len(samples), 2)
        self.assertTrue(all(elapsed >= 0 for _, elapsed, _, _, _ in samples))
        adjacent_transitions = [
            t for state in samples[0][2]["states"] for t in state["transitions"]
        ]
        self.assertTrue(
            any(t["action"]["type"] == "cast" for t in adjacent_transitions)
        )
        remote_transitions = [
            t for state in samples[1][2]["states"] for t in state["transitions"]
        ]
        self.assertTrue(any(t["action"]["type"] == "move" for t in remote_transitions))
        state_by_key = {state["key"]: state for state in samples[1][2]["states"]}
        root = state_by_key[samples[1][2]["rootState"]]
        self.assertTrue(
            any(
                transition["action"]["type"] == "move"
                and any(
                    child["action"]["type"] == "cast"
                    for child in state_by_key[transition["nextState"]]["transitions"]
                )
                for transition in root["transitions"]
            ),
            "the distant corpus placement should model a move followed by a cast",
        )

        # Capture cumulative hotspots on a third warm run, distinct from the
        # unprofiled wall-clock measurements recorded above.
        profiler = cProfile.Profile()
        profile_runtime, profile_provider = samples[1][3], samples[1][4]
        profile_start = time.perf_counter()
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            profiled_request = profiler.runcall(
                build_request, profile_runtime, profile_provider
            )
        profile_wall_seconds = time.perf_counter() - profile_start
        stats = pstats.Stats(profiler).sort_stats("cumulative")
        profile_rows = []
        for function in stats.fcn_list[:10]:
            (
                primitive_calls,
                total_calls,
                own_seconds,
                cumulative_seconds,
                _,
            ) = stats.stats[function]
            filename, line, name = function
            profile_rows.append(
                dict(
                    function=f"{filename}:{line}({name})",
                    calls=total_calls,
                    ownSeconds=round(own_seconds, 6),
                    cumulativeSeconds=round(cumulative_seconds, 6),
                )
            )
        self.native_profile_rows = profile_rows
        self.native_profile_report = dict(
            profiledWallSeconds=round(profile_wall_seconds, 6),
            elapsedMs=profiled_request["producerTrace"]["elapsedMs"],
            previews=profiled_request["producerTrace"]["previews"],
            topCumulative=profile_rows,
        )
        print(
            "cProfile warm approach build_request top cumulative:",
            json.dumps(self.native_profile_report),
        )


if __name__ == "__main__":
    unittest.main()
