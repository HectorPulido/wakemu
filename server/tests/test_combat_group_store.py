import unittest
from concurrent.futures import ThreadPoolExecutor
from psycopg.pq import TransactionStatus
from postgres_case import PostgresCase
from wakfu_server import monster_reproduction
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.monster_wander import edge_index


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

    def test_register_transaction_requires_caller_transaction(self):
        # Bypass Store.connection's intentional transaction wrapper to model
        # a caller that forgot to open the transaction this helper borrows.
        with self.store.database.pool.connection() as db:
            self.assertEqual(db.info.transaction_status, TransactionStatus.IDLE)
            with self.assertRaisesRegex(ValueError, "active transaction"):
                self.groups.register_transaction(
                    db,
                    1134,
                    0,
                    601,
                    [owned_instance(5525, 1, -601, map_id=1134, x=0, y=0, z=0)],
                )
            self.assertEqual(db.info.transaction_status, TransactionStatus.IDLE)
        self.assertFalse(
            any(row["key"] == (1134, 0, 601) for row in self.groups.snapshot())
        )

    def test_register_transaction_leaves_commit_and_rollback_to_caller(self):
        members = [owned_instance(5525, 1, -602, map_id=1134, x=2, y=3, z=0)]
        key = (1134, 0, 602)
        with self.assertRaisesRegex(RuntimeError, "caller rollback"):
            with self.store.connection() as db, db.transaction():
                self.assertEqual(
                    self.groups.register_transaction(db, *key, members), key
                )
                self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
                # The caller can still see its write in the same transaction.
                self.assertIsNotNone(
                    db.execute(
                        "SELECT 1 FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                        key,
                    ).fetchone()
                )
                raise RuntimeError("caller rollback")
        self.assertFalse(any(row["key"] == key for row in self.groups.snapshot()))

        committed_key = (1134, 0, 603)
        committed_members = [owned_instance(5525, 1, -603, map_id=1134, x=4, y=5, z=0)]
        with self.store.connection() as db, db.transaction():
            self.assertEqual(
                self.groups.register_transaction(db, *committed_key, committed_members),
                committed_key,
            )
            self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
        self.assertTrue(
            any(row["key"] == committed_key for row in self.groups.snapshot())
        )

    def test_register_transaction_member_conflict_rolls_back_group_with_caller(self):
        # Member -200 is already owned by group 501. The attempted parent row
        # must not survive the member-identity conflict.
        key = (1134, 0, 604)
        duplicate_member = [owned_instance(5525, 1, -200, map_id=1134, x=8, y=8, z=0)]
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            with self.store.connection() as db, db.transaction():
                self.groups.register_transaction(db, *key, duplicate_member)
        with self.store.connection() as db:
            parent = db.execute(
                "SELECT 1 FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            ).fetchone()
            child = db.execute(
                "SELECT 1 FROM combat_group_members WHERE map_id=1134 AND instance_id=0 AND monster_id=-200 AND group_id=604"
            ).fetchone()
        self.assertIsNone(parent)
        self.assertIsNone(child)

    def test_register_transaction_idempotence_does_not_commit_caller(self):
        key = (1134, 0, 605)
        members = [owned_instance(5525, 1, -605, map_id=1134, x=1, y=2, z=0)]
        with self.store.connection() as db, db.transaction():
            self.assertEqual(self.groups.register_transaction(db, *key, members), key)
        with self.store.connection() as db, db.transaction():
            self.assertEqual(self.groups.register_transaction(db, *key, members), key)
            self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
            self.assertEqual(self.groups.register_transaction(db, *key, members), key)
            self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)

    def test_defeated_survives_restart_without_implicit_respawn(self):
        now = [100.0]
        self.groups.clock = lambda: now[0]
        lease, _ = self.groups.claim(self.key, "alpha", self.fight_id)
        self.assertTrue(self.groups.finish(lease, defeated=True))
        now[0] += 86400
        after = PersistentGroups(self.store, recover=True)
        self.assertEqual(after.register(1134, 0, 501, self.members), self.key)
        self.assertEqual(after.available(1134, 0), [])
        with self.store.connection() as db:
            status = db.execute(
                "SELECT status FROM combat_groups WHERE map_id=1134 AND instance_id=0 AND group_id=501"
            ).fetchone()["status"]
        self.assertEqual("defeated", status)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            after.claim(self.key, "late-reclaim", self.fight_id)

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
            [
                owned_instance(
                    5525,
                    1,
                    -201,
                    map_id=1134,
                    x=1,
                    y=1,
                    z=0,
                    instance_id=other_instance[1],
                )
            ],
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

    def test_failed_claim_and_reproduction_tick_never_revive_defeated_group(self):
        adult = owned_instance(
            4, REFERENCES[4]["min_level"], -203, map_id=1134, x=0, y=0, z=0
        )
        adult_key = self.groups.register(1134, 0, 502, [adult])
        lease, _ = self.groups.claim(adult_key, "alpha", self.fight_id)
        self.groups.finish(lease, defeated=True)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.groups.claim(adult_key, "post-defeat", self.fight_id)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_reproduction_timers"
                "(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                "VALUES(1134,0,-203,4,0,true,1)"
            )
        monster_reproduction.tick(
            self.store,
            {(1134, 0)},
            set(),
            generation="after-defeat",
            now_ms=10**9,
            indexed_by_map={1134: edge_index([])},
            players=[],
            excluded_ids=set(),
            emit=lambda *_: self.fail("defeated group emitted reproduction packets"),
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT status FROM combat_groups WHERE map_id=1134 AND instance_id=0 AND group_id=502"
            ).fetchone()
            receipts = db.execute(
                "SELECT count(*) AS count FROM monster_reproduction_receipts "
                "WHERE map_id=1134 AND instance_id=0 AND monster_id=-203"
            ).fetchone()["count"]
        self.assertEqual("defeated", row["status"])
        self.assertEqual(0, receipts)
