"""Scope batches coalesce without replacing already selected offspring."""
from postgres_case import PostgresCase
from wakfu_server.ecology.protocol import proposal
from test_ecology_service_postgres import service


def births(ids, variant=10):
    return proposal(
        "plants",
        dict(
            kind="resource_growth_bulk",
            world_epoch="boot",
            resources=[
                dict(
                    kind="resource_growth",
                    world_epoch="boot",
                    expected=dict(
                        resource_uid=uid, stage=1, map_id=1134, instance_id=0
                    ),
                    member=dict(ref=variant),
                    draw=variant / 100,
                )
                for uid in ids
            ],
        ),
        "boot",
    )


class EcologyBulkQueueTests(PostgresCase):
    def test_merge_keeps_first_draw_bounded_pending_and_late_ack_safe(self):
        repository = service.Repository(self.store)
        repository.save([births(range(1, 33))], [])
        old = repository.pending()[0]
        repository.acknowledge([dict(id=old["id"], status="retry")])
        repository.save([births(range(1, 101), variant=11)], [])
        with self.store.connection() as db:
            row = db.execute(
                "SELECT id,payload,attempts FROM ecology_service_proposals WHERE delivered_at IS NULL"
            ).fetchone()
        self.assertNotEqual(row["id"], old["id"])
        self.assertEqual(row["attempts"], 1)
        entries = row["payload"]["resources"]
        self.assertEqual(len(entries), 64)
        self.assertEqual(
            [entry["expected"]["resource_uid"] for entry in entries], list(range(1, 65))
        )
        self.assertEqual([entry["member"]["ref"] for entry in entries[:32]], [10] * 32)
        repository.acknowledge([dict(id=old["id"], status="applied")])
        self.assertEqual(repository.pending_count(), 1)
        reopened = service.Repository(self.reopen())
        reopened.save([births(range(1, 101), variant=12)], [])
        self.assertEqual(reopened.pending_count(), 1)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT payload,attempts FROM ecology_service_proposals WHERE delivered_at IS NULL"
            ).fetchone()
        self.assertEqual(saved["payload"], row["payload"])
        self.assertEqual(saved["attempts"], 1)

    def test_identical_entry_set_cannot_reroll_after_five_failed_attempts(self):
        repository = service.Repository(self.store)
        repository.save([births(range(1, 65))], [])
        durable_id = repository.pending()[0]["id"]
        for _ in range(5):
            repository.acknowledge([dict(id=durable_id, status="retry")])
        repository.save([births(range(1, 65), variant=11)], [])
        self.assertEqual(repository.pending_count(), 0)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT payload,attempts,last_error_code FROM ecology_service_proposals WHERE id=%s",
                (durable_id,),
            ).fetchone()
        self.assertEqual(saved["attempts"], 5)
        self.assertEqual(saved["last_error_code"], "retry_exhausted")
        self.assertEqual(saved["payload"]["resources"][0]["member"]["ref"], 10)

    def test_lifecycle_metadata_does_not_duplicate_event_but_incarnation_does(self):
        repository = service.Repository(self.store)
        ticket = dict(
            map_id=1134,
            instance_id=0,
            group_id=1,
            monster_id=-1,
            reference=60,
            cycle=7,
            plan_incarnation="a",
        )
        first = dict(kind="maturation", ticket=ticket, plan=dict(draw=0.1))
        row = proposal(
            "mobs",
            dict(kind="lifecycle_bulk", scope=[1134, 0], operations=[first]),
            "boot",
        )
        repository.save([row], [])
        changed = dict(
            first,
            ticket=dict(
                ticket, decision=dict(attempts=4), plan_policy=dict(probability=0.9)
            ),
            plan=dict(draw=0.9),
        )
        repository.save(
            [proposal("mobs", dict(row["payload"], operations=[changed]), "boot")], []
        )
        saved = repository.pending()[0]
        self.assertEqual(saved["payload"]["operations"], [first])
        reincarnated = dict(changed, ticket=dict(ticket, plan_incarnation="b"))
        repository.save(
            [proposal("mobs", dict(row["payload"], operations=[reincarnated]), "boot")],
            [],
        )
        self.assertEqual(repository.pending_count(), 1)
        saved = repository.pending()[0]
        self.assertEqual(saved["payload"]["operations"], [first, reincarnated])

    def test_exhausted_entry_is_filtered_when_bulk_membership_changes(self):
        repository = service.Repository(self.store)
        a = births([1])
        a["payload"]["resources"][0]["expected"]["resource_reference"] = 60
        repository.save([a], [])
        durable_id = repository.pending()[0]["id"]
        for _ in range(5):
            repository.acknowledge([dict(id=durable_id, status="retry")])
        ab = births([1, 2])
        for entry in ab["payload"]["resources"]:
            entry["expected"]["resource_reference"] = 60
        repository.save([ab], [])
        saved = repository.pending()[0]
        self.assertEqual(
            [r["expected"]["resource_uid"] for r in saved["payload"]["resources"]], [2]
        )
        repository.acknowledge([dict(id=saved["id"], status="deferred")])
        repository.acknowledge([dict(id=saved["id"], status="retry")])
        abc = births([1, 2, 3])
        for entry in abc["payload"]["resources"]:
            entry["expected"]["resource_reference"] = 60
        repository.save([abc], [])
        saved = repository.pending()[0]
        self.assertEqual(
            [r["expected"]["resource_uid"] for r in saved["payload"]["resources"]],
            [2, 3],
        )
        newref = births([1])
        newref["payload"]["resources"][0]["expected"]["resource_reference"] = 61
        repository.save([newref], [])
        saved = repository.pending()[0]
        self.assertIn(
            (1, 61),
            [
                (r["expected"]["resource_uid"], r["expected"]["resource_reference"])
                for r in saved["payload"]["resources"]
            ],
        )

    def test_normal_wait_releases_scope_and_rearms_same_decision_only_after_due(self):
        repository = service.Repository(self.store)
        first = births([1])
        repository.save([first], [])
        a = repository.pending()[0]
        repository.acknowledge([dict(id=a["id"], status="deferred")])
        self.assertEqual(repository.pending_count(), 0)
        repository.save([births([2])], [])
        b = repository.pending()[0]
        self.assertEqual(b["payload"]["resources"][0]["expected"]["resource_uid"], 2)
        repository.acknowledge([dict(id=b["id"], status="applied")])
        repository.save([births([1], variant=11)], [])
        self.assertEqual(repository.pending_count(), 0)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT attempts,last_error_code FROM ecology_service_proposals WHERE id=%s",
                (a["id"],),
            ).fetchone()
            self.assertEqual(
                (saved["attempts"], saved["last_error_code"]), (0, "normal_wait")
            )
            db.execute(
                "UPDATE ecology_service_proposals SET next_attempt_at=CURRENT_TIMESTAMP WHERE id=%s",
                (a["id"],),
            )
        reopened = service.Repository(self.reopen())
        reopened.save([births([1], variant=11)], [])
        ready = reopened.pending()[0]
        self.assertEqual(ready["id"], a["id"])
        self.assertEqual(ready["payload"]["resources"], a["payload"]["resources"])
        reopened.acknowledge([dict(id=ready["id"], status="applied")])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT attempts FROM ecology_service_proposals WHERE id=%s",
                    (a["id"],),
                ).fetchone()["attempts"],
                0,
            )

    def test_completed_lifecycle_pass_rearms_due_same_cas_and_refreshes_new_roster(
        self,
    ):
        repository = service.Repository(self.store)
        ticket = dict(
            map_id=1134,
            instance_id=0,
            group_id=1,
            monster_id=-1,
            reference=60,
            cycle=1,
            plan_incarnation="native",
        )
        operation = dict(
            kind="maturation",
            ticket=ticket,
            configuration=dict(probability=0.1),
            expected_members=[dict(id=-1, ref=60)],
            plan=dict(draw=0.1),
        )
        row = proposal(
            "mobs",
            dict(kind="lifecycle_bulk", scope=[1134, 0], operations=[operation]),
            "boot",
        )
        repository.save([row], [])
        old = repository.pending()[0]
        repository.acknowledge([dict(id=old["id"], status="applied")])
        repository.save([row], [])
        again = repository.pending()[0]
        self.assertEqual(again["id"], old["id"])
        refreshed = dict(
            operation,
            expected_members=[dict(id=-1, ref=60), dict(id=-2, ref=60)],
            plan=dict(draw=0.9),
        )
        repository.save(
            [proposal("mobs", dict(row["payload"], operations=[refreshed]), "boot")], []
        )
        current = repository.pending()[0]
        self.assertNotEqual(current["id"], old["id"])
        entry = current["payload"]["operations"][0]
        self.assertEqual(entry["expected_members"], refreshed["expected_members"])
        self.assertEqual(entry["plan"], operation["plan"])
        repository.acknowledge([dict(id=old["id"], status="applied")])
        self.assertEqual(repository.pending_count(), 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT attempts FROM ecology_service_proposals WHERE id=%s",
                    (current["id"],),
                ).fetchone()["attempts"],
                0,
            )
