"""Durable dirty scopes and restart-safe ecology proposal delivery."""
import importlib.util
from pathlib import Path
from postgres_case import PostgresCase
from wakfu_server.ecology.protocol import proposal

spec = importlib.util.spec_from_file_location(
    "ecology_service_sql",
    Path(__file__).resolve().parents[1] / "ecology-service/service.py",
)
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class EcologyServicePostgresTests(PostgresCase):
    def test_retry_exhaustion_persists_without_resurrection_and_final_attempt_can_succeed(
        self,
    ):
        repository = service.Repository(self.store, max_attempts=2)
        rows = [proposal("plants", {"uid": uid}, "boot") for uid in (701, 702, 703)]
        repository.save(rows, [])
        repository.acknowledge(
            [{"id": row["id"], "status": "retry"} for row in rows[:2]]
        )
        repository.acknowledge(
            [
                {"id": rows[0]["id"], "status": "retry"},
                {"id": rows[1]["id"], "status": "applied"},
            ]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE ecology_service_proposals SET attempts=85 WHERE id=%s",
                (rows[2]["id"],),
            )
        reopened = service.Repository(self.reopen(), max_attempts=2)
        self.assertEqual(reopened.expire_exhausted(), 1)
        self.assertEqual(reopened.pending_count(), 0)
        reopened.save(rows, [])
        self.assertEqual(reopened.pending_count(), 0)
        self.assertEqual(reopened.retry_stats(), {"attempts": 89, "exhausted": 2})
        with self.store.connection() as db:
            success = db.execute(
                "SELECT attempts,last_error_code,delivered_at FROM ecology_service_proposals WHERE id=%s",
                (rows[1]["id"],),
            ).fetchone()
        self.assertEqual(success["attempts"], 2)
        self.assertIsNone(success["last_error_code"])
        self.assertIsNotNone(success["delivered_at"])

    def test_dirty_scope_is_transactional_and_new_revision_survives_ack(self):
        repository = service.Repository(self.store)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) "
                "VALUES(991,527,0,1,2,0,1,0,0)"
            )
        first = [row for row in repository.dirty() if row["map_id"] == 527][0]
        with self.store.connection() as db:
            db.execute("UPDATE planted_resources SET stage=1 WHERE resource_uid=991")
        repository.save([], [first])
        second = [row for row in repository.dirty() if row["map_id"] == 527][0]
        self.assertGreater(second["revision"], first["revision"])
        try:
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) "
                    "VALUES(992,528,0,1,2,0,1,0,0)"
                )
                raise ValueError("rollback")
        except ValueError:
            pass
        self.assertFalse(any(row["map_id"] == 528 for row in repository.dirty()))

    def test_pending_proposal_survives_reopen_duplicate_and_stale_epoch_replan(self):
        repository = service.Repository(self.store)
        row = proposal("plants", {"uid": 991, "revision": 1}, "boot-one")
        repository.save([row], [])
        repository.save([row], [])
        reopened = service.Repository(self.reopen())
        self.assertEqual(reopened.pending(), [row])
        reopened.acknowledge([{"id": row["id"], "status": "stale"}])
        self.assertEqual(reopened.pending(), [])
        fresh = dict(row, world_epoch="boot-two")
        reopened.save([fresh], [])
        self.assertEqual(reopened.pending(), [fresh])

    def test_pause_is_durable_and_retry_rows_do_not_starve_new_work(self):
        repository = service.Repository(self.store)
        repository.set_enabled(False)
        self.assertFalse(service.Repository(self.reopen()).enabled())
        repository.set_enabled(True)
        self.assertTrue(repository.enabled())
        rows = [proposal("mobs", {"uid": i}, "boot") for i in range(20)]
        repository.save(rows, [])
        first = repository.pending()
        self.assertEqual(len(first), 16)
        repository.acknowledge([{"id": row["id"], "status": "retry"} for row in first])
        second = repository.pending()
        self.assertTrue(
            set(row["id"] for row in rows) - set(row["id"] for row in first)
            <= set(row["id"] for row in second)
        )
        self.assertFalse(
            set(row["id"] for row in first) & set(row["id"] for row in second)
        )
        with self.store.connection() as db:
            delayed = db.execute(
                "SELECT next_attempt_at>CURRENT_TIMESTAMP AS delayed,attempts "
                "FROM ecology_service_proposals WHERE id=%s",
                (first[0]["id"],),
            ).fetchone()
        self.assertTrue(delayed["delayed"])
        self.assertEqual(delayed["attempts"], 1)

    def test_only_one_worker_session_owns_database_until_owner_closes(self):
        first = service.Repository(self.store)
        second = service.Repository(self.store)
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        first.acquire()
        first.assert_owner()
        first.owner.close()
        with self.assertRaises(service.OwnershipLost):
            first.assert_owner()
        self.assertIsNone(first.owner)
        first.acquire()
        with self.assertRaisesRegex(RuntimeError, "Another ecology"):
            second.acquire()
        first.close()
        second.acquire()
        second.assert_owner()

    def test_query_returns_real_weather_and_empty_population_with_snapshot_metadata(
        self,
    ):
        repository = service.Repository(self.store)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO territory_weather(map_id,instance_id,region_id,weather,native_payload) "
                "VALUES(527,0,99,'LIGHT',%s)",
                (bytes(37),),
            )
        result = repository.query(
            {"kind": "weather", "map_id": 527, "instance_id": 0, "region_id": 99}
        )
        self.assertTrue(result["authoritative"])
        self.assertGreater(result["revision"], 0)
        self.assertIn("observed_at", result)
        self.assertEqual(result["data"]["regions"][0]["weather"], "LIGHT")
        population = repository.query(
            {"kind": "population", "map_id": 527, "instance_id": 0}
        )
        self.assertTrue(population["data"]["complete"])
        self.assertEqual(population["data"]["regions"], {})

    def test_completed_retention_is_capped_and_pending_rows_are_never_deleted(self):
        repository = service.Repository(self.store)
        pending = proposal("plants", {"uid": 1}, "boot")
        repository.save([pending], [])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch,delivered_at) "
                "SELECT 'archived-'||n,'plants','{}'::jsonb,'boot',CURRENT_TIMESTAMP FROM generate_series(1,4098) n"
            )
        repository.acknowledge([])
        with self.store.connection() as db:
            count = db.execute(
                "SELECT count(*) AS count FROM ecology_service_proposals WHERE delivered_at IS NOT NULL"
            ).fetchone()["count"]
        self.assertEqual(count, 4096)
        self.assertEqual(repository.pending(), [pending])
