"""Real PostgreSQL interleavings for resource cleanup and company ownership."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from queue import Queue
import struct
from threading import Event
from time import monotonic
import unittest

from wakfu_server import resource_collect
from wakfu_server.characters import heroes
from wakfu_server.objectives import environmental_resource_population as population
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage


class ConnectionStore:
    """Keep production SQL intact while exposing an independent backend PID."""

    def __init__(self, store, *, pid_queue=None, transaction=None):
        self.store, self.pid_queue, self.transaction = store, pid_queue, transaction

    def __getattr__(self, name):
        return getattr(self.store, name)

    @contextmanager
    def connection(self):
        if self.transaction is not None:
            yield self.transaction
            return
        with self.store.connection() as db:
            db.execute("SET LOCAL lock_timeout='5s'")
            if self.pid_queue is not None:
                self.pid_queue.put(
                    db.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
                )
            yield db


class EnvironmentalLockOrderPostgresTests(unittest.TestCase):
    def wait_for_blocker(self, db, waiter, holder):
        deadline = monotonic() + 3
        while monotonic() < deadline:
            blockers = db.execute(
                "SELECT pg_blocking_pids(%s) AS pids", (waiter,)
            ).fetchone()["pids"]
            if holder in blockers:
                return
            Event().wait(0.01)
        self.fail("Production worker never waited on the real held PostgreSQL lock")

    def test_environmental_harvest_waits_scope_without_occupation_and_early_retry_is_typed(
        self,
    ):
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )

        fixture = EnvironmentalOwnedResourcePopulationTests(
            methodName="test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        fixture.profile()
        event = fixture.refresh()["instances"][0]["instance_id"]
        with fixture.store.connection() as db:
            resources = [
                dict(r)
                for r in db.execute(
                    "SELECT p.* FROM planted_resources p "
                    "JOIN environmental_owned_resources o USING(resource_uid) ORDER BY resource_uid LIMIT 2"
                )
            ]
        first = fixture.ticket(resources[0])
        body = struct.pack(">Bh", 2, 3)
        with fixture.store.connection() as db:
            occupation = dict(
                db.execute(
                    "SELECT * FROM resource_harvest_occupations WHERE token=%s",
                    (first["token"],),
                ).fetchone()
            )
        with self.assertRaises(resource_collect.HarvestNotReady) as caught:
            resource_collect.complete(fixture.store, first, body)
        self.assertIsInstance(caught.exception, ValueError)
        self.assertEqual(caught.exception.completes_at, occupation["completes_at"])
        with fixture.store.connection() as db:
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM resource_harvest_occupations WHERE token=%s",
                        (first["token"],),
                    ).fetchone()
                ),
                occupation,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts WHERE token=%s",
                    (first["token"],),
                ).fetchone()["n"],
                0,
            )
        fixture.clock[0] = occupation["completes_at"].timestamp() + 0.001
        self.assertTrue(
            resource_collect.complete(fixture.store, first, body)["applied"]
        )
        self.assertFalse(
            resource_collect.complete(fixture.store, first, body)["applied"]
        )
        ticket = fixture.ticket(resources[1])
        with fixture.store.connection() as db:
            due = db.execute(
                "SELECT completes_at FROM resource_harvest_occupations WHERE token=%s",
                (ticket["token"],),
            ).fetchone()["completes_at"]
        fixture.clock[0] = due.timestamp() + 0.001
        worker_pid = Queue()
        observed = ConnectionStore(fixture.store, pid_queue=worker_pid)
        with ThreadPoolExecutor(max_workers=1) as executor:
            with fixture.store.connection() as cleanup:
                cleanup.execute("SET LOCAL lock_timeout='3s'")
                holder = cleanup.execute("SELECT pg_backend_pid() AS pid").fetchone()[
                    "pid"
                ]
                storage._scope_lock(cleanup, 327, 0)
                future = executor.submit(
                    resource_collect.complete, observed, ticket, body
                )
                self.wait_for_blocker(cleanup, worker_pid.get(timeout=3), holder)
                # NOWAIT makes the former inverted occupation->scope order
                # fail immediately, rather than relying on a deadlock timeout.
                row = cleanup.execute(
                    "SELECT token FROM resource_harvest_occupations "
                    "WHERE token=%s FOR UPDATE NOWAIT",
                    (ticket["token"],),
                ).fetchone()
                self.assertEqual(row["token"], ticket["token"])
                self.assertTrue(
                    storage.cancel(
                        cleanup,
                        event,
                        reason="bounded real cleanup interleaving",
                        now_ms=int(fixture.clock[0] * 1000),
                    )
                )
                removed = population.cleanup(
                    cleanup,
                    map_id=327,
                    instance_id=0,
                    now_ms=int(fixture.clock[0] * 1000),
                )
                self.assertIn(resources[1]["resource_uid"], removed)
            self.assertFalse(future.result(timeout=5)["applied"])
        with fixture.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT token FROM resource_harvest_occupations WHERE token=%s",
                    (ticket["token"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts WHERE token=%s",
                    (ticket["token"],),
                ).fetchone()["n"],
                0,
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT retired_at_ms FROM environmental_owned_resources "
                    "WHERE resource_uid=%s",
                    (resources[1]["resource_uid"],),
                ).fetchone()["retired_at_ms"]
            )

    def test_refresh_waits_account_without_session_while_real_hero_remove_commits(self):
        from test_environmental_company import EnvironmentalCompanyPostgresTests

        fixture = EnvironmentalCompanyPostgresTests(
            methodName="test_actual_harvest_credits_loaded_players_once_globally_and_never_replays"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        f = fixture.flora
        worker_pid = Queue()
        observed = ConnectionStore(fixture.store, pid_queue=worker_pid)
        with ThreadPoolExecutor(max_workers=1) as executor:
            with fixture.store.connection() as company:
                company.execute("SET LOCAL lock_timeout='3s'")
                holder = company.execute("SELECT pg_backend_pid() AS pid").fetchone()[
                    "pid"
                ]
                company.execute(
                    "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (f.account,)
                )
                future = executor.submit(
                    service.refresh,
                    observed,
                    f.account,
                    f.generation,
                    f.character["id"],
                    location=fixture.environment.location,
                    now_ms=int(f.clock[0] * 1000),
                )
                self.wait_for_blocker(company, worker_pid.get(timeout=3), holder)
                session = company.execute(
                    "SELECT generation,character_id FROM sessions "
                    "WHERE account_id=%s FOR UPDATE NOWAIT",
                    (f.account,),
                ).fetchone()
                self.assertEqual(
                    (session["generation"], session["character_id"]),
                    (f.generation, f.character["id"]),
                )
                # The real public hero operation joins this already-owned
                # transaction; its account/session/character SQL is unmodified.
                heroes.remove(
                    ConnectionStore(fixture.store, transaction=company),
                    f.account,
                    f.generation,
                    f.character["id"],
                    fixture.hero["id"],
                )
            refreshed = future.result(timeout=5)
        self.assertNotIn(fixture.hero["id"], refreshed.get("hero_rewards", {}))
        with fixture.store.connection() as db:
            slots = [
                r["character_id"]
                for r in db.execute(
                    "SELECT character_id FROM account_hero_slots "
                    "WHERE account_id=%s ORDER BY slot",
                    (f.account,),
                )
            ]
            self.assertEqual(slots, [fixture.low["id"]])
            self.assertEqual(
                db.execute(
                    "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s",
                    (f.account,),
                ).fetchone()["leader_id"],
                f.character["id"],
            )
            self.assertEqual(
                db.execute(
                    "SELECT account_id FROM characters WHERE id=%s",
                    (fixture.hero["id"],),
                ).fetchone()["account_id"],
                f.account,
            )
        generation = fixture.store.begin_session(
            f.account, previous_generation=f.generation
        )
        self.assertNotEqual(generation, f.generation)
        with self.assertRaisesRegex(ValueError, "session"):
            fixture.refresh()
