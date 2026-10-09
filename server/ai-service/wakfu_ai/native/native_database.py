"""Read complete SQL authorities within the owner thread's turn allowance."""
from contextlib import contextmanager
from .native_deadline import check, remaining


class _DeadlineConnection:
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, query, *args, **kwargs):
        check()
        available = remaining()
        # Transaction characteristics must precede any SELECT in PostgreSQL.
        if available is not None and not str(query).startswith("SET TRANSACTION"):
            self.connection.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (str(max(1, int(available * 1000))),),
            )
        result = self.connection.execute(query, *args, **kwargs)
        check()
        return result


@contextmanager
def connection(store):
    check()
    available = remaining()
    pool = getattr(getattr(store, "database", None), "pool", None)
    if available is None or pool is None:
        with store.connection() as db:
            yield db
    else:
        # Preserve the native transaction and row factory. Bound pool waits as
        # well as statements without changing the world's shared Store.
        with pool.connection(timeout=available) as db:
            with db.transaction():
                yield _DeadlineConnection(db)
    check()
