"""World lifecycle fences/failure budgets consume explicit native decision rows.

Seed creation, restart/policy pinning, block extension, orphan rejection and
set-based noops execute in Rust tests/lifecycle_contract.rs.
"""

from copy import deepcopy
import test_monster_reproduction_attempts as fixtures
from wakfu_server import monster_life_plans as plans
from lifecycle_fixture import attach_decision_fixture, read_decision_fixture


class MonsterLifePlansTests(fixtures.MonsterReproductionAttemptTests):
    def test_world_failure_budget_survives_reopen_and_caps_the_current_cycle(self):
        first = attach_decision_fixture(
            self.store, "reproduction", self.ticket, dict(interval_ms=60000, chance=0.1)
        )
        reopened = self.reopen()
        self.assertEqual(
            read_decision_fixture(reopened, "reproduction", self.ticket), first
        )
        for _ in range(8):
            plans.failure(reopened, first, "reproduction")
        with reopened.connection() as db:
            row = db.execute("SELECT events FROM monster_life_plans").fetchone()
            timer = db.execute(
                "SELECT due,last_active_ms,remaining_ms FROM monster_reproduction_timers"
            ).fetchone()
            self.assertFalse(plans.fence(db, first, "reproduction"))
        self.assertEqual(row["events"][0]["attempts"], 5)
        self.assertFalse(timer["due"])
        self.assertIsNone(timer["last_active_ms"])
        self.assertEqual(timer["remaining_ms"], 60000)

    def test_defeat_respawn_and_delete_invalidate_old_tickets(self):
        first = attach_decision_fixture(self.store, "reproduction", self.ticket, {})
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
        respawn = attach_decision_fixture(
            self.store, "reproduction", self.ticket, {}, incarnation="18" * 16
        )
        self.assertNotEqual(first["plan_incarnation"], respawn["plan_incarnation"])
        plans.failure(self.store, first, "reproduction")
        self.assertEqual(
            read_decision_fixture(self.store, "reproduction", self.ticket)["decision"][
                "attempts"
            ],
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

    def test_world_fence_rejects_foreign_incarnation_policy_draw_and_decision(self):
        policy = dict(interval_ms=60000, chance=0.1)
        ticket = attach_decision_fixture(
            self.store, "reproduction", self.ticket, policy
        )
        with self.store.connection() as db:
            self.assertTrue(
                plans.fence(
                    db,
                    ticket,
                    "reproduction",
                    configuration=policy,
                    draw=ticket["decision"]["draw"],
                )
            )
            self.assertFalse(
                plans.fence(
                    db, dict(ticket, plan_incarnation="foreign"), "reproduction"
                )
            )
            self.assertFalse(
                plans.fence(
                    db, ticket, "reproduction", configuration=dict(policy, chance=0.9)
                )
            )
            self.assertFalse(plans.fence(db, ticket, "reproduction", draw=0.99))
            changed = deepcopy(ticket)
            changed["decision"]["variant_seed"] = "ff" * 32
            self.assertFalse(plans.fence(db, changed, "reproduction"))


for _name in dir(fixtures.MonsterReproductionAttemptTests):
    if _name.startswith("test_") and _name not in MonsterLifePlansTests.__dict__:
        setattr(MonsterLifePlansTests, _name, None)
