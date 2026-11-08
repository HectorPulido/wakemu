"""Bounded synchronous batching of disposable, already-verified cache fills."""
from contextlib import contextmanager
from contextvars import ContextVar

_ACTIVE = ContextVar("native_verified_cache_fill_batch", default=None)
_MAX_ENTRIES = 128
_MAX_BYTES = 8 * 1024 * 1024


class _Batch:
    def __init__(self):
        self.rows = []
        self.bytes = 0

    def flush(self):
        pending, self.rows = self.rows, []
        self.bytes = 0
        groups = {}
        for backend, key, raw in pending:
            identity = id(backend)
            if identity not in groups:
                groups[identity] = (backend, [])
            groups[identity][1].append((key, raw))
        for backend, rows in groups.values():
            backend._fill_cached_records(rows)

    def add(self, backend, rows):
        for key, raw in rows:
            size = len(key.encode()) + len(raw)
            if self.rows and (
                len(self.rows) >= _MAX_ENTRIES or self.bytes + size > _MAX_BYTES
            ):
                self.flush()
            if size > _MAX_BYTES:
                backend._fill_cached_records([(key, raw)])
            else:
                self.rows.append((backend, key, raw))
                self.bytes += size


def fill_or_defer(backend, rows):
    batch = _ACTIVE.get()
    if batch is None:
        backend._fill_cached_records(rows)
    else:
        batch.add(backend, rows)


@contextmanager
def verified_cache_fill_scope():
    """Reads and checksum/SQL authority stay immediate; only Redis writes wait.

    The owning scope flushes synchronously, even on gameplay failure. These
    immutable PostgreSQL rows remain valid independently of action rollback.
    Nested scopes reuse the same bound; no worker or thread is created.
    """
    if _ACTIVE.get() is not None:
        yield
        return
    batch = _Batch()
    token = _ACTIVE.set(batch)
    try:
        yield
    finally:
        _ACTIVE.reset(token)
        batch.flush()
