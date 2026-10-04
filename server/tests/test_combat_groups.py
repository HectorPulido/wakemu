import unittest
from concurrent.futures import ThreadPoolExecutor
from wakfu_server.combat_groups import Groups
from wakfu_server.monsters import owned_instance


class GroupTests(unittest.TestCase):
    def group(self):
        registry = Groups()
        members = [owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)]
        key = registry.register(1134, 0, 501, members)
        return registry, key

    def test_atomic_competing_accounts_and_stale_release(self):
        registry, key = self.group()

        def claim(g):
            try:
                return registry.claim(key, g, 77)[0]
            except ValueError:
                return None

        with ThreadPoolExecutor(2) as pool:
            claims = list(pool.map(claim, ["alpha", "beta"]))
        self.assertEqual(sum(c is not None for c in claims), 1)
        lease = next(c for c in claims if c)
        self.assertEqual(registry.available(1134, 0), [])
        self.assertTrue(registry.finish(lease, defeated=False))
        new, _ = registry.claim(key, "new", 78)
        self.assertFalse(registry.finish(lease, defeated=True))
        self.assertEqual(registry.available(1134, 0), [])
        self.assertTrue(registry.finish(new, defeated=True))
        self.assertEqual(len(registry.respawn(key)), 1)

    def test_snapshot_isolated_no_phantom_clone(self):
        registry, key = self.group()
        visible = registry.available(1134, 0)
        visible[0]["members"][0]["x"] = 999
        self.assertEqual(registry.available(1134, 0)[0]["members"][0]["x"], -7)
        member = registry.available(1134, 0)[0]["members"][0]
        with self.assertRaises(ValueError):
            registry.register(1134, 0, 502, [member])
        self.assertEqual(registry.available(1134, 1), [])

    def test_disconnect_releases_only_matching_session(self):
        registry, key = self.group()
        registry.claim(key, "alpha", 77)
        self.assertEqual(registry.release_session("beta"), [])
        self.assertEqual(len(registry.release_session("alpha")), 1)
        self.assertEqual(registry.release_session("alpha"), [])
