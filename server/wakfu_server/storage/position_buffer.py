"""Single-process authoritative positions with generation-safe PostgreSQL batches.

A crash may lose the unflushed interval. Graceful lifecycle barriers must flush
successfully before logout, map transition, character switch or process exit.
The caller owns the live-session registry and validated movement paths.
"""
import threading
import time
from contextlib import contextmanager, ExitStack

_KEYS = ("map_id", "instance_id", "x", "y", "z", "direction")


class PositionOwnerBusy(TimeoutError):
    """Recoverable contention; the authoritative position remains dirty."""


class Positions:
    def __init__(self, store, *, lease_active):
        self.store = store
        self.lease_active = lease_active
        self.lock = threading.RLock()
        self.entries = {}
        self.evictions = []
        self.account_locks = {}
        self.observer = None

    def observe(self, stage, started, **details):
        if callable(self.observer):
            try:
                self.observer(
                    dict(
                        stage=stage,
                        elapsed_ms=round((time.monotonic() - started) * 1000, 3),
                        **details
                    )
                )
            except Exception:
                pass

    @contextmanager
    def account_barrier(self, account_id, *, blocking=True):
        """Serialize ownership changes without blocking unrelated players."""
        with self.lock:
            lock = self.account_locks.setdefault(account_id, threading.RLock())
        if not lock.acquire(blocking=blocking):
            raise PositionOwnerBusy("Position owner is busy; retry checkpoint")
        try:
            yield
        finally:
            lock.release()

    @contextmanager
    def flush_barrier(self, **scope):
        # Keep one atomic DB batch while never holding the registry lock for I/O.
        with self.lock:
            accounts = sorted(
                {
                    key[0]
                    for key in self.entries
                    if scope.get("account_id") is None or key[0] == scope["account_id"]
                }
            )
        with ExitStack() as stack:
            for account in accounts:
                stack.enter_context(self.account_barrier(account, blocking=False))
            yield set(accounts)

    def _entry_snapshot(self):
        with self.lock:
            return list(self.entries.items())

    def attach(self, account_id, generation, character):
        key = (account_id, generation, character["id"])
        with self.account_barrier(account_id), self.store.connection(
            timeout=0.25
        ) as db:
            db.execute("SET LOCAL lock_timeout = '250ms'")
            db.execute("SET LOCAL statement_timeout = '1000ms'")
            row = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
                (account_id, generation, self.store.now()),
            ).fetchone()
            if row is None or row["character_id"] != character["id"]:
                raise ValueError("Invalid buffered position session")
            saved = self.store.character(account_id, character["id"], db)
            if any(saved[k] != character[k] for k in _KEYS):
                raise ValueError("Buffered position baseline does not match storage")
            if key in self.entries and self.entries[key]["dirty"]:
                raise ValueError("Flush buffered position before attaching again")
            with self.lock:
                self.entries[key] = {
                    "current": dict(character),
                    "persisted": {k: saved[k] for k in _KEYS},
                    "dirty": False,
                }
            return dict(character)

    def move(self, account_id, generation, character_id, start, end):
        key = (account_id, generation, character_id)
        with self.account_barrier(account_id):
            entry = self.entries.get(key)
            if entry is None or not self.lease_active(*key):
                raise ValueError("Stale buffered position session")
            current = entry["current"]
            if any(current[k] != start[k] for k in ("x", "y", "z")):
                raise ValueError("Position origin is desynchronized")
            for axis, bits in (("x", 32), ("y", 32), ("z", 16)):
                if type(end.get(axis)) is not int or not -(1 << (bits - 1)) <= end[
                    axis
                ] < (1 << (bits - 1)):
                    raise ValueError("Invalid buffered position coordinate")
            direction = end.get("direction", current["direction"])
            if type(direction) is not int or not 0 <= direction <= 7:
                raise ValueError("Invalid buffered position direction")
            current.update({k: end[k] for k in ("x", "y", "z")})
            current["direction"] = direction
            entry["dirty"] = any(current[k] != entry["persisted"][k] for k in _KEYS)
            return dict(current)

    def merge(self, account_id, generation, character):
        """Merge refreshed HP/build fields without restoring an old DB position."""
        key = (account_id, generation, character["id"])
        with self.account_barrier(account_id):
            entry = self.entries.get(key)
            if entry is None or not self.lease_active(*key):
                raise ValueError("Stale buffered position session")
            entry["current"] = {**character, **{k: entry["current"][k] for k in _KEYS}}
            return dict(entry["current"])

    def flush(self, **scope):
        """Checkpoint accounts independently so one busy owner cannot stall others."""
        if scope.get("account_id") is not None:
            return self._flush_one(**scope)
        with self.lock:
            accounts = sorted({key[0] for key in self.entries})
        count = 0
        failure = None
        for account in accounts:
            try:
                count += self._flush_one(**dict(scope, account_id=account))
            except Exception as error:
                # Preserve dirty state and finish the healthy owners before retry.
                failure = error
        if failure is not None:
            raise failure
        return count

    def _flush_one(self, **scope):
        # Pool waits must happen before taking any player ownership barrier.
        started = time.monotonic()
        with ExitStack() as transaction:
            db = transaction.enter_context(self.store.connection(timeout=0.25))
            self.observe("pool", started, account_id=scope.get("account_id"))
            return self._flush(db, commit=transaction.close, **scope)

    def _flush(
        self, db, *, commit, account_id=None, generation=None, character_id=None
    ):
        """One account transaction; failure preserves its pending entries for retry.

        Stale stored generations are evicted without writing and reported via
        evictions; they cannot poison live entries. CAS conflicts abort the batch;
        callers must resolve/release that entry rather than silently losing data.
        """
        with self.flush_barrier(account_id=account_id) as accounts:
            selected = [
                (key, e)
                for key, e in self._entry_snapshot()
                if key[0] in accounts
                and e["dirty"]
                and (account_id is None or key[0] == account_id)
                and (generation is None or key[1] == generation)
                and (character_id is None or key[2] == character_id)
            ]
            if not selected:
                return 0
            committed = []
            stale = []
            started = time.monotonic()
            # A busy row must fail/retry rather than freeze player threads.
            db.execute("SET LOCAL lock_timeout = '250ms'")
            db.execute("SET LOCAL statement_timeout = '1000ms'")
            for (account, gen, cid), entry in sorted(selected):
                session = db.execute(
                    "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
                    (account, gen, self.store.now()),
                ).fetchone()
                if session is None or session["character_id"] != cid:
                    stale.append((account, gen, cid))
                    continue
                if not self.lease_active(account, gen, cid):
                    raise ValueError("Live lease unavailable for buffered position")
                old = entry["persisted"]
                new = entry["current"]
                result = db.execute(
                    "UPDATE characters SET x=%s,y=%s,z=%s,direction=%s WHERE id=%s AND account_id=%s "
                    "AND map_id=%s AND instance_id=%s AND x=%s AND y=%s AND z=%s AND direction=%s",
                    (
                        new["x"],
                        new["y"],
                        new["z"],
                        new["direction"],
                        cid,
                        account,
                        *[old[k] for k in _KEYS],
                    ),
                )
                if result.rowcount != 1:
                    raise ValueError("Buffered position storage CAS conflict")
                committed.append(((account, gen, cid), entry))
            commit()
            self.observe(
                "postgres_commit",
                started,
                account_id=account_id,
                characters=len(committed),
            )
            for key in stale:
                with self.lock:
                    self.entries.pop(key, None)
                    self.evictions.append(key)
            for key, entry in committed:
                entry["persisted"] = {k: entry["current"][k] for k in _KEYS}
                entry["dirty"] = False
            return len(committed)

    def release(self, account_id, generation, character_id, *, discard_stale=False):
        key = (account_id, generation, character_id)
        with self.account_barrier(account_id):
            entry = self.entries.get(key)
            if entry is not None and entry["dirty"] and not discard_stale:
                raise ValueError("Flush position before release")
            if discard_stale and self.lease_active(*key):
                raise ValueError("Cannot discard a live authoritative position")
            with self.lock:
                self.entries.pop(key, None)
