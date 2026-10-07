"""Retry-safe native-search negotiation and its real HTTP endpoint."""
from copy import deepcopy
from http.client import HTTPConnection
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.context.native_context import encode
from wakfu_ai.planning.query_search import search as real_search
from wakfu_ai.planning.query_sessions import QuerySessions
from wakfu_ai.context.context_store import ContextStore
from wakfu_ai.bridge.world_bridge import _json_bytes


class FakeStore:
    def __init__(self):
        self.graph = encode({"complete": True, "future": [1, 2, 3]})
        self.root = "a" * 64
        self.catalog = "b" * 64

    def manifest(self, digest):
        if digest != self.catalog:
            raise ValueError("Unknown catalogue")
        return {"complete": True}

    def seal_manifest(self, digest):
        return self.manifest(digest)

    def json(self, digest):
        if digest != self.root:
            raise ValueError("Unknown graph")
        return deepcopy(self.graph)


def search_exchange(payload, store, *, clock, root_graph=None):
    response = yield {
        "id": "query-1",
        "operation": "state",
        "state": payload["rootState"],
    }
    if response.get("supported"):
        action = {"type": "move", "path": [[1, 0, 0]]}
    else:
        action = {"type": "end_turn"}
    return {
        "protocol": 3,
        "requestId": payload["requestId"],
        "sourceKey": payload["sourceKey"],
        "rootState": payload["rootState"],
        "action": action,
    }


class QuerySessionsTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.sessions = QuerySessions()
        self.payload = dict(
            protocol=3,
            requestId="request-1",
            sourceKey="c" * 64,
            catalogManifest=self.store.catalog,
            rootState=self.store.root,
            actor_id=101,
            policy={},
            root={
                "key": self.store.root,
                "nativeContext": self.store.root,
                "currentId": 101,
                "phase": "active",
                "actors": [],
            },
        )
        self.search_patch = patch(
            "wakfu_ai.planning.query_sessions.search", side_effect=search_exchange
        )
        self.search_patch.start()
        self.addCleanup(self.search_patch.stop)

    def start(self, payload=None):
        return self.sessions.decide(payload or self.payload, self.store)

    def test_identical_initialization_and_response_replay_are_idempotent(self):
        first = self.start()
        self.assertEqual(first["status"], "query")
        self.assertEqual(self.start(deepcopy(self.payload)), first)

        continuation = dict(
            requestId="request-1",
            sourceKey="c" * 64,
            response={"id": "query-1", "supported": True, "result": {"key": "child"}},
        )
        decided = self.sessions.decide(continuation, self.store)
        self.assertEqual(decided["status"], "decided")
        self.assertEqual(decided["decision"]["action"]["type"], "move")
        self.assertEqual(
            self.sessions.decide(deepcopy(continuation), self.store), decided
        )

    def test_contradictory_replays_and_changed_initialization_are_rejected(self):
        self.start()
        changed_init = dict(self.payload, policy={"weights": {"future": 8}})
        with self.assertRaisesRegex(
            ValueError, "Conflicting native search initialization"
        ):
            self.start(changed_init)
        continuation = dict(
            requestId="request-1",
            sourceKey="c" * 64,
            response={"id": "query-1", "supported": True, "result": {"key": "one"}},
        )
        self.sessions.decide(continuation, self.store)
        contradictory = deepcopy(continuation)
        contradictory["response"]["result"]["key"] = "two"
        with self.assertRaisesRegex(ValueError, "Conflicting repeated"):
            self.sessions.decide(contradictory, self.store)

    def test_source_mismatch_and_foreign_or_out_of_order_continuations_fail(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "source identity changed"):
            self.sessions.decide(dict(self.payload, sourceKey="d" * 64), self.store)
        foreign = dict(
            requestId="request-1",
            sourceKey="c" * 64,
            response={"id": "foreign-query", "supported": True},
        )
        with self.assertRaisesRegex(ValueError, "Out-of-order"):
            self.sessions.decide(foreign, self.store)
        foreign_session = dict(
            requestId="missing-session",
            sourceKey="c" * 64,
            response={"id": "query-1", "supported": True},
        )
        with self.assertRaisesRegex(ValueError, "Unknown or expired"):
            self.sessions.decide(foreign_session, self.store)

    def test_expiry_closes_generator_and_releases_capacity(self):
        current = [10.0]
        closed = []

        def tracked_search(payload, store, *, clock, root_graph=None):
            try:
                yield {
                    "id": "query-1",
                    "operation": "state",
                    "state": payload["rootState"],
                }
                return {
                    "protocol": 3,
                    "requestId": payload["requestId"],
                    "sourceKey": payload["sourceKey"],
                    "rootState": payload["rootState"],
                    "action": {"type": "end_turn"},
                }
            finally:
                closed.append(payload["requestId"])

        with patch(
            "wakfu_ai.planning.query_sessions.search", side_effect=tracked_search
        ):
            sessions = QuerySessions(capacity=1, ttl=5, clock=lambda: current[0])
            sessions.decide(self.payload, self.store)
            second = dict(self.payload, requestId="request-2", sourceKey="d" * 64)
            with self.assertRaisesRegex(ValueError, "capacity"):
                sessions.decide(second, self.store)
            current[0] = 15.01
            reply = sessions.decide(second, self.store)
            self.assertEqual(reply["status"], "query")
            self.assertEqual(closed, ["request-1"])
            self.assertEqual(set(sessions.sessions), {"request-2"})

    def test_cancel_releases_capacity_and_requires_matching_source(self):
        sessions = QuerySessions(capacity=1)
        sessions.decide(self.payload, self.store)
        with self.assertRaisesRegex(ValueError, "source changed"):
            sessions.cancel(dict(requestId="request-1", sourceKey="d" * 64))
        self.assertIn("request-1", sessions.sessions)
        cancellation = dict(requestId="request-1", sourceKey="c" * 64)
        self.assertEqual(sessions.cancel(cancellation), sessions.cancel(cancellation))
        second = dict(self.payload, requestId="request-2")
        self.assertEqual(sessions.decide(second, self.store)["status"], "query")
        self.assertEqual(set(sessions.sessions), {"request-2"})

    def test_completed_turns_do_not_consume_active_session_capacity(self):
        sessions = QuerySessions(capacity=1)
        for index in range(5):
            payload = dict(
                self.payload,
                requestId="completed-%s" % index,
                sourceKey=("%x" % index) * 64,
            )
            query = sessions.decide(payload, self.store)
            self.assertEqual(query["status"], "query")
            completed = sessions.decide(
                dict(
                    requestId=payload["requestId"],
                    sourceKey=payload["sourceKey"],
                    response={
                        "id": "query-1",
                        "supported": True,
                        "result": {"key": "child-%s" % index},
                    },
                ),
                self.store,
            )
            self.assertEqual(completed["status"], "decided")
        self.assertEqual(len(sessions.sessions), 5)


class QuerySessionsConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.sessions = QuerySessions(capacity=4)
        self.payload = dict(
            protocol=3,
            requestId="concurrent-1",
            sourceKey="c" * 64,
            catalogManifest=self.store.catalog,
            rootState=self.store.root,
            actor_id=101,
            policy={},
            root={
                "key": self.store.root,
                "nativeContext": self.store.root,
                "currentId": 101,
                "phase": "active",
                "actors": [],
            },
        )
        self.search_patch = patch(
            "wakfu_ai.planning.query_sessions.search", side_effect=search_exchange
        )
        self.search_patch.start()
        self.addCleanup(self.search_patch.stop)

    @staticmethod
    def payload_for(payload, request_id, source, catalog=None):
        return dict(
            payload,
            requestId=request_id,
            sourceKey=source,
            catalogManifest=catalog or payload["catalogManifest"],
        )

    def test_slow_catalogue_initialization_does_not_block_other_encounter(self):
        entered, release = threading.Event(), threading.Event()

        class SlowStore(FakeStore):
            def manifest(inner, digest):
                if digest == "a" * 64:
                    entered.set()
                    if not release.wait(3):
                        raise AssertionError("slow catalogue was not released")
                return {"complete": True}

        store = SlowStore()
        sessions = QuerySessions(capacity=2)
        first = self.payload_for(self.payload, "slow-a", "1" * 64, "a" * 64)
        second = self.payload_for(self.payload, "fast-b", "2" * 64, "d" * 64)
        # Both manifest hashes are accepted by the fake provider; only A waits.
        replies, failures = [], []

        def run_a():
            try:
                replies.append(sessions.decide(first, store))
            except Exception as error:
                failures.append(error)

        worker = threading.Thread(target=run_a)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(sessions.decide, second, store)
                reply_b = future.result(timeout=1)
            self.assertEqual(reply_b["status"], "query")
            self.assertTrue(worker.is_alive())
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(replies[0]["status"], "query")

    def test_slow_root_graph_loading_does_not_block_other_encounter(self):
        entered, release = threading.Event(), threading.Event()

        class SlowStore(FakeStore):
            root_a = "b" * 64
            root_b = "d" * 64

            def json(inner, digest):
                if digest == inner.root_a:
                    entered.set()
                    if not release.wait(3):
                        raise AssertionError("root graph was not released")
                if digest not in (inner.root_a, inner.root_b):
                    raise ValueError("Unknown graph")
                return deepcopy(inner.graph)

        store = SlowStore()
        sessions = QuerySessions(capacity=2)
        first = dict(
            self.payload_for(self.payload, "graph-a", "a" * 64), rootState=store.root_a
        )
        first["root"] = dict(
            first["root"], key=store.root_a, nativeContext=store.root_a
        )
        second = dict(
            self.payload_for(self.payload, "graph-b", "b" * 64), rootState=store.root_b
        )
        second["root"] = dict(
            second["root"], key=store.root_b, nativeContext=store.root_b
        )
        failures = []
        worker = threading.Thread(
            target=lambda: self._capture(failures, sessions.decide, first, store)
        )
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            with ThreadPoolExecutor(max_workers=1) as pool:
                reply = pool.submit(sessions.decide, second, store).result(timeout=1)
            self.assertEqual(reply["status"], "query")
            self.assertTrue(worker.is_alive())
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])

    def test_initializing_placeholder_reserves_active_capacity(self):
        entered, release = threading.Event(), threading.Event()

        class SlowStore(FakeStore):
            def manifest(inner, digest):
                entered.set()
                if not release.wait(3):
                    raise AssertionError("initialization gate was not released")
                return {"complete": True}

        sessions = QuerySessions(capacity=1)
        payload = self.payload_for(self.payload, "reserved-a", "3" * 64)
        other = self.payload_for(self.payload, "reserved-b", "4" * 64)
        errors = []
        worker = threading.Thread(
            target=lambda: self._capture(errors, sessions.decide, payload, SlowStore())
        )
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaisesRegex(ValueError, "capacity"):
                sessions.decide(other, self.store)
            self.assertEqual(set(sessions.sessions), {"reserved-a"})
            self.assertTrue(sessions.sessions["reserved-a"]["initializing"])
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])

    def test_creator_owns_placeholder_lock_before_same_id_retry_can_inspect(self):
        reserved, release_creator = threading.Event(), threading.Event()
        sessions = QuerySessions(capacity=2)
        initial = self.payload_for(self.payload, "creator-race", "e" * 64)
        replies, errors = [], []
        original_reserve = sessions._reserve

        def pause_creator(identity, source, payload):
            result = original_reserve(identity, source, payload)
            if identity == "creator-race" and result[1]:
                reserved.set()
                if not release_creator.wait(3):
                    raise AssertionError("creator reservation was not released")
            return result

        sessions._reserve = pause_creator
        creator = threading.Thread(
            target=lambda: self._capture(
                errors, lambda: replies.append(sessions.decide(initial, self.store))
            )
        )
        creator.start()
        try:
            self.assertTrue(reserved.wait(2))
            retry = threading.Thread(
                target=lambda: self._capture(
                    errors,
                    lambda: replies.append(
                        sessions.decide(deepcopy(initial), self.store)
                    ),
                )
            )
            retry.start()
            deadline = time.monotonic() + 2
            while (
                sessions.sessions["creator-race"]["users"] < 2
                and time.monotonic() < deadline
            ):
                time.sleep(0.001)
            self.assertEqual(sessions.sessions["creator-race"]["users"], 2)
            self.assertTrue(creator.is_alive())
            self.assertTrue(retry.is_alive())
        finally:
            release_creator.set()
            creator.join(3)
            if "retry" in locals():
                retry.join(3)
        self.assertFalse(creator.is_alive())
        self.assertFalse(retry.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(replies, [replies[0], replies[0]])

    def test_concurrent_duplicate_response_is_serial_and_idempotent(self):
        entered, release = threading.Event(), threading.Event()
        sent = []

        def blocked_search(payload, store, *, clock, root_graph=None):
            try:
                response = yield {
                    "id": "query-1",
                    "operation": "state",
                    "state": payload["rootState"],
                }
                sent.append(response)
                entered.set()
                if not release.wait(3):
                    raise AssertionError("search generator was not released")
                return dict(
                    protocol=3,
                    requestId=payload["requestId"],
                    sourceKey=payload["sourceKey"],
                    rootState=payload["rootState"],
                    action={"type": "end_turn"},
                )
            finally:
                pass

        sessions = QuerySessions()
        continuation = dict(
            requestId="same-session",
            sourceKey="5" * 64,
            response={"id": "query-1", "supported": True, "result": {"key": "child"}},
        )
        initial = self.payload_for(self.payload, "same-session", "5" * 64)
        with patch(
            "wakfu_ai.planning.query_sessions.search", side_effect=blocked_search
        ):
            self.assertEqual(sessions.decide(initial, self.store)["status"], "query")
            first_result, second_result = [], []
            first_errors = []
            first = threading.Thread(
                target=lambda: self._capture(
                    first_errors,
                    lambda: first_result.append(
                        sessions.decide(continuation, self.store)
                    ),
                )
            )
            first.start()
            try:
                self.assertTrue(entered.wait(2))
                second_started = threading.Event()

                def duplicate():
                    second_started.set()
                    second_result.append(
                        sessions.decide(deepcopy(continuation), self.store)
                    )

                second = threading.Thread(target=duplicate)
                second.start()
                self.assertTrue(second_started.wait(2))
                deadline = time.monotonic() + 2
                while (
                    sessions.sessions["same-session"]["users"] < 2
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.001)
                self.assertEqual(sessions.sessions["same-session"]["users"], 2)
                self.assertEqual(second_result, [])
                # A blocked resume owns only this session's lock. A different
                # encounter must still initialize and produce its query.
                other = self.payload_for(self.payload, "independent-session", "f" * 64)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    independent = pool.submit(
                        sessions.decide, other, self.store
                    ).result(timeout=1)
                self.assertEqual(independent["status"], "query")
                self.assertTrue(first.is_alive())
            finally:
                release.set()
                first.join(3)
                if "second" in locals():
                    second.join(3)
                self.assertEqual(first_errors, [])
        self.assertEqual(sent, [continuation["response"]])
        self.assertEqual(first_result, second_result)
        self.assertEqual(first_result[0]["status"], "decided")

    def test_failed_resume_cannot_close_replacement_session(self):
        send_entered, release_send = threading.Event(), threading.Event()
        cleanup_entered, release_cleanup = threading.Event(), threading.Event()
        errors = []
        search_calls = []
        sessions = QuerySessions(capacity=2)
        original_close_all = sessions._close_all

        def failing_search(payload, store, *, clock, root_graph=None):
            try:
                yield {
                    "id": "query-1",
                    "operation": "state",
                    "state": payload["rootState"],
                }
                send_entered.set()
                if not release_send.wait(3):
                    raise AssertionError("failed response was not released")
                raise RuntimeError("fake search failure")
            finally:
                pass

        def factory(payload, store, *, clock, root_graph=None):
            search_calls.append(payload["requestId"])
            if len(search_calls) == 1:
                return failing_search(payload, store, clock=clock)
            return search_exchange(payload, store, clock=clock)

        def delayed_close(entries):
            if any(entry.get("source") == "a" * 64 for entry in entries):
                cleanup_entered.set()
                if not release_cleanup.wait(3):
                    raise AssertionError("failed-session cleanup was not released")
            original_close_all(entries)

        initial = self.payload_for(self.payload, "replace-after-failure", "a" * 64)
        continuation = dict(
            requestId="replace-after-failure",
            sourceKey="a" * 64,
            response={"id": "query-1", "supported": True, "result": {}},
        )
        with patch("wakfu_ai.planning.query_sessions.search", side_effect=factory):
            sessions._close_all = delayed_close
            self.assertEqual(sessions.decide(initial, self.store)["status"], "query")
            first = threading.Thread(
                target=lambda: self._capture(
                    errors, sessions.decide, continuation, self.store
                )
            )
            first.start()
            try:
                self.assertTrue(send_entered.wait(2))
                second = threading.Thread(
                    target=lambda: self._capture(
                        errors, sessions.decide, deepcopy(continuation), self.store
                    )
                )
                second.start()
                deadline = time.monotonic() + 2
                old_entry = sessions.sessions["replace-after-failure"]
                while old_entry["users"] < 2 and time.monotonic() < deadline:
                    time.sleep(0.001)
                self.assertEqual(old_entry["users"], 2)
                release_send.set()
                self.assertTrue(cleanup_entered.wait(2))
                self.assertNotIn("replace-after-failure", sessions.sessions)

                # The failing generation is retired, so the same source/request
                # may be initialized again while old leased retries still wait.
                replacement = sessions.decide(initial, self.store)
                self.assertEqual(replacement["status"], "query")
                new_entry = sessions.sessions["replace-after-failure"]
                self.assertIsNot(new_entry, old_entry)
            finally:
                release_send.set()
                release_cleanup.set()
                first.join(3)
                if "second" in locals():
                    second.join(3)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(len(errors), 2)
        self.assertEqual(
            search_calls, ["replace-after-failure", "replace-after-failure"]
        )
        self.assertIs(sessions.sessions["replace-after-failure"], new_entry)
        self.assertFalse(new_entry["removed"])
        sessions.cancel(dict(requestId="replace-after-failure", sourceKey="a" * 64))

    def test_cancel_waits_for_active_generator_and_never_closes_it_in_flight(self):
        entered, release = threading.Event(), threading.Event()
        closed, cancel_started = [], threading.Event()

        def blocked_search(payload, store, *, clock, root_graph=None):
            try:
                response = yield {
                    "id": "query-1",
                    "operation": "state",
                    "state": payload["rootState"],
                }
                entered.set()
                if not release.wait(3):
                    raise AssertionError("search generator was not released")
                yield {
                    "id": "query-2",
                    "operation": "state",
                    "state": payload["rootState"],
                }
                return dict(
                    protocol=3,
                    requestId=payload["requestId"],
                    sourceKey=payload["sourceKey"],
                    rootState=payload["rootState"],
                    action={"type": "end_turn"},
                )
            finally:
                closed.append("closed")

        sessions = QuerySessions()
        initial = self.payload_for(self.payload, "cancel-active", "6" * 64)
        continuation = dict(
            requestId="cancel-active",
            sourceKey="6" * 64,
            response={"id": "query-1", "supported": True, "result": {}},
        )
        with patch(
            "wakfu_ai.planning.query_sessions.search", side_effect=blocked_search
        ):
            sessions.decide(initial, self.store)
            worker_errors = []
            worker = threading.Thread(
                target=lambda: self._capture(
                    worker_errors, sessions.decide, continuation, self.store
                )
            )
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                result = []

                def cancel():
                    cancel_started.set()
                    result.append(
                        sessions.cancel(
                            dict(requestId="cancel-active", sourceKey="6" * 64)
                        )
                    )

                cancel_worker = threading.Thread(target=cancel)
                cancel_worker.start()
                self.assertTrue(cancel_started.wait(2))
                deadline = time.monotonic() + 2
                while (
                    sessions.sessions["cancel-active"]["users"] < 2
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.001)
                self.assertEqual(closed, [])
                self.assertEqual(result, [])
            finally:
                release.set()
                worker.join(3)
                if "cancel_worker" in locals():
                    cancel_worker.join(3)
        self.assertEqual(closed, ["closed"])
        self.assertEqual(result[0]["cancelled"], True)
        self.assertEqual(worker_errors, [])
        self.assertNotIn("cancel-active", sessions.sessions)

    def test_expiry_does_not_close_generator_while_an_exchange_is_active(self):
        now = [10.0]
        entered, release = threading.Event(), threading.Event()
        closed = []

        def blocked_search(payload, store, *, clock, root_graph=None):
            try:
                response = yield {
                    "id": "query-1",
                    "operation": "state",
                    "state": payload["rootState"],
                }
                entered.set()
                if not release.wait(3):
                    raise AssertionError("search generator was not released")
                yield {
                    "id": "query-2",
                    "operation": "state",
                    "state": payload["rootState"],
                }
                return dict(
                    protocol=3,
                    requestId=payload["requestId"],
                    sourceKey=payload["sourceKey"],
                    rootState=payload["rootState"],
                    action={"type": "end_turn"},
                )
            finally:
                closed.append("closed")

        sessions = QuerySessions(capacity=2, ttl=5, clock=lambda: now[0])
        initial = self.payload_for(self.payload, "expire-active", "7" * 64)
        continuation = dict(
            requestId="expire-active",
            sourceKey="7" * 64,
            response={"id": "query-1", "supported": True, "result": {}},
        )
        with patch(
            "wakfu_ai.planning.query_sessions.search", side_effect=blocked_search
        ):
            sessions.decide(initial, self.store)
            worker_errors = []
            worker = threading.Thread(
                target=lambda: self._capture(
                    worker_errors, sessions.decide, continuation, self.store
                )
            )
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                now[0] = 20.0
                # This request reaps only idle entries. The in-use session is
                # leased and its generator must remain untouched.
                self.assertEqual(
                    sessions.cancel(dict(requestId="unrelated", sourceKey="8" * 64))[
                        "cancelled"
                    ],
                    True,
                )
                self.assertEqual(closed, [])
                self.assertIn("expire-active", sessions.sessions)
            finally:
                release.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(worker_errors, [])
        # Expiry after the operation becomes idle closes the suspended search.
        now[0] = 26.0
        expired_payload = dict(
            requestId="expire-active",
            sourceKey="7" * 64,
            response={"id": "stale", "supported": True},
        )
        with self.assertRaisesRegex(ValueError, "Unknown or expired"):
            sessions.decide(expired_payload, self.store)
        self.assertEqual(closed, ["closed"])

    @staticmethod
    def _capture(errors, function, *args):
        try:
            function(*args)
        except Exception as error:
            errors.append(error)

    def test_failed_initialization_releases_capacity_for_retry(self):
        class FailingStore(FakeStore):
            fail = True

            def manifest(inner, digest):
                if inner.fail:
                    raise ValueError("catalogue failed")
                return {"complete": True}

        store = FailingStore()
        sessions = QuerySessions(capacity=1)
        first = self.payload_for(self.payload, "init-fails", "9" * 64)
        with self.assertRaisesRegex(ValueError, "catalogue failed"):
            sessions.decide(first, store)
        self.assertNotIn("init-fails", sessions.sessions)
        store.fail = False
        second = self.payload_for(self.payload, "init-retry", "a" * 64)
        self.assertEqual(sessions.decide(second, store)["status"], "query")

    def test_expiry_close_error_does_not_leak_replacement_capacity(self):
        now = [0.0]

        def bad_close(payload, store, *, clock, root_graph=None):
            try:
                yield {
                    "id": "query-1",
                    "operation": "state",
                    "state": payload["rootState"],
                }
            finally:
                raise RuntimeError("cleanup callback failed")

        sessions = QuerySessions(capacity=1, ttl=1, clock=lambda: now[0])
        first = self.payload_for(self.payload, "bad-close", "b" * 64)
        second = self.payload_for(self.payload, "after-bad-close", "c" * 64)
        with patch("wakfu_ai.planning.query_sessions.search", side_effect=bad_close):
            self.assertEqual(sessions.decide(first, self.store)["status"], "query")
            now[0] = 2.0
            # Reaping closes the old generator, whose finally raises. That
            # cleanup error must not escape after reserving the new placeholder.
            with patch(
                "wakfu_ai.planning.query_sessions.search", side_effect=search_exchange
            ):
                reply = sessions.decide(second, self.store)
        self.assertEqual(reply["status"], "query")
        self.assertEqual(set(sessions.sessions), {"after-bad-close"})
        self.assertEqual(sessions.sessions["after-bad-close"]["users"], 0)

    def test_session_ttl_must_be_finite(self):
        for ttl in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(ttl=ttl), self.assertRaisesRegex(ValueError, "TTL"):
                QuerySessions(ttl=ttl)


class QuerySessionsRootGraphTests(unittest.TestCase):
    def test_real_search_reuses_verified_root_graph_but_new_cas_read_rejects_corruption(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            store = ContextStore(temporary)
            fight = SimpleNamespace(walkable=frozenset({(0, 0, 0)}), edges=frozenset())
            graph = encode({"runtime": SimpleNamespace(fight=fight)})
            graph_bytes = _json_bytes(graph)
            root_digest = hashlib.sha256(graph_bytes).hexdigest()
            store.put(root_digest, len(graph_bytes), 0, graph_bytes)
            metadata = encode({"spells": []})
            metadata_bytes = _json_bytes(metadata)
            metadata_digest = hashlib.sha256(metadata_bytes).hexdigest()
            store.put(metadata_digest, len(metadata_bytes), 0, metadata_bytes)
            manifest_bytes = _json_bytes(
                {"format": "wakfu-complete-context-1", "entries": []}
            )
            manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
            store.put(manifest_digest, len(manifest_bytes), 0, manifest_bytes)
            original_json = store.json
            reads = []

            def tracked_json(digest):
                reads.append(digest)
                return original_json(digest)

            store.json = tracked_json
            root = dict(
                key=root_digest,
                nativeContext=root_digest,
                actors=[
                    dict(
                        id=1,
                        team=1,
                        controlled=False,
                        position=[0, 0, 0],
                        hp=10,
                        max_hp=10,
                        ap=1,
                        mp=0,
                        wp=0,
                        armor=0,
                    )
                ],
                phase="active",
                currentId=1,
                turnId=5,
                stateRevision=9,
            )
            payload = dict(
                protocol=3,
                requestId="root-reuse",
                sourceKey="a" * 64,
                catalogManifest=manifest_digest,
                rootState=root_digest,
                root=root,
                actor_id=1,
                policy={},
            )
            sessions = QuerySessions()
            with patch(
                "wakfu_ai.planning.query_sessions.search", wraps=real_search
            ) as patched_search:
                first = sessions.decide(payload, store)
                self.assertEqual(first["status"], "query")
                self.assertEqual(reads.count(root_digest), 1)
                validated_graph = patched_search.call_args.kwargs["root_graph"]
                runtime_ref = validated_graph.field(
                    validated_graph.data["root"], "runtime"
                )
                fight_ref = validated_graph.field(runtime_ref, "fight")
                walkable_ref = validated_graph.field(fight_ref, "walkable")
                self.assertEqual(
                    validated_graph.plain(walkable_ref), frozenset({(0, 0, 0)})
                )

                # The in-flight session retains the exact graph object whose
                # canonical bytes passed SHA and NativeGraph validation.
                root_path = store._path(root_digest)
                root_path.write_bytes(b"x" * root_path.stat().st_size)
                self.assertFalse(store.has(root_digest))
                query = first["queries"][0]
                result = sessions.decide(
                    dict(
                        requestId="root-reuse",
                        sourceKey="a" * 64,
                        response={
                            "id": query["id"],
                            "supported": True,
                            "result": {"nativeMetadata": metadata_digest},
                        },
                    ),
                    store,
                )
                self.assertEqual(result["status"], "decided")
                self.assertEqual(reads.count(root_digest), 1)
                with self.assertRaisesRegex(
                    ValueError, "Context content changed while reading"
                ):
                    store.json(root_digest)
                self.assertEqual(reads.count(root_digest), 2)
            store.close()


class QuerySessionsHttpTests(unittest.TestCase):
    def test_v3_decide_http_initial_query_and_retry_safe_completion(self):
        from wakfu_ai.http import server

        store = FakeStore()
        sessions = QuerySessions()
        httpd = server.BoundedHTTPServer(("127.0.0.1", 0), server.Handler)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        with patch.object(server, "_QUERY_SESSIONS", sessions), patch.object(
            server, "context_store", return_value=store
        ), patch(
            "wakfu_ai.planning.query_sessions.search", side_effect=search_exchange
        ):
            try:
                initial = dict(
                    protocol=3,
                    requestId="http-request",
                    sourceKey="e" * 64,
                    catalogManifest=store.catalog,
                    rootState=store.root,
                    actor_id=101,
                    policy={},
                    root={
                        "key": store.root,
                        "nativeContext": store.root,
                        "currentId": 101,
                        "phase": "active",
                        "actors": [],
                    },
                )
                query = self.post(httpd, initial)
                self.assertEqual(query["status"], "query")
                self.assertEqual(self.post(httpd, deepcopy(initial)), query)

                continuation = dict(
                    requestId="http-request",
                    sourceKey="e" * 64,
                    response={
                        "id": "query-1",
                        "supported": True,
                        "result": {"key": "child"},
                    },
                )
                decision = self.post(httpd, continuation)
                self.assertEqual(decision["status"], "decided")
                self.assertEqual(decision["decision"]["action"]["type"], "move")
                self.assertEqual(self.post(httpd, continuation), decision)
            finally:
                httpd.shutdown()
                httpd.server_close()
                worker.join(2)

    @staticmethod
    def post(httpd, payload):
        client = HTTPConnection(*httpd.server_address, timeout=3)
        try:
            body = json.dumps(payload, separators=(",", ":")).encode()
            client.request(
                "POST", "/v3/decide", body, {"Content-Type": "application/json"}
            )
            response = client.getresponse()
            result = json.loads(response.read())
            if response.status != 200:
                raise AssertionError(
                    "unexpected HTTP status %s: %s" % (response.status, result)
                )
            return result
        finally:
            client.close()


class NativeQueryRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wakfu_server.combat_server_spell import prewarm_runtime_catalogs

        prewarm_runtime_catalogs()

    def test_real_search_and_native_session_select_freshly_certified_cast(self):
        import hashlib
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.spells import encode_deck
        from wakfu_ai.native.native_oracle import NativeOracle
        from wakfu_ai.bridge.world_bridge import NativeSession, _json_bytes

        # Search the actual Wonejo's native attack from its own turn, using the
        # complete installed arena rather than a reduced target-cell fixture.
        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.spells import default_deck

        fixture = NativeNpcAttackTests()
        fixture.setUp()
        character, monster, fight = fixture.character, fixture.monster, fixture.fight
        monster.update(id=fixture.npc.id, map_id=1134)
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_terrain import local_arena

        fight.actors[7].position = (-8, -7, -1)
        fight.actors[fixture.npc.id].position = (-7, -7, -1)
        terrain = local_arena(1134, fight.id, (-8, -7, -1), (-7, -7, -1))
        fight.walkable = terrain["validated_cells"]
        fight.edges = terrain["valid_edges"]
        freeze_terrain(fight)
        fight.order = [fixture.npc.id, fixture.pc.id]
        fight.turn_index = 0
        fixture.npc.turn_count = 1
        runtime = RuntimeMessages(fight)
        deck = default_deck(character)
        oracle = NativeOracle(
            runtime,
            characters={7: character},
            monsters={fixture.npc.id: monster},
            decks={7: deck},
            excluded_decks={7: frozenset()},
            viewer_id=7,
            flags={},
        )
        source_before = encode(runtime)

        class Store(FakeStore):
            def __init__(self):
                super().__init__()
                self.graphs = {}

            def manifest(self, digest):
                return {"complete": True}

            def json(self, digest):
                if digest in self.graphs:
                    return deepcopy(self.graphs[digest])
                if digest == self.root:
                    return deepcopy(self.graph)
                raise ValueError("Unknown graph")

        store = Store()
        sessions = QuerySessions()

        class Transport:
            def catalog(self, exporter):
                return store.catalog

            def instance(self, graph):
                payload = _json_bytes(graph)
                digest = hashlib.sha256(payload).hexdigest()
                store.graphs[digest] = json.loads(payload)
                return digest

            def _retry_request(self, endpoint, payload):
                if endpoint != "/v3/decide":
                    raise AssertionError("unexpected transport endpoint: " + endpoint)
                return sessions.decide(payload, store)

        transport = Transport()
        session = NativeSession(
            oracle,
            transport,
            object(),
            policy={"limits": {"depth": 1, "beam": 4, "nodes": 48, "budgetMs": 5000}},
            policy_version="native-test",
            fight_instance_id="wonejo-roundtrip",
        )
        observed = []
        original_preview = oracle.preview

        def tracked_preview(source, action, **kwargs):
            observed.append(deepcopy(action))
            return original_preview(source, action, **kwargs)

        oracle.preview = tracked_preview
        from unittest.mock import patch

        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            decision = session.decide(max_queries=128)

        self.assertEqual(
            decision["action"]["type"], "cast", msg=repr((decision, observed))
        )
        self.assertEqual(decision["action"]["spellId"], 7962)
        self.assertEqual(decision["action"]["targetId"], 7)
        self.assertGreaterEqual(len(observed), 2)
        self.assertEqual(observed[-1], decision["action"])
        self.assertEqual(encode(runtime), source_before)
        self.assertEqual(runtime.fight.actors[7].hp, 60)
        self.assertEqual(runtime.fight.actors[fixture.npc.id].ap, 3)


if __name__ == "__main__":
    unittest.main()
