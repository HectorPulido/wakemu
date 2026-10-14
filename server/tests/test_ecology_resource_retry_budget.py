"""Resource execution failures are bounded independently of envelopes and boots."""
from unittest.mock import patch

from postgres_case import PostgresCase
from test_ecology_service_postgres import service
from wakfu_server.ecology.protocol import proposal


def birth_batch(uids, epoch="boot", incarnation=100):
    return proposal(
        "plants",
        dict(
            kind="resource_growth_bulk",
            world_epoch=epoch,
            resources=[
                dict(
                    kind="resource_growth",
                    world_epoch=epoch,
                    expected=dict(
                        resource_uid=uid,
                        stage=1,
                        map_id=527,
                        instance_id=0,
                        resource_reference=10,
                        creation_time=incarnation,
                    ),
                    member=dict(id=-uid),
                )
                for uid in uids
            ],
        ),
        epoch,
    )


class ResourceRetryBudgetTests(PostgresCase):
    def make_due(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE ecology_service_proposals SET next_attempt_at=CURRENT_TIMESTAMP"
            )

    def test_three_occupied_executions_stop_across_batches_and_restart(self):
        repository = service.Repository(self.store)
        for index in range(3):
            repository.save([birth_batch([1, index + 2], epoch=f"boot-{index}")], [])
            row = next(
                row
                for row in repository.pending()
                if row["world_epoch"] == f"boot-{index}"
            )
            repository.acknowledge(
                [dict(id=row["id"], status="applied", resource_failures=[1])]
            )
            repository = service.Repository(self.reopen())
        repository.save([birth_batch([1, 9], epoch="boot-final")], [])
        final = next(
            row for row in repository.pending() if row["world_epoch"] == "boot-final"
        )
        self.assertEqual(
            [
                entry["expected"]["resource_uid"]
                for entry in final["payload"]["resources"]
            ],
            [9],
        )
        repository.acknowledge([dict(id=final["id"], status="applied")])
        repository.save([birth_batch([1], epoch="boot-final")], [])
        self.assertEqual(repository.pending_count(), 0)
        repository.save([birth_batch([1], epoch="boot-final", incarnation=101)], [])
        self.assertEqual(repository.pending_count(), 1)

    def test_timer_wait_does_not_consume_resource_failure_budget(self):
        repository = service.Repository(self.store)
        for _ in range(5):
            repository.save([birth_batch([1])], [])
            row = repository.pending()[0]
            repository.acknowledge([dict(id=row["id"], status="deferred")])
            self.make_due()
        with self.store.connection() as db:
            guards = db.execute(
                "SELECT count(*) AS n FROM ecology_service_proposals "
                "WHERE payload->>'kind'='bulk_failure_guard'"
            ).fetchone()
        self.assertEqual(guards["n"], 0)
        repository.save([birth_batch([1])], [])
        self.assertEqual(repository.pending_count(), 1)

    def test_occupied_single_resource_does_not_keep_a_delivery_slot_forever(self):
        repository = service.Repository(self.store)
        payload = birth_batch([1])["payload"]["resources"][0]
        for _ in range(3):
            repository.save([proposal("plants", payload, "boot")], [])
            row = repository.pending()[0]
            repository.acknowledge(
                [dict(id=row["id"], status="deferred", resource_failures=[1])]
            )
            self.make_due()
        repository.save([], [])
        self.assertEqual(repository.pending_count(), 0)

    def test_full_background_lane_preserves_interactive_capacity(self):
        repository = service.Repository(self.store)
        with patch.object(service, "MAX_PENDING", 5), patch.object(
            service, "RESERVED_INTERACTIVE", 1
        ), patch.object(service, "RESERVED_GROWTH", 1):
            background = [
                proposal("weather", dict(revision=i), "boot") for i in range(20)
            ]
            statistics = repository.save(background, [])
            self.assertEqual(repository.pending_count(), 3)
            self.assertEqual(statistics["capacity_deferred"], 17)
            repository.save([birth_batch([1])], [])
            self.assertEqual(repository.pending_count(), 4)
            repository.save(
                [proposal("plants", dict(kind="planting_begin", intent_id=1), "boot")],
                [],
            )
            self.assertEqual(repository.pending_count(), 5)
            statistics = repository.save(background, [])
            self.assertEqual(repository.pending_count(), 5)
            self.assertGreater(statistics["capacity_deferred"], 0)
