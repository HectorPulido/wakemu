"""Regression coverage for paid movement steps and native area callbacks."""
import copy
from pathlib import Path
import sys
import unittest

from wakfu_server.combat_state import Actor, Fight


class SequentialAreaMovementTests(unittest.TestCase):
    @staticmethod
    def _native_wonejo_runtime(*, native_area_callbacks=True):
        ai_root = str(Path(__file__).resolve().parents[1] / "ai-service")
        ai_tests = str(Path(ai_root) / "tests")
        for path in (ai_root, ai_tests):
            if path not in sys.path:
                sys.path.insert(0, path)
        from test_native_oracle import NativeOracleTests
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.spells import default_deck

        fixture = NativeOracleTests.wonejo_fixture()
        runtime = RuntimeMessages(fixture.fight)
        deck = default_deck(fixture.character)
        oracle = NativeOracleTests.oracle_for(
            runtime,
            fixture.character,
            fixture.monster,
            deck,
            flags={"native_area_callbacks": native_area_callbacks},
        )
        return NativeOracleTests, fixture, runtime, oracle, deck

    @staticmethod
    def _search_decision(oracle, runtime, deck):
        from test_native_session import StubTransport
        from wakfu_ai.bridge.world_bridge import NativeSession
        from wakfu_ai.planning.query_search import search

        transport = StubTransport()
        session = NativeSession(
            oracle,
            transport,
            None,
            policy=dict(limits=dict(depth=2, beam=8, nodes=40, budgetMs=10000)),
            policy_version="sequential-movement-regression",
            fight_instance_id="sequential-movement-regression",
        )
        envelope = session.envelope()
        envelope["operations"] = [
            operation
            for operation in envelope["operations"]
            if operation != "project_turn"
        ]
        store = type("Store", (), {"json": lambda _, key: transport.graphs[key]})()
        coroutine = search(envelope, store)
        request = next(coroutine)
        while True:
            try:
                request = coroutine.send(session.query(request))
            except StopIteration as completed:
                return session, completed.value

    def test_ref46_mp_loss_interrupts_after_the_paid_entry_step(self):
        """The actual ref46 entry effect can consume MP before the next step."""
        from dataclasses import replace
        from types import SimpleNamespace

        from test_combat_effect_runtime import NativeRuntimeFactoryTests
        from wakfu_server.combat_battleground_border import (
            POLICY,
            install_battleground_border,
        )
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
        from wakfu_server.combat_effect_area_catalog import area_effect_catalog
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
        from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_summon import RegisteredSummonAuthority
        from wakfu_server.spell_audit import states_catalog

        fixture = NativeRuntimeFactoryTests()
        NativeRuntimeFactoryTests.setUpClass()
        fixture.setUp()
        fight = fixture.fight
        actor = fight.actors[7]
        fight.actors = {actor.id: actor}
        fight.order = [actor.id]
        fight.turn_index = 0
        fight.walkable = {(0, 0, 0), (1, 0, 0), (2, 0, 0)}
        actor.mp = 2
        actor.effect_stats[3] = 2
        actor.max_mp = 6
        actor.effect_maxima[3] = 6
        actor.effect_stats[86] = 0
        actor.effect_minima[86] = 0
        actor.effect_maxima[86] = 1000
        actor.effect_stats[8] = 100
        from test_combat_tackle_movement import Authority as MovementAuthority

        fight.native_rail_movement_authority = MovementAuthority()
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=3, height=1, cell_masks=[0, 128, 0]
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        install_battleground_border(
            fight,
            dict(
                native_border_policy=POLICY,
                native_border_cells={(1, 0, 0)},
                min_z=0,
            ),
            reference=46,
            identity=-100,
        )

        states = states_catalog()
        timing = NativeEffectTimingProvider(states)

        def condition(preview, plan, effect, invocation):
            retained = native_retained_condition_effects(preview, invocation.target_id)
            target = preview.actors[invocation.target_id]
            return ConditionContext(
                {
                    "caster": ConditionActor(actor_id=-100, is_native_fighter=False),
                    "target": ConditionActor(
                        actor_id=target.id,
                        characteristics={"WILLPOWER": target.effect_stats[86]},
                        retained_effect_ids=frozenset(row[0] for row in retained),
                    ),
                }
            )

        actor_authority = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=15, level=1)},
            monsters={},
            decks={7: []},
            excluded_decks={7: []},
        )
        adapter = SimpleNamespace(actor_authority=actor_authority)

        def healing_events(preview, plan, replay, retention):
            return OrdinaryHealingEvents(
                adapter=adapter,
                preview=preview,
                plan=plan,
                replay=replay,
                retention=retention,
            )

        contexts = replace(
            fixture.contexts,
            condition=condition,
            stat=timing.stat,
            healing_events=healing_events,
        )

        class TestSummonAuthority(RegisteredSummonAuthority):
            def __init__(self):
                super().__init__(object())

            def properties(self, preview, target):
                return frozenset()

        factory = NativeEffectRuntimeFactory(
            effects=dict(area_effect_catalog()["effects"]),
            state_catalog=states,
            characteristic_registry=characteristic_registry(),
            action_id=1,
            contexts=contexts,
            summon_authority=TestSummonAuthority(),
        )
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        area_events = dispatcher.native_area_events
        observed = []

        def deliver_step(staged_fight, moving_actor, before, cell):
            observed.append((before, cell, moving_actor.mp))
            with staged_fight.effect_resolution():
                area_events.movement(moving_actor.id, from_cell=before, to_cell=cell)

        event = fight.move(
            3, actor.id, [(1, 0, 0), (2, 0, 0)], step_callback=deliver_step
        )

        self.assertEqual(observed, [((0, 0, 0), (1, 0, 0), 1)])
        self.assertEqual(event["path"], [(1, 0, 0)])
        self.assertEqual(event["cost"], 1)
        self.assertEqual(
            (actor.position, actor.mp, actor.effect_stats[3]), ((1, 0, 0), 0, 0)
        )
        retained = native_retained_condition_effects(fight, actor.id)
        self.assertIn(152028, {row[0] for row in retained})

    def test_native_npc_crossing_two_ref48_cells_applies_loss_once(self):
        """The real NPC oracle replays entry and repeat callbacks per cell."""
        from collections import deque
        from pathlib import Path
        import sys

        ai_root = str(Path(__file__).resolve().parents[1] / "ai-service")
        ai_tests = str(Path(ai_root) / "tests")
        for import_path in (ai_root, ai_tests):
            if import_path not in sys.path:
                sys.path.insert(0, import_path)

        from test_native_oracle import NativeOracleTests
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_effect_area_catalog import area_effect_catalog

        fixture = NativeOracleTests.wonejo_fixture(
            compact=True,
            terrain_effect_id=48,
            map_id=312,
            player_position=(10, -4, 0),
            monster_position=(10, -5, 0),
            monster_ref=2616,
            monster_level=4,
        )
        fight, actor = fixture.fight, fixture.npc
        area_definition = native_effect_areas()["48"]
        self.assertEqual(area_definition["entry_masks"], [10001, 10008, 10000])
        self.assertEqual(area_definition["effect_ids"], [177618])
        native_effects = area_effect_catalog()["effects"]
        self.assertEqual(native_effects["177618"]["children"], [177619, 177620])
        self.assertEqual(
            native_effects["177618"]["criteria"],
            'not HasEffectWithSpecificId("target", 177620)',
        )
        self.assertEqual(native_effects["177619"]["effect_class"], 55)
        self.assertEqual(native_effects["177619"]["parameters"][0], 4.0)
        border_cells = fight.native_border_constructor["arena"]["native_border_cells"]
        self.assertTrue(border_cells)
        border = {tuple(cell) for cell in border_cells}

        # Find one paid route that enters two adjacent border cells. Keep the
        # test tied to this encounter's selected terrain and directed edges.
        occupied = {
            other.position
            for other in fight.actors.values()
            if other.id != actor.id and other.hp > 0
        }
        pending = deque([(actor.position, ())])
        visited = {actor.position}
        path = None
        while pending:
            cell, route = pending.popleft()
            if len(route) >= 2 and route[-1] in border and route[-2] in border:
                path = route
                break
            if len(route) >= actor.mp:
                continue
            for _, destination in sorted(
                edge for edge in fight.edges if edge[0] == cell
            ):
                if destination in occupied or destination in visited:
                    continue
                visited.add(destination)
                pending.append((destination, route + (destination,)))
        self.assertIsNotNone(path, "no two-cell border route fits the NPC MP")
        before_border_pair = actor.position if len(path) == 2 else path[-3]
        self.assertNotIn(before_border_pair, border)

        # Make this NPC the active server-controlled actor so the exercised
        # path is NativeOracle.preview's production AI movement branch.
        fight.order = [actor.id, fixture.pc.id]
        fight.turn_index = 0
        runtime = RuntimeMessages(fight)
        deck = __import__(
            "wakfu_server.spells", fromlist=["default_deck"]
        ).default_deck(fixture.character)
        oracle = NativeOracleTests.oracle_for(
            runtime,
            fixture.character,
            fixture.monster,
            deck,
            flags={"native_area_callbacks": True, "native_start_events": False},
        )
        private, _, _ = oracle.preview(
            runtime,
            {"type": "move", "path": [list(cell) for cell in path]},
            forecast=False,
        )

        moved = private.fight.actors[actor.id]
        self.assertEqual(moved.position, path[-1])
        # Native ref48 requests four AP; eVZ applies half before the target's
        # live willpower modifier and stochastic rounding. The area has no
        # fighter caster, so its caster willpower is zero.
        from wakfu_server.combat_parameters import _float32

        target_willpower = actor.effect_stats[86]
        expected_raw_loss = _float32(
            _float32(4 * 0.5) * _float32(1 - _float32(target_willpower / 100))
        )
        self.assertEqual(actor.ap, 6)
        self.assertEqual(target_willpower, 0)
        self.assertEqual(expected_raw_loss, 2.0)
        actual_loss = actor.ap - moved.ap
        self.assertGreater(actual_loss, 0)
        self.assertEqual((actor.ap, moved.ap, actual_loss), (6, 4, 2))
        border_area = next(
            row
            for row in private.fight.native_effect_areas.values()
            if row.get("reference") == 48
        )
        border_footprint = {tuple(cell) for cell in border_area["native_cells_xy"]}
        self.assertTrue(all(tuple(cell[:2]) in border_footprint for cell in path[-2:]))
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )

        retained = native_retained_condition_effects(private.fight, actor.id)
        retained_ids = [row[0] for row in retained]
        self.assertEqual(retained_ids.count(177620), 1)
        self.assertEqual(border_area["remaining_activations"], -1)

        # Separately exercise an actor already standing on the glyph when its
        # native turn-start callback is delivered. The installed mask includes
        # 10000, and this fresh clone has no retained once-marker from movement.
        from wakfu_server.combat_qi_fight import move_registered_actor

        standing = copy.deepcopy(fight)
        standing_actor = standing.actors[actor.id]
        move_registered_actor(standing, standing_actor, path[-1])
        standing.order = [actor.id, fixture.pc.id]
        standing.turn_index = 0
        started, _ = oracle.start_boundary(
            standing,
            actor_id=actor.id,
            action_id=runtime.action_id + 1,
            forecast=True,
        )
        started_actor = started.actors[actor.id]
        self.assertEqual((standing_actor.ap, started_actor.ap), (6, 4))
        started_markers = native_retained_condition_effects(started, actor.id)
        self.assertEqual([row[0] for row in started_markers].count(177620), 1)

    def test_callback_keeps_ordinary_route_cost_and_path(self):
        actor = Actor(7, 0, (0, 0, 0), 100, 6, 4, 20, 60, 3, True)
        enemy = Actor(8, 1, (4, 0, 0), 100, 6, 4, 10, 60)
        cells = {(x, 0, 0) for x in range(5)}
        fight = Fight(
            2,
            [actor, enemy],
            cells,
            {0: {actor.position}, 1: {enemy.position}},
        )
        fight.ready(3)
        actor.controlled = False
        observed = []

        event = fight.server_move(
            actor.id,
            [(1, 0, 0), (2, 0, 0)],
            step_callback=lambda current, mover, before, cell: observed.append(
                (before, cell, mover.mp)
            ),
        )

        self.assertEqual(event["path"], [(1, 0, 0), (2, 0, 0)])
        self.assertEqual(event["cost"], 2)
        self.assertEqual(actor.position, (2, 0, 0))
        self.assertEqual(actor.mp, 2)
        self.assertEqual(
            observed,
            [((0, 0, 0), (1, 0, 0), 3), ((1, 0, 0), (2, 0, 0), 2)],
        )

    def test_callback_preserves_tackle_costs_for_the_same_complete_route(self):
        from test_combat_tackle_movement import NativeTackleMovementTests

        source, _, _ = NativeTackleMovementTests().fixture()
        source.current.controlled = False
        path = [(0, 1, 0), (0, 2, 0)]
        expected = copy.deepcopy(source)
        expected_event = expected.server_move(expected.current.id, path)
        seen = []
        actual_event = source.server_move(
            source.current.id,
            path,
            step_callback=lambda fight, actor, before, cell: seen.append(
                (before, cell, actor.ap, actor.mp)
            ),
        )

        self.assertEqual(actual_event, expected_event)
        self.assertEqual(
            (source.current.position, source.current.ap, source.current.mp),
            (expected.current.position, expected.current.ap, expected.current.mp),
        )
        self.assertEqual(
            [row[:2] for row in seen], [((0, 0, 0), path[0]), (path[0], path[1])]
        )

    def test_callback_preserves_aggregate_native_rail_cost(self):
        from test_combat_rail_movement import RailMovementTests

        runtime = RailMovementTests().actual_fight()
        source = runtime.fight
        path = [(x, 0, 0) for x in range(1, 5)]
        expected = copy.deepcopy(source)
        expected_event = expected.move(3, 7, path)
        observed = []
        actual_event = source.move(
            3,
            7,
            path,
            step_callback=lambda fight, actor, before, cell: observed.append(cell),
        )

        self.assertEqual(actual_event, expected_event)
        self.assertTrue(actual_event["on_rails"])
        self.assertEqual(actual_event["cost"], 2)
        self.assertEqual(source.actors[7].mp, 4)
        self.assertEqual(observed, path)

    def test_native_oracle_movement_serialization_failure_rolls_back_callback_state(
        self,
    ):
        _, fixture, runtime, oracle, _ = self._native_wonejo_runtime()
        actor = fixture.npc
        destination = (-6, -7, -1)
        self.assertIn((actor.position, destination), runtime.fight.edges)
        before = oracle.state_identity(runtime)

        def fail_serialization(actor, fight):
            raise ValueError("sequential movement serialization failure")

        with self.assertRaisesRegex(
            ValueError, "sequential movement serialization failure"
        ):
            oracle.commit(
                {"type": "move", "path": [list(destination)]},
                stats_serializer=fail_serialization,
            )

        self.assertEqual(oracle.state_identity(runtime), before)
        self.assertEqual((actor.position, actor.mp), ((-7, -7, -1), 3))

    def test_native_committed_cast_searches_retreat_and_replan_does_not_approach(self):
        from unittest.mock import patch

        _, fixture, runtime, oracle, deck = self._native_wonejo_runtime()
        actor, target = fixture.npc, fixture.pc
        initial_distance = sum(
            abs(a - b) for a, b in zip(actor.position[:2], target.position[:2])
        )
        cast = dict(
            type="cast",
            spellId=7962,
            level=1,
            targetId=target.id,
            target=list(target.position),
        )
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            oracle.commit(cast, stats_serializer=lambda current, fight: b"")

        events = runtime.fight.events
        self.assertTrue(
            any(
                event.get("kind") == "damage"
                and event.get("source_id") == actor.id
                and event.get("amount", 0) > 0
                for event in events
            )
        )
        self.assertTrue(
            any(
                event.get("kind") == "npc_cast"
                and event.get("actor_id") == actor.id
                and event.get("spell_id") == 7962
                and event.get("turn_id") == runtime.fight.turn_id
                for event in events
            )
        )
        self.assertEqual(actor.ap, 6)  # Native 7962 has zero AP cost.
        self.assertEqual(actor.mp, 3)

        # Restrict search to a short corridor selected from the placement's
        # actual validated terrain edges, avoiding a full-map route frontier.
        from wakfu_server.combat_geometry_snapshot import freeze_terrain

        route = [
            actor.position,
            (-6, -7, -1),
            (-5, -7, -1),
            (-4, -7, -1),
        ]
        self.assertTrue(
            all(
                (origin, destination) in runtime.fight.edges
                for origin, destination in zip(route, route[1:])
            )
        )
        native_edges = set(runtime.fight.edges)
        self.assertIn((actor.position, target.position), native_edges)
        runtime.fight.walkable = set(route) | {target.position}
        runtime.fight.edges = set(zip(route, route[1:])) | set(zip(route[1:], route))
        runtime.fight.edges.update(
            edge
            for edge in (
                (actor.position, target.position),
                (target.position, actor.position),
            )
            if edge in native_edges
        )
        freeze_terrain(runtime.fight)

        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            session, decision = self._search_decision(oracle, runtime, deck)
        session.guard()
        self.assertTrue(decision["plan"], decision)
        self.assertEqual(decision["plan"][0]["type"], "move", decision)
        retreat = decision["plan"][0]
        retreat_cell = tuple(retreat["path"][-1])
        retreat_distance = sum(
            abs(a - b) for a, b in zip(retreat_cell[:2], target.position[:2])
        )
        self.assertGreater(retreat_distance, initial_distance)

        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            oracle.commit(
                {"type": "move", "path": retreat["path"]},
                stats_serializer=lambda current, fight: b"",
            )
            _, replanned = self._search_decision(oracle, runtime, deck)
        if not replanned["plan"]:
            # An empty search result proposes no step at all. The actor remains
            # at the committed retreat cell, so it cannot approach the target.
            self.assertEqual(runtime.fight.actors[actor.id].position, retreat_cell)
            self.assertGreater(retreat_distance, initial_distance)
            return
        next_action = replanned["plan"][0]
        if next_action["type"] == "move":
            next_distance = sum(
                abs(a - b)
                for a, b in zip(tuple(next_action["path"][-1])[:2], target.position[:2])
            )
            self.assertGreaterEqual(next_distance, retreat_distance)
        else:
            self.assertEqual(next_action["type"], "end_turn")


if __name__ == "__main__":
    unittest.main()
