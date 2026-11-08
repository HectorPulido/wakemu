"""Idle worker lifetime checks; no catalog, database or gameplay services."""
import gc
from threading import RLock
from types import SimpleNamespace
import unittest
import weakref

from wakfu_server.checkpoint_worker import CheckpointWorker


class Owner:
    pass


def make_shared():
    fight = Owner()
    fight.id = 77
    fight.actors = {6: SimpleNamespace(hp=80, controlled=True)}
    runtime = Owner()
    runtime.action_id = runtime.native_action_id = runtime.round = 1
    runtime.awaiting_ack = None
    runtime.duration = 30
    runtime.fight = fight
    shared = Owner()
    shared.fight, shared.runtime = fight, runtime
    shared.lock = RLock()
    shared.checkpoint_revision = None
    shared.checkpoint_terminal = False
    return shared


class Persistence:
    def __init__(self, fail=False):
        self.fail = fail
        self.revision = None
        self.calls = []

    def save_prepared(
        self, account, generation, fight, state, *, expected_revision, **kwargs
    ):
        if self.fail:
            raise ConnectionError("test storage offline")
        if expected_revision != self.revision:
            raise AssertionError("CAS revision changed")
        self.revision = (self.revision or 0) + 1
        self.calls.append(("save", fight.id, state["hp"]))
        return self.revision

    def reconcile_write(self, *args, **kwargs):
        return dict(committed=False, terminal=False, revision=self.revision)

    def end(
        self, account, generation, identity, *, expected_revision, status, **kwargs
    ):
        if expected_revision != self.revision:
            raise AssertionError("Terminal CAS revision changed")
        self.revision += 1
        self.calls.append(("end", identity, status))
        return self.revision


class CheckpointIdleReleaseTests(unittest.TestCase):
    def worker(self, persistence):
        worker = CheckpointWorker(
            persistence,
            workers=1,
            serializer=lambda fight, runtime: dict(hp=fight.actors[6].hp),
        )
        self.addCleanup(worker.close, timeout=2)
        return worker

    def wait_idle(self, worker, *, failed=False):
        with worker.condition:
            self.assertTrue(
                worker.condition.wait_for(
                    lambda: not worker.inflight
                    and 77 in worker.states
                    and (
                        worker.states[77]["error"] is not None
                        if failed
                        else worker.states[77]["committed"]
                        == worker.states[77]["sequence"]
                    ),
                    timeout=2,
                )
            )

    def submit_and_release_external_owners(self, worker):
        shared = make_shared()
        references = tuple(
            weakref.ref(value) for value in (shared, shared.fight, shared.runtime)
        )
        worker.submit(shared, 1, "test-generation", status="finished")
        return references

    def test_successful_terminal_job_releases_graph_while_worker_stays_idle(self):
        persistence = Persistence()
        worker = self.worker(persistence)
        references = self.submit_and_release_external_owners(worker)
        self.wait_idle(worker)
        gc.collect()
        self.assertTrue(worker.threads[0].is_alive())
        self.assertFalse(worker.pending)
        self.assertTrue(all(reference() is None for reference in references))
        self.assertEqual(persistence.calls, [("save", 77, 80), ("end", 77, "finished")])

    def test_failed_terminal_intent_survives_until_explicit_retry_then_releases(self):
        persistence = Persistence(fail=True)
        worker = self.worker(persistence)
        references = self.submit_and_release_external_owners(worker)
        self.wait_idle(worker, failed=True)
        gc.collect()
        self.assertTrue(all(reference() is not None for reference in references))
        with worker.condition:
            self.assertIs(worker.pending[77].shared, references[0]())
            self.assertEqual(worker.pending[77].status, "finished")
        persistence.fail = False
        self.assertTrue(worker.retry_failed(77, 1, "test-generation"))
        self.wait_idle(worker)
        gc.collect()
        self.assertTrue(worker.threads[0].is_alive())
        self.assertFalse(worker.pending)
        self.assertTrue(all(reference() is None for reference in references))
        self.assertEqual(persistence.calls, [("save", 77, 80), ("end", 77, "finished")])


if __name__ == "__main__":
    unittest.main()
