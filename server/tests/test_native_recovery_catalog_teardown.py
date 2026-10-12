"""Actual private catalog class callbacks, isolated from engine/catalog imports."""
import ast, gc, threading, unittest, weakref
from pathlib import Path


class Tests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(
            (
                Path(__file__).resolve().parents[1]
                / "wakfu_server/combat/combat_static_catalogs.py"
            ).read_text()
        )
        nodes = [
            n
            for n in tree.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef))
            and n.name in ("ImmutableCatalog", "_freeze")
        ]
        self.ns = {
            "threading": threading,
            "weakref": weakref,
            "_VIEW_CACHE_LOCK": threading.RLock(),
            "_VIEW_CACHE": {},
        }
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                "private_catalog",
                "exec",
            ),
            self.ns,
        )
        self.cls = self.ns["ImmutableCatalog"]
        self.cache = self.ns["_VIEW_CACHE"]
        self.lock = self.ns["_VIEW_CACHE_LOCK"]

    def owner(self):
        owner = self.cls({"nested": {"value": 1}})
        owner["nested"]
        entry = self.cache[id(owner)]
        return owner, entry[0], entry[0].__callback__

    def test_actual_gc_after_module_globals_cleared(self):
        owner, reference, callback = self.owner()
        identity = id(owner)
        self.ns["_VIEW_CACHE_LOCK"] = None
        self.ns["_VIEW_CACHE"] = None
        del owner
        gc.collect()
        self.assertIsNone(reference())
        self.assertNotIn(identity, self.cache)

    def test_stale_callback_preserves_replacement_identity(self):
        owner, reference, callback = self.owner()
        identity = id(owner)
        replacement = weakref.ref(self.cls({}))
        self.cache[identity] = (replacement, {})
        callback(reference)
        self.assertIs(self.cache[identity][0], replacement)

    def test_callback_keeps_original_lock_and_cache(self):
        owner, reference, callback = self.owner()
        new = {id(owner): ("new", {})}
        self.ns["_VIEW_CACHE"] = new
        self.ns["_VIEW_CACHE_LOCK"] = None
        callback(reference)
        self.assertNotIn(id(owner), self.cache)
        self.assertIn(id(owner), new)

    def test_callback_waits_for_shared_lock(self):
        owner, reference, callback = self.owner()
        entered = threading.Event()
        finished = threading.Event()

        def worker():
            entered.set()
            callback(reference)
            finished.set()

        with self.lock:
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(entered.wait(1))
            self.assertFalse(finished.wait(0.05))
            self.assertIn(id(owner), self.cache)
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertTrue(finished.is_set())
        self.assertNotIn(id(owner), self.cache)


if __name__ == "__main__":
    unittest.main()
