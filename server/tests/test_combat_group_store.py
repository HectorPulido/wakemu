import unittest
from concurrent.futures import ThreadPoolExecutor
from postgres_case import PostgresCase
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import owned_instance


class DurableGroupsTests(PostgresCase):
    def setUp(self):
        super().setUp()
        with self.store.connection() as db:
            self.fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        self.groups = PersistentGroups(self.store)
        self.members = [owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)]
        self.key = self.groups.register(1134, 0, 501, self.members)

    def test_defeated_survives_restart_without_implicit_respawn(self):
        lease, _ = self.groups.claim(self.key, "alpha", self.fight_id)
        self.assertTrue(self.groups.finish(lease, defeated=True))
        after = PersistentGroups(self.store, recover=True)
        self.assertEqual(after.register(1134, 0, 501, self.members), self.key)
        self.assertEqual(after.available(1134, 0), [])
        self.assertEqual(after.respawn(self.key), tuple(self.members))
        self.assertEqual(len(after.available(1134, 0)), 1)

    def test_restart_aborts_reserved_and_invalidates_old_lease(self):
        old, _ = self.groups.claim(self.key, "alpha", self.fight_id)
        self.assertEqual(PersistentGroups(self.store).available(1134, 0), [])
        after = PersistentGroups(self.store, recover=True)
        self.assertEqual(len(after.available(1134, 0)), 1)
        new, _ = after.claim(self.key, "alpha", self.fight_id)
        self.assertFalse(after.finish(old, defeated=True))
        self.assertTrue(after.finish(new, defeated=False))

    def test_postgres_serializes_distinct_registry_workers(self):
        second = PersistentGroups(self.store)

        def reserve(pair):
            registry, generation = pair
            try:
                return registry.claim(self.key, generation, self.fight_id)[0]
            except ValueError:
                return None

        with ThreadPoolExecutor(2) as pool:
            claims = list(pool.map(reserve, [(self.groups, "a"), (second, "b")]))
        self.assertEqual(sum(c is not None for c in claims), 1)
        winner = next(c for c in claims if c)
        self.assertEqual(second.release_session("unrelated"), [])
        self.assertEqual(len(second.release_session(winner[1])), 1)
        self.assertFalse(self.groups.finish(winner, defeated=True))

    def test_scoped_snapshot_includes_fighting_groups_only_for_requested_location(self):
        other_instance = (1134, 1, 502)
        other_map = (1200, 0, 503)
        self.groups.register(
            *other_instance,
            [owned_instance(5525, 1, -201, map_id=1134, x=1, y=1, z=0)],
        )
        self.groups.register(
            *other_map,
            [owned_instance(5525, 1, -202, map_id=1200, x=1, y=1, z=0)],
        )
        self.groups.claim(self.key, "snapshot-fight", self.fight_id)

        scoped = self.groups.snapshot(1134, 0)
        self.assertEqual([row["key"] for row in scoped], [self.key])
        self.assertEqual(scoped[0]["status"], "fighting")
        self.assertEqual(
            {row["key"] for row in self.groups.snapshot()},
            {
                self.key,
                other_instance,
                other_map,
            },
        )
        self.assertEqual(
            {row["status"] for row in self.groups.snapshot() if row["key"] == self.key},
            {"fighting"},
        )
        for args in ((1134, None), (None, 0)):
            with self.subTest(args=args), self.assertRaisesRegex(
                ValueError, "map and instance together"
            ):
                self.groups.snapshot(*args)

    def test_respawn_due_only_after_delay_and_once(self):
        now = [100.0]
        self.groups.clock = lambda: now[0]
        lease, _ = self.groups.claim(self.key, "alpha", self.fight_id)
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
        lease, _ = self.groups.claim(self.key, "alpha", self.fight_id)
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
