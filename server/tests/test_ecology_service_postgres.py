"""Durable dirty scopes and restart-safe ecology proposal delivery."""
import importlib.util
from pathlib import Path
from postgres_case import PostgresCase
from wakfu_server.ecology.protocol import proposal
from wakfu_server.ecology.proposal_identity import identity as proposal_identity

spec = importlib.util.spec_from_file_location(
    "ecology_service_sql",
    Path(__file__).resolve().parents[1] / "ecology-service/service.py",
)
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class EcologyServicePostgresTests(PostgresCase):
    def test_exhausted_semantic_decision_survives_history_pruning_and_cannot_resurrect(
        self,
    ):
        repository = service.Repository(self.store)
        payload = {
            "kind": "resource_growth",
            "expected": {"resource_uid": 991, "stage": 1},
            "member": {"id": -991},
        }
        repository.save([proposal("plants", payload, "boot")], [])
        durable_id = repository.pending()[0]["id"]
        for _ in range(3):
            repository.acknowledge([{"id": durable_id, "status": "retry"}])
        with self.store.connection() as db:
            db.execute(
                "UPDATE ecology_service_proposals SET delivered_at=CURRENT_TIMESTAMP-interval '8 days' WHERE id=%s",
                (durable_id,),
            )
            db.execute(
                "INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch,delivered_at) SELECT 'history-'||i,'weather','{}'::jsonb,'boot',CURRENT_TIMESTAMP FROM generate_series(1,4400) AS i"
            )
        repository.acknowledge([])
        repository.save(
            [proposal("plants", dict(payload, member={"id": -992}), "boot")], []
        )
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT attempts,last_error_code FROM ecology_service_proposals WHERE id=%s",
                (durable_id,),
            ).fetchone()
            ordinary = db.execute(
                "SELECT count(*) AS count FROM ecology_service_proposals WHERE domain='weather'"
            ).fetchone()["count"]
        self.assertEqual(saved["attempts"], 3)
        self.assertEqual(saved["last_error_code"], "retry_exhausted")
        self.assertLess(ordinary, 4400)
        self.assertEqual(repository.pending_count(), 0)

    def test_late_stale_ack_cannot_reclassify_successful_semantic_decision(self):
        repository = service.Repository(self.store)
        payload = {
            "kind": "resource_growth",
            "expected": {"resource_uid": 991, "stage": 1},
            "member": {"id": -991},
        }
        repository.save([proposal("plants", payload, "boot")], [])
        durable_id = repository.pending()[0]["id"]
        repository.acknowledge([{"id": durable_id, "status": "applied"}])
        repository.acknowledge([{"id": durable_id, "status": "stale"}])
        repository.save([proposal("plants", payload, "boot")], [])
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT attempts,last_error_code FROM ecology_service_proposals WHERE id=%s",
                (durable_id,),
            ).fetchone()
        self.assertEqual(saved["attempts"], 1)
        self.assertIsNone(saved["last_error_code"])
        self.assertEqual(repository.pending_count(), 0)

    def test_successful_random_decision_is_not_rearmed_by_fresh_random_output(self):
        repository = service.Repository(self.store)
        payload = {
            "kind": "resource_growth",
            "expected": {"resource_uid": 99, "stage": 1},
            "member": {"id": -99, "ref": 10},
            "draw": 0.1,
        }
        repository.save([proposal("plants", payload, "boot")], [])
        durable_id = repository.pending()[0]["id"]
        repository.acknowledge([{"id": durable_id, "status": "applied"}])
        repository.save(
            [
                proposal(
                    "plants",
                    dict(payload, member={"id": -100, "ref": 11}, draw=0.9),
                    "boot",
                )
            ],
            [],
        )
        self.assertEqual(repository.pending_count(), 0)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT payload,attempts FROM ecology_service_proposals WHERE id=%s",
                (durable_id,),
            ).fetchone()
        self.assertEqual(saved["payload"]["member"], payload["member"])
        self.assertEqual(saved["attempts"], 1)

    def test_stale_reproduction_refreshes_roster_without_rerolling_or_resetting_retry_limit(
        self,
    ):
        repository = service.Repository(self.store)
        payload = {
            "kind": "reproduction",
            "world_epoch": "boot",
            "scope": [527, 0],
            "ticket": {
                "map_id": 527,
                "instance_id": 0,
                "group_id": 7,
                "monster_id": -71,
                "reference": 10,
                "cycle": 3,
            },
            "expected_members": [{"id": -71, "ref": 10}],
            "draw": 0.2,
            "group_draw": 0.3,
            "destination": [1, 2, 0],
            "child": {"id": -900, "ref": 11, "x": 1, "y": 2, "z": 0},
        }
        repository.save([proposal("mobs", payload, "boot")], [])
        durable_id = repository.pending()[0]["id"]
        for attempt in range(1, 4):
            repository.acknowledge([{"id": durable_id, "status": "stale"}])
            if attempt == 1:
                repository.save(
                    [proposal("mobs", dict(payload, draw=0.97), "boot")], []
                )
                self.assertEqual(repository.pending_count(), 0)
            fresh = dict(
                payload,
                expected_members=[
                    {"id": -71, "ref": 10},
                    {"id": -72 - attempt, "ref": 10},
                ],
                draw=0.99,
                group_draw=0.98,
                destination=[3, 4, 0],
                child={"id": -999, "ref": 12, "x": 3, "y": 4, "z": 0},
            )
            repository.save([proposal("mobs", fresh, "boot")], [])
            with self.store.connection() as db:
                saved = db.execute(
                    "SELECT id,payload,attempts,delivered_at FROM ecology_service_proposals WHERE id=%s",
                    (durable_id,),
                ).fetchone()
            self.assertEqual(saved["attempts"], attempt)
            self.assertEqual(saved["payload"]["draw"], 0.2)
            self.assertEqual(saved["payload"]["group_draw"], 0.3)
            self.assertEqual(saved["payload"]["child"]["id"], -900)
            self.assertEqual(saved["payload"]["child"]["ref"], 11)
            if attempt < 3:
                self.assertIsNone(saved["delivered_at"])
                self.assertEqual(
                    saved["payload"]["expected_members"], fresh["expected_members"]
                )
                self.assertEqual(saved["payload"]["destination"], [3, 4, 0])
            else:
                self.assertIsNotNone(saved["delivered_at"])
        self.assertEqual(repository.pending_count(), 0)

    def test_maximum_population_repeated_random_cycles_keep_one_durable_entry_each(
        self,
    ):
        repository = service.Repository(self.store)
        for tick in range(100):
            rows = []
            for identity in range(500):
                rows.append(
                    proposal(
                        "mobs",
                        {
                            "kind": "maturation",
                            "world_epoch": "load",
                            "scope": [527, 0],
                            "ticket": {
                                "map_id": 527,
                                "instance_id": 0,
                                "group_id": identity // 5,
                                "monster_id": -identity - 1,
                                "reference": 10,
                                "cycle": 7,
                                "due_at": 1000,
                            },
                            "expected_members": [{"id": -identity - 1, "ref": 10}],
                            "draw": (tick * 500 + identity) / 50000,
                            "grown": {"ref": 11 + tick % 2},
                        },
                        "load",
                    )
                )
            repository.save(rows, [])
        self.assertEqual(repository.pending_count(), 500)
        with self.store.connection() as db:
            counts = db.execute(
                "SELECT count(*) AS total, count(DISTINCT payload->'ticket'->>'group_id') AS groups FROM ecology_service_proposals"
            ).fetchone()
        self.assertEqual(counts["total"], 500)
        self.assertEqual(counts["groups"], 100)

    def test_default_three_failures_exhaust_once_and_replanning_cannot_resurrect(self):
        repository = service.Repository(self.store)
        self.assertEqual(repository.max_attempts, 3)
        row = proposal(
            "mobs",
            {
                "kind": "wander",
                "world_epoch": "boot",
                "scope": [527, 0],
                "group_id": 1,
                "expected_members": [],
            },
            "boot",
        )
        repository.save([row], [])
        for attempt in range(3):
            repository.acknowledge([{"id": row["id"], "status": "retry"}])
            self.assertEqual(repository.pending_count(), int(attempt < 2))
        repository.save([row], [])
        self.assertEqual(repository.pending_count(), 0)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT attempts,last_error_code FROM ecology_service_proposals WHERE id=%s",
                (row["id"],),
            ).fetchone()
        self.assertEqual(saved["attempts"], 3)
        self.assertEqual(saved["last_error_code"], "retry_exhausted")

    def test_pending_flora_growth_does_not_consume_reserved_monster_birth_capacity(
        self,
    ):
        repository = service.Repository(self.store)
        flora = [
            proposal(
                "plants",
                {
                    "kind": "resource_growth",
                    "expected": {"resource_uid": uid, "stage": 1},
                    "resource": {"resource_uid": uid},
                    "member": None,
                },
                "boot",
            )
            for uid in range(16)
        ]
        repository.save(flora, [])
        self.assertEqual(repository.growth_pending_count(), 0)
        birth = proposal(
            "plants",
            {
                "kind": "resource_growth",
                "expected": {"resource_uid": 99, "stage": 1},
                "member": {"id": -99},
            },
            "boot",
        )
        repository.save([birth], [])
        self.assertEqual(repository.growth_pending_count(), 1)
        self.assertEqual(repository.pending_count(), 17)

    def test_seed_growth_precedes_ambient_and_deduplicates_random_offspring(self):
        repository = service.Repository(self.store)
        ambient = proposal("mobs", {"kind": "ambient_test"}, "boot")
        growth = proposal(
            "plants",
            {
                "kind": "resource_growth",
                "expected": {"resource_uid": 7, "stage": 1},
                "member": {"id": -7, "ref": 2},
            },
            "boot",
        )
        duplicate = proposal(
            "plants",
            {
                "kind": "resource_growth",
                "expected": {"resource_uid": 7, "stage": 1},
                "member": {"id": -8, "ref": 39},
            },
            "boot",
        )
        repository.save([ambient, growth, duplicate], [])
        rows = repository.pending()
        self.assertEqual(
            [row["id"] for row in rows], [proposal_identity(growth)[2], ambient["id"]]
        )
        self.assertEqual(repository.growth_pending_count(), 1)
        self.assertEqual(rows[0]["payload"]["member"]["ref"], 2)

    def test_reserved_player_proposals_are_read_before_older_background_backlog(self):
        repository = service.Repository(self.store)
        background = proposal(
            "mobs",
            {
                "kind": "wander",
                "scope": [527, 0],
                "group_id": 1,
                "expected_members": [],
            },
            "boot",
        )
        player = proposal("plants", {"kind": "planting_begin", "intent_id": 71}, "boot")
        rejection = proposal(
            "plants", {"kind": "planting_rejected", "intent_id": 72}, "boot"
        )
        repository.save([background], [])
        repository.save([player, rejection], [])
        rows = repository.pending()
        self.assertEqual(
            {row["id"] for row in rows[:2]},
            {proposal_identity(player)[2], proposal_identity(rejection)[2]},
        )
        self.assertEqual(rows[2]["id"], background["id"])

    def test_background_deferrals_never_consume_retry_budget_or_drop_work(self):
        repository = service.Repository(self.store, max_attempts=2)
        row = proposal(
            "mobs",
            {
                "kind": "wander",
                "world_epoch": "boot",
                "scope": [527, 0],
                "group_id": 1,
                "expected_members": [],
            },
            "boot",
        )
        repository.save([row], [])
        for _ in range(8):
            repository.acknowledge([{"id": row["id"], "status": "deferred"}])
        self.assertEqual(repository.pending_count(), 1)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT attempts,delivered_at,last_error_code,next_attempt_at>CURRENT_TIMESTAMP AS delayed FROM ecology_service_proposals WHERE id=%s",
                (row["id"],),
            ).fetchone()
        self.assertEqual(saved["attempts"], 0)
        self.assertIsNone(saved["delivered_at"])
        self.assertTrue(saved["delayed"])
        repository.acknowledge([{"id": row["id"], "status": "applied"}])
        self.assertEqual(repository.pending_count(), 0)

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
