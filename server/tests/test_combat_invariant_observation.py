"""Opt-in invariant observation stays passive and boundary scoped."""
import asyncio
import random
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_invariant_observation import (
    invariant_observation_scope,
    observe_prepared_boundary,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight


def make_registry(*, server_first=False):
    session = Session(3, 7, "invariant-observer-test", 1134, 0)
    player_initiative, npc_initiative = (10, 100) if server_first else (100, 10)
    player = Actor(7, 0, (0, 0, 0), 60, 6, 3, player_initiative, 1, 3, True)
    npc = Actor(-7, 1, (1, 0, 0), 20, 4, 2, npc_initiative, 1)
    fight = Fight(
        903,
        (player, npc),
        {player.position, npc.position},
        {0: {player.position}, 1: {npc.position}},
    )
    fight.ready(session.account_id)
    runtime = RuntimeMessages(fight, clock=lambda: 0.0)
    registry = Registry(lambda candidate: candidate == session)
    shared = registry.register(fight, session, runtime=runtime)
    return registry, shared, session


def accepted_player_action(registry, shared, session, *, damage=1):
    def operation(candidate, runtime):
        candidate.actors[7].hp -= damage
        return [(12847, b"invariant-observation-probe")]

    sequence = registry.execute(shared.fight.id, session, 7, operation)
    batch = shared.outboxes[session.account_id][-1]
    return sequence, shared.fight.actors[7].hp, batch.packets


class CombatInvariantObservationTests(unittest.TestCase):
    def test_actual_registry_execute_marks_completed_candidate_before_adoption(self):
        import wakfu_server.combat_invariant_observation as observation

        registry, shared, session = make_registry()
        seen = {}
        original = observation.observe_prepared_boundary

        def inspect(candidate, runtime, **options):
            seen["candidate"] = candidate
            seen["runtime"] = runtime
            seen["source_fight"] = shared.fight
            original(candidate, runtime, **options)

        with invariant_observation_scope() as scope, patch.object(
            observation, "observe_prepared_boundary", side_effect=inspect
        ):
            outcome = accepted_player_action(registry, shared, session)

        self.assertIsNot(seen["candidate"], seen["source_fight"])
        self.assertIs(shared.fight, seen["candidate"])
        self.assertIs(shared.runtime, seen["runtime"])
        self.assertEqual(outcome[:2], (1, 59))
        reports = scope.require_boundary("Registry.execute")
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].boundary.stage, "pre_adoption")
        self.assertIsInstance(reports[0].findings, tuple)

    def test_actual_registry_execute_server_has_its_own_pre_adoption_marker(self):
        registry, shared, session = make_registry(server_first=True)
        self.assertEqual(shared.fight.current.id, -7)

        def operation(candidate, runtime):
            candidate.actors[-7].hp -= 1
            return [(12847, b"server-observation-probe")]

        with invariant_observation_scope() as scope:
            sequence = registry.execute_server(
                shared.fight.id, -7, operation, expected_sequence=shared.sequence
            )
        reports = scope.require_boundary("Registry.execute_server")
        self.assertEqual(sequence, 1)
        self.assertEqual(shared.fight.actors[-7].hp, 19)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].boundary.stage, "pre_adoption")

    def test_default_off_and_observer_errors_do_not_change_gameplay_outcome(self):
        import wakfu_server.combat_invariant_observation as observation

        baseline_registry, baseline_shared, baseline_session = make_registry()
        observed_registry, observed_shared, observed_session = make_registry()
        with patch.object(
            observation,
            "check_prepared_boundary",
            side_effect=AssertionError("default-off checker call"),
        ) as checker:
            baseline = accepted_player_action(
                baseline_registry, baseline_shared, baseline_session, damage=2
            )
        checker.assert_not_called()

        with invariant_observation_scope() as scope, patch.object(
            observation,
            "check_prepared_boundary",
            side_effect=RuntimeError("diagnostic-only failure"),
        ):
            observed = accepted_player_action(
                observed_registry, observed_shared, observed_session, damage=2
            )
        self.assertEqual(observed, baseline)
        self.assertEqual(observed_shared.sequence, baseline_shared.sequence)
        self.assertEqual(
            observed_shared.outboxes[3][-1].packets,
            baseline_shared.outboxes[3][-1].packets,
        )
        self.assertFalse(scope.complete)
        (report,) = scope.reports
        self.assertEqual(report.findings[0].invariant, "checker.failed")
        self.assertEqual(report.findings[0].status, "unknown")
        with self.assertRaisesRegex(AssertionError, "incomplete"):
            scope.require_boundary("Registry.execute")

    def test_nested_scopes_own_reports_and_context_resets(self):
        _, shared, _ = make_registry()
        with invariant_observation_scope() as outer:
            observe_prepared_boundary(
                shared.fight, shared.runtime, operation="outer.before"
            )
            with invariant_observation_scope() as inner:
                observe_prepared_boundary(
                    shared.fight, shared.runtime, operation="inner.only"
                )
            observe_prepared_boundary(
                shared.fight, shared.runtime, operation="outer.after"
            )
        self.assertEqual(
            [row.boundary.operation for row in outer.reports],
            ["outer.before", "outer.after"],
        )
        self.assertEqual(
            [row.boundary.operation for row in inner.reports], ["inner.only"]
        )
        observe_prepared_boundary(
            shared.fight, shared.runtime, operation="outside.scope"
        )
        self.assertEqual(len(outer.reports), 2)
        self.assertEqual(len(inner.reports), 1)

    def test_inherited_async_task_cannot_append_to_parent_collector(self):
        _, shared, _ = make_registry()

        async def run():
            with invariant_observation_scope() as scope:

                async def child():
                    observe_prepared_boundary(
                        shared.fight, shared.runtime, operation="child.task"
                    )

                await asyncio.create_task(child())
                self.assertEqual(scope.reports, ())
                observe_prepared_boundary(
                    shared.fight, shared.runtime, operation="parent.task"
                )
                self.assertEqual(
                    [r.boundary.operation for r in scope.reports], ["parent.task"]
                )

        asyncio.run(run())

    def test_report_limit_truncates_and_marks_collector_incomplete(self):
        _, shared, _ = make_registry()
        with invariant_observation_scope(limit=1) as scope:
            observe_prepared_boundary(shared.fight, shared.runtime, operation="first")
            observe_prepared_boundary(shared.fight, shared.runtime, operation="dropped")
        self.assertEqual(len(scope.reports), 1)
        self.assertFalse(scope.complete)
        with self.assertRaisesRegex(AssertionError, "incomplete"):
            scope.require_boundary("first")

    def test_missing_marker_and_invalid_scope_cannot_be_counted_as_clean(self):
        _, _, _ = make_registry()
        with invariant_observation_scope() as scope:
            pass
        self.assertTrue(scope.complete)
        with self.assertRaisesRegex(AssertionError, "Missing or incomplete"):
            scope.require_boundary("Registry.execute")
        with self.assertRaisesRegex(AssertionError, "Missing or incomplete"):
            scope.raise_if_violated()
        for limit in (0, -1, True, 4097):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                with invariant_observation_scope(limit=limit):
                    pass

    def test_actual_spell_commit_observes_source_bound_transaction_before_swap(self):
        import os
        from test_combat_reproduction_actions import ReproductionActionTests
        from wakfu_server.combat_reproduction_actions import prepare_context
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_los import authoritative_visible

        fixture = ReproductionActionTests()
        runtime, inputs = fixture.fixture()
        source_fight = runtime.fight
        target = runtime.fight.actors[-7].position
        action = dict(
            type="player_spell",
            body=struct.pack(">qqiih", 7, (7 << 32) | 6266, *target),
            owner_id=3,
            critical=None,
        )
        fallback = random.Random(88)
        serializer, _ = prepare_context(
            runtime, action, inputs, fallback, lambda: 123.0
        )
        with patch.dict(os.environ, {"WAKFU_NATIVE_AREA_CALLBACKS": "1"}):
            transaction = prepare_server_spell(
                action["body"],
                inputs["character"],
                inputs["monsters"],
                runtime.fight,
                action["owner_id"],
                inputs["deck_blob"],
                action_id=runtime.action_id + 1,
                critical=None,
                player_characters=inputs["player_characters"],
                deck_blobs=inputs["deck_blobs"],
                line_of_sight=lambda origin, destination, state: authoritative_visible(
                    inputs["map_id"],
                    origin,
                    destination,
                    state,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in state.actors.values()
                        if actor.hp > 0
                    },
                ),
            )

        import wakfu_server.combat_invariant_observation as observation

        seen = {}
        original = observation.observe_prepared_boundary

        def inspect(candidate, candidate_runtime, **options):
            seen["candidate"] = candidate
            seen["runtime"] = candidate_runtime
            seen["source"] = runtime.fight
            self.assertIs(candidate_runtime.fight, candidate)
            self.assertIs(runtime.fight, source_fight)
            seen["projection"] = (candidate.actors[-7].hp, candidate.actors[7].ap)
            original(candidate, candidate_runtime, **options)

        with invariant_observation_scope() as scope, patch.object(
            observation, "observe_prepared_boundary", side_effect=inspect
        ):
            packets = commit_spell_transaction(
                runtime, transaction, stats_serializer=serializer
            )
        reports = scope.require_boundary("commit_spell_transaction")
        self.assertTrue(packets)
        self.assertEqual(runtime.action_id, transaction.action_id)
        self.assertIs(seen["source"], source_fight)
        self.assertIsNot(seen["candidate"], source_fight)
        self.assertIsNot(seen["candidate"], runtime.fight)
        self.assertIs(runtime.fight, transaction.fight)
        self.assertIsNot(seen["runtime"], runtime)
        self.assertIs(seen["runtime"].fight, runtime.fight)
        self.assertEqual(seen["runtime"].action_id, transaction.action_id)
        self.assertEqual(
            seen["projection"],
            (runtime.fight.actors[-7].hp, runtime.fight.actors[7].ap),
        )
        self.assertEqual(reports[0].boundary.runtime_binding, "candidate")
        self.assertEqual(reports[0].boundary.stage, "pre_adoption")


if __name__ == "__main__":
    unittest.main()
