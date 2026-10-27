"""All-owner transport recovery waits for real sources without advancing combat."""
import ast
import os
from copy import deepcopy
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from test_party_instance_publication_recovery import (
    PartyPublicationRecoveryTests,
    published,
)
from wakfu_server.combat_shared import Session
from wakfu_server.combat_instance_publication import require_current_publication
from wakfu_server.combat_instance_publication_recovery import (
    rebind_recovered_owner,
    publication_recovery_waiting,
)


class StagedPartyPublicationRecoveryTests(unittest.TestCase):
    def setUp(self):
        feature = patch.dict(os.environ, {"WAKFU_NATIVE_PARTY_STAGED_RECOVERY": "1"})
        feature.start()
        self.addCleanup(feature.stop)

    def fixture(self, *, active=False):
        (
            fixture,
            bindings,
            second,
            second_source,
        ) = PartyPublicationRecoveryTests().party()
        if active:
            from wakfu_server.combat_runtime_messages import RuntimeMessages

            fixture.shared.fight.ready(1)
            fixture.shared.fight.ready(2)
            runtime = RuntimeMessages(fixture.shared.fight, clock=lambda: 100.0)
            runtime.awaiting_ack = 1
            runtime.pending = [
                (
                    13482,
                    struct.pack(">iiiqq", 99, 31, -1, runtime.fight.current.id, 60000),
                )
            ]
            runtime.native_action_id = 30
            fixture.shared.runtime = runtime
            fixture.shared.ack.arm(1, [fixture.one, fixture.two])
        fixture.registry.disconnect(fixture.two)
        bindings[0][0].invalidate()
        fixture.live.remove(fixture.one)
        fixture.registry.disconnect(fixture.one)
        first = Session(1, 10, "first-recovered", 1134, 0)
        fixture.live.add(first)
        return fixture, first, published(first), second, second_source

    def takeover(self, fixture, session, source, *, persisted=None, bootstrap=None):
        return fixture.registry.takeover(
            99,
            session,
            bootstrap
            or (
                lambda fight, view, owner: (
                    (12044, struct.pack(">ii", owner.account_id, owner.character_id)),
                )
            ),
            recover_disconnected=True,
            persist_takeover=persisted or (lambda previous: None),
            prepare_authority=lambda fight, view, owner: rebind_recovered_owner(
                fight, view, owner, source, session_live=fixture.registry._lease_live
            ),
        )

    def test_default_configuration_stages_real_sources_until_last_owner_returns(self):
        # Production previously defaulted this flag to zero, creating a cycle:
        # neither replacement source could be retained before the other arrived.
        for setting in (None, "0"):
            with self.subTest(setting=setting), patch.dict(os.environ):
                if setting is None:
                    os.environ.pop("WAKFU_NATIVE_PARTY_STAGED_RECOVERY", None)
                else:
                    os.environ["WAKFU_NATIVE_PARTY_STAGED_RECOVERY"] = setting
                fixture, first, source1, second, source2 = self.fixture(active=True)
                shared = fixture.shared
                original = shared.fight, shared.runtime, shared.ack
                self.takeover(fixture, first, source1)
                self.assertEqual(shared.participants[1], first)
                self.assertFalse(shared.connected)
                self.assertEqual((shared.fight, shared.runtime, shared.ack), original)
                self.assertTrue(publication_recovery_waiting(shared))
                self.takeover(fixture, second, source2)
                self.assertEqual(shared.connected, {1, 2})
                self.assertFalse(publication_recovery_waiting(shared))
                require_current_publication(shared.fight)

    def test_progress_token_tracks_real_publication_changes_and_staged_disconnect(self):
        from wakfu_server.combat_instance_publication_recovery import (
            publication_recovery_token,
        )
        from test_native_recovery_instance_publication_hooks import frames

        fixture, first, source1, _second, _source2 = self.fixture()
        shared = fixture.shared
        before = publication_recovery_token(shared)
        self.takeover(fixture, first, source1)
        staged = publication_recovery_token(shared)
        self.assertNotEqual(before, staged)
        self.assertEqual(staged, publication_recovery_token(shared))
        source1[0].invalidate()
        invalid = publication_recovery_token(shared)
        self.assertNotEqual(staged, invalid)
        source1[0].after_write(frames(2, instance=first.instance_id), source1[1])
        self.assertNotEqual(invalid, publication_recovery_token(shared))
        fixture.live.remove(first)
        before = publication_recovery_token(shared)
        fixture.registry.disconnect(first)
        self.assertNotEqual(before, publication_recovery_token(shared))

    def test_explicit_pending_abort_preserves_cohort_until_all_health_exits_commit(
        self,
    ):
        fixture, first, source1, _second, _source2 = self.fixture(active=True)
        shared = fixture.shared
        self.takeover(fixture, first, source1)
        original = shared.fight, shared.runtime, shared.ack
        pending = deepcopy(shared.runtime.pending)
        observed = []

        def failed_persist(candidate):
            observed.append(candidate)
            self.assertIs(fixture.registry.lookup(99), shared)
            raise RuntimeError("durable abort failed")

        with self.assertRaisesRegex(RuntimeError, "durable abort failed"):
            fixture.registry.abort_pending_publication_recovery(
                first, persist=failed_persist
            )
        self.assertEqual(observed, [shared])
        self.assertIs(fixture.registry.lookup(99), shared)
        self.assertEqual((shared.fight, shared.runtime, shared.ack), original)
        self.assertEqual(shared.runtime.pending, pending)
        self.assertTrue(publication_recovery_waiting(shared))
        exits = {
            owner.character_id: {"character": {"id": owner.character_id}}
            for owner in shared.participants.values()
        }
        result = fixture.registry.abort_pending_publication_recovery(
            first, persist=lambda candidate: exits
        )
        self.assertIs(result["shared"], shared)
        self.assertIs(result["exits"], exits)
        self.assertNotIn(99, fixture.registry.fights)
        self.assertNotIn(first.character_id, fixture.registry.by_character)
        self.assertNotIn(fixture.two.character_id, fixture.registry.by_character)
        self.assertFalse(set(shared.fight.actors) & set(fixture.registry.by_actor))
        self.assertEqual((shared.fight, shared.runtime, shared.ack), original)
        self.assertEqual(shared.runtime.pending, pending)
        self.assertIsNone(shared.fight.winner)

    def test_pending_abort_accepts_complete_idempotent_health_receipts(self):
        fixture, first, source1, _second, _source2 = self.fixture()
        shared = fixture.shared
        self.takeover(fixture, first, source1)
        exits = {
            owner.character_id: {"applied": False}
            for owner in shared.participants.values()
        }
        result = fixture.registry.abort_pending_publication_recovery(
            first, persist=lambda candidate: exits
        )
        self.assertIs(result["exits"], exits)
        self.assertNotIn(99, fixture.registry.fights)

    def test_pending_abort_rejects_foreign_live_cohort_and_incomplete_durable_exits(
        self,
    ):
        for kind in ("foreign", "connected", "duel", "incomplete"):
            with self.subTest(kind=kind):
                fixture, first, source1, _second, _source2 = self.fixture()
                shared = fixture.shared
                self.takeover(fixture, first, source1)
                requester = first
                if kind == "foreign":
                    requester = Session(1, 10, "foreign-replaced-generation", 1134, 0)
                    fixture.live.add(requester)
                elif kind == "connected":
                    shared.connected.add(2)
                elif kind == "duel":
                    shared.is_duel = True
                persisted = []
                with self.assertRaises(ValueError):
                    fixture.registry.abort_pending_publication_recovery(
                        requester,
                        persist=lambda candidate: persisted.append(candidate) or {},
                    )
                self.assertEqual(len(persisted), 1 if kind == "incomplete" else 0)
                self.assertIs(fixture.registry.lookup(99), shared)
                self.assertEqual(shared.participants[1], first)
                self.assertTrue(publication_recovery_waiting(shared))

    def test_all_owners_reattach_durably_before_each_gets_its_own_bootstrap(self):
        fixture, first, source1, second, source2 = self.fixture(active=True)
        shared = fixture.shared
        original_fight, original_runtime = shared.fight, shared.runtime
        pending = deepcopy(original_runtime.pending)
        persisted, bootstraps = [], []

        def bootstrap(fight, view, owner):
            require_current_publication(fight)
            bootstraps.append(owner.account_id)
            return ((12044, struct.pack(">ii", owner.account_id, owner.character_id)),)

        self.takeover(
            fixture,
            first,
            source1,
            persisted=lambda old: persisted.append(old),
            bootstrap=bootstrap,
        )
        self.assertEqual(persisted, [fixture.one])
        self.assertEqual(shared.participants[1], first)
        self.assertFalse(shared.connected)
        self.assertEqual(bootstraps, [])
        self.assertIs(shared.fight, original_fight)
        self.assertIs(shared.runtime, original_runtime)
        self.assertEqual(shared.runtime.pending, pending)
        self.assertTrue(publication_recovery_waiting(shared))
        with self.assertRaises(ValueError):
            fixture.registry.expire_current_turn(99, first, now_ms=999999)
        with self.assertRaises(ValueError):
            fixture.registry.execute(99, first, 10, lambda fight, runtime: [])
        self.assertEqual(shared.runtime.pending, pending)
        self.takeover(
            fixture,
            second,
            source2,
            persisted=lambda old: persisted.append(old),
            bootstrap=bootstrap,
        )
        self.assertEqual(set(bootstraps), {1, 2})
        self.assertEqual(shared.connected, {1, 2})
        self.assertFalse(publication_recovery_waiting(shared))
        self.assertIsNot(shared.fight, original_fight)
        self.assertIsNone(shared.runtime.awaiting_ack)
        self.assertIsNone(shared.ack.turn)
        self.assertIs(shared.runtime.fight, shared.fight)
        for owner in (first, second):
            packets = fixture.registry.drain(99, owner)[0].packets
            self.assertEqual(
                packets,
                ((12044, struct.pack(">ii", owner.account_id, owner.character_id)),),
            )
        require_current_publication(shared.fight)

    def test_staged_socket_loss_and_new_generation_cannot_revive_old_publication(self):
        fixture, first, source1, second, source2 = self.fixture()
        self.takeover(fixture, first, source1)
        source1[0].invalidate()
        fixture.live.remove(first)
        fixture.registry.disconnect(first)
        self.assertNotIn(1, fixture.shared.pending_publication_recoveries)
        self.assertTrue(publication_recovery_waiting(fixture.shared))
        newest = Session(1, 10, "first-recovered-again", 1134, 0)
        fixture.live.add(newest)
        self.takeover(fixture, newest, published(newest))
        # A delayed finalizer for the replaced generation cannot erase this entry.
        fixture.registry.disconnect(first)
        self.assertEqual(
            fixture.shared.pending_publication_recoveries[1].session, newest
        )
        self.takeover(fixture, second, source2)
        self.assertEqual(fixture.shared.participants[1], newest)
        require_current_publication(fixture.shared.fight)

    def test_last_owner_persistence_failure_keeps_prior_staging_and_fsm_retryable(self):
        fixture, first, source1, second, source2 = self.fixture(active=True)
        shared = fixture.shared
        self.takeover(fixture, first, source1)
        original_fight, original_runtime, original_ack = (
            shared.fight,
            shared.runtime,
            shared.ack,
        )
        pending = deepcopy(original_runtime.pending)
        with self.assertRaisesRegex(RuntimeError, "last durable failure"):
            self.takeover(
                fixture,
                second,
                source2,
                persisted=lambda old: (_ for _ in ()).throw(
                    RuntimeError("last durable failure")
                ),
            )
        self.assertIs(shared.fight, original_fight)
        self.assertIs(shared.runtime, original_runtime)
        self.assertIs(shared.ack, original_ack)
        self.assertEqual(shared.runtime.pending, pending)
        self.assertEqual(shared.participants[1], first)
        self.assertEqual(shared.participants[2], fixture.two)
        self.assertFalse(shared.connected)
        self.assertFalse(shared.outboxes[1])
        self.assertFalse(shared.outboxes[2])
        self.takeover(fixture, second, source2)
        self.assertEqual(shared.connected, {1, 2})
        require_current_publication(shared.fight)

    def test_pending_socket_loss_does_not_spend_frozen_turn_deadline(self):
        fixture, first, source1, second, source2 = self.fixture()
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        shared = fixture.shared
        runtime = RuntimeMessages(shared.fight, clock=lambda: 100.0)
        runtime.turn_deadline = 130.0
        shared.runtime = runtime
        shared.reconnect_remaining_turn_seconds = 30.0
        self.takeover(fixture, first, source1)
        source1[0].invalidate()
        fixture.live.remove(first)
        runtime.clock = lambda: 1000.0
        fixture.registry.disconnect(first)
        self.assertEqual(shared.reconnect_remaining_turn_seconds, 30.0)
        self.assertTrue(shared.disconnect_abort_pending)

    def test_actual_socket_guard_holds_world_actions_even_after_failed_last_takeover(
        self,
    ):
        fixture, first, source1, second, source2 = self.fixture()
        self.takeover(fixture, first, source1)
        tree = ast.parse(
            (Path(__file__).parents[1] / "local_game_server.py").read_text()
        )
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "deferred_native_combat_attachment"
        )
        namespace = dict(
            COMBAT_TEST=True,
            loaded=True,
            character={"id": 20},
            account_id=2,
            generation=second.generation,
            COMBAT_SESSIONS=type(
                "Sessions",
                (),
                {"lookup_character": lambda self, identity: fixture.shared},
            )(),
        )
        exec(
            compile(
                ast.Module(body=[function], type_ignores=[]),
                "<actual-native-recovery-socket-guard>",
                "exec",
            ),
            namespace,
        )
        self.assertIs(namespace["deferred_native_combat_attachment"](), fixture.shared)
        self.takeover(fixture, second, source2)
        self.assertIsNone(namespace["deferred_native_combat_attachment"]())

    def test_owner_source_lost_inside_final_persistence_pauses_and_retries_without_second_sql(
        self,
    ):
        fixture, first, source1, second, source2 = self.fixture(active=True)
        shared = fixture.shared
        self.takeover(fixture, first, source1)
        original_fight, original_runtime, original_ack = (
            shared.fight,
            shared.runtime,
            shared.ack,
        )
        pending = deepcopy(shared.runtime.pending)
        persisted = []

        def lose_source(previous):
            persisted.append(previous)
            source1[0].invalidate()

        self.takeover(fixture, second, source2, persisted=lose_source)
        self.assertEqual(persisted, [fixture.two])
        self.assertEqual(shared.participants[2], second)
        self.assertFalse(shared.connected)
        self.assertTrue(publication_recovery_waiting(shared))
        self.assertIs(shared.fight, original_fight)
        self.assertIs(shared.runtime, original_runtime)
        self.assertIs(shared.ack, original_ack)
        self.assertEqual(shared.runtime.pending, pending)
        self.assertFalse(shared.outboxes[1])
        self.assertFalse(shared.outboxes[2])
        # This is a new actual publication of the already durable generation,
        # not permission to reuse the invalid old transport receipt.
        from test_native_recovery_instance_publication_hooks import frames

        source1[0].after_write(frames(2, instance=first.instance_id), source1[1])
        self.takeover(
            fixture,
            first,
            source1,
            persisted=lambda previous: self.fail(
                "Already durable staged owner was persisted twice"
            ),
        )
        self.assertEqual(shared.connected, {1, 2})
        self.assertFalse(publication_recovery_waiting(shared))
        self.assertIsNone(shared.runtime.awaiting_ack)
        require_current_publication(shared.fight)
        for owner in (first, second):
            self.assertEqual(
                fixture.registry.drain(99, owner)[0].packets,
                ((12044, struct.pack(">ii", owner.account_id, owner.character_id)),),
            )

    def test_placement_deadline_retains_elapsed_before_pause_and_not_waiting_duration(
        self,
    ):
        from wakfu_server.placement_deadline import Deadline

        with patch("wakfu_server.combat_shared.time.monotonic", return_value=110.0):
            fixture, first, source1, second, source2 = self.fixture()
        shared = fixture.shared
        shared.join_context = {"fight_started_at": 100.0, "duration_ms": 30000}
        with patch("wakfu_server.combat_shared.time.monotonic", return_value=500.0):
            self.takeover(fixture, first, source1)
        self.assertEqual(shared.reconnect_placement_paused_at, 110.0)
        with patch("wakfu_server.combat_shared.time.monotonic", return_value=1000.0):
            self.takeover(fixture, second, source2)
        self.assertEqual(shared.join_context["fight_started_at"], 990.0)
        self.assertIsNone(shared.reconnect_placement_paused_at)
        deadline = Deadline()
        deadline.start(
            shared.fight.id,
            shared.join_context["duration_ms"],
            shared.join_context["fight_started_at"],
        )
        self.assertFalse(deadline.take_expired(shared.fight, 1019.0))
        self.assertTrue(deadline.take_expired(shared.fight, 1020.0))

    def test_waiting_socket_refresh_uses_resumed_shared_placement_origin(self):
        from types import SimpleNamespace
        from wakfu_server.placement_deadline import Deadline

        fixture, first, source1, second, source2 = self.fixture()
        shared = fixture.shared
        shared.join_context = {"fight_started_at": 990.0, "duration_ms": 30000}
        shared.disconnect_abort_pending = False
        tree = ast.parse(
            (Path(__file__).parents[1] / "local_game_server.py").read_text()
        )
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "refresh_shared_combat"
        )
        function.decorator_list = (
            []
        )  # Instrumentation is outside the deadline contract.
        initialization = """def make(shared, deadline):
    fight = shared.fight
    fight_messages = shared.runtime
    group_lease = TEST_MONSTERS = TEST_MONSTERS_BY_ID = pve_withdrawal_pending = None
    combat_session = shared.participants[1]
    loaded = True
    fight_started_at = 100.0
    placement_deadline = deadline
"""
        body = "\n".join("    " + line for line in ast.unparse(function).splitlines())
        source = (
            initialization
            + body
            + "\n    return refresh_shared_combat, lambda: fight_started_at\n"
        )
        namespace = {
            "COMBAT_SESSIONS": SimpleNamespace(
                registry=SimpleNamespace(lookup=lambda *args, **kwargs: shared)
            )
        }
        exec(compile(source, "<actual-shared-placement-refresh>", "exec"), namespace)
        deadline = Deadline()
        refresh, origin = namespace["make"](shared, deadline)
        self.assertIs(refresh(blocking=False), shared)
        self.assertEqual(origin(), 990.0)
        self.assertFalse(deadline.take_expired(shared.fight, 1019.0))
        self.assertTrue(deadline.take_expired(shared.fight, 1020.0))
        # The claimed deadline must not be restarted on each idle refresh.
        refresh(blocking=False)
        self.assertIsNone(deadline.until)

    def test_recovery_keeps_retired_owner_inactive_without_requiring_its_dead_transport(
        self,
    ):
        from wakfu_server.combat_instance_publication import bind_party_encounter
        from wakfu_server.combat_instance_publication_withdrawal import (
            retire_withdrawn_publication,
        )
        from test_native_recovery_instance_publication_hooks import frames

        fixture, bindings, second, source2 = PartyPublicationRecoveryTests().party()
        shared = fixture.shared
        # Establish three real frame-backed authorities, then exercise the
        # production retirement helper before the remaining owners disconnect.
        bindings[1][0].after_write(frames(2), bindings[1][1])
        retired = Session(3, 30, "withdrawn-generation", 1134, 0)
        source3 = published(retired)
        actor = deepcopy(shared.fight.actors[20])
        actor.id, actor.owner_id = 30, 3
        shared.fight.actors[30] = actor
        bind_party_encounter(
            shared.fight,
            publications=(*bindings, source3),
            npc_ids=(-200,),
            player_ids=(10, 20, 30),
        )
        actor.pve_withdrawn = True
        retire_withdrawn_publication(shared.fight, 3)
        source3[0].invalidate()
        snapshots = deepcopy(shared.fight.native_instance_difficulty_snapshots)
        fixture.registry.disconnect(fixture.two)
        bindings[1][0].invalidate()
        fixture.live.remove(fixture.one)
        fixture.registry.disconnect(fixture.one)
        bindings[0][0].invalidate()
        first = Session(1, 10, "after-retirement-first", 1134, 0)
        fixture.live.add(first)
        self.takeover(fixture, first, published(first))
        self.takeover(fixture, second, source2)
        self.assertEqual(shared.connected, {1, 2})
        self.assertTrue(shared.fight.actors[30].pve_withdrawn)
        self.assertEqual(shared.fight.native_instance_difficulty_snapshots, snapshots)
        self.assertEqual(
            {
                scope[0]
                for _, scope in shared.fight.native_instance_publication_lease.owner_bindings
            },
            {1, 2},
        )
        require_current_publication(shared.fight)

    def test_socket_loss_inside_final_durable_callback_keeps_replacement_retryable(
        self,
    ):
        fixture, first, source1, second, source2 = self.fixture(active=True)
        shared = fixture.shared
        self.takeover(fixture, first, source1)
        original_fight, original_runtime = shared.fight, shared.runtime

        def close_staged_socket(previous):
            fixture.live.remove(first)
            fixture.registry.disconnect(first)
            source1[0].invalidate()

        self.takeover(fixture, second, source2, persisted=close_staged_socket)
        self.assertFalse(shared.connected)
        self.assertIs(shared.fight, original_fight)
        self.assertIs(shared.runtime, original_runtime)
        self.assertNotIn(1, shared.pending_publication_recoveries)
        self.assertEqual(shared.pending_publication_recoveries[2].session, second)
        newest = Session(1, 10, "after-durable-callback-socket-loss", 1134, 0)
        fixture.live.add(newest)
        self.takeover(fixture, newest, published(newest))
        self.assertEqual(shared.connected, {1, 2})
        self.assertEqual(shared.participants[1], newest)
        self.assertIsNone(shared.runtime.awaiting_ack)
        require_current_publication(shared.fight)
