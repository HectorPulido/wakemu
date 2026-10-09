"""Retry-safe native-query negotiation with short registry locking.

The registry lock protects only session membership, capacity reservations and
expiry bookkeeping. Slow catalogue verification, graph loading and generator
work run under the individual session lock, so unrelated encounters proceed
independently while retries for one encounter remain serialized.
"""
import threading
import time
import math
from contextlib import nullcontext

from ..native.native_deadline import bounded, check

from .query_search import search
from ..context.native_context import NativeGraph
from ..context.native_graph_parts import load_graph


class QuerySessions:
    def __init__(self, *, capacity=8, ttl=300, clock=time.monotonic):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Invalid native search session capacity")
        if type(ttl) not in (int, float) or not math.isfinite(ttl) or ttl <= 0:
            raise ValueError("Invalid native search session TTL")
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self.lock = threading.RLock()
        self.sessions = {}

    def _release(self, entry):
        with self.lock:
            entry["users"] -= 1
            if entry["users"] < 0:
                raise RuntimeError("Native search session lease underflow")

    def _close_all(self, entries):
        for entry in entries:
            generator = entry.get("generator")
            if generator is not None:
                try:
                    generator.close()
                except Exception:
                    # Eviction/cancellation already removed the entry. A
                    # generator's cleanup error must not strand a new lease.
                    pass

    def _reap_locked(self, now):
        """Remove idle expired/completed entries; caller closes outside lock."""
        removed = []
        expired = [
            key
            for key, entry in self.sessions.items()
            if entry["users"] == 0
            and (
                now - entry["updated"] > self.ttl
                or entry["final"] is None
                and entry.get("ownerDeadline") is not None
                and now >= entry["ownerDeadline"]
            )
        ]
        for key in expired:
            entry = self.sessions.pop(key)
            entry["removed"] = True
            removed.append(entry)

        maximum = self.capacity * 16
        if len(self.sessions) > maximum:
            completed = sorted(
                (entry["updated"], key)
                for key, entry in self.sessions.items()
                if entry["users"] == 0 and entry["final"] is not None
            )
            excess = len(self.sessions) - maximum
            for _, key in completed[:excess]:
                entry = self.sessions.pop(key)
                entry["removed"] = True
                removed.append(entry)
        return removed

    @staticmethod
    def _validate_identity(payload):
        if not isinstance(payload, dict):
            raise ValueError("Invalid native search exchange")
        identity, source = payload.get("requestId"), payload.get("sourceKey")
        if (
            not isinstance(identity, str)
            or not identity
            or not isinstance(source, str)
            or len(source) != 64
        ):
            raise ValueError("Missing native search source identity")
        return identity, source

    @staticmethod
    def _validate_initial(payload):
        if (
            type(payload.get("protocol")) is not int
            or payload["protocol"] != 3
            or "response" in payload
        ):
            raise ValueError("Unknown or expired native search session")
        required = {"catalogManifest", "rootState", "root", "actor_id", "policy"}
        if not required <= payload.keys():
            raise ValueError("Incomplete native search initialization")
        root = payload["root"]
        if (
            not isinstance(root, dict)
            or root.get("key") != payload["rootState"]
            or root.get("nativeContext") != payload["rootState"]
            or root.get("currentId") != payload["actor_id"]
            or root.get("phase") != "active"
            or not isinstance(root.get("actors"), list)
            or not isinstance(payload["policy"], dict)
        ):
            raise ValueError("Invalid native search root identity")

    def _reserve(self, identity, source, payload):
        """Acquire a per-entry lease or reserve an initializing placeholder."""
        removed = []
        try:
            with self.lock:
                now = self.clock()
                removed = self._reap_locked(now)
                entry = self.sessions.get(identity)
                if entry is not None:
                    if entry["source"] != source:
                        raise ValueError("Native search source identity changed")
                    if entry["removed"]:
                        raise ValueError("Unknown or expired native search session")
                    entry["users"] += 1
                    initialize = False
                else:
                    self._validate_initial(payload)
                    if (
                        sum(value["final"] is None for value in self.sessions.values())
                        >= self.capacity
                    ):
                        # Preserve the historical bounded replay cache while
                        # ensuring completed sessions never consume active slots.
                        raise ValueError("Native search session capacity reached")
                    if len(self.sessions) >= self.capacity * 16:
                        completed = sorted(
                            (value["updated"], key)
                            for key, value in self.sessions.items()
                            if value["users"] == 0 and value["final"] is not None
                        )
                        for _, key in completed[
                            : len(self.sessions) - self.capacity * 16 + 1
                        ]:
                            old = self.sessions.pop(key)
                            old["removed"] = True
                            removed.append(old)
                    session_lock = threading.RLock()
                    # Own the initializing entry before publishing it. A same-ID
                    # retry can reserve a lease, but cannot inspect an
                    # uninitialized generator ahead of its creator.
                    session_lock.acquire()
                    entry = dict(
                        lock=session_lock,
                        source=source,
                        updated=now,
                        received=now,
                        ownerDeadline=None,
                        initial=payload,
                        initialReply=None,
                        answers={},
                        final=None,
                        generator=None,
                        query=None,
                        users=1,
                        initializing=True,
                        removed=False,
                    )
                    self.sessions[identity] = entry
                    initialize = True
        finally:
            self._close_all(removed)
        return entry, initialize

    def _still_registered(self, identity, entry):
        with self.lock:
            return self.sessions.get(identity) is entry and not entry["removed"]

    def _drop_failed_init(self, identity, entry):
        with self.lock:
            entry["removed"] = True
            if self.sessions.get(identity) is entry:
                self.sessions.pop(identity)

    def _initialize(self, identity, entry, payload, store):
        """Owner time includes full context verification, not just search work."""
        if "nativeBudgetMs" in payload:
            budget = payload["nativeBudgetMs"]
            if (
                type(budget) not in (int, float)
                or not math.isfinite(budget)
                or budget < 0
            ):
                raise ValueError("Invalid native owner budget hint")
            entry["ownerDeadline"] = entry["received"] + budget / 1000
        deadline = entry["ownerDeadline"]
        scope = (
            nullcontext() if deadline is None else bounded(deadline, clock=self.clock)
        )
        with scope:
            self._initialize_ready(identity, entry, payload, store)

    def _initialize_ready(self, identity, entry, payload, store):
        """Perform all complete-context I/O outside the global registry lock."""
        metrics = entry["initializationMetrics"] = {}

        def measure(name, operation):
            started, cpu_started = time.monotonic(), time.thread_time()
            try:
                return operation()
            finally:
                metrics[name] = dict(
                    wallMs=(time.monotonic() - started) * 1000,
                    threadCpuMs=(time.thread_time() - cpu_started) * 1000,
                )

        if not measure(
            "catalogSeal", lambda: store.seal_manifest(payload["catalogManifest"])
        )["complete"]:
            raise ValueError("Incomplete native search catalogue")
        # Verify the entire source graph before retaining an executable search.
        check()
        root_graph = measure(
            "rootGraph", lambda: load_graph(store, payload["rootState"])
        )
        check()
        if entry["ownerDeadline"] is not None:
            payload = dict(
                payload,
                nativeBudgetMs=max(0.0, (entry["ownerDeadline"] - self.clock()) * 1000),
            )
        generator = search(payload, store, clock=self.clock, root_graph=root_graph)
        entry["generator"] = generator
        try:
            query = measure("firstQuery", lambda: next(generator))
        except StopIteration as finished:
            entry["final"] = finished.value
            query = None
        entry["query"] = query
        entry["initialReply"] = self._reply(identity, entry)
        entry["initializing"] = False
        entry["updated"] = self.clock()

    def _continue(self, identity, entry, payload):
        source = payload["sourceKey"]
        if source != entry["source"]:
            raise ValueError("Native search source identity changed")
        if "response" not in payload:
            if payload != entry["initial"]:
                raise ValueError("Conflicting native search initialization")
            entry["updated"] = self.clock()
            return entry["initialReply"]
        if set(payload) != {"requestId", "sourceKey", "response"}:
            raise ValueError("Invalid native search continuation")
        response = payload["response"]
        if not isinstance(response, dict) or not isinstance(response.get("id"), str):
            raise ValueError("Invalid native search response identity")
        identifier = response["id"]
        if identifier in entry["answers"]:
            old, reply = entry["answers"][identifier]
            if old != response:
                raise ValueError("Conflicting repeated native search response")
            entry["updated"] = self.clock()
            return reply
        if entry["query"] is None or identifier != entry["query"]["id"]:
            raise ValueError("Out-of-order native search response")
        try:
            deadline = entry["ownerDeadline"]
            scope = (
                nullcontext()
                if deadline is None
                else bounded(deadline, clock=self.clock)
            )
            with scope:
                entry["query"] = entry["generator"].send(response)
        except StopIteration as finished:
            entry["query"], entry["final"] = None, finished.value
        except Exception:
            # This method is called while holding the entry lock. Retire the
            # failed entry here, before another leased retry can resume or
            # close the same generator.
            with self.lock:
                entry["removed"] = True
                if self.sessions.get(identity) is entry:
                    self.sessions.pop(identity)
            self._close_all([entry])
            raise
        reply = self._reply(identity, entry)
        entry["answers"][identifier] = (response, reply)
        entry["updated"] = self.clock()
        return reply

    def _check_entry(self, identity, entry):
        if not self._still_registered(identity, entry):
            raise ValueError("Unknown or expired native search session")
        if entry["initializing"]:
            raise RuntimeError("Native search initialization was not completed")
        if self.clock() - entry["updated"] > self.ttl:
            # This check runs with the per-session lock held and after acquiring
            # an operation lease, so no active generator can be closed here.
            with self.lock:
                if self.sessions.get(identity) is entry:
                    self.sessions.pop(identity)
                entry["removed"] = True
            generator = entry.get("generator")
            if generator is not None:
                generator.close()
            raise ValueError("Unknown or expired native search session")

    def decide(self, payload, store):
        identity, source = self._validate_identity(payload)
        entry, initialize = self._reserve(identity, source, payload)
        try:
            if initialize:
                # _reserve acquired this new RLock before publishing the
                # placeholder; it remains owned by this thread across the
                # slow initialization work.
                try:
                    if not self._still_registered(identity, entry):
                        raise ValueError("Unknown or expired native search session")
                    try:
                        self._initialize(identity, entry, payload, store)
                    except Exception:
                        self._drop_failed_init(identity, entry)
                        self._close_all([entry])
                        raise
                    return entry["initialReply"]
                finally:
                    entry["lock"].release()
            with entry["lock"]:
                if not self._still_registered(identity, entry):
                    raise ValueError("Unknown or expired native search session")
                self._check_entry(identity, entry)
                return self._continue(identity, entry, payload)
        finally:
            self._release(entry)

    def cancel(self, payload):
        if (
            not isinstance(payload, dict)
            or set(payload) != {"requestId", "sourceKey"}
            or not isinstance(payload["requestId"], str)
            or not payload["requestId"]
            or not isinstance(payload["sourceKey"], str)
            or len(payload["sourceKey"]) != 64
        ):
            raise ValueError("Invalid native search cancellation")
        identity, source = payload["requestId"], payload["sourceKey"]
        removed = []
        entry = None
        try:
            with self.lock:
                removed = self._reap_locked(self.clock())
                entry = self.sessions.get(identity)
                if entry is not None:
                    if entry["source"] != source:
                        raise ValueError("Native search cancellation source changed")
                    entry["users"] += 1
        finally:
            self._close_all(removed)
        if entry is not None:
            try:
                with entry["lock"]:
                    if self._still_registered(identity, entry):
                        with self.lock:
                            if self.sessions.get(identity) is entry:
                                self.sessions.pop(identity)
                            entry["removed"] = True
                        generator = entry.get("generator")
                        if generator is not None:
                            generator.close()
            finally:
                self._release(entry)
        return dict(cancelled=True, requestId=identity)

    @staticmethod
    def _reply(identity, entry):
        metrics = entry.get("initializationMetrics")
        diagnostics = {} if metrics is None else dict(backendPreparation=metrics)
        if entry["final"] is not None:
            return dict(status="decided", decision=entry["final"], **diagnostics)
        return dict(
            status="query",
            requestId=identity,
            sourceKey=entry["source"],
            queries=[entry["query"]],
            **diagnostics,
        )
