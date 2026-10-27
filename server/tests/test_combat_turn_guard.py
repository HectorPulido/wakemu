import threading
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server.combat_turn_guard import run_shared_npc_attempt


class SharedNpcGuardTests(unittest.TestCase):
    def setUp(self):
        self.shared = SimpleNamespace(
            lock=threading.RLock(),
            fight=SimpleNamespace(
                phase="active",
                current=SimpleNamespace(id=-7, controlled=False),
                turn_id=3,
            ),
            runtime=SimpleNamespace(awaiting_ack=None, pending=[]),
        )
        self.now = 10.0
        self.failures = []

    def run_attempt(self, callback):
        return run_shared_npc_attempt(
            self.shared,
            callback,
            lambda identity, error: self.failures.append((identity, type(error))),
            clock=lambda: self.now,
        )

    def test_preparation_failure_preserves_state_and_backs_off_until_retry(self):
        original = (self.shared.fight, self.shared.runtime)

        def fail():
            raise AttributeError("Missing source field")

        self.assertFalse(self.run_attempt(fail))
        self.assertEqual((self.shared.fight, self.shared.runtime), original)
        self.assertEqual(self.failures, [((-7, 3), AttributeError)])
        self.assertFalse(self.run_attempt(lambda: self.fail("Retry before cooldown")))
        self.now = 12
        calls = []
        self.assertTrue(self.run_attempt(lambda: calls.append("actual-runner")))
        self.assertEqual(calls, ["actual-runner"])
        self.assertIsNone(self.shared.native_npc_retry)

    def test_new_turn_has_no_stale_retry_delay_and_ack_blocks_attempt(self):
        self.shared.native_npc_retry = ((-7, 2), 100)
        self.assertTrue(self.run_attempt(lambda: None))
        self.shared.runtime.awaiting_ack = 3
        self.assertFalse(self.run_attempt(lambda: self.fail("Pending real ACK")))

    def test_queued_or_running_background_work_skips_sdk_loading_until_finished(self):
        from wakfu_server.combat_background_work import BackgroundWork

        work = BackgroundWork(max_jobs=2, max_workers=1)
        occupied, release = threading.Event(), threading.Event()
        calls = []
        try:
            work.submit("occupy", lambda: (occupied.set(), release.wait(2)))
            self.assertTrue(occupied.wait(2))
            key = ("native-ai", id(self.shared))
            self.assertEqual(
                work.submit(key, lambda: calls.append("worker")), "submitted"
            )
            with patch("wakfu_server.combat_turn_guard.NATIVE_WORK", work):
                self.assertFalse(
                    self.run_attempt(lambda: self.fail("SDK loaded for queued job"))
                )
                release.set()
                work.executor.shutdown(wait=True)
                self.assertEqual(calls, ["worker"])
                self.assertTrue(self.run_attempt(lambda: calls.append("next-turn")))
        finally:
            release.set()
            work.executor.shutdown(wait=True)
            work.shutdown()

    def test_active_claim_skips_loader_and_retries_after_claim_cleanup(self):
        self.shared.native_ai_turn_claim = (-7, 3, "actual-worker")
        self.assertFalse(self.run_attempt(lambda: self.fail("Duplicate SDK load")))
        del self.shared.native_ai_turn_claim
        self.assertTrue(self.run_attempt(lambda: None))

    def test_busy_fight_does_not_block_reader_or_drop_next_attempt(self):
        occupied, release = threading.Event(), threading.Event()

        def hold_fight():
            with self.shared.lock:
                occupied.set()
                release.wait(2)

        worker = threading.Thread(target=hold_fight)
        worker.start()
        self.assertTrue(occupied.wait(2))
        try:
            self.assertFalse(self.run_attempt(lambda: self.fail("Fight is busy")))
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertTrue(self.run_attempt(lambda: None))

    def test_transport_failure_propagates_without_gameplay_retry(self):
        def disconnected():
            raise BrokenPipeError("closed transport")

        with self.assertRaises(BrokenPipeError):
            self.run_attempt(disconnected)
        self.assertEqual(self.failures, [])
        self.assertFalse(hasattr(self.shared, "native_npc_retry"))

    def test_concurrent_attempt_has_one_claim_and_failure_releases_it(self):
        entered, release = threading.Event(), threading.Event()

        def fail():
            entered.set()
            self.assertTrue(release.wait(2))
            raise AttributeError("missing source")

        worker = threading.Thread(target=lambda: self.run_attempt(fail))
        worker.start()
        self.assertTrue(entered.wait(2))
        try:
            self.assertFalse(self.run_attempt(lambda: self.fail("Duplicate runner")))
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertIsNone(self.shared.native_npc_retry_claim)
        self.assertEqual(len(self.failures), 1)
        self.now = 12
        self.assertTrue(self.run_attempt(lambda: None))
        self.assertIsNone(self.shared.native_npc_retry_claim)

    def test_diagnostic_failure_preserves_retry_and_releases_claim(self):
        def preparation():
            raise AttributeError("missing source")

        def diagnostic(*args):
            raise RuntimeError("diagnostic formatter failed")

        result = run_shared_npc_attempt(
            self.shared, preparation, diagnostic, clock=lambda: self.now
        )
        self.assertFalse(result)
        self.assertIsNone(self.shared.native_npc_retry_claim)
        self.assertEqual(self.shared.native_npc_retry, ((-7, 3), 12.0))
        self.assertEqual(
            self.shared.native_npc_retry_diagnostic_failure,
            dict(
                actor_id=-7,
                turn_id=3,
                original_error_type="AttributeError",
                diagnostic_error_type="RuntimeError",
            ),
        )

    def test_diagnostic_transport_failure_still_propagates(self):
        def preparation():
            raise AttributeError("missing source")

        def diagnostic(*args):
            raise BrokenPipeError("closed transport")

        with self.assertRaises(BrokenPipeError):
            run_shared_npc_attempt(
                self.shared, preparation, diagnostic, clock=lambda: self.now
            )
        self.assertIsNone(self.shared.native_npc_retry_claim)

    def test_inflight_claim_survives_actual_ai_shared_context_encoding(self):
        ai_root = str(Path(__file__).resolve().parents[1] / "ai-service")
        if ai_root not in sys.path:
            sys.path.insert(0, ai_root)
        from wakfu_ai.context.native_context import encode_bytes

        def actual_metadata_boundary():
            metadata = dict(vars(self.shared))
            metadata["fight"] = dict(nativeReference="runtime.fight")
            metadata["runtime"] = dict(nativeReference="runtime")
            metadata["lock"] = dict(
                module=type(self.shared.lock).__module__,
                name=type(self.shared.lock).__qualname__,
                ownerThread=True,
            )
            token = self.shared.native_npc_retry_claim
            self.assertIsInstance(token, str)
            self.assertIn(token.encode(), encode_bytes(metadata))

        self.assertTrue(self.run_attempt(actual_metadata_boundary))
        self.assertEqual(self.failures, [])
        self.assertIsNone(self.shared.native_npc_retry_claim)
