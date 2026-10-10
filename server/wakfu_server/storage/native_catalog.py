"""Versioned PostgreSQL catalog authority with bounded Redis caching.

Plain files are import artifacts. Readers pin one published release so a
process never mixes catalog versions. Protocol reads never fall back to files.
"""
import builtins
import hashlib
import io
import json
import logging
import os
import time
import threading
from functools import lru_cache
from pathlib import Path

from wakfu_server.paths import DATA_ROOT

LOG = logging.getLogger(__name__)
CACHE_MAX_BYTES = 2 * 1024 * 1024
CACHE_TTL = 3600
_decode_lock = threading.RLock()


def _key(path):
    try:
        return Path(path).resolve().relative_to(DATA_ROOT.resolve()).as_posix()
    except ValueError:
        return None


def _live(path):
    return _key(path) is not None


@lru_cache(maxsize=1)
def _database():
    from wakfu_server.postgres import Database

    return Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        min_size=1,
        max_size=2,
    )


@lru_cache(maxsize=1)
def _redis():
    import redis

    return redis.Redis.from_url(
        os.environ["WAKFU_REDIS_URL"], socket_connect_timeout=1, socket_timeout=1
    )


@lru_cache(maxsize=1)
def release():
    with _database().connection() as db:
        row = db.execute(
            "SELECT a.revision FROM native_catalog_active a "
            "JOIN native_catalog_releases r USING(revision) "
            "WHERE a.id=1 AND r.complete"
        ).fetchone()
    if row is None:
        raise RuntimeError("No published native catalog release")
    expected = os.environ.get("WAKFU_CATALOG_REVISION")
    if expected and row["revision"] != expected:
        raise RuntimeError("Published native catalog release differs from image")
    return row["revision"]


def document_hashes():
    """Return the active release's published path-to-SHA256 inventory."""
    revision = release()
    with _database().connection() as db:
        rows = db.execute(
            "SELECT path,sha256 FROM native_catalog_documents "
            "WHERE revision=%s ORDER BY path",
            (revision,),
        ).fetchall()
    return {row["path"]: row["sha256"] for row in rows}


def read_bytes(path):
    if not _live(path):
        return Path(path).read_bytes()
    started = time.monotonic()
    name = _key(path)
    revision = release()
    redis_started = time.monotonic()
    cache_key = "wakemu:catalog:" + revision + ":" + name
    try:
        cached = _redis().get(cache_key)
    except Exception as error:
        LOG.warning(
            "Catalog Redis read failed; using PostgreSQL: %s", type(error).__name__
        )
        cached = None
    redis_ms = (time.monotonic() - redis_started) * 1000
    if cached is not None:
        digest, separator, raw = cached.partition(b"\n")
        if separator and hashlib.sha256(raw).hexdigest().encode() == digest:
            _observe_read(name, "redis", raw, started, redis_ms=redis_ms)
            return raw
        LOG.error("Invalid Redis catalog payload: %s", name)
    pool_started = time.monotonic()
    with _database().connection() as db:
        pool_ms = (time.monotonic() - pool_started) * 1000
        query_started = time.monotonic()
        row = db.execute(
            "SELECT raw,sha256 FROM native_catalog_documents "
            "WHERE revision=%s AND path=%s",
            (revision, name),
        ).fetchone()
        query_ms = (time.monotonic() - query_started) * 1000
    if row is None:
        raise FileNotFoundError(name)
    raw = bytes(row["raw"])
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("Native catalog checksum mismatch: " + name)
    if len(raw) <= CACHE_MAX_BYTES:
        try:
            _redis().setex(cache_key, CACHE_TTL, row["sha256"].encode() + b"\n" + raw)
        except Exception as error:
            LOG.warning("Catalog Redis write failed: %s", type(error).__name__)
    _observe_read(
        name,
        "postgres",
        raw,
        started,
        redis_ms=redis_ms,
        pool_ms=pool_ms,
        query_ms=query_ms,
    )
    return raw


def _observe_read(name, source, raw, started, **stages):
    """Bounded slow-read metadata; never log catalog contents or credentials."""
    elapsed_ms = (time.monotonic() - started) * 1000
    # Aggregate fixed labels, never individual document paths or cache keys.
    from .performance_profiler import PROFILER

    try:
        PROFILER.observe("catalog.read." + source, elapsed_ms / 1000)
        for stage in ("redis_ms", "query_ms"):
            if stage in stages:
                PROFILER.observe("catalog." + stage[:-3], stages[stage] / 1000)
    except Exception:
        pass
    if elapsed_ms >= 250:
        LOG.warning(
            "Slow native catalog read path=%s source=%s bytes=%s elapsed_ms=%.3f stages=%s",
            name,
            source,
            len(raw),
            elapsed_ms,
            {key: round(value, 3) for key, value in stages.items()},
        )


def read_text(path, encoding="utf8"):
    return read_bytes(path).decode(encoding)


@lru_cache(maxsize=32)
def _decoded(revision, name):
    return json.loads(read_bytes(DATA_ROOT / name))


def load(path):
    if not _live(path):
        return json.loads(Path(path).read_bytes())
    # Share parsed documents across readers, including cold concurrent calls.
    # Domain indexes keep referencing this immutable source instead of each
    # reader decoding a second copy of large spell/state catalogs.
    with _decode_lock:
        return _decoded(release(), _key(path))


def open(path, mode="rt", encoding=None):
    if not _live(path):
        return builtins.open(path, mode, encoding=encoding)
    if mode not in ("r", "rt", "rb"):
        raise ValueError("Native catalogs are read-only")
    stream = io.BytesIO(read_bytes(path))
    return (
        stream
        if mode == "rb"
        else io.TextIOWrapper(stream, encoding=encoding or "utf8")
    )


@lru_cache(maxsize=8192)
def _exists(revision, name):
    with _database().connection() as db:
        return (
            db.execute(
                "SELECT 1 FROM native_catalog_documents "
                "WHERE revision=%s AND path=%s",
                (revision, name),
            ).fetchone()
            is not None
        )


def exists(path):
    return _exists(release(), _key(path)) if _live(path) else Path(path).is_file()


def record(path, collection, record_key):
    """Read a single entity through the PostgreSQL composite primary index."""
    if not _live(path):
        rows = load(path)[collection]
        if isinstance(rows, dict):
            return rows.get(str(record_key))
        raise ValueError("Indexed record lookup requires database backend for arrays")
    with _database().connection() as db:
        row = db.execute(
            "SELECT payload FROM native_catalog_records WHERE revision=%s "
            "AND path=%s AND collection=%s AND record_key=%s",
            (release(), _key(path), collection, str(record_key)),
        ).fetchone()
    return row["payload"] if row else None
