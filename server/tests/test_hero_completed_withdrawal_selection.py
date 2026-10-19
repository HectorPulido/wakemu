"""Completed native withdrawals release only their own historical combat fence."""
from postgres_case import PostgresCase
from wakfu_server.characters.heroes import CompanySelectionRejected


class CompletedWithdrawalSelectionTests(PostgresCase):
    def state(self, *, foreign_receipt=False):
        store = self.store
        account = store.register("owner", "test-password")["id"]
        main = store.create_character(account, "Main")
        alternate = store.create_character(account, "Alternate")
        generation = store.begin_session(account)
        store.select_character(account, generation, main["id"])
        foreign = store.register("foreign", "test-password")["id"]
        with store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(7,'active')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(7,%s,%s,0,%s)",
                (main["id"], account, generation),
            )
            db.execute(
                "INSERT INTO combat_pve_withdrawals(fight_id,character_id,account_id,session_generation,created_at) "
                "VALUES(7,%s,%s,%s,%s)",
                (
                    main["id"],
                    foreign if foreign_receipt else account,
                    generation,
                    store.now(),
                ),
            )
        return account, main, alternate, generation

    def rejected(self, values):
        account, main, alternate, generation = values
        with self.assertRaises(CompanySelectionRejected):
            self.store.select_character(account, generation, alternate["id"])
        self.assertTrue(
            self.store.current_character_session(account, generation, main["id"])
        )

    def test_selection_requires_both_native_return_and_health_completion(self):
        values = self.state()
        account, main, alternate, generation = values
        self.rejected(values)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s WHERE fight_id=7",
                (self.store.now(),),
            )
        self.rejected(values)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET health_returned_at=%s WHERE fight_id=7",
                (self.store.now(),),
            )
        selected = self.store.select_character(account, generation, alternate["id"])
        self.assertEqual(selected["id"], alternate["id"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT status FROM combat_fights WHERE id=7").fetchone()[
                    "status"
                ],
                "active",
            )

    def test_foreign_receipt_and_another_active_fight_cannot_release_selection(self):
        values = self.state(foreign_receipt=True)
        account, main, alternate, generation = values
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s,health_returned_at=%s WHERE fight_id=7",
                (self.store.now(), self.store.now()),
            )
        self.rejected(values)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET account_id=%s WHERE fight_id=7",
                (account,),
            )
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(8,'placement')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(8,%s,%s,0,%s)",
                (main["id"], account, generation),
            )
        self.rejected(values)
        with self.store.connection() as db:
            db.execute("UPDATE combat_fights SET status='aborted' WHERE id=8")
        selected = self.store.select_character(account, generation, alternate["id"])
        self.assertEqual(selected["id"], alternate["id"])
