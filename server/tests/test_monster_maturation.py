from contextlib import contextmanager
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_maturation
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class MonsterMaturationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        # Keep transition tests fast and deterministic; migration 035 has its
        # own assertion for the production default of 15 active minutes.
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{interval_ms}','60000'::jsonb) "
                "WHERE name='monster_maturation'"
            )
        self.groups = PersistentGroups(self.store)
        self.map_id = 1134
        self.instance_id = 0
        self.group_id = 87001
        # 2 and 39 are tied alternatives at the first growable tier for family 68.
        self.assertIn(2, monster_maturation.GROWABLE)
        self.assertIn(39, monster_maturation.GROWABLE)
        members = [self._member(2, -87001, 0), self._member(39, -87002, 1)]
        self.key = self.groups.register(
            self.map_id, self.instance_id, self.group_id, members
        )

    def _member(self, reference, actor_id, x):
        level = REFERENCES[reference]["min_level"]
        return owned_instance(
            reference, level, actor_id, map_id=self.map_id, x=x, y=0, z=0
        )

    def _timer(self, monster_id):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM monster_maturation_timers "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                (self.map_id, self.instance_id, monster_id),
            ).fetchone()

    def _capture_observation_queries(self, map_id, instance_id, *, present, now_ms):
        statements = []
        original_connection = self.store.connection

        class RecordingConnection:
            def __init__(self, db):
                self.db = db

            def execute(self, sql, params=None):
                statements.append(sql)
                return self.db.execute(sql, params)

        @contextmanager
        def recording_connection():
            with original_connection() as db:
                yield RecordingConnection(db)

        with patch.object(self.store, "connection", recording_connection):
            due = monster_maturation.observe(
                self.store,
                map_id,
                instance_id,
                present=present,
                generation="query-count-run",
                now_ms=now_ms,
            )
        return statements, due

    def test_observe_uses_fixed_five_queries_for_hundred_growable_members(self):
        map_id = 1135
        members = [
            {**self._member(2, -90000 - index, index), "map_id": map_id}
            for index in range(100)
        ]
        self.groups.register(map_id, self.instance_id, 87003, members)
        statements, due = self._capture_observation_queries(
            map_id,
            self.instance_id,
            present=True,
            now_ms=100,
        )
        self.assertEqual([], due)
        self.assertEqual(5, len(statements))
        self.assertEqual(
            1, sum("SELECT value FROM settings" in sql for sql in statements)
        )
        self.assertEqual(
            1,
            sum(
                "SELECT group_id,members,status FROM combat_groups" in sql
                for sql in statements
            ),
        )
        self.assertEqual(
            1, sum("INSERT INTO monster_maturation_timers" in sql for sql in statements)
        )
        self.assertEqual(
            1,
            sum("SELECT * FROM monster_maturation_timers" in sql for sql in statements),
        )
        self.assertEqual(
            1, sum("UPDATE monster_maturation_timers" in sql for sql in statements)
        )
        with self.store.connection() as db:
            count = db.execute(
                "SELECT count(*) AS count FROM monster_maturation_timers "
                "WHERE map_id=%s AND instance_id=%s",
                (map_id, self.instance_id),
            ).fetchone()["count"]
        self.assertEqual(100, count)

    def test_terminal_member_adds_one_delete_to_batched_observation(self):
        map_id = 1136
        members = [
            {**self._member(2, -91001, 0), "map_id": map_id},
            {**self._member(39, -91002, 1), "map_id": map_id},
            {**self._member(44, -91003, 2), "map_id": map_id},
        ]
        self.groups.register(map_id, self.instance_id, 87004, members)
        statements, _ = self._capture_observation_queries(
            map_id,
            self.instance_id,
            present=True,
            now_ms=100,
        )
        self.assertEqual(6, len(statements))
        self.assertEqual(
            1, sum("DELETE FROM monster_maturation_timers" in sql for sql in statements)
        )

    def test_absent_observation_uses_only_guarded_timer_update(self):
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="query-count-run",
            now_ms=100,
        )
        statements, due = self._capture_observation_queries(
            self.map_id,
            self.instance_id,
            present=False,
            now_ms=500000,
        )
        self.assertEqual([], due)
        self.assertEqual(1, len(statements))
        self.assertIn("UPDATE monster_maturation_timers", statements[0])
        self.assertIn("last_active_ms IS NOT NULL", statements[0])
        self.assertNotIn("SELECT", statements[0])

    def test_tied_catalog_alternatives_get_independent_valid_level_clocks(self):
        self.assertEqual(
            {
                "interval_ms": 60000,
                "base_probability": 0.25,
                "stage_decay": 0.5,
                "boss_probability": 0.00001,
            },
            monster_maturation.policy(self.store),
        )
        due = monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=100,
        )
        self.assertEqual([], due)
        for monster_id, reference in ((-87001, 2), (-87002, 39)):
            timer = self._timer(monster_id)
            self.assertEqual(reference, timer["reference"])
            self.assertEqual(60000, timer["remaining_ms"])
            self.assertEqual("run-a", timer["observer_generation"])

    def test_miaumiau_stages_require_full_active_interval_after_each_transition(self):
        # Family563's seeded path is 2616/2617 -> 2598 -> 1816. Use certainty
        # only to isolate minimum timing from probabilistic outcomes.
        map_id, instance_id, group_id, monster_id = 527, 0, 87563, -87563
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_maturation'",
                (
                    Jsonb(
                        {
                            "interval_ms": 900000,
                            "base_probability": 1.0,
                            "stage_decay": 1.0,
                            "boss_probability": 0.0,
                        }
                    ),
                ),
            )
        kitten = owned_instance(
            2616,
            REFERENCES[2616]["min_level"],
            monster_id,
            map_id=map_id,
            instance_id=instance_id,
            x=27,
            y=4,
            z=0,
        )
        key = self.groups.register(map_id, instance_id, group_id, [kitten])

        def timer():
            with self.store.connection() as db:
                return db.execute(
                    "SELECT * FROM monster_maturation_timers WHERE map_id=%s "
                    "AND instance_id=%s AND monster_id=%s",
                    (map_id, instance_id, monster_id),
                ).fetchone()

        self.assertEqual(
            [],
            monster_maturation.observe(
                self.store,
                map_id,
                instance_id,
                present=True,
                generation="miau-run-a",
                now_ms=0,
            ),
        )
        self.assertEqual(
            [],
            monster_maturation.observe(
                self.store,
                map_id,
                instance_id,
                present=True,
                generation="miau-run-a",
                now_ms=899999,
            ),
        )
        self.assertEqual(1, timer()["remaining_ms"])
        due = monster_maturation.observe(
            self.store,
            map_id,
            instance_id,
            present=True,
            generation="miau-run-a",
            now_ms=900000,
        )
        ticket = next(row for row in due if row["monster_id"] == monster_id)
        grown = monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.5,
            choose=lambda candidates: candidates[0],
        )
        self.assertEqual((2616, 2598), (grown["from_reference"], grown["to_reference"]))
        timer_row = timer()
        self.assertEqual(
            (2598, 900000, False, 1),
            (
                timer_row["reference"],
                timer_row["remaining_ms"],
                timer_row["due"],
                timer_row["cycle"],
            ),
        )

        # Consume five active minutes, pause through absence, then simulate a
        # fresh observer generation. Neither pause nor restart charges time.
        self.assertEqual(
            [],
            monster_maturation.observe(
                self.store,
                map_id,
                instance_id,
                present=True,
                generation="miau-run-a",
                now_ms=900000,
            ),
        )
        self.assertEqual(
            [],
            monster_maturation.observe(
                self.store,
                map_id,
                instance_id,
                present=True,
                generation="miau-run-a",
                now_ms=1200000,
            ),
        )
        self.assertEqual(600000, timer()["remaining_ms"])
        self.assertEqual(
            [],
            monster_maturation.observe(
                self.store,
                map_id,
                instance_id,
                present=False,
                generation="miau-run-a",
                now_ms=1250000,
            ),
        )
        reopened = self.reopen()
        self.assertEqual(
            [],
            monster_maturation.observe(
                reopened,
                map_id,
                instance_id,
                present=True,
                generation="miau-run-b",
                now_ms=10000000,
            ),
        )
        self.assertEqual(600000, timer()["remaining_ms"])
        self.assertEqual(
            [],
            monster_maturation.observe(
                reopened,
                map_id,
                instance_id,
                present=True,
                generation="miau-run-b",
                now_ms=10599999,
            ),
        )
        due = monster_maturation.observe(
            reopened,
            map_id,
            instance_id,
            present=True,
            generation="miau-run-b",
            now_ms=10600000,
        )
        ticket = next(row for row in due if row["monster_id"] == monster_id)
        grown = monster_maturation.attempt(
            reopened,
            ticket,
            present=True,
            draw=0.5,
            choose=lambda candidates: candidates[0],
        )
        self.assertEqual((2598, 1816), (grown["from_reference"], grown["to_reference"]))
        timer_row = timer()
        self.assertEqual(
            (1816, 900000, False, 2),
            (
                timer_row["reference"],
                timer_row["remaining_ms"],
                timer_row["due"],
                timer_row["cycle"],
            ),
        )
        with self.store.connection() as db:
            transitions = db.execute(
                "SELECT from_reference,to_reference FROM monster_maturation_receipts "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s ORDER BY cycle",
                (map_id, instance_id, monster_id),
            ).fetchall()
        self.assertEqual(
            [(2616, 2598), (2598, 1816)], [tuple(row.values()) for row in transitions]
        )
        self.assertEqual(key, self.groups.snapshot(map_id, instance_id)[0]["key"])

    def test_clock_policy_is_frozen_per_monster_and_new_rows_use_updates(self):
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=100,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_maturation'",
                (
                    Jsonb(
                        {
                            "interval_ms": 120000,
                            "base_probability": 0.25,
                            "stage_decay": 0.5,
                            "boss_probability": 0.00001,
                        }
                    ),
                ),
            )
        extra = self._member(2, -87003, 3)
        self.groups.register(self.map_id, self.instance_id, 87002, [extra])
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=200,
        )
        self.assertEqual(59900, self._timer(-87001)["remaining_ms"])
        self.assertEqual(120000, self._timer(-87003)["remaining_ms"])

    def test_absent_zone_pauses_without_loading_policy_or_combat_groups(self):
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=1000,
        )
        statements = []
        original_connection = self.store.connection

        class RecordingConnection:
            def __init__(self, db):
                self.db = db

            def execute(self, sql, params=None):
                statements.append(sql)
                return self.db.execute(sql, params)

        @contextmanager
        def recording_connection():
            with original_connection() as db:
                yield RecordingConnection(db)

        with patch.object(self.store, "connection", recording_connection):
            self.assertEqual(
                [],
                monster_maturation.observe(
                    self.store,
                    self.map_id,
                    self.instance_id,
                    present=False,
                    generation="run-a",
                    now_ms=500000,
                ),
            )
        self.assertEqual(1, len(statements))
        self.assertIn("UPDATE monster_maturation_timers", statements[0])
        self.assertNotIn("combat_groups", statements[0])
        self.assertNotIn("settings", statements[0])
        self.assertIsNone(self._timer(-87001)["last_active_ms"])

        # Time spent away is not charged when this zone is observed again.
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=900000,
        )
        self.assertEqual(60000, self._timer(-87001)["remaining_ms"])

    def test_combat_and_harvest_exclusions_freeze_elapsed_time(self):
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=1000,
        )
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(self.key, "fight-generation", fight_id)
        self.assertEqual(
            [],
            monster_maturation.observe(
                self.store,
                self.map_id,
                self.instance_id,
                present=True,
                generation="run-a",
                now_ms=21000,
            ),
        )
        self.assertIsNone(self._timer(-87001)["last_active_ms"])
        self.assertTrue(self.groups.finish(lease, defeated=False))
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=41000,
        )
        self.assertEqual(60000, self._timer(-87001)["remaining_ms"])
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=51000,
            excluded_ids={-87001},
        )
        self.assertIsNone(self._timer(-87001)["last_active_ms"])
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=61000,
        )
        self.assertEqual(60000, self._timer(-87001)["remaining_ms"])
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=71000,
        )
        self.assertEqual(50000, self._timer(-87001)["remaining_ms"])

    def test_new_observer_generation_does_not_catch_up_offline_time(self):
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="old-run",
            now_ms=1000,
        )
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="new-run",
            now_ms=50000,
        )
        self.assertEqual(60000, self._timer(-87001)["remaining_ms"])
        self.assertEqual("new-run", self._timer(-87001)["observer_generation"])
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="new-run",
            now_ms=60000,
        )
        self.assertEqual(50000, self._timer(-87001)["remaining_ms"])

    def test_due_cycle_is_claimed_once_and_reopens_durably(self):
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=0,
        )
        due = monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=60000,
        )
        self.assertEqual(2, len(due))
        self.assertEqual({1}, {row["cycle"] for row in due})
        self.assertEqual(
            [],
            monster_maturation.observe(
                self.store,
                self.map_id,
                self.instance_id,
                present=True,
                generation="run-a",
                now_ms=70000,
            ),
        )
        reopened = self.reopen()
        self.assertEqual(
            [],
            monster_maturation.observe(
                reopened,
                self.map_id,
                self.instance_id,
                present=True,
                generation="run-b",
                now_ms=80000,
            ),
        )
        for monster_id in (-87001, -87002):
            timer = self._timer(monster_id)
            self.assertTrue(timer["due"])
            self.assertEqual(1, timer["cycle"])
            self.assertEqual(0, timer["remaining_ms"])

    def test_reference_change_resets_clock_but_keeps_cycle_number(self):
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=100,
        )
        # 39 is another verified, non-terminal catalog candidate in a tied tier.
        changed = self._member(39, -87001, 0)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET members=%s "
                "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (
                    Jsonb([changed, self._member(39, -87002, 1)]),
                    self.map_id,
                    self.instance_id,
                    self.group_id,
                ),
            )
            db.execute(
                "UPDATE monster_maturation_timers SET cycle=3,due=true "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                (self.map_id, self.instance_id, -87001),
            )
        self.assertEqual(
            [],
            monster_maturation.observe(
                self.store,
                self.map_id,
                self.instance_id,
                present=True,
                generation="run-a",
                now_ms=30000,
            ),
        )
        timer = self._timer(-87001)
        self.assertEqual(39, timer["reference"])
        self.assertEqual(60000, timer["remaining_ms"])
        self.assertEqual(3, timer["cycle"])
        self.assertFalse(timer["due"])
        self.assertIsNone(timer["last_active_ms"])

    def test_terminal_and_unrecognized_references_do_not_get_clocks(self):
        # Seed valid native members first; mutate only persisted catalog refs to
        # exercise fail-closed behavior for stale and unrecognized durable rows.
        members = [
            self._member(2, -87005, 0),
            self._member(2, -87003, 3),
            self._member(2, -87004, 4),
        ]
        self.groups.register(self.map_id, self.instance_id, 87002, members)
        changed = [dict(member) for member in members]
        changed[1]["ref"] = 44  # Verified terminal tier.
        changed[2]["ref"] = 999999  # Absent from the verified monster catalog.
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET members=%s "
                "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (Jsonb(changed), self.map_id, self.instance_id, 87002),
            )
            db.execute(
                "INSERT INTO monster_maturation_timers"
                "(map_id,instance_id,monster_id,reference,remaining_ms) "
                "VALUES(%s,%s,%s,%s,60000),(%s,%s,%s,%s,60000)",
                (
                    self.map_id,
                    self.instance_id,
                    -87003,
                    44,
                    self.map_id,
                    self.instance_id,
                    -87004,
                    999999,
                ),
            )
        monster_maturation.observe(
            self.store,
            self.map_id,
            self.instance_id,
            present=True,
            generation="run-a",
            now_ms=100,
        )
        self.assertIsNotNone(self._timer(-87005))
        self.assertIsNone(self._timer(-87003))
        self.assertIsNone(self._timer(-87004))

    def test_next_tier_uses_single_boss_draw_then_ordinary_weight(self):
        configuration = {
            "interval_ms": 60000,
            "base_probability": 0.25,
            "stage_decay": 0.5,
            "boss_probability": 0.00001,
        }
        chosen_sets = []

        def choose(candidates):
            chosen_sets.append([row["reference"] for row in candidates])
            return candidates[0]["reference"]

        # Family 68 at rank four has one boss (44) and one arch (4086).
        self.assertEqual(
            44,
            monster_maturation.choose_next(
                4085, configuration, draw=0.000009, choose=choose
            ),
        )
        self.assertEqual([44], chosen_sets[-1])
        self.assertEqual(
            4086,
            monster_maturation.choose_next(
                4085, configuration, draw=0.00001, choose=choose
            ),
        )
        self.assertEqual([4086], chosen_sets[-1])
        self.assertIsNone(
            monster_maturation.choose_next(
                4085, configuration, draw=0.015635, choose=choose
            )
        )
        # The final tier does not start an additional clock/transition.
        self.assertIsNone(
            monster_maturation.choose_next(44, configuration, draw=0.0, choose=choose)
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_maturation'",
                (Jsonb({**configuration, "base_probability": 1.0}),),
            )
        with self.assertRaises(ValueError):
            monster_maturation.policy(self.store)
