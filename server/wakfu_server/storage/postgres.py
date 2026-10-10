"""PostgreSQL connection ownership and versioned schema; no dialect adapters."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import re
import time

from psycopg import connect
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from .performance_profiler import PROFILER


def _observe_duration(name, started, *, error=False):
    """Diagnostics must never change connection or transaction outcomes."""
    try:
        PROFILER.observe(name, time.monotonic() - started, error=error)
    except Exception:
        pass


class Database:
    def __init__(self, conninfo, *, password_file=None, min_size=1, max_size=12):
        kwargs = {"row_factory": dict_row}
        if password_file is not None:
            kwargs["password"] = Path(password_file).read_text().strip()
            if not kwargs["password"]:
                raise ValueError("Empty PostgreSQL password file")
        self.conninfo = conninfo
        self.connection_kwargs = kwargs
        self.runtime_lock_connection = None
        self.pool = ConnectionPool(
            conninfo,
            kwargs=kwargs,
            min_size=min_size,
            max_size=max_size,
            open=False,
            timeout=10,
        )
        self.pool.open(wait=True)

    @contextmanager
    def connection(self, *, timeout=None):
        pool_started = time.monotonic()
        acquired = False
        try:
            with self.pool.connection(timeout=timeout) as db:
                acquired = True
                _observe_duration("postgres.pool_wait", pool_started)
                transaction_started = time.monotonic()
                failed = True
                try:
                    with db.transaction():
                        yield db
                    failed = False
                finally:
                    _observe_duration(
                        "postgres.transaction", transaction_started, error=failed
                    )
        finally:
            if not acquired:
                _observe_duration("postgres.pool_wait", pool_started, error=True)

    def acquire_runtime_lock(self):
        """Prevent a second world from recovering the same live database."""
        if self.runtime_lock_connection is not None:
            return
        connection = connect(
            self.conninfo, **self.connection_kwargs, autocommit=True, connect_timeout=10
        )
        try:
            acquired = connection.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired", (5790545554,)
            ).fetchone()["acquired"]
            if not acquired:
                raise RuntimeError(
                    "Another world owns this PostgreSQL database; use an isolated database"
                )
        except BaseException:
            connection.close()
            raise
        self.runtime_lock_connection = connection

    def close(self):
        try:
            self.pool.close()
        finally:
            if self.runtime_lock_connection is not None:
                self.runtime_lock_connection.close()
                self.runtime_lock_connection = None


def migrate(db, directory):
    """Apply a checked prefix under one transaction and cross-process lock."""
    files = []
    for path in sorted(Path(directory).glob("*.sql")):
        match = re.fullmatch(r"([0-9]{3})_[a-z0-9_]+\.sql", path.name)
        if match is None:
            raise ValueError("Invalid migration filename")
        raw = path.read_bytes()
        files.append((int(match[1]), sha256(raw).hexdigest(), raw.decode("utf8")))
    if not files or [v for v, _, _ in files] != list(range(1, len(files) + 1)):
        raise ValueError("Migration versions must form a contiguous sequence")
    with db.transaction():
        db.execute("SELECT pg_advisory_xact_lock(%s)", (5790545553,))
        db.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
            version integer PRIMARY KEY, checksum text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
        )
        applied = {
            r["version"]: r["checksum"]
            for r in db.execute("SELECT version,checksum FROM schema_migrations")
        }
        if sorted(applied) != list(range(1, len(applied) + 1)):
            raise ValueError("Applied migrations contain a gap")
        expected = {v: checksum for v, checksum, _ in files}
        if any(expected.get(v) != checksum for v, checksum in applied.items()):
            raise ValueError("Applied migration checksum differs from source")
        count = 0
        for version, checksum, sql in files:
            if version in applied:
                continue
            db.execute(sql, prepare=False)
            db.execute(
                "INSERT INTO schema_migrations(version,checksum) VALUES(%s,%s)",
                (version, checksum),
            )
            count += 1
        return count
