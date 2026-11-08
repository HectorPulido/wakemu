"""Root deltas preserve retired cycles, actual leases and local traversal."""
import unittest
from wakfu_server.combat_retired_area_index import RetiredAreaIndex


class RetiredAreaIndexTests(unittest.TestCase):
    def test_cycle_waits_for_last_external_root_and_unknown_proof(self):
        graph = RetiredAreaIndex()
        graph.area(101, 102, active=False, retired=True, protected=False)
        graph.area(102, 101, active=False, retired=True, protected=False)
        graph.root(("record", 7), (101,))
        self.assertEqual(graph.plan(), ())
        graph.root(("record", 8), None)
        graph.root(("record", 7), ())
        self.assertIsNone(graph.plan())
        graph.root(("record", 8), ())
        self.assertEqual(graph.plan(), (101, 102))
        self.assertEqual(graph.tokens, {})

    def test_owner_rebind_releases_old_parent_after_last_caster_reference(self):
        graph = RetiredAreaIndex()
        graph.area(2, None, active=False, retired=True, protected=False)
        graph.area(3, None, active=False, retired=True, protected=True)
        graph.area(1, 2, active=True, retired=False, protected=False)
        graph.root(("ledger", 2), {2: 2})
        self.assertEqual(graph.plan(), ())
        graph.area(1, 3, active=True, retired=False, protected=False)
        graph.area(3, None, active=False, retired=True, protected=False)
        graph.root(("ledger", 2), {2: 1})
        self.assertEqual(graph.plan(), ())
        graph.root(("ledger", 2), {})
        self.assertEqual(graph.plan(), (2,))

    def test_local_root_delta_does_not_iterate_unrelated_history(self):
        graph = RetiredAreaIndex()
        for identity in range(1000, 1100):
            graph.area(identity, None, active=False, retired=True, protected=False)
            graph.root(("record", identity), (identity,))
        self.assertEqual(graph.plan(), ())

        class NoIteration(dict):
            def __iter__(self):
                raise AssertionError("global graph traversal")

            def items(self):
                raise AssertionError("global graph traversal")

            def keys(self):
                raise AssertionError("global graph traversal")

        graph.owners = NoIteration(graph.owners)
        graph.root(("record", 1042), ())
        self.assertEqual(graph.plan(), (1042,))
        graph.area(1042, None, active=False, retired=False, protected=False)
        self.assertEqual(graph.plan(), ())


if __name__ == "__main__":
    unittest.main()
