"""Optional Redis write-ahead mirror for generation-scoped position batches.

PostgreSQL owns leases and committed state. Redis holds only validated unflushed
positions, including the exact PostgreSQL baseline required for crash recovery.
This is not a distributed world server or a replacement for PostgreSQL ownership.
"""
from contextlib import ExitStack
import copy
import json
import uuid
import time
from .position_buffer import Positions, _KEYS


class PositionJournalError(ValueError):
    pass


class PositionJournalUnavailable(PositionJournalError):
    """Transient backend failure, distinct from malformed data or CAS conflict."""


_PUT = """local old=redis.call('HGET',KEYS[1],ARGV[1]);
if (ARGV[2]=='' and old) or (ARGV[2]~='' and old~=ARGV[2]) then return 0 end;
redis.call('HSET',KEYS[1],ARGV[1],ARGV[3]); return 1"""
_ACK = """local old=redis.call('HGET',KEYS[1],ARGV[1]);
if not old then return 1 end;
if old~=ARGV[2] then return 0 end;
redis.call('HDEL',KEYS[1],ARGV[1]); return 1"""


def _identity(key):
    account, generation, character = key
    if (
        type(account) is not int
        or account <= 0
        or type(character) is not int
        or character <= 0
        or not isinstance(generation, str)
        or not generation
        or len(generation) > 512
    ):
        raise PositionJournalError("Invalid journal owner identity")
    return json.dumps([account, generation, character], separators=(",", ":"))


def _position(value):
    if not isinstance(value, dict) or set(value) != set(_KEYS):
        raise PositionJournalError("Invalid journal position fields")
    for field, bits in (
        ("map_id", 32),
        ("instance_id", 64),
        ("x", 32),
        ("y", 32),
        ("z", 16),
    ):
        if type(value[field]) is not int or not -(1 << (bits - 1)) <= value[field] < (
            1 << (bits - 1)
        ):
            raise PositionJournalError("Invalid journal position range")
    if type(value["direction"]) is not int or not 0 <= value["direction"] <= 7:
        raise PositionJournalError("Invalid journal direction")
    return value


class Journal:
    def __init__(self, client, *, namespace="wakfu:positions:v2"):
        self.client = client
        self.namespace = namespace

    def _call(self, method, *args):
        try:
            return getattr(self.client, method)(*args)
        except Exception as error:
            raise PositionJournalUnavailable(
                "Redis position journal unavailable"
            ) from error

    def put(self, key, entry, expected=None):
        value = dict(
            version=2,
            owner=list(key),
            revision=uuid.uuid4().hex,
            baseline={k: entry["persisted"][k] for k in _KEYS},
            current={k: entry["current"][k] for k in _KEYS},
        )
        _identity(key)
        _position(value["baseline"])
        _position(value["current"])
        if any(
            value["baseline"][k] != value["current"][k]
            for k in ("map_id", "instance_id")
        ):
            raise PositionJournalError(
                "Map transitions require a flushed position barrier"
            )
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if (
            self._call(
                "eval", _PUT, 1, self.namespace, _identity(key), expected or "", encoded
            )
            != 1
        ):
            raise PositionJournalError("Redis position revision conflict")
        return encoded

    def ack(self, key, encoded):
        # A later revision may exist; never delete it with an old flush ACK.
        return bool(
            self._call("eval", _ACK, 1, self.namespace, _identity(key), encoded)
        )

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
            try:
                value = json.loads(encoded)
                key = tuple(value["owner"])
                if (
                    value["version"] != 2
                    or field != _identity(key)
                    or not isinstance(value["revision"], str)
                    or len(value["revision"]) != 32
                ):
                    raise PositionJournalError("Invalid Redis position record identity")
                _position(value["baseline"])
                _position(value["current"])
                if any(
                    value["baseline"][k] != value["current"][k]
                    for k in ("map_id", "instance_id")
                ):
                    raise PositionJournalError("Invalid Redis position map transition")
            except (KeyError, TypeError, json.JSONDecodeError) as error:
                raise PositionJournalError("Invalid Redis position record") from error
            yield key, value, encoded

    def recover(self, store):
        """Replay CAS only for current selected PostgreSQL leases, before accepting clients.

        A crash after PostgreSQL commit but before Redis ACK is recognized as already
        committed. Conflicting baselines remain in Redis and are reported untouched.
        Expired/replaced leases are removed, never applied to a new generation.
        """
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
                if (
                    session is None
                    or session["character_id"] != character_id
                    or row is None
                ):
                    status = "stale"
                elif all(row[k] == value["current"][k] for k in _KEYS):
                    status = "already_committed"
                elif all(row[k] == value["baseline"][k] for k in _KEYS):
                    old = value["baseline"]
                    new = value["current"]
                    changed = db.execute(
                        "UPDATE characters SET x=%s,y=%s,z=%s,direction=%s WHERE id=%s AND account_id=%s AND map_id=%s AND instance_id=%s AND x=%s AND y=%s AND z=%s AND direction=%s",
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
                else:
                    status = "conflict"
            if status == "conflict":
                report["conflicts"].append(key)
            else:
                report[status] += 1
                self.ack(key, encoded)
        return report


class RedisPositions(Positions):
    def __init__(self, store, *, lease_active, journal):
        super().__init__(store, lease_active=lease_active)
        self.journal = journal
        self.mirrors = {}
        self.pending_acks = {}

    def move(self, account_id, generation, character_id, start, end):
        key = (account_id, generation, character_id)
        with self.account_barrier(account_id):
            if key not in self.entries:
                raise ValueError("Stale buffered position session")
            # Use the same validated algorithm on an isolated candidate; durable
            # Redis write occurs before any authoritative in-memory mutation.
            candidate = Positions(self.store, lease_active=self.lease_active)
            candidate.entries[key] = copy.deepcopy(self.entries[key])
            current = candidate.move(account_id, generation, character_id, start, end)
            entry = candidate.entries[key]
            encoded = self.journal.put(key, entry, self.mirrors.get(key))
            with self.lock:
                self.entries[key] = entry
                self.mirrors[key] = encoded
                self.pending_acks.pop(key, None)
                if not entry["dirty"]:
                    self.pending_acks[key] = encoded
            return current

    def _ack_pending(self, accounts):
        with self.lock:
            pending = list(self.pending_acks.items())
        for key, encoded in pending:
            if key[0] not in accounts:
                continue
            if not self.journal.ack(key, encoded):
                raise PositionJournalError(
                    "Redis position changed after committed flush"
                )
            with self.lock:
                self.pending_acks.pop(key, None)
                if self.mirrors.get(key) == encoded:
                    self.mirrors.pop(key, None)

    def registered_accounts(self):
        with self.lock:
            return (
                super().registered_accounts()
                | {key[0] for key in self.pending_acks}
                | {key[0] for key in self.mirrors}
            )

    def background_accounts(self):
        with self.lock:
            return (
                super().background_accounts()
                | {key[0] for key in self.pending_acks}
                | {key[0] for key in self.mirrors}
            )

    def _flush_one(self, **scope):
        # Redis ACK recovery remains work even after PostgreSQL committed and
        # cleared dirty state. Clean mirrors need Redis only, never a DB slot.
        with self.flush_barrier(**scope) as accounts:
            if not self.has_dirty(**scope):
                with self.lock:
                    for key, encoded in self.mirrors.items():
                        entry = self.entries.get(key)
                        if key[0] in accounts and (entry is None or not entry["dirty"]):
                            self.pending_acks[key] = encoded
                self._ack_pending(accounts)
                return 0
        # Acquire scarce DB capacity before holding any account barrier.
        started = time.monotonic()
        with ExitStack() as transaction:
            db = transaction.enter_context(self.store.connection(timeout=0.25))
            self.observe("pool", started, account_id=scope.get("account_id"))
            with self.flush_barrier(**scope) as accounts:
                self._ack_pending(accounts)
                count = self._flush(db, commit=transaction.close, **scope)
                with self.lock:
                    mirrors = list(self.mirrors.items())
                for key, encoded in mirrors:
                    if key[0] not in accounts:
                        continue
                    entry = self.entries.get(key)
                    if entry is None or not entry["dirty"]:
                        with self.lock:
                            self.pending_acks[key] = encoded
                started = time.monotonic()
                self._ack_pending(accounts)
                self.observe("redis_ack", started, account_id=scope.get("account_id"))
                return count

    def release(self, account_id, generation, character_id, *, discard_stale=False):
        key = (account_id, generation, character_id)
        with self.account_barrier(account_id):
            entry = self.entries.get(key)
            if entry is not None and entry["dirty"] and not discard_stale:
                raise ValueError("Flush position before release")
            if discard_stale and self.lease_active(*key):
                raise ValueError("Cannot discard a live authoritative position")
            encoded = self.mirrors.get(key)
            if encoded is not None:
                if not self.journal.ack(key, encoded):
                    raise PositionJournalError(
                        "Redis position revision conflict during release"
                    )
                with self.lock:
                    self.mirrors.pop(key, None)
                    self.pending_acks.pop(key, None)
            super().release(
                account_id, generation, character_id, discard_stale=discard_stale
            )


def create(store, *, lease_active, url=None, namespace="wakfu:positions:v2"):
    """No URL means the existing memory-only backend, with no Redis import/network."""
    if not url:
        return Positions(store, lease_active=lease_active), None
    import redis

    journal = Journal(
        redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2),
        namespace=namespace,
    )
    journal._call("ping")
    recovery = journal.recover(store)
    if recovery["conflicts"]:
        raise PositionJournalError(
            "Redis position recovery has unresolved PostgreSQL baselines"
        )
    return RedisPositions(store, lease_active=lease_active, journal=journal), recovery
