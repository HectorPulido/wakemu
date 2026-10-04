import tempfile, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import owned_instance


class DurableGroupsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "world.sqlite3")
        self.groups = PersistentGroups(self.store)
        self.members = [owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)]
        self.key = self.groups.register(1134, 0, 501, self.members)

    def test_defeated_survives_restart_without_implicit_respawn(self):
        lease, _ = self.groups.claim(self.key, "alpha", 77)
        self.assertTrue(self.groups.finish(lease, defeated=True))
        after = PersistentGroups(self.store, recover=True)
        self.assertEqual(after.register(1134, 0, 501, self.members), self.key)
        self.assertEqual(after.available(1134, 0), [])
        self.assertEqual(after.respawn(self.key), tuple(self.members))
        self.assertEqual(len(after.available(1134, 0)), 1)

    def test_restart_aborts_reserved_and_invalidates_old_lease(self):
        old, _ = self.groups.claim(self.key, "alpha", 77)
        self.assertEqual(PersistentGroups(self.store).available(1134, 0), [])
        after = PersistentGroups(self.store, recover=True)
        self.assertEqual(len(after.available(1134, 0)), 1)
        new, _ = after.claim(self.key, "alpha", 77)
        self.assertFalse(after.finish(old, defeated=True))
        self.assertTrue(after.finish(new, defeated=False))

    def test_sqlite_serializes_distinct_registry_workers(self):
        second = PersistentGroups(self.store)

        def reserve(pair):
            registry, generation = pair
            try:
                return registry.claim(self.key, generation, 77)[0]
            except ValueError:
                return None

        with ThreadPoolExecutor(2) as pool:
            claims = list(pool.map(reserve, [(self.groups, "a"), (second, "b")]))
        self.assertEqual(sum(c is not None for c in claims), 1)
        winner = next(c for c in claims if c)
        self.assertEqual(second.release_session("unrelated"), [])
        self.assertEqual(len(second.release_session(winner[1])), 1)
        self.assertFalse(self.groups.finish(winner, defeated=True))

    def test_respawn_due_only_after_delay_and_once(self):
        now = [100.0]
        self.groups.clock = lambda: now[0]
        lease, _ = self.groups.claim(self.key, "alpha", 77)
        self.groups.finish(lease, defeated=True)
        now[0] = 159
        self.assertEqual(self.groups.respawn_due(60), [])
        now[0] = 160
        result = self.groups.respawn_due(60)
        self.assertEqual(result[0]["key"], self.key)
        self.assertEqual(result[0]["members"], tuple(self.members))
        self.assertEqual(self.groups.respawn_due(60), [])

    def test_multiworker_due_claim_once_and_zero_time_is_valid(self):
        self.groups.clock = lambda: 0
        lease, _ = self.groups.claim(self.key, "alpha", 77)
        self.groups.finish(lease, defeated=True)
        second = PersistentGroups(self.store, clock=lambda: 60)
        self.groups.clock = lambda: 60
        with ThreadPoolExecutor(2) as pool:
            results = list(
                pool.map(
                    lambda registry: registry.respawn_due(60), [self.groups, second]
                )
            )
        self.assertEqual(sum(len(result) for result in results), 1)
        for delay in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.groups.respawn_due(delay)
