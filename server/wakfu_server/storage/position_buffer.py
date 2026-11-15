"""PostgreSQL checkpoint I/O for the sole native spatial position authority."""

import threading
import time
from collections.abc import Mapping
from contextlib import contextmanager, ExitStack

_KEYS = ("map_id", "instance_id", "x", "y", "z", "direction")


class PositionOwnerBusy(TimeoutError):
    """Recoverable ownership contention; native dirty work remains retained."""


class PositionBaselineChanged(ValueError):
    """The selected durable scene differs from the prepared baseline."""


@contextmanager
def _recoverable_position_lock():
    from psycopg.errors import LockNotAvailable

    try:
        yield
    except LockNotAvailable as error:
        raise PositionOwnerBusy("Position owner is busy; retry checkpoint") from error


class _EntryView(Mapping):
    """Detached native snapshots, never a mutable position registry."""

    def __init__(self, positions):
        self.positions = positions

    def __getitem__(self, key):
        value = self.positions.entry_snapshot(key)
        if value is None:
            raise KeyError(key)
        return value

    def __iter__(self):
        return (key for key, _entry in self.positions._entry_snapshot())

    def __len__(self):
        return len(self.positions._call("entries"))


class Positions:
    def __init__(self, store, *, lease_active, native=None):
        from wakfu_server.spatial_native import NativeSpatial

        self.store = store
        self.lease_active = lease_active
        self.native = native if native is not None else NativeSpatial()
        # These locks serialize Python I/O, not spatial state. Native commands
        # release their own mutex before PostgreSQL or callbacks can run.
        self.lock = threading.RLock()
        self.account_locks = {}
        self.background_lock = threading.Lock()
        self.observer = None
        self._entry_view = _EntryView(self)

    @property
    def entries(self):
        return self._entry_view

    def _call(self, operation, **values):
        try:
            return self.native.call("positions." + operation, **values)
        except ValueError as error:
            code = getattr(error, "native_code", getattr(error, "code", None))
            if code == "busy":
                raise PositionOwnerBusy(str(error)) from error
            if code == "baseline":
                raise PositionBaselineChanged(str(error)) from error
            if code == "journal":
                from wakfu_server.position_redis import PositionJournalError

                raise PositionJournalError(str(error)) from error
            raise

    def _character(self, key, current):
        metadata = self.native.character(tuple(key), domain="positions")
        if metadata is None:
            raise RuntimeError("Missing native position character projection")
        return dict(metadata, id=key[2], account_id=key[0], **current)

    def _bind(self, key, character):
        self.native.bind_character(tuple(key), character, domain="positions")

    def entry_state(self, key):
        """Return compact current/baseline/revision state from Rust."""
        return self._call("entry", key=list(key))

    def entry_snapshot(self, key):
        value = self.entry_state(key)
        if value is None:
            return None
        return dict(value, current=self._character(key, value["current"]))

    def _entry_snapshot(self):
        return [(tuple(row["key"]), row["entry"]) for row in self._call("entries")]

    @property
    def evictions(self):
        return [tuple(key) for key in self._call("evictions", drain=False)]

    def drain_evictions(self):
        return tuple(tuple(key) for key in self._call("evictions", drain=True))

    @property
    def background_cursor(self):
        return self._call("cursor")

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
        accounts = self._call("accounts", scope=scope, work_only=False)
        with ExitStack() as stack:
            for account in accounts:
                stack.enter_context(self.account_barrier(account, blocking=False))
            yield set(accounts)

    def registered_accounts(self):
        return set(self._call("accounts", work_only=False))

    def background_accounts(self):
        return set(self._call("accounts", work_only=True))

    def attach(self, account_id, generation, character):
        return self._attach(
            account_id, generation, character["id"], character=character
        )

    def rebind_selected(self, account_id, generation, character_id):
        return self._attach(
            account_id, generation, character_id, skip_stale_selection=True
        )

    def _attach(
        self,
        account_id,
        generation,
        character_id,
        *,
        character=None,
        skip_stale_selection=False
    ):
        key = (account_id, generation, character_id)
        # Borrow scarce database capacity before owning the account barrier.
        with _recoverable_position_lock(), self.store.connection(
            timeout=0.25
        ) as db, self.account_barrier(account_id):
            db.execute("SET LOCAL lock_timeout = '250ms'")
            db.execute("SET LOCAL statement_timeout = '1000ms'")
            row = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
                (account_id, generation, self.store.now()),
            ).fetchone()
            saved = (
                self.store.character(account_id, character_id, db)
                if row is not None and row["character_id"] == character_id
                else None
            )
            current = saved if character is None else character
            state = self._call(
                "attach",
                key=list(key),
                current=None if current is None else {k: current[k] for k in _KEYS},
                persisted=None if saved is None else {k: saved[k] for k in _KEYS},
                selected_character_id=None if row is None else row["character_id"],
                skip_stale_selection=skip_stale_selection,
            )
            if state is None:
                return None
            self._bind(key, current)
            return self._character(key, state["current"])

    def _prepare_move(self, key, start, end):
        state = self.entry_state(key)
        return self._call(
            "prepare_move",
            key=list(key),
            start={k: start[k] for k in ("x", "y", "z")},
            end={k: end[k] for k in ("x", "y", "z", "direction") if k in end},
            lease_active=state is not None and bool(self.lease_active(*key)),
        )

    def move(self, account_id, generation, character_id, start, end):
        key = (account_id, generation, character_id)
        with self.account_barrier(account_id):
            plan = self._prepare_move(key, start, end)
            state = self._call("commit_move", token=plan["token"], encoded=None)
            return self._character(key, state["current"])

    def merge(self, account_id, generation, character):
        key = (account_id, generation, character["id"])
        with self.account_barrier(account_id):
            state = self.entry_state(key)
            state = self._call(
                "merge",
                key=list(key),
                lease_active=state is not None and bool(self.lease_active(*key)),
            )
            self._bind(key, character)
            return self._character(key, state["current"])

    def has_dirty(self, **scope):
        return bool(self._call("has_dirty", scope=scope))

    def flush(self, **scope):
        if scope.get("account_id") is not None:
            return self._flush_one(**scope)
        count, failure = 0, None
        for account in self._call("accounts", work_only=False):
            try:
                count += self._flush_one(**dict(scope, account_id=account))
            except Exception as error:
                failure = error
        if failure is not None:
            raise failure
        return count

    def flush_background(self, *, max_accounts, max_seconds, clock=time.monotonic):
        # Scheduling time and I/O execution stay here; candidate selection and
        # rotation of the durable work cursor belong to the native authority.
        accounts = self._call(
            "background_plan", max_accounts=max_accounts, max_seconds=max_seconds
        )["accounts"]
        if not self.background_lock.acquire(blocking=False):
            return dict(attempted=0, characters=0, failures=0, busy=True)
        try:
            started = clock()
            attempted = count = failures = 0
            for account in accounts:
                if clock() - started >= max_seconds:
                    break
                self._call("cursor_advance", account_id=account)
                attempted += 1
                try:
                    count += self._flush_one(account_id=account)
                except Exception as error:
                    failures += 1
                    self.observe(
                        "background_account_failed",
                        started,
                        account_id=account,
                        error_type=type(error).__name__,
                    )
            return dict(
                attempted=attempted, characters=count, failures=failures, busy=False
            )
        finally:
            self.background_lock.release()

    def _flush_one(self, **scope):
        if not self.has_dirty(**scope):
            return 0
        started = time.monotonic()
        with _recoverable_position_lock(), ExitStack() as transaction:
            db = transaction.enter_context(self.store.connection(timeout=0.25))
            self.observe("pool", started, account_id=scope.get("account_id"))
            return self._flush(db, commit=transaction.close, **scope)

    def _flush(self, db, *, commit, **scope):
        with self.flush_barrier(**scope):
            candidates = self._call("entries", scope=scope, dirty_only=True)
            if not candidates:
                return 0
            started = time.monotonic()
            db.execute("SET LOCAL lock_timeout = '250ms'")
            db.execute("SET LOCAL statement_timeout = '1000ms'")
            leases = []
            for candidate in candidates:
                key = tuple(candidate["key"])
                row = db.execute(
                    "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
                    (*key[:2], self.store.now()),
                ).fetchone()
                selected = None if row is None else row["character_id"]
                leases.append(
                    dict(
                        key=list(key),
                        selected_character_id=selected,
                        lease_active=selected == key[2]
                        and bool(self.lease_active(*key)),
                    )
                )
            plan = self._call("prepare_checkpoint", scope=scope, leases=leases)
            try:
                for entry in plan["writes"]:
                    key = entry["key"]
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
                            key[2],
                            key[0],
                            *[old[k] for k in _KEYS],
                        ),
                    )
                    if result.rowcount != 1:
                        raise ValueError("Buffered position storage CAS conflict")
                commit()
            except BaseException:
                self._call("abort", token=plan["token"])
                raise
            # The account guards still fence this prevalidated native token.
            # No lease checks, SQL or Redis happen while adopting committed data.
            self._call("commit_checkpoint", token=plan["token"])
            for key in plan["stale_keys"]:
                self.native.release_character(tuple(key), "positions")
            self.observe(
                "postgres_commit",
                started,
                account_id=scope.get("account_id"),
                characters=len(plan["writes"]),
            )
            return len(plan["writes"])

    def _release_plan(self, plan):
        self._call("release_commit", token=plan["token"])
        self.native.release_character(tuple(plan["key"]), "positions")

    def release_committed_transition(
        self, account_id, generation, character_id, source, destination
    ):
        key = (account_id, generation, character_id)
        with ExitStack() as transaction:
            db = transaction.enter_context(self.store.connection())
            with self.account_barrier(account_id):
                saved = db.execute(
                    "SELECT c.map_id,c.instance_id,c.x,c.y,c.z FROM characters c "
                    "JOIN sessions s ON s.account_id=c.account_id "
                    "WHERE c.id=%s AND c.account_id=%s AND s.generation=%s "
                    "AND s.character_id=c.id AND s.expires_at>%s",
                    (character_id, account_id, generation, self.store.now()),
                ).fetchone()
                transaction.close()
                plan = self._call(
                    "transition_prepare",
                    key=list(key),
                    source={k: source[k] for k in _KEYS},
                    destination={k: destination[k] for k in _KEYS[:-1]},
                    saved=None if saved is None else dict(saved),
                )
                self._release_plan(plan)

    def release(self, account_id, generation, character_id, *, discard_stale=False):
        key = (account_id, generation, character_id)
        with self.account_barrier(account_id):
            plan = self._call(
                "release_prepare",
                key=list(key),
                discard_stale=discard_stale,
                lease_active=discard_stale and bool(self.lease_active(*key)),
            )
            self._release_plan(plan)
