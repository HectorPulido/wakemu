"""The actual Store selection producer must use World's public exception type."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import unittest

from psycopg.pq import TransactionStatus

from wakfu_server.heroes import CompanySelectionRejected
from wakfu_server.store import Store


class _Rows:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _FrozenCompanyDatabase:
    """Return locked relational facts, not substituted domain exceptions."""

    info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)

    def __init__(self):
        self.queries = []

    def execute(self, sql, params=()):
        self.queries.append(sql)
        if "FROM account_hero_rosters" in sql:
            return _Rows([{"leader_id": 101}])
        if "FROM account_hero_slots" in sql:
            return _Rows([{"character_id": 102}])
        if "SELECT id FROM characters" in sql:
            return _Rows({"id": identity} for identity in (101, 102, 103))
        if "FROM combat_fight_participants" in sql:
            return _Rows()
        if "FROM rift_instances" in sql:
            return _Rows([{"exists": 1}])
        if "FROM accounts" in sql or "FROM sessions" in sql:
            return _Rows()
        raise AssertionError("Unexpected operation after company preflight: " + sql)


def _select_while_frozen(store_class):
    database = _FrozenCompanyDatabase()

    @contextmanager
    def connection():
        yield database

    store = store_class.__new__(store_class)
    store.connection = connection
    store.lock_character = lambda db, owner, generation, identity, **kw: None
    try:
        store.select_character(7, "current-owned-generation", 103)
    finally:
        assert not any(
            sql.lstrip().startswith(("UPDATE", "INSERT", "DELETE"))
            for sql in database.queries
        )


class CompanySelectionNamespaceTests(unittest.TestCase):
    def test_actual_store_selection_raises_public_catchable_company_rejection(self):
        with self.assertRaisesRegex(CompanySelectionRejected, "active rift"):
            _select_while_frozen(Store)

    def test_recorded_live_store_reproduces_uncaught_nested_exception(self):
        path = (
            Path(__file__).resolve().parents[2]
            / ".runtime"
            / "rift-namespace-repair"
            / "store-before-company-namespace.py"
        )
        if not path.is_file():
            self.skipTest("Private incident source is not part of default checkout")
        spec = importlib.util.spec_from_file_location("_company_incident_store", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(ValueError) as caught:
            _select_while_frozen(module.Store)
        self.assertEqual(type(caught.exception).__name__, "CompanySelectionRejected")
        self.assertFalse(isinstance(caught.exception, CompanySelectionRejected))


if __name__ == "__main__":
    unittest.main()
