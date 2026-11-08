"""Completed native withdrawals release only their own historical combat fence."""
from postgres_case import PostgresCase
from wakfu_server.heroes import CompanySelectionRejected


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

    def test_departed_rift_roster_does_not_freeze_creation_or_selection(self):
        from psycopg.types.json import Jsonb
        from wakfu_server import heroes

        values = self.state()
        account, main, alternate, generation = values
        with self.store.connection() as db:
            run = db.execute(
                "INSERT INTO rift_instances(wave_definition_id,owner_character_id,members,catalog,policy,seed,status,fight_id) "
                "VALUES(3,%s,%s,'{}','{}','departed-company','running',7) RETURNING instance_id",
                (main["id"], Jsonb([main["id"]])),
            ).fetchone()["instance_id"]
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=%s", (run, main["id"])
            )
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s,health_returned_at=%s WHERE fight_id=7",
                (self.store.now(), self.store.now()),
            )
        # A completed combat return alone cannot release an interior company.
        self.rejected(values)
        with self.assertRaises(CompanySelectionRejected):
            self.store.create_character(
                account, "Premature", selection_generation=generation
            )
        with self.store.connection() as db:
            db.execute("UPDATE characters SET instance_id=0 WHERE id=%s", (main["id"],))
        created = self.store.create_character(
            account, "AfterRift", selection_generation=generation
        )
        self.assertEqual(
            self.store.select_character(account, generation, created["id"])["id"],
            created["id"],
        )
        self.assertEqual(
            self.store.select_character(account, generation, main["id"])["id"],
            main["id"],
        )
        heroes.add(self.store, account, generation, main["id"], alternate["id"])
        # The new hero was never in the old fight; switching cannot claim or
        # rewrite that other owners' still-running historical Rift.
        self.store.select_character(account, generation, alternate["id"])
        self.store.select_character(account, generation, main["id"])
        with self.store.connection() as db:
            historical = db.execute(
                "SELECT status,members,owner_character_id FROM rift_instances WHERE instance_id=%s",
                (run,),
            ).fetchone()
            self.assertEqual(
                historical,
                {
                    "status": "running",
                    "members": [main["id"]],
                    "owner_character_id": main["id"],
                },
            )
            self.assertEqual(
                db.execute("SELECT status FROM combat_fights WHERE id=7").fetchone()[
                    "status"
                ],
                "active",
            )
        # A genuinely new instance still freezes the current company.
        with self.store.connection() as db:
            next_run = db.execute(
                "INSERT INTO rift_instances(wave_definition_id,owner_character_id,members,catalog,policy,seed) "
                "VALUES(3,%s,%s,'{}','{}','next-company') RETURNING instance_id",
                (main["id"], Jsonb([main["id"], alternate["id"]])),
            ).fetchone()["instance_id"]
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=ANY(%s)",
                (next_run, [main["id"], alternate["id"]]),
            )
        with self.assertRaises(CompanySelectionRejected):
            self.store.select_character(account, generation, created["id"])
        # Admission reserves membership before the transport commits. An
        # exterior location without this run's completed withdrawal is frozen.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET instance_id=0 WHERE id=ANY(%s)",
                ([main["id"], alternate["id"]],),
            )
        with self.assertRaises(CompanySelectionRejected):
            self.store.select_character(account, generation, created["id"])
