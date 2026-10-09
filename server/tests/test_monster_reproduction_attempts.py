from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_reproduction, npc_actor_identity, monster_maturation
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.monster_wander import edge_index


class MonsterReproductionAttemptTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.map_id = 1134
        self.instance_id = 0
        self.group_id = 77001
        self.monster_id = -77001
        self.groups = PersistentGroups(self.store)
        self.parent = self._member(4, self.monster_id, 0, 0)
        self.members = [self.parent]
        self.key = self.groups.register(
            self.map_id, self.instance_id, self.group_id, self.members
        )
        self.ticket = self._seed_due(self.parent)
        self.indexed = edge_index([((0, 0, 0), (1, 0, 0))])

    def _member(self, reference, actor_id, x, y, *, instance_id=None):
        member = owned_instance(
            reference,
            REFERENCES[reference]["min_level"],
            actor_id,
            map_id=self.map_id,
            x=x,
            y=y,
            z=0,
            instance_id=0 if instance_id is None else instance_id,
        )
        return member

    def _seed_due(self, member):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_reproduction_timers"
                "(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                "VALUES(%s,%s,%s,%s,0,true,1)",
                (self.map_id, self.instance_id, member["id"], member["ref"]),
            )
        return dict(
            map_id=self.map_id,
            instance_id=self.instance_id,
            group_id=self.group_id,
            monster_id=member["id"],
            reference=member["ref"],
            cycle=1,
        )

    def _set_policy(
        self,
        *,
        birth=1.0,
        new_group=0.0,
        max_members=8,
        birth_stage_decay=0.5,
        max_zone_members=128,
        max_zone_groups=32
    ):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_reproduction'",
                (
                    Jsonb(
                        {
                            "interval_ms": 60000,
                            "birth_probability": birth,
                            "birth_stage_decay": birth_stage_decay,
                            "new_group_probability": new_group,
                            "max_members": max_members,
                            "max_zone_members": max_zone_members,
                            "max_zone_groups": max_zone_groups,
                        }
                    ),
                ),
            )

    def _group(self, group_id=None):
        group_id = self.group_id if group_id is None else group_id
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (self.map_id, self.instance_id, group_id),
            ).fetchone()

    def _receipt(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM monster_reproduction_receipts WHERE map_id=%s AND instance_id=%s "
                "AND monster_id=%s AND cycle=%s",
                (self.map_id, self.instance_id, self.monster_id, self.ticket["cycle"]),
            ).fetchone()

    def _outbox(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM monster_reproduction_outbox WHERE map_id=%s AND instance_id=%s "
                "AND monster_id=%s AND cycle=%s",
                (self.map_id, self.instance_id, self.monster_id, self.ticket["cycle"]),
            ).fetchall()

    def _attempt(self, **kwargs):
        return monster_reproduction.attempt(
            self.store,
            self.ticket,
            present=True,
            indexed=self.indexed,
            choose=lambda choices: choices[0],
            **kwargs,
        )

    def test_birth_appends_tier_zero_child_at_native_indexed_neighbor(self):
        self._set_policy(birth=1.0, new_group=0.0, max_members=8)
        result = self._attempt(draw=0.0, group_draw=0.99)
        child_id = result["child_id"]
        self.assertLess(child_id, 0)
        self.assertEqual(self.group_id, result["child_group_id"])
        group = self._group()
        self.assertEqual(2, len(group["members"]))
        child = next(member for member in group["members"] if member["id"] == child_id)
        self.assertEqual(6, child["ref"])
        self.assertEqual(REFERENCES[6]["min_level"], child["level"])
        self.assertEqual((1, 0, 0), (child["x"], child["y"], child["z"]))
        self.assertEqual(0, child["hp"] - child["max_hp"])
        with self.store.connection() as db:
            membership = db.execute(
                "SELECT group_id FROM combat_group_members WHERE map_id=%s AND instance_id=%s "
                "AND monster_id=%s",
                (self.map_id, self.instance_id, child_id),
            ).fetchone()
            timer = db.execute(
                "SELECT count(*) AS count FROM monster_reproduction_timers "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                (self.map_id, self.instance_id, child_id),
            ).fetchone()["count"]
        self.assertEqual(self.group_id, membership["group_id"])
        self.assertEqual(
            0, timer
        )  # The next active-zone observe seeds its first clock.
        self.assertEqual(1, self._group()["revision"])
        outbox = self._outbox()
        self.assertEqual(1, len(outbox))
        self.assertEqual(self.group_id, outbox[0]["group_id"])
        self.assertFalse(outbox[0]["new_group"])

    def test_full_eight_member_roster_creates_separate_group(self):
        members = [self._member(4, -77100 - index, index * 2, 0) for index in range(8)]
        self.groups.register(self.map_id, self.instance_id, 77002, members)
        self.group_id = 77002
        self.monster_id = members[0]["id"]
        self.parent = members[0]
        self.members = members
        self.ticket = self._seed_due(self.parent)
        self.indexed = edge_index([((0, 0, 0), (0, 1, 0))])
        self._set_policy(birth=1.0, new_group=0.0, max_members=8)
        result = self._attempt(draw=0.0, group_draw=0.99)
        child_group = result["child_group_id"]
        child_id = result["child_id"]
        self.assertNotEqual(self.group_id, child_group)
        self.assertGreaterEqual(child_group, npc_actor_identity.MINIMUM)
        self.assertLessEqual(child_group, npc_actor_identity.MAXIMUM)
        self.assertTrue(npc_actor_identity.lua_exact_identity(child_id))
        self.assertEqual(-child_group, child_id)
        self.assertEqual(8, len(self._group()["members"]))
        spawned = self._group(child_group)
        self.assertEqual("available", spawned["status"])
        self.assertEqual([child_id], [member["id"] for member in spawned["members"]])
        self.assertEqual(6, spawned["members"][0]["ref"])
        outbox = self._outbox()
        self.assertEqual(1, len(outbox))
        self.assertEqual(child_group, outbox[0]["group_id"])
        self.assertTrue(outbox[0]["new_group"])

    def test_zone_member_limit_rejects_birth_before_random_draws(self):
        other = self._member(4, -77901, 4, 0)
        self.groups.register(self.map_id, self.instance_id, 77902, [other])
        self._set_policy(birth=1.0, max_zone_members=2, max_zone_groups=32)
        with patch.object(
            monster_reproduction.secrets,
            "randbelow",
            side_effect=AssertionError("population cap must reject before RNG"),
        ):
            result = self._attempt(draw=None, group_draw=None)
        self.assertIsNone(result)
        self.assertIsNone(self._receipt())
        self.assertEqual(1, len(self._group()["members"]))

    def test_concurrent_different_parents_cannot_exceed_zone_group_limit(self):
        other = self._member(4, -77911, 4, 0)
        other_group_id = 77912
        self.groups.register(self.map_id, self.instance_id, other_group_id, [other])
        other_ticket = self._seed_due(other)
        other_ticket["group_id"] = other_group_id
        self.indexed = edge_index(
            [
                ((0, 0, 0), (1, 0, 0)),
                ((4, 0, 0), (5, 0, 0)),
            ]
        )
        self._set_policy(
            birth=1.0,
            new_group=1.0,
            max_members=1,
            max_zone_members=3,
            max_zone_groups=3,
        )
        barrier = Barrier(2)

        def reproduce(ticket):
            barrier.wait()
            return monster_reproduction.attempt(
                self.store,
                ticket,
                present=True,
                indexed=self.indexed,
                draw=0.0,
                group_draw=0.0,
                choose=lambda choices: choices[0],
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reproduce, (self.ticket, other_ticket)))
        self.assertEqual(1, sum(result is not None for result in results))
        self.assertEqual(
            1,
            sum(
                result is not None and result["child_id"] is not None
                for result in results
            ),
        )
        with self.store.connection() as db:
            groups = db.execute(
                "SELECT count(*) AS count FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s AND status!='defeated'",
                (self.map_id, self.instance_id),
            ).fetchone()["count"]
            members = db.execute(
                "SELECT count(*) AS count FROM combat_group_members "
                "WHERE map_id=%s AND instance_id=%s",
                (self.map_id, self.instance_id),
            ).fetchone()["count"]
            receipts = db.execute(
                "SELECT count(*) AS count FROM monster_reproduction_receipts "
                "WHERE map_id=%s AND instance_id=%s",
                (self.map_id, self.instance_id),
            ).fetchone()["count"]
        self.assertEqual(3, groups)
        self.assertEqual(3, members)
        self.assertEqual(1, receipts)

    def test_replay_returns_receipt_without_random_or_second_child(self):
        self._set_policy(birth=0.05)
        first = self._attempt(draw=0.039, group_draw=0.99)
        self.assertAlmostEqual(0.04, first["probability"])
        self._set_policy(birth=0.9, birth_stage_decay=1.0)
        group_before = self._group()
        with patch.object(
            monster_reproduction.secrets,
            "randbelow",
            side_effect=AssertionError("replay redrew"),
        ):
            replay = self._attempt(draw=None, group_draw=None)
        self.assertTrue(replay["duplicate"])
        self.assertEqual(first["child_id"], replay["child_id"])
        self.assertAlmostEqual(0.04, replay["probability"])
        self.assertAlmostEqual(0.05, replay["policy"]["birth_probability"])
        self.assertEqual(group_before["revision"], self._group()["revision"])
        self.assertEqual(2, len(self._group()["members"]))
        self.assertEqual(1, len(self._outbox()))

    def test_probability_boundary_is_strict_and_saved_for_failed_birth(self):
        self._set_policy(birth=0.05, birth_stage_decay=0.5)
        result = self._attempt(draw=0.04, group_draw=0.0)
        self.assertIsNone(result["child_id"])
        self.assertAlmostEqual(0.04, result["probability"])
        self.assertAlmostEqual(0.04, self._receipt()["probability"])
        self.assertEqual(1, len(self._group()["members"]))

    def test_register_seed_accepts_receipted_birth_movement_and_child_maturation(self):
        self._set_policy(birth=1.0)
        self._attempt(draw=0.0, group_draw=0.99)
        persisted = self._group()["members"]
        child = next(member for member in persisted if member["id"] != self.monster_id)
        self.assertEqual(6, child["ref"])
        self.assertEqual(
            self.key,
            self.groups.register_seed(
                self.map_id, self.instance_id, self.group_id, [self.parent]
            ),
        )

    def test_nonzero_instance_survives_append_maturation_recovery_and_separate_birth(
        self,
    ):
        instance_id = 17
        append_group_id = 77117
        parent = self._member(4, -77117, 0, 0, instance_id=instance_id)
        append_key = self.groups.register(
            self.map_id, instance_id, append_group_id, [parent]
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_reproduction_timers"
                "(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                "VALUES(%s,%s,%s,4,0,true,1)",
                (self.map_id, instance_id, parent["id"]),
            )
        append_ticket = {
            "map_id": self.map_id,
            "instance_id": instance_id,
            "group_id": append_group_id,
            "monster_id": parent["id"],
            "reference": 4,
            "cycle": 1,
        }
        self._set_policy(birth=1.0, new_group=0.0)
        indexed = edge_index([((0, 0, 0), (1, 0, 0))])
        result = monster_reproduction.attempt(
            self.store,
            append_ticket,
            present=True,
            indexed=indexed,
            draw=0.0,
            group_draw=0.99,
            choose=lambda choices: choices[0],
        )
        child = result["child"]
        self.assertEqual(instance_id, child["instance_id"])
        self.assertEqual(
            append_key,
            self.groups.register_seed(
                self.map_id, instance_id, append_group_id, [parent]
            ),
        )

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_maturation_timers"
                "(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                "VALUES(%s,%s,%s,6,0,true,1)",
                (self.map_id, instance_id, child["id"]),
            )
        grown = monster_maturation.attempt(
            self.store,
            {
                "map_id": self.map_id,
                "instance_id": instance_id,
                "group_id": append_group_id,
                "monster_id": child["id"],
                "reference": 6,
                "cycle": 1,
            },
            present=True,
            draw=0.0,
            choose=lambda choices: choices[0],
        )
        self.assertEqual(4, grown["to_reference"])
        recovered_group = next(
            group
            for group in self.groups.snapshot(self.map_id, instance_id)
            if group["key"] == append_key
        )
        recovered = next(
            member
            for member in recovered_group["members"]
            if member["id"] == child["id"]
        )
        self.assertEqual(instance_id, recovered["instance_id"])
        self.assertEqual(
            append_key,
            self.groups.register_seed(
                self.map_id, instance_id, append_group_id, [parent]
            ),
        )
        recovered_group = next(
            group
            for group in self.groups.snapshot(self.map_id, instance_id)
            if group["key"] == append_key
        )
        self.assertEqual(
            instance_id,
            next(
                member
                for member in recovered_group["members"]
                if member["id"] == child["id"]
            )["instance_id"],
        )

        separate_group_id = 77217
        full = [
            self._member(4, -77200 - index, 20 + index * 2, 0, instance_id=instance_id)
            for index in range(8)
        ]
        self.groups.register(self.map_id, instance_id, separate_group_id, full)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_reproduction_timers"
                "(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                "VALUES(%s,%s,%s,4,0,true,1)",
                (self.map_id, instance_id, full[0]["id"]),
            )
        separate = monster_reproduction.attempt(
            self.store,
            {
                "map_id": self.map_id,
                "instance_id": instance_id,
                "group_id": separate_group_id,
                "monster_id": full[0]["id"],
                "reference": 4,
                "cycle": 1,
            },
            present=True,
            indexed=edge_index([((20, 0, 0), (20, 1, 0))]),
            draw=0.0,
            group_draw=0.99,
            choose=lambda choices: choices[0],
        )
        self.assertTrue(separate["child_group_id"] != separate_group_id)
        self.assertEqual(instance_id, separate["child"]["instance_id"])
        separate_group = self.groups.snapshot(self.map_id, instance_id)
        newborn = next(
            group
            for group in separate_group
            if group["key"][2] == separate["child_group_id"]
        )
        self.assertEqual(instance_id, newborn["members"][0]["instance_id"])

    def test_owned_instance_validates_instance_id_as_strict_nonnegative_i64(self):
        for invalid in (True, -1, 1 << 63):
            with self.subTest(instance_id=invalid), self.assertRaises(ValueError):
                owned_instance(
                    4,
                    REFERENCES[4]["min_level"],
                    -77199,
                    map_id=self.map_id,
                    x=0,
                    y=0,
                    z=0,
                    instance_id=invalid,
                )
        member = owned_instance(
            4,
            REFERENCES[4]["min_level"],
            -77199,
            map_id=self.map_id,
            x=0,
            y=0,
            z=0,
            instance_id=17,
        )
        self.assertEqual(17, member["instance_id"])

    def test_register_seed_rejects_unreceipted_birth_wrong_prefix_family_and_forged_snapshot(
        self,
    ):
        unrelated_parent = self._member(4, -77200, 49, 0)
        baby = self._member(6, -77201, 50, 0)
        self.groups.register(
            self.map_id, self.instance_id, 77003, [unrelated_parent, baby]
        )
        with self.assertRaisesRegex(ValueError, "unreceipted offspring"):
            self.groups.register_seed(
                self.map_id, self.instance_id, 77003, [unrelated_parent]
            )

        self._set_policy(birth=1.0)
        self._attempt(draw=0.0, group_draw=0.99)
        persisted = self._group()["members"]
        child = next(member for member in persisted if member["id"] != self.monster_id)
        with self.assertRaisesRegex(
            ValueError, "Conflicting existing group seed identity"
        ):
            self.groups.register_seed(
                self.map_id, self.instance_id, self.group_id, [child, self.parent]
            )

        with self.store.connection() as db:
            db.execute(
                "UPDATE monster_reproduction_receipts SET child=jsonb_set(child,'{ref}','123'::jsonb) "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s AND cycle=1",
                (self.map_id, self.instance_id, self.monster_id),
            )
        with self.assertRaisesRegex(ValueError, "Invalid offspring birth reference"):
            self.groups.register_seed(
                self.map_id, self.instance_id, self.group_id, [self.parent]
            )

    def test_register_seed_rejects_forged_birth_health_snapshot(self):
        self._set_policy(birth=1.0)
        self._attempt(draw=0.0, group_draw=0.99)
        with self.store.connection() as db:
            db.execute(
                "UPDATE monster_reproduction_receipts SET child=jsonb_set(child,'{hp}','0'::jsonb) "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s AND cycle=1",
                (self.map_id, self.instance_id, self.monster_id),
            )
        with self.assertRaisesRegex(ValueError, "Invalid offspring birth snapshot"):
            self.groups.register_seed(
                self.map_id, self.instance_id, self.group_id, [self.parent]
            )

    def test_failed_birth_chance_records_cycle_without_child_and_resets_clock(self):
        self._set_policy(birth=0.05)
        with patch.object(
            monster_reproduction,
            "allocate_identity",
            side_effect=AssertionError("allocated without birth"),
        ):
            result = self._attempt(draw=0.9, group_draw=0.0)
        self.assertIsNone(result["child_id"])
        self.assertIsNone(result["child_group_id"])
        self.assertIsNotNone(self._receipt())
        self.assertEqual([], self._outbox())
        with self.store.connection() as db:
            timer = db.execute(
                "SELECT remaining_ms,last_active_ms,due,cycle FROM monster_reproduction_timers "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                (self.map_id, self.instance_id, self.monster_id),
            ).fetchone()
        self.assertEqual(
            (60000, None, False, 1),
            (
                timer["remaining_ms"],
                timer["last_active_ms"],
                timer["due"],
                timer["cycle"],
            ),
        )

    def test_absent_fighting_harvesting_stale_baby_and_blocked_cases_do_not_draw(self):
        with patch.object(
            self.store, "connection", side_effect=AssertionError("absent DB access")
        ):
            self.assertIsNone(
                monster_reproduction.attempt(
                    self.store,
                    self.ticket,
                    present=False,
                    indexed=self.indexed,
                )
            )

        def no_choice(_choices):
            self.fail("Ineligible reproduction selected a cell/candidate")

        with patch.object(
            monster_reproduction.secrets,
            "randbelow",
            side_effect=AssertionError("ineligible reproduction drew"),
        ):
            self.assertIsNone(
                monster_reproduction.attempt(
                    self.store,
                    self.ticket,
                    present=True,
                    indexed=self.indexed,
                    excluded_ids={self.monster_id},
                    choose=no_choice,
                )
            )
            with self.store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
            lease, _ = self.groups.claim(self.key, "reproduction-fight", fight_id)
            self.assertIsNone(
                monster_reproduction.attempt(
                    self.store,
                    self.ticket,
                    present=True,
                    indexed=self.indexed,
                    choose=no_choice,
                )
            )
            self.assertTrue(self.groups.finish(lease, defeated=False))

            with self.store.connection() as db:
                db.execute(
                    "UPDATE monster_reproduction_timers SET due=false WHERE map_id=%s "
                    "AND instance_id=%s AND monster_id=%s",
                    (self.map_id, self.instance_id, self.monster_id),
                )
            self.assertIsNone(
                monster_reproduction.attempt(
                    self.store,
                    self.ticket,
                    present=True,
                    indexed=self.indexed,
                    choose=no_choice,
                )
            )

            # A valid but rank-zero offspring is never itself a parent.
            baby = self._member(6, self.monster_id, 0, 0)
            with self.store.connection() as db:
                db.execute(
                    "UPDATE combat_groups SET members=%s WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    (Jsonb([baby]), *self.key),
                )
                db.execute(
                    "UPDATE monster_reproduction_timers SET reference=6,due=true "
                    "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                    (self.map_id, self.instance_id, self.monster_id),
                )
            baby_ticket = {**self.ticket, "reference": 6}
            self.assertIsNone(
                monster_reproduction.attempt(
                    self.store,
                    baby_ticket,
                    present=True,
                    indexed=self.indexed,
                    choose=no_choice,
                )
            )

        # Every adjacent surface is occupied, so no chance draw is consumed.
        self.assertIsNone(
            monster_reproduction.attempt(
                self.store,
                self.ticket,
                present=True,
                indexed=self.indexed,
                players=[
                    dict(map_id=self.map_id, instance_id=self.instance_id, x=1, y=0)
                ],
                draw=None,
                choose=no_choice,
            )
        )

    def test_outbox_failure_rolls_back_group_membership_receipt_timer_and_roster(self):
        self._set_policy(birth=1.0)
        before = self._group()
        with self.store.connection() as db:
            before_timer = dict(
                db.execute(
                    "SELECT * FROM monster_reproduction_timers WHERE map_id=%s AND instance_id=%s "
                    "AND monster_id=%s",
                    (self.map_id, self.instance_id, self.monster_id),
                ).fetchone()
            )
            db.execute(
                "CREATE FUNCTION reject_reproduction_outbox() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'reproduction outbox rejected'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_reproduction_outbox BEFORE INSERT ON monster_reproduction_outbox "
                "FOR EACH ROW EXECUTE FUNCTION reject_reproduction_outbox()"
            )
        with self.assertRaisesRegex(Exception, "reproduction outbox rejected"):
            self._attempt(draw=0.0, group_draw=0.99)
        after = self._group()
        self.assertEqual(before["members"], after["members"])
        self.assertEqual(before["revision"], after["revision"])
        with self.store.connection() as db:
            timer = dict(
                db.execute(
                    "SELECT * FROM monster_reproduction_timers WHERE map_id=%s AND instance_id=%s "
                    "AND monster_id=%s",
                    (self.map_id, self.instance_id, self.monster_id),
                ).fetchone()
            )
            member_count = db.execute(
                "SELECT count(*) AS count FROM combat_group_members WHERE map_id=%s "
                "AND instance_id=%s",
                (self.map_id, self.instance_id),
            ).fetchone()["count"]
        self.assertEqual(before_timer, timer)
        self.assertEqual(1, member_count)
        self.assertIsNone(self._receipt())
        self.assertEqual([], self._outbox())

    def test_concurrent_same_cycle_creates_one_birth_and_one_receipt(self):
        self._set_policy(birth=1.0, new_group=0.0)
        barrier = Barrier(2)
        lock = Lock()
        rng_calls = []
        allocator_calls = []
        original_allocate = monster_reproduction.allocate_identity

        def draw(_upper):
            with lock:
                rng_calls.append(1)
            return 0

        def allocate(db):
            with lock:
                allocator_calls.append(1)
            return original_allocate(db)

        with patch.object(
            monster_reproduction.secrets, "randbelow", side_effect=draw
        ), patch.object(
            monster_reproduction, "allocate_identity", side_effect=allocate
        ):

            def one_attempt():
                barrier.wait(timeout=5)
                return monster_reproduction.attempt(
                    self.store,
                    self.ticket,
                    present=True,
                    indexed=self.indexed,
                    choose=lambda choices: choices[0],
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: one_attempt(), range(2)))
        self.assertEqual(2, len(rng_calls))  # One birth roll and one group-choice roll.
        self.assertEqual(1, len(allocator_calls))
        self.assertEqual(1, sum(bool(result["duplicate"]) for result in results))
        self.assertEqual(2, len(self._group()["members"]))
        self.assertIsNotNone(self._receipt())
        self.assertEqual(1, len(self._outbox()))


if __name__ == "__main__":
    unittest.main()
