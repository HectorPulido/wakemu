"""Scheduler contention must defer an account without poisoning other receipts."""
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.objectives import assignments, repository


class ObjectivesAssignmentLockPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.owners = []
        for index, name in enumerate(("Lock First", "Lock Second")):
            account = self.store.register(f"assignment-lock-{index}", "local-password")[
                "id"
            ]
            actor = self.store.create_character(account, name)["id"]
            generation = self.store.begin_session(account, ttl=7200)
            self.store.select_character(account, generation, actor)
            self.owners.append((account, actor))
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='objectives_assignment_counts'",
                (Jsonb({"daily": 1, "weekly": 0, "mission": 0}),),
            )
            repository.put_definition(
                db,
                {
                    "key": "test.assignment-lock.daily",
                    "title": "Assignment lock",
                    "description": "Contention receipt",
                    "kind": "daily",
                    "enabled": True,
                    "objectives": [
                        {
                            "key": "done",
                            "event": "test.assignment_lock",
                            "filters": {},
                            "target": 1,
                        }
                    ],
                    "schedule": {"type": "daily", "timezone": "America/Bogota"},
                    "rewards": [],
                },
                0,
            )

    def test_busy_account_is_deferred_then_assigned_once_after_release(self):
        first, second = self.owners
        # Foreground holds the higher account while the scheduler visits the
        # lower account first: the exact two-account production lock inversion.
        with self.store.connection() as foreground:
            foreground.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"objective-assignments:{second[0]}",),
            )
            with self.store.connection() as scheduler:
                scheduler.execute("SET LOCAL statement_timeout='1000ms'")
                self.assertGreater(assignments.ensure_online(scheduler), 0)
                self.assertTrue(
                    scheduler.execute(
                        "SELECT 1 FROM objectives_assignment_periods WHERE account_id=%s",
                        (first[0],),
                    ).fetchone()
                )
                self.assertIsNone(
                    scheduler.execute(
                        "SELECT 1 FROM objectives_assignment_periods WHERE account_id=%s",
                        (second[0],),
                    ).fetchone()
                )
            # Scheduler committed and released the lower lock, so the original
            # foreground transaction can take it without a deadlock/retry.
            self.assertTrue(
                foreground.execute(
                    "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS locked",
                    (f"objective-assignments:{first[0]}",),
                ).fetchone()["locked"]
            )
        with self.store.connection() as scheduler:
            self.assertGreater(assignments.ensure_online(scheduler), 0)
            before = scheduler.execute(
                "SELECT * FROM objectives_assignments ORDER BY account_id,group_key,period_key,definition_key"
            ).fetchall()
        with self.store.connection() as scheduler:
            self.assertEqual(assignments.ensure_online(scheduler), 0)
            self.assertEqual(
                before,
                scheduler.execute(
                    "SELECT * FROM objectives_assignments ORDER BY account_id,group_key,period_key,definition_key"
                ).fetchall(),
            )

    def test_foreground_default_keeps_transaction_lock_until_commit(self):
        account, actor = self.owners[0]
        with self.store.connection() as foreground:
            assignments.ensure_for_character(foreground, account, actor, 1)
            with self.store.connection() as other:
                self.assertFalse(
                    other.execute(
                        "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS locked",
                        (f"objective-assignments:{account}",),
                    ).fetchone()["locked"]
                )
