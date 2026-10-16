"""Cold bootstrap pool ownership and account/session lock order regressions."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import unittest

ROOT = Path(__file__).resolve().parents[1]


def extract(path, name, namespace):
    node = next(
        n for n in ast.parse(path.read_text()).body if getattr(n, "name", None) == name
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            str(path),
            "exec",
        ),
        namespace,
    )
    return namespace[name]


class OrderedDatabase:
    def __init__(self):
        self.account_locked = False
        self.calls = []
        self.row = {"account_id": 5, "generation": "owned"}

    def execute(self, sql, params):
        self.calls.append(sql)
        if "FOR UPDATE" in sql and not self.account_locked:
            raise AssertionError("Session locked before account")
        return self

    def fetchone(self):
        return self.row


class LoginConcurrencyTests(unittest.TestCase):
    def test_intergame_all_entrypoints_lock_account_before_session(self):
        for method in ("issue_token", "authenticate", "_authorize"):
            with self.subTest(method=method):
                db = OrderedDatabase()

                @contextmanager
                def connection():
                    yield db

                def guard(db, account, now):
                    db.account_locked = True

                def authorize(store, db, *args):
                    if not db.account_locked:
                        raise AssertionError(
                            "Session authorization before account guard"
                        )

                ns = {
                    "secrets": secrets,
                    "require_access": guard,
                    "_authorize": authorize,
                }
                cls = extract(
                    ROOT / "wakfu_server/intergame_domain.py", "Intergame", ns
                )
                store = SimpleNamespace(
                    connection=connection,
                    digest=lambda token: "digest",
                    now=lambda *args: 1,
                )
                service = cls(store)
                if method == "_authorize":
                    service._authorize(db, {"account_id": 5, "generation": "owned"})
                else:
                    getattr(service, method)("valid-native-token-value")
                self.assertTrue(db.account_locked)
                if method != "_authorize":
                    self.assertTrue(any("FOR UPDATE" in sql for sql in db.calls))

    def test_missing_token_is_rejected_without_acquiring_session(self):
        db = OrderedDatabase()
        db.row = None

        @contextmanager
        def connection():
            yield db

        ns = {"secrets": secrets, "require_access": lambda *args: None}
        cls = extract(ROOT / "wakfu_server/intergame_domain.py", "Intergame", ns)
        store = SimpleNamespace(
            connection=connection, digest=lambda token: "digest", now=lambda *args: 1
        )
        for method in ("issue_token", "authenticate"):
            with self.assertRaises(PermissionError):
                getattr(cls(store), method)("valid-native-token-value")
        self.assertFalse(any("FOR UPDATE" in sql for sql in db.calls))

    def test_protector_policy_does_not_hold_catalog_pool_during_cold_read(self):
        catalog_busy = False

        @contextmanager
        def policy_connection():
            yield "policy-db"

        def forbidden():
            raise AssertionError("Policy borrowed bounded catalog pool")

        def bootstrap(db, *args, **kwargs):
            self.assertEqual(db, "policy-db")
            self.assertFalse(catalog_busy)
            return ("encoded",)

        ns = {
            "_policy_database": lambda: SimpleNamespace(connection=policy_connection),
            "native_catalog": SimpleNamespace(_database=forbidden),
            "bootstrap_records": bootstrap,
        }
        call = extract(
            ROOT / "wakfu_server/maps/protector_ecosystem.py", "message_records", ns
        )
        self.assertEqual(call(1385), ("encoded",))

    def test_twelve_cold_joins_do_not_exhaust_two_catalog_connections(self):
        class Pool:
            def __init__(self, size):
                self.semaphore = threading.BoundedSemaphore(size)

            @contextmanager
            def connection(self):
                if not self.semaphore.acquire(timeout=0.2):
                    raise TimeoutError("pool exhausted")
                try:
                    yield self
                finally:
                    self.semaphore.release()

        def run(use_policy):
            catalog = Pool(2)
            policy = Pool(12)
            pairs = threading.Barrier(2)

            def bootstrap(db, *args, **kwargs):
                pairs.wait(timeout=2)
                with catalog.connection():
                    time.sleep(0.005)
                return ("encoded",)

            ns = {
                "_policy_database": lambda: policy,
                "native_catalog": SimpleNamespace(_database=lambda: catalog),
                "bootstrap_records": bootstrap,
            }
            call = extract(
                ROOT / "wakfu_server/maps/protector_ecosystem.py", "message_records", ns
            )
            if not use_policy:
                ns["_policy_database"] = lambda: catalog

            def worker(_):
                try:
                    return call(1385)
                except TimeoutError:
                    return "pool exhausted"

            with ThreadPoolExecutor(max_workers=12) as executor:
                return list(executor.map(worker, range(12)))

        original = run(False)
        self.assertIn("pool exhausted", original)
        self.assertEqual(run(True), [("encoded",)] * 12)


if __name__ == "__main__":
    unittest.main()
