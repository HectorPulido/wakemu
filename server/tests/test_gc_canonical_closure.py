"""The graph proof must not retain inspected Fight graphs until cyclic GC."""
import gc
import unittest
import weakref
from wakfu_server.combat_state import Fight
from wakfu_server.combat_retained_gc_boundary import _canonical_graph


class CanonicalClosureTests(unittest.TestCase):
    def test_accept_reject_and_exception_release_inspected_fight_without_gc(self):
        class ExplodingActors(dict):
            def values(self):
                raise RuntimeError("intentional actor iteration failure")

        def inspect(mode):
            fight = Fight.__new__(Fight)
            fight.actors = ExplodingActors() if mode == "exception" else {}
            fight.payload = object() if mode == "reject" else {"nested": [1, 2]}
            reference = weakref.ref(fight)
            details = []
            if mode == "exception":
                try:
                    _canonical_graph(fight, diagnostic=details)
                except RuntimeError:
                    pass
                else:
                    self.fail("Expected actor iteration failure")
            else:
                self.assertIs(
                    _canonical_graph(fight, diagnostic=details), mode == "accept"
                )
                if mode == "reject":
                    self.assertEqual(
                        details,
                        [("payload", "object", "unsupported_or_nonplain_value")],
                    )
            return reference

        previous = gc.isenabled()
        gc.disable()
        try:
            for mode in ("accept", "reject", "exception"):
                with self.subTest(mode=mode):
                    self.assertIsNone(inspect(mode)())
        finally:
            if previous:
                gc.enable()
