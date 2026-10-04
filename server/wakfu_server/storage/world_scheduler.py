"""Interval task execution with renewable leases and stable occurrence IDs.

Actions must honor occurrence IDs: a process may die after an external mutation
but before recording completion. Distributed leases alone cannot ensure exactly once.
"""
import threading
import time
import uuid


class RedisBackend:
    CLAIM = """if redis.call('EXISTS',KEYS[2])==1 then return 0 end
if redis.call('EXISTS',KEYS[3])==1 then return 0 end
if tonumber(redis.call('GET',KEYS[4]) or '0')>=tonumber(ARGV[3]) then return 0 end
if not redis.call('SET',KEYS[1],ARGV[1],'NX','PX',ARGV[2]) then return 0 end
redis.call('INCR',KEYS[4]);redis.call('PEXPIRE',KEYS[4],ARGV[4]);return 1"""
    RENEW = """if redis.call('GET',KEYS[1])~=ARGV[1] then return 0 end
return redis.call('PEXPIRE',KEYS[1],ARGV[2])"""
    FINISH = """if redis.call('GET',KEYS[1])~=ARGV[1] then return 0 end
redis.call('SET',KEYS[2],ARGV[2],'PX',ARGV[3]);redis.call('DEL',KEYS[1]);return 1"""

    def __init__(self, client, prefix="wakfu:cron"):
        self.client = client
        self.prefix = prefix

    def keys(self, name, occurrence):
        # Shared task lease prevents overlap even across different intervals.
        return [
            f"{self.prefix}:{{{name}}}:lease",
            f"{self.prefix}:{{{name}}}:done:{occurrence}",
            f"{self.prefix}:{{{name}}}:retry:{occurrence}",
        ]

    def claim(self, name, occurrence, token, ttl, max_attempts=3, retention=604800):
        return bool(
            self.client.eval(
                self.CLAIM,
                4,
                *self.keys(name, occurrence),
                self.keys(name, occurrence)[1] + ":attempts",
                token,
                int(ttl * 1000),
                max_attempts,
                int(retention * 1000),
            )
        )

    def renew(self, name, occurrence, token, ttl):
        return bool(
            self.client.eval(
                self.RENEW, 1, self.keys(name, occurrence)[0], token, int(ttl * 1000)
            )
        )

    def finish(self, name, occurrence, token, *, success, delay, retention):
        keys = self.keys(name, occurrence)
        key = keys[1] if success else keys[2]
        return bool(
            self.client.eval(
                self.FINISH,
                2,
                keys[0],
                key,
                token,
                "1",
                int((retention if success else delay) * 1000),
            )
        )


class MemoryBackend:
    """Single-process backend for local verification; production uses Redis."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.leases = {}
        self.done = {}
        self.retry = {}
        self.attempts = {}

    def claim(self, name, occurrence, token, ttl, max_attempts=3, retention=604800):
        with self.lock:
            now = self.clock()
            key = (name, occurrence)
            if (
                self.done.get(key, 0) > now
                or self.retry.get(key, 0) > now
                or self.attempts.get(key, 0) >= max_attempts
            ):
                return False
            if self.leases.get(name, ("", 0))[1] > now:
                return False
            self.leases[name] = (token, now + ttl)
            self.attempts[key] = self.attempts.get(key, 0) + 1
            return True

    def renew(self, name, occurrence, token, ttl):
        with self.lock:
            if (
                self.leases.get(name, ("", 0))[0] != token
                or self.leases[name][1] <= self.clock()
            ):
                return False
            self.leases[name] = (token, self.clock() + ttl)
            return True

    def finish(self, name, occurrence, token, *, success, delay, retention):
        with self.lock:
            if not self.renew(name, occurrence, token, 1):
                return False
            (self.done if success else self.retry)[
                (name, occurrence)
            ] = self.clock() + (retention if success else delay)
            del self.leases[name]
            return True


class Scheduler:
    def __init__(self, backend, tasks, *, clock=time.time):
        self.backend = backend
        self.tasks = tasks
        self.clock = clock
        for name, task in tasks.items():
            if not name or any(
                c
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for c in name
            ):
                raise ValueError("Invalid scheduler task name")
            if task["interval"] <= 0 or task.get("lease_seconds", 30) < 1:
                raise ValueError("Invalid scheduler timing")

    def tick(self):
        outcomes = []
        for name, task in self.tasks.items():
            if not task.get("enabled", True):
                continue
            slot = int(self.clock() // task["interval"])
            occurrence = f"{name}:{slot}"
            token = uuid.uuid4().hex
            ttl = task.get("lease_seconds", 30)
            if not self.backend.claim(
                name,
                occurrence,
                token,
                ttl,
                task.get("max_attempts", 3),
                task.get("retention_seconds", 604800),
            ):
                continue
            stop = threading.Event()
            lost = threading.Event()

            def renew():
                while not stop.wait(ttl / 3):
                    try:
                        if not self.backend.renew(name, occurrence, token, ttl):
                            lost.set()
                            return
                    except Exception:
                        lost.set()
                        return

            thread = threading.Thread(target=renew, daemon=True)
            thread.start()
            success = False
            error = None
            try:
                task["action"](occurrence, lost)
                success = not lost.is_set()
            except Exception as exc:
                error = str(exc)
            finally:
                stop.set()
                thread.join(timeout=1)
            committed = self.backend.finish(
                name,
                occurrence,
                token,
                success=success,
                delay=task.get("retry_seconds", 5),
                retention=task.get("retention_seconds", 604800),
            )
            outcomes.append(
                dict(
                    task=name,
                    occurrence=occurrence,
                    success=success and committed,
                    lease_lost=lost.is_set() or not committed,
                    error=error,
                )
            )
        return outcomes
