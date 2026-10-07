"""Session-independent retry-safe persistence callbacks.

Redis Scheduler owns distributed leases. This process deduplicates completed
occurrences; a crash before reply may safely repeat a durable journal flush.
"""
import threading
import time

ALLOWED_TASKS = frozenset(("positions_flush", "territory_weather_tick"))


class GlobalTasks:
    def __init__(
        self,
        callbacks,
        *,
        clock=time.monotonic,
        retention_seconds=604800,
        observer=None,
    ):
        if set(callbacks) - ALLOWED_TASKS or any(
            not callable(c) for c in callbacks.values()
        ):
            raise ValueError("Unknown or invalid global callback")
        self.callbacks = dict(callbacks)
        self.clock = clock
        self.retention_seconds = retention_seconds
        if observer is not None and not callable(observer):
            raise ValueError("Invalid global task observer")
        self.observer = observer
        self.completed = {}
        self.announced = {}
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.running = set()

    def _cleanup(self, now):
        self.completed = {k: v for k, v in self.completed.items() if v[0] > now}
        self.announced = {k: v for k, v in self.announced.items() if v[0] > now}

    def _notify(self, name, request_id, status, *, error_type=None):
        if self.observer is None:
            return
        key = (name, request_id)
        with self.lock:
            now = self.clock()
            self._cleanup(now)
            expires, events = self.announced.get(
                key, (now + self.retention_seconds, set())
            )
            if status in events:
                return
            events.add(status)
            self.announced[key] = (expires, events)
        event = dict(task=name, request_id=request_id, status=status)
        if error_type is not None:
            # Never pass exception text to an observer that may announce it to
            # all online players; it can contain SQL, paths or other internals.
            event["error_type"] = error_type
        try:
            self.observer(event)
        except Exception:
            # Announcements are observational. They cannot change task outcome.
            pass
        if status == "failed":
            # Failed occurrences may be retried. Let each retry announce its
            # own start/failure lifecycle instead of deduplicating it away.
            with self.lock:
                current = self.announced.get(key)
                if current is not None:
                    current[1].discard("started")
                    current[1].discard("failed")

    def names(self):
        return sorted(self.callbacks)

    def run(self, name, request_id):
        if name not in self.callbacks:
            raise ValueError("Unknown global task")
        if not isinstance(request_id, str) or not request_id or len(request_id) > 200:
            raise ValueError("Global task requires a bounded occurrence ID")
        if not request_id.startswith(name + ":"):
            raise ValueError("Occurrence does not belong to task")
        key = (name, request_id)
        with self.condition:
            now = self.clock()
            self._cleanup(now)
            while key in self.running:
                self.condition.wait()
                now = self.clock()
                self._cleanup(now)
            if key in self.completed:
                return dict(self.completed[key][1], deduplicated=True)
            self.running.add(key)
        self._notify(name, request_id, "started")
        try:
            self.callbacks[name]()
        except Exception as error:
            self._notify(name, request_id, "failed", error_type=type(error).__name__)
            with self.condition:
                self.running.discard(key)
                self.condition.notify_all()
            raise
        with self.condition:
            now = self.clock()
            result = dict(task=name, request_id=request_id, status="completed")
            self.completed[key] = (now + self.retention_seconds, result)
            self.running.discard(key)
            self.condition.notify_all()
        self._notify(name, request_id, "completed")
        return dict(result, deduplicated=False)


class SlowSaveAnnouncements:
    """Announce a global flush only when it exceeds a latency threshold."""

    STARTED_TEXT = "Guardado del servidor en curso…"
    COMPLETED_TEXT = "Guardado del servidor completado."
    FAILED_TEXT = "Falló el guardado del servidor."

    def __init__(self, world, *, threshold_seconds=1.0, timer_factory=threading.Timer):
        if (
            not isinstance(threshold_seconds, (int, float))
            or isinstance(threshold_seconds, bool)
            or threshold_seconds < 0
        ):
            raise ValueError("Invalid global save announcement threshold")
        if not callable(timer_factory):
            raise ValueError("Invalid global save announcement timer")
        self.world = world
        self.threshold_seconds = threshold_seconds
        self.timer_factory = timer_factory
        self.condition = threading.Condition(threading.RLock())
        self.pending = {}

    def __call__(self, event):
        if not isinstance(event, dict):
            return
        task, request_id, status = (
            event.get("task"),
            event.get("request_id"),
            event.get("status"),
        )
        if task != "positions_flush" or not isinstance(request_id, str):
            return
        key = (task, request_id)
        if status == "started":
            self._start(key)
        elif status in ("completed", "failed"):
            self._finish(key, status)

    def _start(self, key):
        with self.condition:
            current = self.pending.get(key)
            if current is not None and (
                current["started"] or current["timer"] is not None
            ):
                return
            state = {"timer": None, "started": False, "sending": False}
            timer = self.timer_factory(
                self.threshold_seconds, self._announce_started, args=(key, state)
            )
            timer.daemon = True
            state["timer"] = timer
            self.pending[key] = state
            timer.start()

    def _announce_started(self, key, state):
        with self.condition:
            if self.pending.get(key) is not state or state["sending"]:
                return
            state["timer"] = None
            state["sending"] = True
        try:
            delivered = self.world.information_all(self.STARTED_TEXT)
        except Exception:
            delivered = 0
        with self.condition:
            state["started"] = type(delivered) is int and delivered > 0
            state["sending"] = False
            self.condition.notify_all()

    def _finish(self, key, status):
        with self.condition:
            state = self.pending.get(key)
            if state is None:
                return
            timer = state["timer"]
            state["timer"] = None
            if timer is not None:
                timer.cancel()
            while state["sending"]:
                self.condition.wait()
            self.pending.pop(key, None)
            should_announce = state["started"]
        if should_announce:
            message = self.COMPLETED_TEXT if status == "completed" else self.FAILED_TEXT
            try:
                self.world.information_all(message)
            except Exception:
                pass
