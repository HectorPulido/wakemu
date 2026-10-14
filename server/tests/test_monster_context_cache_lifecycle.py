"""Interrupted contexts never leak cached fixtures into the next native case."""
import unittest
from qualify_monster_exact_context_queue import verified_fixture_cache_scope


class Cache:
    def __init__(self):
        self.entries = {"attested": object()}

    def clear(self):
        self.entries.clear()


class ContextCacheLifecycleTests(unittest.TestCase):
    def test_completed_context_retains_same_attested_fixture(self):
        cache = Cache()
        before = cache.entries["attested"]
        with verified_fixture_cache_scope(cache):
            self.assertIs(cache.entries["attested"], before)
        self.assertIs(cache.entries["attested"], before)

    def test_timeout_and_error_invalidate_before_next_context(self):
        for error in (
            TimeoutError("bounded"),
            ValueError("native failure"),
            KeyboardInterrupt(),
        ):
            with self.subTest(error=type(error).__name__):
                cache = Cache()
                with self.assertRaises(type(error)):
                    with verified_fixture_cache_scope(cache):
                        raise error
                self.assertEqual(cache.entries, {})
