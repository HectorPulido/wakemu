"""Assignment parent contention defers without taking the inverted advisory lock."""
from test_objectives_assignment_lock_postgres import (
    ObjectivesAssignmentLockPostgresTests,
)
from wakfu_server.objectives import assignments


class ObjectivesParentLockTests(ObjectivesAssignmentLockPostgresTests):
    def test_parent_contention_defers_before_advisory_and_retries_after_commit(self):
        account, actor = self.owners[0]
        with self.store.connection() as foreground:
            foreground.execute(
                "SELECT id FROM characters WHERE id=%s FOR UPDATE", (actor,)
            )
            with self.store.connection() as scheduler:
                scheduler.execute("SET LOCAL statement_timeout='500ms'")
                self.assertEqual(
                    assignments.ensure_for_character(
                        scheduler, account, actor, 1, wait_for_lock=False
                    ),
                    0,
                )
                # The foreground can acquire the exact assignment lock while
                # the background transaction remains open: no circular wait.
                self.assertTrue(
                    foreground.execute(
                        "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS locked",
                        ("objective-assignments:" + str(account),),
                    ).fetchone()["locked"]
                )
        with self.store.connection() as scheduler:
            self.assertGreater(
                assignments.ensure_for_character(
                    scheduler, account, actor, 1, wait_for_lock=False
                ),
                0,
            )
        with self.store.connection() as scheduler:
            self.assertEqual(
                assignments.ensure_for_character(
                    scheduler, account, actor, 1, wait_for_lock=False
                ),
                0,
            )
