"""Durable event draws survive restart but never cross a defeated incarnation."""
import test_monster_reproduction_attempts as fixtures
from wakfu_server import monster_life_plans as plans


class MonsterLifePlansTests(fixtures.MonsterReproductionAttemptTests):
    # Hide inherited cases; reuse only the durable roster fixture.
    def test_restart_failures_policy_and_next_block_preserve_original_seed(self):
        first = plans.attach(
            self.store,
            (self.map_id, 0),
            "reproduction",
            [self.ticket],
            dict(chance=0.1, interval_ms=60000),
        )[0]
        reopened = self.reopen()
        again = plans.attach(
            reopened,
            (self.map_id, 0),
            "reproduction",
            [self.ticket],
            dict(chance=0.9, interval_ms=60000),
        )[0]
        self.assertEqual(first, again)
        for _ in range(8):
            plans.failure(reopened, first, "reproduction")
        self.assertEqual(
            plans.attach(reopened, (self.map_id, 0), "reproduction", [self.ticket], {}),
            [],
        )
        next_ticket = dict(self.ticket, cycle=33)
        later = plans.attach(
            reopened, (self.map_id, 0), "reproduction", [next_ticket], {}
        )[0]
        with reopened.connection() as db:
            row = db.execute("SELECT seed,events FROM monster_life_plans").fetchone()
        self.assertEqual(later["decision"], plans.event(row["seed"], 33))
        self.assertEqual(later["plan_policy"], dict(chance=0.1, interval_ms=60000))
        self.assertEqual(later["plan_incarnation"], first["plan_incarnation"])

    def test_defeat_respawn_and_delete_invalidate_old_tickets(self):
        first = plans.attach(
            self.store, (self.map_id, 0), "reproduction", [self.ticket], {}
        )[0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET status='defeated' WHERE map_id=%s AND instance_id=0 AND group_id=%s",
                (self.map_id, self.group_id),
            )
            self.assertFalse(plans.fence(db, first, "reproduction"))
            db.execute(
                "UPDATE combat_groups SET status='available' WHERE map_id=%s AND instance_id=0 AND group_id=%s",
                (self.map_id, self.group_id),
            )
        respawn = plans.attach(
            self.store, (self.map_id, 0), "reproduction", [self.ticket], {}
        )[0]
        self.assertNotEqual(respawn["plan_incarnation"], first["plan_incarnation"])
        plans.failure(self.store, first, "reproduction")
        self.assertEqual(
            plans.attach(
                self.store, (self.map_id, 0), "reproduction", [self.ticket], {}
            )[0]["decision"]["attempts"],
            0,
        )
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM combat_groups WHERE map_id=%s AND instance_id=0 AND group_id=%s",
                (self.map_id, self.group_id),
            )
            self.assertFalse(plans.fence(db, respawn, "reproduction"))
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM monster_life_plans").fetchone()[
                    "n"
                ],
                0,
            )

    def test_set_based_noops_commit_once_and_reject_stale_or_fighting_rosters(self):
        self._set_policy(birth=0.0, new_group=0.0, max_members=8)
        from wakfu_server import monster_reproduction

        policy = monster_reproduction.policy(self.store)
        ticket = plans.attach(
            self.store, (self.map_id, 0), "reproduction", [self.ticket], policy
        )[0]
        proposal = dict(
            kind="reproduction",
            ticket=ticket,
            configuration=policy,
            expected_members=self._group()["members"],
            draw=ticket["decision"]["draw"],
        )
        stale = dict(proposal, expected_members=[])
        plans.resolve_noops(self.store, [stale])
        self.assertIsNone(self._receipt())
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "UPDATE combat_groups SET generation='test',fight_id=%s,status='fighting' WHERE map_id=%s AND instance_id=0 AND group_id=%s",
                (fight_id, self.map_id, self.group_id),
            )
        plans.resolve_noops(self.store, [proposal])
        self.assertIsNone(self._receipt())
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET status='available' WHERE map_id=%s AND instance_id=0 AND group_id=%s",
                (self.map_id, self.group_id),
            )
        bad_incarnation = dict(proposal, ticket=dict(ticket, plan_incarnation="wrong"))
        plans.resolve_noops(self.store, [bad_incarnation])
        self.assertIsNone(self._receipt())
        self.assertEqual(plans.resolve_noops(self.store, [proposal]), [])
        first = self._receipt()
        self.assertIsNotNone(first)
        self.assertIsNone(first["child_id"])
        plans.resolve_noops(self.reopen(), [proposal])
        self.assertEqual(self._receipt(), first)
        with self.store.connection() as db:
            timer = db.execute(
                "SELECT due,remaining_ms FROM monster_reproduction_timers WHERE monster_id=%s",
                (self.monster_id,),
            ).fetchone()
            self.assertFalse(timer["due"])
            self.assertEqual(timer["remaining_ms"], policy["interval_ms"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_preexisting_defeated_due_timers_cannot_create_any_life_plan(self):
        from wakfu_server import monster_maturation, monster_reproduction

        with self.store.connection() as db:
            db.execute(
                "UPDATE monster_maturation_timers SET due=true,cycle=1,remaining_ms=0 WHERE monster_id=%s",
                (self.monster_id,),
            )
            db.execute(
                "UPDATE combat_groups SET status='defeated' WHERE map_id=%s AND instance_id=0 AND group_id=%s",
                (self.map_id, self.group_id),
            )
        for kind, domain in (
            ("maturation", monster_maturation),
            ("reproduction", monster_reproduction),
        ):
            with self.subTest(kind=kind):
                self.assertEqual(domain.pending(self.store, self.map_id, 0), [])
                self.assertEqual(
                    plans.attach(
                        self.store,
                        (self.map_id, 0),
                        kind,
                        [self.ticket],
                        dict(interval_ms=60000),
                    ),
                    [],
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM monster_life_plans").fetchone()[
                    "n"
                ],
                0,
            )

    def test_ticket_read_before_defeat_cannot_recreate_deleted_plan(self):
        from wakfu_server import monster_reproduction

        tickets = monster_reproduction.pending(self.store, self.map_id, 0)
        self.assertEqual(len(tickets), 1)
        first = plans.attach(
            self.store,
            (self.map_id, 0),
            "reproduction",
            tickets,
            dict(interval_ms=60000),
        )
        self.assertEqual(len(first), 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET status='defeated' WHERE map_id=%s AND instance_id=0 AND group_id=%s",
                (self.map_id, self.group_id),
            )
        self.assertEqual(
            plans.attach(
                self.reopen(),
                (self.map_id, 0),
                "reproduction",
                tickets,
                dict(interval_ms=60000),
            ),
            [],
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM monster_life_plans").fetchone()[
                    "n"
                ],
                0,
            )


for _name in dir(fixtures.MonsterReproductionAttemptTests):
    if _name.startswith("test_") and _name not in MonsterLifePlansTests.__dict__:
        setattr(MonsterLifePlansTests, _name, None)
