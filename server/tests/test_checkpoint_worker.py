"""Asynchronous persistence keeps gameplay detached, ordered and bounded."""
import ast
from pathlib import Path
from threading import Event, RLock
from types import SimpleNamespace
import unittest
from wakfu_server.checkpoint_worker import (
    CheckpointWorker,
    checkpoint_cleanup_barrier,
    detach,
)


def shared(identity=1):
    fight = SimpleNamespace(
        id=identity, actors={6: SimpleNamespace(hp=100, controlled=True, owner_id=1)}
    )
    runtime = SimpleNamespace(
        action_id=1, native_action_id=1, awaiting_ack=None, round=1, duration=30
    )
    return SimpleNamespace(
        fight=fight,
        runtime=runtime,
        checkpoint_revision=None,
        checkpoint_terminal=False,
        lock=RLock(),
    )


class Persistence:
    def __init__(self):
        self.started, self.release = Event(), Event()
        self.calls = []
        self.revisions = {}

    def save_prepared(
        self,
        account,
        generation,
        fight,
        state,
        *,
        expected_revision,
        trace,
        allow_terminal_receipt=False
    ):
        if fight.id == 1 and not self.started.is_set():
            self.started.set()
            if not self.release.wait(3):
                raise TimeoutError("Test release missing")
        self.assert_revision(fight.id, expected_revision)
        self.calls.append(("save", fight.id, state["hp"]))
        revision = (expected_revision or 0) + 1
        self.revisions[fight.id] = revision
        return revision

    def assert_revision(self, identity, expected):
        if self.revisions.get(identity) != expected:
            raise AssertionError("Stale asynchronous CAS")

    def end(
        self,
        account,
        generation,
        identity,
        *,
        expected_revision,
        status,
        trace,
        allow_terminal_receipt=False
    ):
        self.assert_revision(identity, expected_revision)
        self.calls.append(("end", identity, status))
        self.revisions[identity] += 1
        return self.revisions[identity]


class CheckpointWorkerTests(unittest.TestCase):
    def test_failed_placement_checkpoint_cannot_skip_owned_disconnect_cleanup(self):
        from wakfu_server.combat_shared import Registry, Session
        from wakfu_server.combat_state import Actor, Fight

        owner = Session(1, 6, "generation", 1134, 0)
        registry = Registry(lambda session: session == owner)
        fight = Fight(
            64,
            [
                Actor(6, 0, (0, 0, 0), 100, 6, 3, 10, 1, 1, True),
                Actor(-1, 1, (1, 0, 0), 50, 6, 3, 5, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        source = registry.register(fight, owner, runtime=None)
        errors = []
        legacy_worker = SimpleNamespace()

        self.assertFalse(
            checkpoint_cleanup_barrier(
                lambda: legacy_worker.terminal_pending(fight.id), failed=errors.append
            )
        )
        self.assertIsInstance(errors[0], AttributeError)
        self.assertEqual(registry.disconnect(owner), [fight.id])
        self.assertTrue(source.disconnect_abort_pending)
        # Checkpoint failure alone never unregisters the durable fight.
        self.assertIs(registry.lookup_character(6), source)
        # The existing caller retires only after its separate abort commit.
        self.assertTrue(registry.retire_disconnected_pve(fight.id, owner))
        self.assertIsNone(registry.lookup_character(6))
        replacement = Fight(
            65,
            [
                Actor(6, 0, (0, 0, 0), 100, 6, 3, 10, 1, 1, True),
                Actor(-1, 1, (1, 0, 0), 50, 6, 3, 5, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.assertEqual(registry.register(replacement, owner).fight.id, 65)

    def worker(self, **kwargs):
        persistence = Persistence()
        worker = CheckpointWorker(
            persistence,
            serializer=lambda fight, runtime: dict(hp=fight.actors[6].hp),
            **kwargs
        )
        self.addCleanup(lambda: (persistence.release.set(), worker.close(timeout=3)))
        return worker, persistence

    def test_actual_fight_and_state_ledger_detach_without_runtime_authority(self):
        from wakfu_server.combat_state import Actor, Fight

        actors = [
            Actor(6, 0, (0, 0, 0), 100, 6, 3, 10, 1, 1, True),
            Actor(-1, 1, (1, 0, 0), 50, 6, 3, 5, 1),
        ]
        fight = Fight(
            1, actors, {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        fight.native_rail_movement_authority = lambda: None
        value = shared()
        value.fight = fight
        frozen, runtime, revision = detach(value)
        fight.actors[6].hp = 10
        self.assertEqual(frozen.actors[6].hp, 100)
        self.assertIsNot(frozen.actors[6].state_ledger, fight.actors[6].state_ledger)
        self.assertIs(runtime.fight, frozen)
        self.assertFalse(hasattr(frozen, "native_rail_movement_authority"))

    def test_actual_placement_checkpoint_preserves_absent_runtime(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.fight_checkpoint_store import snapshot

        actors = [
            Actor(6, 0, (0, 0, 0), 100, 6, 3, 10, 1, 1, True),
            Actor(-1, 1, (1, 0, 0), 50, 6, 3, 5, 1),
        ]
        fight = Fight(
            2, actors, {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        value = shared(2)
        value.fight, value.runtime = fight, None
        self.assertEqual(fight.phase, "placement")
        frozen, runtime, revision = detach(value)
        self.assertIsNone(runtime)
        self.assertIsNone(revision)
        self.assertEqual(snapshot(frozen, runtime=runtime), snapshot(fight))

        persistence = Persistence()

        def save_placement(
            account,
            generation,
            detached,
            state,
            *,
            expected_revision,
            trace,
            allow_terminal_receipt=False
        ):
            self.assertEqual(state["phase"], "placement")
            self.assertNotIn("runtime", state)
            self.assertEqual(state["actors"]["6"]["hp"], 100)
            persistence.assert_revision(detached.id, expected_revision)
            persistence.revisions[detached.id] = 1
            return 1

        persistence.save_prepared = save_placement
        worker = CheckpointWorker(persistence, workers=1)
        self.addCleanup(lambda: worker.close(timeout=3))
        worker.submit(value, 1, "generation")
        self.assertTrue(worker.flush_fight(2, timeout=1))
        self.assertEqual(value.checkpoint_revision, 1)

    def test_slow_sql_does_not_block_submit_or_other_fight(self):
        worker, database = self.worker(workers=2)
        one, two = shared(), shared(2)
        worker.submit(one, 1, "generation")
        self.assertTrue(database.started.wait(1))
        one.fight.actors[6].hp = 90
        worker.submit(one, 1, "generation")
        worker.submit(two, 1, "generation")
        self.assertTrue(worker.flush_fight(2, timeout=1))
        self.assertFalse(worker.flush_fight(1, timeout=0.01))
        database.release.set()
        self.assertTrue(worker.flush_fight(1, timeout=1))
        self.assertEqual(
            [r[2] for r in database.calls if r[:2] == ("save", 1)], [100, 90]
        )

    def test_active_coalesces_terminal_preserved_ordered_and_replay(self):
        worker, database = self.worker(workers=2)
        fight = shared()
        worker.submit(fight, 1, "generation")
        self.assertTrue(database.started.wait(1))
        fight.fight.actors[6].hp = 80
        worker.submit(fight, 1, "generation")
        fight.fight.actors[6].hp = 70
        worker.submit(fight, 1, "generation", status="finished")
        self.assertTrue(
            worker.submit(fight, 1, "generation", status="finished")["replay"]
        )
        database.release.set()
        self.assertTrue(worker.flush_fight(1, timeout=1))
        self.assertEqual(
            database.calls, [("save", 1, 100), ("save", 1, 70), ("end", 1, "finished")]
        )
        self.assertTrue(fight.checkpoint_terminal)
        self.assertEqual(fight.checkpoint_revision, 3)

    def test_capacity_defers_new_fights_without_losing_intents(self):
        worker, database = self.worker(capacity=1)
        one = shared()
        worker.submit(one, 1, "generation")
        self.assertTrue(database.started.wait(1))
        queued = [shared(identity) for identity in range(2, 140)]
        for value in queued:
            worker.submit(value, 1, "generation")
        self.assertEqual(len(worker.inflight), 1)
        self.assertTrue(
            all(not hasattr(job, "fight") for job in worker.pending.values())
        )
        with self.assertRaisesRegex(ValueError, "ownership"):
            worker.submit(one, 1, "replacement")
        database.release.set()
        for value in queued:
            self.assertTrue(worker.flush_fight(value.fight.id, timeout=2))
        self.assertEqual(len(database.revisions), 139)

    def test_transient_failure_before_commit_retries_without_poisoning(self):
        worker, database = self.worker(workers=1)
        original = database.save_prepared
        attempts = []
        database.release.set()

        def save(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise ConnectionError("connection lost before commit")
            return original(*args, **kwargs)

        database.save_prepared = save
        database.reconcile_write = lambda *args, **kwargs: dict(committed=False)
        worker.submit(shared(), 1, "generation")
        self.assertTrue(worker.flush_fight(1, timeout=1))
        self.assertEqual(len(attempts), 2)
        self.assertIsNone(worker.states[1]["error"])

    def test_ambiguous_commit_uses_receipt_without_duplicate_write(self):
        worker, database = self.worker(workers=1)
        database.release.set()
        original = database.save_prepared

        def save(*args, **kwargs):
            original(*args, **kwargs)
            raise ConnectionError("commit response lost")

        database.save_prepared = save
        database.reconcile_write = lambda *args, **kwargs: dict(
            committed=True, revision=1, terminal=False
        )
        value = shared()
        worker.submit(value, 1, "generation")
        self.assertTrue(worker.flush_fight(1, timeout=1))
        self.assertEqual(database.calls, [("save", 1, 100)])
        self.assertEqual(value.checkpoint_revision, 1)

    def test_retries_stop_at_three_and_retain_dirty_intent(self):
        worker, database = self.worker(workers=1)
        attempts = []

        def save(*args, **kwargs):
            attempts.append(1)
            raise ConnectionError("temporarily unavailable")

        database.save_prepared = save
        database.reconcile_write = lambda *args, **kwargs: dict(committed=False)
        worker.submit(shared(), 1, "generation")
        with self.assertRaisesRegex(ValueError, "checkpoint failed"):
            worker.flush_fight(1, timeout=1)
        self.assertEqual(len(attempts), 3)
        self.assertIn(1, worker.pending)
        self.assertFalse(worker.close(timeout=1))
        self.assertEqual(len(attempts), 3)

    def test_explicit_recovery_reconciles_before_persisting_latest_intent(self):
        worker, database = self.worker(workers=1)
        database.release.set()
        original = database.save_prepared
        attempts = []

        def unavailable(*args, **kwargs):
            attempts.append(1)
            raise ConnectionError("database unavailable")

        database.save_prepared = unavailable
        checks = []

        def reconcile(*args, **kwargs):
            checks.append(kwargs)
            return dict(committed=False)

        database.reconcile_write = reconcile
        value = shared()
        worker.submit(value, 1, "generation")
        with self.assertRaisesRegex(ValueError, "checkpoint failed"):
            worker.flush_fight(1, timeout=1)
        value.fight.actors[6].hp = 70
        worker.submit(value, 1, "generation")
        database.save_prepared = original
        with self.assertRaisesRegex(ValueError, "another writer"):
            worker.retry_failed(1, 1, "foreign")
        self.assertTrue(worker.retry_failed(1, 1, "generation"))
        self.assertTrue(worker.flush_fight(1, timeout=1))
        self.assertEqual(len(attempts), 3)
        self.assertIn("snapshot_digest", checks[-1])
        self.assertEqual(database.calls, [("save", 1, 70)])

    def test_new_login_recovers_once_and_followup_takeover_is_idempotent(self):
        worker, database = self.worker(workers=1)
        database.release.set()
        original = database.save_prepared
        attempts = []

        def unavailable(*args, **kwargs):
            attempts.append(args[1])
            raise ConnectionError("database unavailable")

        database.save_prepared = unavailable
        database.reconcile_write = lambda *args, **kwargs: dict(committed=False)
        value = shared()
        worker.submit(value, 1, "old")
        with self.assertRaisesRegex(ValueError, "checkpoint failed"):
            worker.flush_fight(1, timeout=1)
        self.assertEqual(attempts, ["old"] * 3)
        recoveries = []

        def recover(account, old, new, fight, receipt, **kwargs):
            recoveries.append((account, old, new))
            if len(recoveries) == 1:
                raise ConnectionError("membership commit response lost")
            return dict(committed=False)

        database.recover_write_for_takeover = recover
        database.save_prepared = original
        self.assertTrue(worker.flush_for_takeover(1, 1, "old", "new", timeout=1))
        self.assertEqual(recoveries, [(1, "old", "new")] * 2)
        self.assertEqual(worker.states[1]["owners"], {1: "new"})
        calls = []
        worker.takeover_writer(1, 1, "old", "new", persist=lambda: calls.append(1))
        self.assertEqual(calls, [1])
        self.assertTrue(worker.flush_for_takeover(1, 1, "old", "new", timeout=1))
        self.assertEqual(len(recoveries), 2)
        with self.assertRaisesRegex(ValueError, "another writer"):
            worker.flush_for_takeover(1, 1, "foreign", "new", timeout=1)
        with self.assertRaisesRegex(ValueError, "Stale checkpoint writer"):
            worker.takeover_writer(1, 1, "foreign", "new")
        with self.assertRaisesRegex(ValueError, "ownership changed"):
            worker.submit(value, 1, "old")

    def test_repeated_idle_probe_cannot_reset_failed_replacement_budget(self):
        worker, database = self.worker(workers=1)
        attempts = []

        def fail(*args, **kwargs):
            attempts.append(args[1])
            raise ConnectionError("database unavailable")

        database.save_prepared = fail
        database.reconcile_write = lambda *args, **kwargs: dict(committed=False)
        database.recover_write_for_takeover = lambda *args, **kwargs: dict(
            committed=False
        )
        worker.submit(shared(), 1, "old")
        with self.assertRaisesRegex(ValueError, "checkpoint failed"):
            worker.flush_fight(1, timeout=1)
        with self.assertRaisesRegex(ValueError, "another writer"):
            worker.flush_for_takeover(1, 1, "foreign", "new", timeout=1)
        with self.assertRaisesRegex(ValueError, "checkpoint failed"):
            worker.flush_for_takeover(1, 1, "old", "new", timeout=1)
        self.assertEqual(attempts, ["old"] * 3 + ["new"] * 3)
        for _ in range(4):
            with self.assertRaisesRegex(ValueError, "checkpoint failed"):
                worker.flush_for_takeover(1, 1, "old", "new", timeout=1)
        self.assertEqual(len(attempts), 6)

    def test_later_login_reconciles_lost_membership_transfer_responses(self):
        worker, database = self.worker(workers=1)
        database.release.set()
        original = database.save_prepared

        def unavailable(*args, **kwargs):
            raise ConnectionError("database unavailable")

        database.save_prepared = unavailable
        database.reconcile_write = lambda *args, **kwargs: dict(committed=False)
        worker.submit(shared(), 1, "old")
        with self.assertRaises(ValueError):
            worker.flush_fight(1, timeout=1)
        transfers = []

        def transfer(account, old, new, fight, receipt, **kwargs):
            transfers.append(new)
            if new == "second":
                raise ConnectionError("transfer committed but response lost")
            self.assertIn("second", kwargs["recovery_generations"])
            return dict(committed=False)

        database.recover_write_for_takeover = transfer
        with self.assertRaises(ValueError):
            worker.flush_for_takeover(1, 1, "old", "second", timeout=1)
        self.assertEqual(transfers, ["second"] * 3)
        database.save_prepared = original
        self.assertTrue(worker.flush_for_takeover(1, 1, "old", "third", timeout=1))
        self.assertEqual(worker.states[1]["owners"], {1: "third"})
        worker.takeover_writer(1, 1, "old", "third")

    def test_nontransient_failure_never_starts_replacement_retry(self):
        worker, database = self.worker(workers=1)

        def fail(*args, **kwargs):
            raise ValueError("ownership validation failed")

        database.save_prepared = fail
        worker.submit(shared(), 1, "old")
        with self.assertRaisesRegex(ValueError, "checkpoint failed"):
            worker.flush_for_takeover(1, 1, "old", "new", timeout=1)
        self.assertEqual(worker.states[1]["takeover_attempts"], set())

    def test_health_recovery_requires_new_receipt_and_real_down_up_epoch(self):
        worker, database = self.worker(workers=1)
        database.release.set()
        original = database.save_prepared
        value = shared()
        worker.submit(value, 1, "generation")
        self.assertTrue(worker.flush_fight(1, timeout=1))
        worker.observe_database_health(1, "generation", renewed_until="before")
        attempts = []

        def unavailable(*args, **kwargs):
            attempts.append(1)
            raise ConnectionError("write unavailable")

        database.save_prepared = unavailable
        database.reconcile_write = lambda *args, **kwargs: dict(committed=False)
        worker.submit(value, 1, "generation")
        with self.assertRaises(ValueError):
            worker.flush_fight(1, timeout=1)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(
            worker.observe_database_health(1, "generation", renewed_until="before")[
                "resumed"
            ],
            0,
        )
        self.assertEqual(
            worker.observe_database_health(
                1, "generation", renewed_until="healthy-one"
            )["resumed"],
            1,
        )
        with self.assertRaises(ValueError):
            worker.flush_fight(1, timeout=1)
        self.assertEqual(len(attempts), 6)
        for token in ("healthy-one", "healthy-two", "healthy-three"):
            self.assertEqual(
                worker.observe_database_health(1, "generation", renewed_until=token)[
                    "resumed"
                ],
                0,
            )
        self.assertEqual(len(attempts), 6)
        worker.observe_database_health(
            1, "generation", error=ConnectionError("renew failed")
        )
        database.save_prepared = original
        self.assertEqual(
            worker.observe_database_health(
                1, "generation", renewed_until="healthy-four"
            ),
            dict(epoch=2, resumed=1),
        )
        self.assertTrue(worker.flush_fight(1, timeout=1))
        self.assertEqual(len(attempts), 6)

    def test_health_witness_does_not_restart_another_owners_stale_writer(self):
        worker, database = self.worker(workers=1)
        database.release.set()
        original = database.save_prepared
        one, two = shared(), shared(2)
        worker.submit(one, 1, "owner-one")
        worker.submit(two, 2, "owner-two")
        self.assertTrue(worker.flush_fight(2, timeout=1))

        def fail(*args, **kwargs):
            raise ConnectionError("unavailable")

        database.save_prepared = fail
        database.reconcile_write = lambda *args, **kwargs: dict(committed=False)
        worker.submit(one, 1, "owner-one")
        with self.assertRaises(ValueError):
            worker.flush_fight(1, timeout=1)
        self.assertEqual(
            worker.observe_database_health(
                2, "owner-two", renewed_until="peer-healthy"
            ),
            dict(epoch=1, resumed=0),
        )
        self.assertIsNotNone(worker.states[1]["error"])
        database.save_prepared = original
        self.assertEqual(
            worker.observe_database_health(
                1, "owner-one", renewed_until="owner-healthy"
            ),
            dict(epoch=1, resumed=1),
        )
        self.assertTrue(worker.flush_fight(1, timeout=1))

    def test_query_timeout_does_not_create_database_availability_epoch(self):
        from psycopg.errors import QueryCanceled

        worker, database = self.worker(workers=1)

        def unavailable(*args, **kwargs):
            raise QueryCanceled("statement timeout")

        database.save_prepared = unavailable
        database.reconcile_write = lambda *args, **kwargs: dict(committed=False)
        worker.submit(shared(), 1, "generation")
        with self.assertRaises(ValueError):
            worker.flush_fight(1, timeout=1)
        worker.observe_database_health(1, "generation", error=QueryCanceled("timeout"))
        self.assertEqual(
            worker.observe_database_health(1, "generation", renewed_until="healthy"),
            dict(epoch=0, resumed=0),
        )
        self.assertIsNotNone(worker.states[1]["error"])

    def test_explicit_current_owner_recovery_deduplicates_request_receipt(self):
        from psycopg.errors import QueryCanceled

        worker, database = self.worker(workers=1)
        attempts = []

        def unavailable(*args, **kwargs):
            attempts.append(1)
            raise QueryCanceled("statement timeout")

        database.save_prepared = unavailable
        database.reconcile_write = lambda *args, **kwargs: dict(committed=False)
        worker.submit(shared(), 1, "generation")
        with self.assertRaises(ValueError):
            worker.flush_fight(1, timeout=1)
        with self.assertRaisesRegex(ValueError, "another writer"):
            worker.recover_pending(1, 1, "foreign", request_token=(13332, 10))
        self.assertTrue(
            worker.recover_pending(1, 1, "generation", request_token=(13332, 10))
        )
        with self.assertRaises(ValueError):
            worker.flush_fight(1, timeout=1)
        self.assertFalse(
            worker.recover_pending(1, 1, "generation", request_token=(13332, 10))
        )
        self.assertEqual(len(attempts), 6)

    def test_deferred_terminal_survives_registry_removal(self):
        worker, database = self.worker(capacity=1, workers=1)
        worker.submit(shared(), 1, "generation")
        self.assertTrue(database.started.wait(1))
        registry = {2: shared(2)}
        registry[2].fight.actors[6].hp = 35
        worker.submit(registry[2], 1, "generation", status="ended")
        # A later registry transition replaces canonical objects. The accepted
        # terminal source remains pinned until its receipt is persisted.
        registry[2].fight = shared(2).fight
        del registry[2]
        database.release.set()
        self.assertTrue(worker.flush_fight(2, timeout=1))
        self.assertIn(("save", 2, 35), database.calls)
        self.assertIn(("end", 2, "ended"), database.calls)

    def test_ambiguous_terminal_commit_does_not_repeat_save_or_end(self):
        worker, database = self.worker(workers=1)
        database.release.set()
        original = database.end

        def end(*args, **kwargs):
            original(*args, **kwargs)
            raise TimeoutError("terminal response lost")

        database.end = end
        database.reconcile_write = lambda *args, **kwargs: dict(
            committed=True, revision=2, terminal=True
        )
        value = shared()
        worker.submit(value, 1, "generation", status="ended")
        self.assertTrue(worker.flush_fight(1, timeout=1))
        self.assertEqual(database.calls, [("save", 1, 100), ("end", 1, "ended")])
        self.assertEqual(value.checkpoint_revision, 2)
        self.assertTrue(value.checkpoint_terminal)

    def test_settlement_terminal_receipt_supersedes_queued_old_snapshot(self):
        worker, database = self.worker(workers=1)
        fight = shared()

        def settled(*args, **kwargs):
            database.started.set()
            self.assertTrue(database.release.wait(1))
            self.assertTrue(kwargs["allow_terminal_receipt"])
            return dict(revision=9, terminal=True)

        database.save_prepared = settled
        worker.submit(fight, 1, "generation")
        self.assertTrue(database.started.wait(1))
        worker.submit(fight, 1, "generation", status="ended")
        database.release.set()
        self.assertTrue(worker.flush_fight(1, timeout=1))
        self.assertEqual(database.calls, [])
        self.assertTrue(fight.checkpoint_terminal)
        self.assertEqual(fight.checkpoint_revision, 9)
        self.assertTrue(worker.submit(fight, 1, "generation", status="ended")["replay"])

    def test_failure_does_not_commit_later_or_terminal(self):
        worker, database = self.worker()

        def fail(*args, **kwargs):
            raise ValueError("Foreign generation")

        database.save_prepared = fail
        worker.submit(shared(), 1, "generation")
        with self.assertRaisesRegex(ValueError, "checkpoint failed"):
            worker.flush_fight(1, timeout=1)
        self.assertEqual(database.calls, [])

    def test_reconnect_writer_takeover_fences_old_generation_and_preserves_peer(self):
        worker, database = self.worker(workers=1)
        value = shared()
        worker.submit(value, 1, "old-owner")
        self.assertTrue(database.started.wait(1))
        worker.submit(value, 2, "peer-generation")
        database.release.set()
        self.assertTrue(worker.flush_fight(1, timeout=1))

        persisted = []
        worker.takeover_writer(
            1,
            1,
            "old-owner",
            "new-owner",
            persist=lambda: persisted.append("durable-takeover"),
        )
        state = worker.states[1]
        self.assertEqual(state["owners"], {1: "new-owner", 2: "peer-generation"})
        self.assertEqual(persisted, ["durable-takeover"])
        with self.assertRaisesRegex(ValueError, "Stale checkpoint writer takeover"):
            worker.takeover_writer(1, 1, "old-owner", "newer-owner")
        self.assertEqual(state["owners"], {1: "new-owner", 2: "peer-generation"})
        with self.assertRaisesRegex(ValueError, "ownership changed"):
            worker.submit(value, 1, "old-owner")
        worker.submit(value, 1, "new-owner")
        self.assertTrue(worker.flush_fight(1, timeout=1))

    def test_reconnect_writer_requires_drain_and_rolls_back_failed_durable_fence(self):
        worker, database = self.worker(workers=1)
        value = shared()
        worker.submit(value, 1, "old-owner")
        self.assertTrue(database.started.wait(1))
        with self.assertRaisesRegex(ValueError, "requires a drained writer"):
            worker.takeover_writer(1, 1, "old-owner", "new-owner")
        database.release.set()
        self.assertTrue(worker.flush_fight(1, timeout=1))

        def failed_persist():
            raise ValueError("durable participant CAS rejected")

        with self.assertRaisesRegex(ValueError, "durable participant CAS rejected"):
            worker.takeover_writer(
                1, 1, "old-owner", "new-owner", persist=failed_persist
            )
        worker.submit(value, 1, "old-owner")
        with self.assertRaisesRegex(ValueError, "ownership changed"):
            worker.submit(value, 1, "new-owner")

    def test_real_reconnect_dispatch_drains_before_registry_takeover(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        adopt = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef) and node.name == "adopt_shared_duel"
        )
        drain = next(
            node
            for node in ast.walk(adopt)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "CHECKPOINT_WRITER.flush_for_takeover"
        )
        takeover = next(
            node
            for node in ast.walk(adopt)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "COMBAT_SESSIONS.registry.takeover"
        )
        worker_takeover = next(
            node
            for node in ast.walk(adopt)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "CHECKPOINT_WRITER.takeover_writer"
        )
        self.assertLess(drain.lineno, takeover.lineno)
        self.assertLess(worker_takeover.lineno, takeover.lineno)
