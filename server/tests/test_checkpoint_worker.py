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

    def test_capacity_and_replaced_generation_rejected(self):
        worker, database = self.worker(capacity=1)
        one = shared()
        worker.submit(one, 1, "generation")
        self.assertTrue(database.started.wait(1))
        with self.assertRaisesRegex(ValueError, "capacity"):
            worker.submit(shared(2), 1, "generation")
        with self.assertRaisesRegex(ValueError, "ownership"):
            worker.submit(one, 1, "replacement")

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
            and ast.unparse(node.func) == "CHECKPOINT_WRITER.flush_fight"
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
