from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_maturation
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class MonsterMaturationAttemptTests(PostgresCase):
    def setUp(self):
        super().setUp()
        # Most receipt tests exercise transaction semantics, not production
        # pacing; the dedicated pacing test covers the 900000ms default.
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{interval_ms}','60000'::jsonb) "
                "WHERE name='monster_maturation'"
            )
        self.groups = PersistentGroups(self.store)
        self.map_id = 1134
        self.instance_id = 0
        self.group_id = 88101
        self.monster_id = -88101
        self.other_id = -88102
        self.members = [
            self._member(2, self.monster_id, 0),
            self._member(39, self.other_id, 1),
        ]
        self.group_key = self.groups.register(
            self.map_id, self.instance_id, self.group_id, self.members
        )

    def _member(self, reference, actor_id, x):
        return owned_instance(
            reference,
            REFERENCES[reference]["min_level"],
            actor_id,
            map_id=self.map_id,
            x=x,
            y=0,
            z=0,
        )

    def _ticket(self, monster_id=None):
        monster_id = self.monster_id if monster_id is None else monster_id
        due = monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="maturation-run",
            now_ms=0,
        )
        due = monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="maturation-run",
            now_ms=60000,
        )
        return next(row for row in due if row["monster_id"] == monster_id)

    def _group(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                self.group_key,
            ).fetchone()

    def _timer(self, monster_id=None):
        monster_id = self.monster_id if monster_id is None else monster_id
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM monster_maturation_timers WHERE map_id=%s AND instance_id=%s "
                "AND monster_id=%s",
                (self.map_id, self.instance_id, monster_id),
            ).fetchone()

    def _receipt(self, ticket):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM monster_maturation_receipts WHERE map_id=%s AND instance_id=%s "
                "AND monster_id=%s AND cycle=%s",
                (
                    ticket["map_id"],
                    ticket["instance_id"],
                    ticket["monster_id"],
                    ticket["cycle"],
                ),
            ).fetchone()

    def _outbox(self, ticket):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM monster_maturation_outbox WHERE map_id=%s AND instance_id=%s "
                "AND monster_id=%s AND cycle=%s",
                (
                    ticket["map_id"],
                    ticket["instance_id"],
                    ticket["monster_id"],
                    ticket["cycle"],
                ),
            ).fetchone()

    def test_success_transforms_only_member_and_commits_receipt_outbox_together(self):
        ticket = self._ticket()
        before = self._group()
        old_by_id = {row["id"]: row for row in before["members"]}
        result = monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        self.assertEqual(1, result["to_reference"])
        self.assertEqual(2, result["from_reference"])
        after = self._group()
        changed = {row["id"]: row for row in after["members"]}
        grown = changed[self.monster_id]
        self.assertEqual(self.monster_id, grown["id"])
        self.assertEqual((0, 0, 0), (grown["x"], grown["y"], grown["z"]))
        self.assertEqual(REFERENCES[1]["min_level"], grown["level"])
        self.assertEqual(grown["max_hp"], grown["hp"])
        self.assertEqual(old_by_id[self.other_id], changed[self.other_id])
        self.assertEqual(before["revision"] + 1, after["revision"])
        receipt = self._receipt(ticket)
        outbox = self._outbox(ticket)
        self.assertIsNotNone(receipt)
        self.assertEqual(1, receipt["to_reference"])
        self.assertEqual(0.1, receipt["draw"])
        self.assertEqual(receipt["cycle"], outbox["cycle"])
        self.assertEqual(after["revision"], outbox["revision"])
        self.assertFalse(outbox["published"])
        timer = self._timer()
        self.assertEqual(1, timer["reference"])
        self.assertEqual(60000, timer["remaining_ms"])
        self.assertFalse(timer["due"])

    def test_nonadvancing_outcome_records_cycle_but_has_no_outbox(self):
        ticket = self._ticket()
        revision = self._group()["revision"]
        result = monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.9,
            choose=lambda candidates: self.fail("No category should be selected"),
        )
        self.assertIsNone(result["to_reference"])
        self.assertEqual(2, result["from_reference"])
        self.assertEqual(revision, self._group()["revision"])
        self.assertIsNotNone(self._receipt(ticket))
        self.assertIsNone(self._outbox(ticket))
        self.assertEqual(2, self._timer()["reference"])
        self.assertEqual(60000, self._timer()["remaining_ms"])
        self.assertFalse(self._timer()["due"])

    def test_replay_returns_committed_receipt_without_redrawing_or_mutating_again(self):
        ticket = self._ticket()
        first = monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        revision = self._group()["revision"]
        with patch.object(
            monster_maturation.secrets,
            "randbelow",
            side_effect=AssertionError("redrew"),
        ):
            second = monster_maturation.attempt(
                self.store,
                ticket,
                present=True,
                draw=None,
                choose=lambda candidates: self.fail("Replay called choose"),
            )
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["to_reference"], second["to_reference"])
        self.assertEqual(first["draw"], second["draw"])
        self.assertEqual(revision, self._group()["revision"])

    def test_foreign_ticket_for_committed_cycle_is_rejected(self):
        ticket = self._ticket()
        monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        foreign = {**ticket, "group_id": ticket["group_id"] + 1}
        with self.assertRaisesRegex(ValueError, "Foreign monster maturation cycle"):
            monster_maturation.attempt(self.store, foreign, present=True, draw=0.5)

    def test_absent_or_excluded_and_fighting_tickets_do_not_draw(self):
        ticket = self._ticket()
        with patch.object(
            self.store,
            "connection",
            side_effect=AssertionError("DB access while absent"),
        ):
            self.assertIsNone(
                monster_maturation.attempt(self.store, ticket, present=False)
            )

        choose = lambda candidates: self.fail("Ineligible attempt drew a candidate")
        self.assertIsNone(
            monster_maturation.attempt(
                self.store,
                ticket,
                present=True,
                excluded_ids={self.monster_id},
                draw=0.1,
                choose=choose,
            )
        )
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(self.group_key, "fight-run", fight_id)
        self.assertIsNone(
            monster_maturation.attempt(
                self.store, ticket, present=True, draw=0.1, choose=choose
            )
        )
        self.assertIsNone(self._receipt(ticket))
        self.assertTrue(self.groups.finish(lease, defeated=False))

    def test_stale_timer_or_changed_reference_does_not_draw(self):
        ticket = self._ticket()
        with self.store.connection() as db:
            db.execute(
                "UPDATE monster_maturation_timers SET due=false WHERE map_id=%s "
                "AND instance_id=%s AND monster_id=%s",
                (self.map_id, self.instance_id, self.monster_id),
            )
        choose = lambda candidates: self.fail("Stale clock drew a candidate")
        self.assertIsNone(
            monster_maturation.attempt(
                self.store, ticket, present=True, draw=0.1, choose=choose
            )
        )
        self.assertIsNone(self._receipt(ticket))

        # Restore a due timer, then make the durable roster identity disagree.
        with self.store.connection() as db:
            db.execute(
                "UPDATE monster_maturation_timers SET due=true WHERE map_id=%s "
                "AND instance_id=%s AND monster_id=%s",
                (self.map_id, self.instance_id, self.monster_id),
            )
            changed = [dict(row) for row in self._group()["members"]]
            changed[0]["ref"] = 39
            db.execute(
                "UPDATE combat_groups SET members=%s WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (Jsonb(changed), *self.group_key),
            )
        self.assertIsNone(
            monster_maturation.attempt(
                self.store, ticket, present=True, draw=0.1, choose=choose
            )
        )
        self.assertIsNone(self._receipt(ticket))

    def test_outbox_failure_rolls_back_roster_timer_receipt_and_revision(self):
        ticket = self._ticket()
        before_group = self._group()
        before_timer = dict(self._timer())
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_maturation_outbox() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'outbox rejected'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_maturation_outbox BEFORE INSERT ON monster_maturation_outbox "
                "FOR EACH ROW EXECUTE FUNCTION reject_maturation_outbox()"
            )
        with self.assertRaisesRegex(Exception, "outbox rejected"):
            monster_maturation.attempt(
                self.store,
                ticket,
                present=True,
                draw=0.1,
                choose=lambda candidates: candidates[0],
            )
        after_group = self._group()
        after_timer = dict(self._timer())
        self.assertEqual(before_group["members"], after_group["members"])
        self.assertEqual(before_group["revision"], after_group["revision"])
        self.assertEqual(before_timer, after_timer)
        self.assertIsNone(self._receipt(ticket))
        self.assertIsNone(self._outbox(ticket))

    def test_pending_due_cycle_survives_reopen_for_recovery(self):
        ticket = self._ticket()
        reopened = self.reopen()
        recovered = monster_maturation.pending(reopened, self.map_id, self.instance_id)
        self.assertIn(ticket, recovered)
        self.assertEqual(
            {self.monster_id, self.other_id}, {row["monster_id"] for row in recovered}
        )
        self.assertEqual({1}, {row["cycle"] for row in recovered})

    def test_concurrent_attempts_for_one_group_cycle_commit_once(self):
        ticket = self._ticket()
        barrier = Barrier(2)
        count_lock = Lock()
        draw_calls = []
        choose_calls = []

        def counted_draw(_upper):
            with count_lock:
                draw_calls.append(1)
            return 0  # Select the rare/boss category if present, otherwise ordinary.

        def choose(candidates):
            with count_lock:
                choose_calls.append(tuple(row["reference"] for row in candidates))
            return candidates[0]

        with patch.object(
            monster_maturation.secrets, "randbelow", side_effect=counted_draw
        ):

            def run_one():
                barrier.wait(timeout=5)
                return monster_maturation.attempt(
                    self.store, ticket, present=True, draw=None, choose=choose
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: run_one(), range(2)))
        self.assertEqual(1, len(draw_calls))
        self.assertEqual(1, len(choose_calls))
        self.assertEqual(1, sum(bool(result["duplicate"]) for result in results))
        after = self._group()
        changed = {row["id"]: row for row in after["members"]}
        self.assertEqual(1, changed[self.monster_id]["ref"])
        self.assertEqual(39, changed[self.other_id]["ref"])
        self.assertEqual(1, after["revision"])
        self.assertIsNotNone(self._receipt(ticket))
        self.assertIsNotNone(self._outbox(ticket))

    def test_unpublished_uses_latest_roster_and_ack_is_exact_and_idempotent(self):
        ticket = self._ticket()
        monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        first = monster_maturation.unpublished(
            self.store, self.map_id, self.instance_id
        )
        self.assertEqual(1, len(first))
        event = first[0]
        self.assertEqual(1, event["revision"])
        current = self._group()
        moved = [dict(member) for member in current["members"]]
        moved[0]["x"] = 5
        self.assertTrue(
            self.groups.move_members(self.group_key, current["members"], moved)
        )

        refreshed = monster_maturation.unpublished(
            self.store, self.map_id, self.instance_id
        )
        self.assertEqual(1, len(refreshed))
        event = refreshed[0]
        self.assertEqual(1, event["revision"])
        self.assertEqual(2, event["current_revision"])
        self.assertEqual(
            5,
            next(
                member["x"]
                for member in event["members"]
                if member["id"] == self.monster_id
            ),
        )

        stale = {**event, "current_revision": 1}
        self.assertFalse(monster_maturation.acknowledge(self.store, stale))
        self.assertEqual(
            1,
            len(
                monster_maturation.unpublished(
                    self.store, self.map_id, self.instance_id
                )
            ),
        )
        self.assertTrue(monster_maturation.acknowledge(self.store, event))
        self.assertFalse(monster_maturation.acknowledge(self.store, event))
        self.assertEqual(
            [],
            monster_maturation.unpublished(self.store, self.map_id, self.instance_id),
        )

    def test_ack_is_refused_when_group_is_fighting(self):
        ticket = self._ticket()
        monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        event = monster_maturation.unpublished(
            self.store, self.map_id, self.instance_id
        )[0]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(self.group_key, "fight-for-ack", fight_id)
        self.assertFalse(monster_maturation.acknowledge(self.store, event))
        remaining = monster_maturation.unpublished(
            self.store, self.map_id, self.instance_id
        )
        self.assertEqual([event["cycle"]], [row["cycle"] for row in remaining])
        self.assertTrue(self.groups.finish(lease, defeated=False))

    def test_acknowledging_one_of_multiple_group_events_leaves_the_other_pending(self):
        first_ticket = self._ticket(self.monster_id)
        second_ticket = next(
            row
            for row in monster_maturation.pending(
                self.store, self.map_id, self.instance_id
            )
            if row["monster_id"] == self.other_id
        )
        # _ticket has already advanced both members to cycle one.
        first_result = monster_maturation.attempt(
            self.store,
            first_ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        second_result = monster_maturation.attempt(
            self.store,
            second_ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        self.assertEqual(1, first_result["to_reference"])
        self.assertEqual(1, second_result["to_reference"])
        events = monster_maturation.unpublished(
            self.store, self.map_id, self.instance_id
        )
        self.assertEqual(2, len(events))
        self.assertEqual({2}, {event["current_revision"] for event in events})
        selected = next(
            event for event in events if event["monster_id"] == self.monster_id
        )
        other = next(event for event in events if event["monster_id"] == self.other_id)
        self.assertTrue(monster_maturation.acknowledge(self.store, selected))
        remaining = monster_maturation.unpublished(
            self.store, self.map_id, self.instance_id
        )
        self.assertEqual(
            [other["monster_id"]], [event["monster_id"] for event in remaining]
        )
        self.assertEqual([other["cycle"]], [event["cycle"] for event in remaining])
        self.assertTrue(monster_maturation.acknowledge(self.store, other))
        self.assertEqual(
            [],
            monster_maturation.unpublished(self.store, self.map_id, self.instance_id),
        )

    def test_reconcile_accepts_original_seed_and_position_only_drift(self):
        current = self._group()["members"]
        self.assertEqual(
            self.group_key,
            monster_maturation.reconcile_seed(
                self.store, self.group_key, self.members, current
            ),
        )
        moved = [dict(member) for member in current]
        moved[0]["x"] = 7
        self.assertTrue(self.groups.move_members(self.group_key, current, moved))
        self.assertEqual(
            self.group_key,
            monster_maturation.reconcile_seed(
                self.store, self.group_key, self.members, self._group()["members"]
            ),
        )

    def test_reconcile_accepts_receipted_growth_followed_by_position_change(self):
        ticket = self._ticket()
        monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        current = self._group()["members"]
        moved = [dict(member) for member in current]
        moved[0]["x"] = 9
        self.assertTrue(self.groups.move_members(self.group_key, current, moved))
        self.assertEqual(
            self.group_key,
            monster_maturation.reconcile_seed(
                self.store, self.group_key, self.members, self._group()["members"]
            ),
        )

    def test_reconcile_accepts_nonadvancing_receipt_before_successful_cycle(self):
        failed_ticket = self._ticket()
        failed = monster_maturation.attempt(
            self.store,
            failed_ticket,
            present=True,
            draw=0.9,
            choose=lambda candidates: candidates[0],
        )
        self.assertIsNone(failed["to_reference"])
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="maturation-run",
            now_ms=70000,
        )
        due = monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="maturation-run",
            now_ms=130000,
        )
        next_ticket = next(row for row in due if row["monster_id"] == self.monster_id)
        grown = monster_maturation.attempt(
            self.store,
            next_ticket,
            present=True,
            draw=0.1,
            choose=lambda candidates: candidates[0],
        )
        self.assertEqual(1, grown["to_reference"])
        receipts = self.store.connection()
        with receipts as db:
            rows = db.execute(
                "SELECT cycle,from_reference,to_reference FROM monster_maturation_receipts "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s ORDER BY cycle",
                (self.map_id, self.instance_id, self.monster_id),
            ).fetchall()
        self.assertEqual(
            [(1, 2, None), (2, 2, 1)],
            [
                (row["cycle"], row["from_reference"], row["to_reference"])
                for row in rows
            ],
        )
        self.assertEqual(
            self.group_key,
            monster_maturation.reconcile_seed(
                self.store, self.group_key, self.members, self._group()["members"]
            ),
        )

    def test_reconcile_rejects_missing_receipt_chain_and_forged_member_state(self):
        current = self._group()["members"]
        grown_without_receipt = [dict(member) for member in current]
        grown_without_receipt[0] = self._member(1, self.monster_id, 0)
        with self.assertRaisesRegex(ValueError, "Conflicting existing group seed"):
            monster_maturation.reconcile_seed(
                self.store, self.group_key, self.members, grown_without_receipt
            )

        forged_hp = [dict(member) for member in current]
        forged_hp[0]["hp"] -= 1
        forged_id = [dict(member) for member in current]
        forged_id[0]["id"] = -99999
        short_roster = current[:-1]
        for invalid in (forged_hp, forged_id, short_roster):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    monster_maturation.reconcile_seed(
                        self.store, self.group_key, self.members, invalid
                    )

    def test_reconcile_rejects_broken_and_skipped_tier_receipts(self):
        current = self._group()["members"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_maturation_receipts(map_id,instance_id,monster_id,cycle,"
                "group_id,from_reference,to_reference,draw,policy) "
                "VALUES(%s,%s,%s,1,%s,39,1,0.1,%s)",
                (
                    self.map_id,
                    self.instance_id,
                    self.monster_id,
                    self.group_id,
                    Jsonb({"interval_ms": 60000}),
                ),
            )
        persisted = [dict(member) for member in current]
        persisted[0] = self._member(1, self.monster_id, 0)
        with self.assertRaisesRegex(
            ValueError, "Broken monster maturation receipt chain"
        ):
            monster_maturation.reconcile_seed(
                self.store, self.group_key, self.members, persisted
            )

        with self.store.connection() as db:
            db.execute(
                "DELETE FROM monster_maturation_receipts WHERE map_id=%s AND instance_id=%s "
                "AND monster_id=%s",
                (self.map_id, self.instance_id, self.monster_id),
            )
            db.execute(
                "INSERT INTO monster_maturation_receipts(map_id,instance_id,monster_id,cycle,"
                "group_id,from_reference,to_reference,draw,policy) "
                "VALUES(%s,%s,%s,1,%s,2,44,0.1,%s)",
                (
                    self.map_id,
                    self.instance_id,
                    self.monster_id,
                    self.group_id,
                    Jsonb({"interval_ms": 60000}),
                ),
            )
        persisted[0] = self._member(44, self.monster_id, 0)
        with self.assertRaisesRegex(
            ValueError, "Invalid monster maturation receipt transition"
        ):
            monster_maturation.reconcile_seed(
                self.store, self.group_key, self.members, persisted
            )


if __name__ == "__main__":
    unittest.main()
