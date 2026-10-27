"""Real per-scope PostgreSQL contention must not destroy admin job progress."""
from contextlib import contextmanager
import json
import threading
from types import SimpleNamespace
from unittest.mock import patch

from psycopg.errors import LockNotAvailable
from postgres_case import PostgresCase


class EcologyAdminRetryPostgresTests(PostgresCase):
    def test_short_scope_lock_retries_outside_world_fences_and_preserves_live_fight(
        self,
    ):
        from wakfu_server import ecology_admin

        account = self.store.register("ecology-retry", "password")["id"]
        actor = self.store.create_character(account, "Ecology Retry")
        members = [dict(id=-9401, ref=8, level=1, x=5, y=6, z=0)]
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=TRUE WHERE id=%s", (account,))
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status,generation,fight_id) "
                "VALUES(1134,0,9401,%s::jsonb,'fighting','live-fight-generation',%s)",
                (json.dumps(members), fight_id),
            )
            before = db.execute(
                "SELECT * FROM combat_groups WHERE group_id=9401"
            ).fetchone()
        depth, waits, published = [0], [], []

        @contextmanager
        def coordination(scope):
            depth[0] += 1
            try:
                yield
            finally:
                depth[0] -= 1

        with self.store.connection() as blocker:
            blocker.execute(
                "SELECT pg_advisory_lock(hashtextextended(%s,0))",
                ("monster-population:1134:0",),
            )

            def release_after_real_timeout(delay):
                self.assertEqual(depth[0], 0, "retry slept while holding World fences")
                waits.append(delay)
                blocker.execute(
                    "SELECT pg_advisory_unlock(hashtextextended(%s,0))",
                    ("monster-population:1134:0",),
                )

            try:
                with patch.object(
                    ecology_admin, "_scopes", return_value=[(1134, 0, None)]
                ), patch.object(
                    ecology_admin,
                    "_retry_wait",
                    release_after_real_timeout,
                    create=True,
                ):
                    result = ecology_admin.execute(
                        self.store,
                        SimpleNamespace(lock=threading.RLock()),
                        actor,
                        "!nuke-all",
                        coordination=coordination,
                        validate_actor=lambda db, job: None,
                        publish=published.append,
                    )
            finally:
                blocker.execute(
                    "SELECT pg_advisory_unlock(hashtextextended(%s,0))",
                    ("monster-population:1134:0",),
                )
        self.assertEqual(waits, [0.05])
        self.assertEqual(result["scopes"], [(1134, 0, None)])
        self.assertEqual(
            (result["removed"], result["deferred"], result["failures"]), (0, 1, [])
        )
        self.assertEqual(len(published), 1)
        with self.store.connection() as db:
            after = db.execute(
                "SELECT * FROM combat_groups WHERE group_id=9401"
            ).fetchone()
            for key in ("members", "status", "revision", "generation", "fight_id"):
                self.assertEqual(after[key], before[key], key)
            self.assertEqual(after["ecology_admin_removed_ids"], [-9401])
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM ecology_admin_operations"
                ).fetchone()["n"],
                1,
            )

    def test_exhausted_transient_is_bounded_and_next_scope_still_commits(self):
        from wakfu_server import ecology_admin

        account = self.store.register("ecology-retry-bounded", "password")["id"]
        actor = self.store.create_character(account, "Ecology Bounded")
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=TRUE WHERE id=%s", (account,))
        original, calls, waits = ecology_admin._nuke, [], []

        def contended(db, map_id, instance_id, region):
            calls.append(map_id)
            if map_id == 1134:
                raise LockNotAvailable("isolated exhausted transient")
            return original(db, map_id, instance_id, region)

        with patch.object(
            ecology_admin, "_scopes", return_value=[(1134, 0, None), (1135, 0, None)]
        ), patch.object(ecology_admin, "_nuke", contended), patch.object(
            ecology_admin, "_retry_wait", waits.append, create=True
        ):
            result = ecology_admin.execute(
                self.store,
                SimpleNamespace(lock=threading.RLock()),
                actor,
                "!nuke-all",
                validate_actor=lambda db, job: None,
            )
        self.assertEqual(calls, [1134] * 8 + [1135])
        self.assertEqual(len(waits), 7)
        self.assertEqual(result["scopes"], [(1135, 0, None)])
        self.assertEqual(len(result["failures"]), 1)
        self.assertIn("LockNotAvailable", result["failures"][0][3])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM ecology_admin_operations"
                ).fetchone()["n"],
                1,
            )
