"""Redis journal transport for the native spatial position authority.

PostgreSQL owns committed leases. Rust validates records, selects recovery
outcomes and owns mirror/ACK state; this module performs only database I/O.
"""

from contextlib import ExitStack
from functools import lru_cache
import uuid
import time
from .position_buffer import Positions, _KEYS, _recoverable_position_lock


class PositionJournalError(ValueError):
    pass


class PositionJournalUnavailable(PositionJournalError):
    """A transient backend failure, distinct from a journal CAS conflict."""


_PUT = """local old=redis.call('HGET',KEYS[1],ARGV[1]);
if (ARGV[2]=='' and old) or (ARGV[2]~='' and old~=ARGV[2]) then return 0 end;
redis.call('HSET',KEYS[1],ARGV[1],ARGV[3]); return 1"""
_ACK = """local old=redis.call('HGET',KEYS[1],ARGV[1]);
if not old then return 1 end;
if old~=ARGV[2] then return 0 end;
redis.call('HDEL',KEYS[1],ARGV[1]); return 1"""


@lru_cache(maxsize=1)
def _record_validator():
    from wakfu_server.spatial_native import NativeSpatial

    return NativeSpatial()


def _journal_call(native, operation, **values):
    try:
        return native.call("positions." + operation, **values)
    except ValueError as error:
        raise PositionJournalError(str(error)) from error


def _identity(key):
    return _journal_call(_record_validator(), "identity", key=list(key))


def _position(value):
    return _journal_call(_record_validator(), "validate_position", value=value)


class Journal:
    def __init__(self, client, *, namespace="wakfu:positions:v2", native=None):
        from wakfu_server.spatial_native import NativeSpatial

        self.client = client
        self.namespace = namespace
        self.native = native if native is not None else NativeSpatial()

    def _call(self, method, *args):
        try:
            return getattr(self.client, method)(*args)
        except Exception as error:
            raise PositionJournalUnavailable(
                "Redis position journal unavailable"
            ) from error

    def put(self, key, entry, expected=None):
        record = _journal_call(
            self.native,
            "encode_record",
            key=list(key),
            entry={
                "current": {k: entry["current"][k] for k in _KEYS},
                "persisted": {k: entry["persisted"][k] for k in _KEYS},
            },
            revision=uuid.uuid4().hex,
        )
        if (
            self._call(
                "eval",
                _PUT,
                1,
                self.namespace,
                record["field"],
                expected or "",
                record["encoded"],
            )
            != 1
        ):
            raise PositionJournalError("Redis position revision conflict")
        return record["encoded"]

    def ack(self, key, encoded):
        field = _journal_call(self.native, "identity", key=list(key))
        return bool(self._call("eval", _ACK, 1, self.namespace, field, encoded))

    def records(self):
        try:
            rows = list(self.client.hscan_iter(self.namespace))
        except Exception as error:
            raise PositionJournalUnavailable(
                "Redis position journal unavailable"
            ) from error
        for field, encoded in rows:
            field = field.decode() if isinstance(field, bytes) else field
            encoded = encoded.decode() if isinstance(encoded, bytes) else encoded
            record = _journal_call(
                self.native, "validate_record", field=field, encoded=encoded
            )
            yield tuple(record["key"]), record["value"], encoded

    def recover(self, store):
        report = dict(recovered=0, already_committed=0, stale=0, conflicts=[])
        for key, value, encoded in self.records():
            account, generation, character_id = key
            with store.connection() as db:
                session = db.execute(
                    "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
                    (account, generation, store.now()),
                ).fetchone()
                row = db.execute(
                    "SELECT * FROM characters WHERE id=%s AND account_id=%s FOR UPDATE",
                    (character_id, account),
                ).fetchone()
                status = _journal_call(
                    self.native,
                    "record_status",
                    key=list(key),
                    value=value,
                    saved=None if row is None else {k: row[k] for k in _KEYS},
                    selected_character_id=(
                        None if session is None else session["character_id"]
                    ),
                )
                if status == "recoverable":
                    old, new = value["baseline"], value["current"]
                    changed = db.execute(
                        "UPDATE characters SET x=%s,y=%s,z=%s,direction=%s WHERE id=%s AND account_id=%s "
                        "AND map_id=%s AND instance_id=%s AND x=%s AND y=%s AND z=%s AND direction=%s",
                        (
                            new["x"],
                            new["y"],
                            new["z"],
                            new["direction"],
                            character_id,
                            account,
                            *[old[k] for k in _KEYS],
                        ),
                    )
                    if changed.rowcount != 1:
                        raise PositionJournalError(
                            "Position recovery storage CAS conflict"
                        )
                    status = "recovered"
            if status == "conflict":
                report["conflicts"].append(key)
            else:
                report[status] += 1
                self.ack(key, encoded)
        return report


class RedisPositions(Positions):
    def __init__(self, store, *, lease_active, journal, native=None):
        native = journal.native if native is None else native
        if journal.native is not native:
            raise ValueError("Position journal must share its native spatial authority")
        super().__init__(store, lease_active=lease_active, native=native)
        self.journal = journal

    @property
    def mirrors(self):
        return {
            tuple(row["key"]): row["encoded"]
            for row in self._call("journal_state")["mirrors"]
        }

    @property
    def pending_acks(self):
        return {
            tuple(row["key"]): row["encoded"]
            for row in self._call("journal_state")["pending_acks"]
        }

    def move(self, account_id, generation, character_id, start, end):
        key = (account_id, generation, character_id)
        with self.account_barrier(account_id):
            plan = self._prepare_move(key, start, end)
            try:
                encoded = self.journal.put(key, plan, plan.get("expected"))
            except BaseException:
                self._call("abort", token=plan["token"])
                raise
            state = self._call("commit_move", token=plan["token"], encoded=encoded)
            return self._character(key, state["current"])

    def _ack_pending(self, accounts):
        for record in self._call(
            "pending_acks", accounts=sorted(accounts), mark_clean_mirrors=True
        ):
            key, encoded = tuple(record["key"]), record["encoded"]
            if not self.journal.ack(key, encoded):
                raise PositionJournalError(
                    "Redis position changed after committed flush"
                )
            self._call("ack_complete", key=list(key), encoded=encoded)

    def _flush_one(self, **scope):
        with self.flush_barrier(**scope) as accounts:
            if not self.has_dirty(**scope):
                self._ack_pending(accounts)
                return 0
        started = time.monotonic()
        with _recoverable_position_lock(), ExitStack() as transaction:
            db = transaction.enter_context(self.store.connection(timeout=0.25))
            self.observe("pool", started, account_id=scope.get("account_id"))
            with self.flush_barrier(**scope) as accounts:
                self._ack_pending(accounts)
                count = self._flush(db, commit=transaction.close, **scope)
                started = time.monotonic()
                self._ack_pending(accounts)
                self.observe("redis_ack", started, account_id=scope.get("account_id"))
                return count

    def _release_plan(self, plan):
        encoded = plan.get("encoded")
        try:
            if encoded is not None and not self.journal.ack(
                tuple(plan["key"]), encoded
            ):
                raise PositionJournalError(
                    "Redis position revision conflict during release"
                )
        except BaseException:
            self._call("abort", token=plan["token"])
            raise
        super()._release_plan(plan)


def create(
    store, *, lease_active, url=None, namespace="wakfu:positions:v2", native=None
):
    """Both persistence configurations use the same mandatory native authority."""
    from wakfu_server.spatial_native import NativeSpatial

    native = native if native is not None else NativeSpatial()
    if not url:
        return Positions(store, lease_active=lease_active, native=native), None
    import redis

    journal = Journal(
        redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2),
        namespace=namespace,
        native=native,
    )
    journal._call("ping")
    recovery = journal.recover(store)
    if recovery["conflicts"]:
        raise PositionJournalError(
            "Redis position recovery has unresolved PostgreSQL baselines"
        )
    return (
        RedisPositions(
            store, lease_active=lease_active, journal=journal, native=native
        ),
        recovery,
    )
