"""Local bundle caps and durable transaction allocation regressions."""
from decimal import Decimal
import unittest
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from wakfu_server import drop_allocation as allocation
from wakfu_server.combat_drops import DropDecision
from postgres_case import PostgresCase


def decision(index=0, reference=10272, quantity=7, success=True):
    return DropDecision(
        -100 - index,
        1,
        index,
        0,
        reference,
        success,
        quantity if success else None,
        Decimal(1),
        Decimal(1),
        Decimal(1),
        0,
        0 if success else None,
        1,
        10,
        -1,
        1,
        0,
    )


def policy(scope="recipient_item"):
    return {
        "policy": allocation.POLICY,
        "enabled": True,
        "scope": scope,
        "rarity_caps": {"0": None, "1": None, "7": 1},
    }


class DropAllocationTests(unittest.TestCase):
    def test_bundle_cap_preserves_quantities_draws_and_native_limit(self):
        original = (decision(), decision(1))
        filtered, audit, counts = allocation.filter_decisions(
            original, policy=policy(), rarities={10272: 7}
        )
        self.assertEqual(filtered[0], original[0])
        self.assertFalse(filtered[1].success)
        self.assertIsNone(filtered[1].quantity)
        self.assertIsNone(filtered[1].quantity_draw_numerator)
        self.assertEqual(filtered[1].native_roll_max, 1)
        self.assertEqual(filtered[1].draw_numerator, original[1].draw_numerator)
        self.assertEqual(counts, {10272: 1})
        self.assertEqual([row["allowed"] for row in audit], [True, False])
        self.assertTrue(audit[1]["planned_success"])
        self.assertEqual(audit[1]["planned_quantity"], original[1].quantity)
        self.assertEqual(
            audit[1]["planned_quantity_draw_numerator"],
            original[1].quantity_draw_numerator,
        )

    def test_common_unlimited_and_failures_never_consume(self):
        original = (decision(success=False), decision(1), decision(2))
        filtered, audit, counts = allocation.filter_decisions(
            original, policy=policy(), rarities={10272: 1}
        )
        self.assertEqual(filtered, original)
        self.assertEqual(counts, {10272: 2})
        self.assertEqual(len(audit), 2)

    def test_fight_counts_apply_across_sources_but_items_independent(self):
        original = (decision(), decision(1, 24309))
        filtered, _, counts = allocation.filter_decisions(
            original,
            policy=policy("fight_item"),
            rarities={10272: 7, 24309: 7},
            consumed={10272: 1},
        )
        self.assertFalse(filtered[0].success)
        self.assertTrue(filtered[1].success)
        self.assertEqual(counts, {10272: 1, 24309: 1})

    def test_unknown_success_and_invalid_caps_fail(self):
        with self.assertRaises(ValueError):
            allocation.filter_decisions((decision(),), policy=policy(), rarities={})
        for cap in (-1, True, 1.5):
            invalid = policy()
            invalid["rarity_caps"]["7"] = cap
            with self.assertRaises(ValueError):
                allocation.validate_policy(invalid)


class DropAllocationPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account_id = self.store.register("allocation", "local-password")["id"]
        self.character = self.store.create_character(
            self.account_id, "Allocation Winner"
        )
        with self.store.connection() as db:
            self.fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (self.fight_id, self.character["id"], self.account_id),
            )

    def test_receipt_replay_and_policy_snapshot_survive_setting_changes(self):
        with self.store.connection() as db:
            first, snapshot = allocation.allocate(
                db, self.fight_id, self.character["id"], (decision(), decision(1))
            )
            self.assertEqual([d.success for d in first], [True, False])
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{rarity_caps,7}','0') WHERE name=%s",
                (allocation.SETTING,),
            )
            replay, again = allocation.allocate(
                db, self.fight_id, self.character["id"], ()
            )
            self.assertEqual(replay, first)
            self.assertEqual(again, snapshot)

    def test_allocation_rollback_does_not_consume_cap(self):
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with self.store.connection() as db:
                allocation.allocate(
                    db, self.fight_id, self.character["id"], (decision(),)
                )
                raise RuntimeError("rollback")
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT fight_id FROM fight_drop_allocations WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()
            )
            filtered, _ = allocation.allocate(
                db, self.fight_id, self.character["id"], (decision(),)
            )
            self.assertTrue(filtered[0].success)

    def test_scope_controls_cap_across_recipients_and_policy_is_fight_pinned(self):
        hero = self.store.create_character(self.account_id, "Allocation Hero")
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (self.fight_id, hero["id"], self.account_id),
            )
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{scope}','\"fight_item\"') WHERE name=%s",
                (allocation.SETTING,),
            )
            allocation.allocate(db, self.fight_id, self.character["id"], (decision(),))
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{scope}','\"recipient_item\"') WHERE name=%s",
                (allocation.SETTING,),
            )
            filtered, snapshot = allocation.allocate(
                db, self.fight_id, hero["id"], (decision(),)
            )
            self.assertFalse(filtered[0].success)
            self.assertEqual(snapshot["policy"]["scope"], "fight_item")

    def test_concurrent_fight_item_allocations_serialize_and_share_one_cap(self):
        hero = self.store.create_character(self.account_id, "Concurrent Allocation")
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (self.fight_id, hero["id"], self.account_id),
            )
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{scope}','\"fight_item\"') WHERE name=%s",
                (allocation.SETTING,),
            )
        started = threading.Event()
        worker_pid = []

        def allocate_second_recipient():
            with self.store.connection() as db:
                db.execute("SET LOCAL lock_timeout='5s'")
                worker_pid.append(
                    db.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
                )
                started.set()
                return allocation.allocate(
                    db, self.fight_id, hero["id"], (decision(1),)
                )

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.store.connection() as db:
                first, _ = allocation.allocate(
                    db, self.fight_id, self.character["id"], (decision(),)
                )
                self.assertTrue(first[0].success)
                future = executor.submit(allocate_second_recipient)
                self.assertTrue(
                    started.wait(3), "Second database connection did not start"
                )
                deadline = time.monotonic() + 3
                blocked = False
                while time.monotonic() < deadline:
                    db.execute("SELECT pg_stat_clear_snapshot()")
                    waiting = db.execute(
                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s",
                        (worker_pid[0],),
                    ).fetchone()
                    if waiting is not None and waiting["wait_event_type"] == "Lock":
                        blocked = True
                        break
                    time.sleep(0.01)
                self.assertTrue(
                    blocked, "Second allocation did not wait on the fight lock"
                )
                self.assertFalse(future.done())
            second, snapshot = future.result(timeout=5)
        self.assertFalse(second[0].success)
        self.assertEqual(snapshot["allocations"][0]["consumed_before"], 1)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT snapshot FROM fight_drop_allocations WHERE fight_id=%s",
                (self.fight_id,),
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                sum(row["snapshot"]["accepted_counts"].get("10272", 0) for row in rows),
                1,
            )
