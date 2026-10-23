"""Actual Ranch cycle clocks, pending fBU rewards and native retrieval routes."""
import struct
import unittest
from unittest.mock import patch

import test_haven_ranch_occupancy_postgres as ranch_fixture


class RanchCycleRewardsPostgresTests(unittest.TestCase):
    def setUp(self):
        # Reuse the real isolated Ranch owner/session/scene fixture and its
        # native constructors instead of creating a parallel test world.
        self.ranch_case = ranch_fixture.RanchOccupancyPostgresTests()
        self.ranch_case.setUp()
        self.addCleanup(self.ranch_case.doCleanups)
        self.store = self.ranch_case.store
        self.account = self.ranch_case.account
        self.generation = self.ranch_case.generation
        self.character = self.ranch_case.character
        self.ranch = self.ranch_case.ranch
        self.now = self.ranch_case.now
        self.now[0] = 1_700_000_000.0

    def test_overbudget_earned_cycles_drain_while_packed_and_on_release(self):
        import struct
        from unittest.mock import patch

        from wakfu_server import (
            haven_ranch_building_knowledge,
            haven_ranch_buildings,
            haven_ranch_herd,
            ranch_cycle_rewards,
        )
        from wakfu_server.inventory_items import grant

        bag_uid = self.character["inventory_containers"][0]["uid"]
        fence = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=33111,
            quantity=1,
            container=bag_uid,
            slot=8,
            allowed_references={33111},
        )
        self.assertTrue(
            haven_ranch_building_knowledge.learn(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">iq", 15153, fence["uid"]),
            )["applied"]
        )
        for x in range(4, 9):
            for y in range(4, 9):
                if x in (4, 8) or y in (4, 8):
                    self.assertTrue(
                        haven_ranch_buildings.operate(
                            self.store,
                            self.account,
                            self.generation,
                            self.ranch.inside,
                            12671,
                            struct.pack(">iBiii", 6, 1, 85, x, y),
                            session=self.ranch,
                        )["changed"]
                    )

        source = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=33032,
            quantity=2,
            container=bag_uid,
            slot=9,
            allowed_references={33032},
        )
        creatures = []
        for seed in (
            "00000000000000000000000000000001",
            "00000000000000000000000000000002",
        ):
            with patch.object(haven_ranch_herd.secrets, "token_hex", return_value=seed):
                result = haven_ranch_herd.use(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    struct.pack(">iq", 15107, source["uid"]),
                )
            self.assertEqual(result["creature"]["definition"], 8)
            creatures.append(result["creature"]["uid"])

        day_seconds = ranch_cycle_rewards.catalog()[0][8]["cycle_seconds"]

        def deploy(uid, x):
            from wakfu_server import combat_terrain

            return haven_ranch_herd.deploy(
                self.store,
                self.account,
                self.generation,
                self.ranch.inside,
                struct.pack(">qii", uid, x, 6),
                session=self.ranch,
                geometry=combat_terrain.map_geometry(1440),
            )

        def cycle_number(uid):
            with self.store.connection() as db:
                return db.execute(
                    "SELECT cycle_number FROM account_ranch_cycle_progress WHERE monster_uid=%s",
                    (uid,),
                ).fetchone()["cycle_number"]

        def settle():
            with self.store.connection() as db:
                return ranch_cycle_rewards.settle_account(
                    db,
                    self.store,
                    self.account,
                    now_ms=int(self.store.now().timestamp() * 1000),
                )

        # A five-day lapse exceeds the per-settlement budget. Repacking stores
        # the two completed cycles that remain; packed wall time adds nothing,
        # but the already-earned remainder must still drain.
        first_uid, second_uid = creatures
        first_deployment_ms = int(self.store.now().timestamp() * 1000)
        deploy(first_uid, 6)
        self.now[0] += 5 * day_seconds
        repacked = haven_ranch_herd.repack(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            struct.pack(">q", first_uid),
            session=self.ranch,
        )
        self.assertTrue(repacked["applied"])
        self.assertEqual(cycle_number(first_uid), 3)
        self.now[0] += 10 * day_seconds
        packed_carry = settle()
        self.assertTrue(packed_carry)
        self.assertTrue(all(row["monster_uid"] == first_uid for row in packed_carry))
        self.assertEqual(cycle_number(first_uid), 5)
        deploy(first_uid, 6)
        self.assertEqual(settle(), [])
        self.assertEqual(cycle_number(first_uid), 5)
        # Pause the first animal again before advancing the second one. This
        # prevents it from legitimately earning another batch during the
        # second animal's five-day run.
        repacked_again = haven_ranch_herd.repack(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            struct.pack(">q", first_uid),
            session=self.ranch,
        )
        self.assertTrue(repacked_again["applied"])

        # A second five-day lapse is settled by native release before the
        # tombstone. The earned remainder is preserved and drained with no new
        # time; released ownership never accrues later cycles.
        second_deployment_ms = int(self.store.now().timestamp() * 1000)
        deploy(second_uid, 7)
        self.now[0] += 5 * day_seconds
        released = haven_ranch_herd.release(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            struct.pack(">q", second_uid),
            session=self.ranch,
        )
        self.assertTrue(released["applied"])
        released_carry = settle()
        self.assertTrue(released_carry)
        self.assertTrue(all(row["monster_uid"] == second_uid for row in released_carry))
        self.assertEqual(cycle_number(second_uid), 5)
        self.now[0] += day_seconds
        self.assertEqual(settle(), [])
        self.assertEqual(cycle_number(second_uid), 5)
        with self.store.connection() as db:
            for uid in creatures:
                rows = list(
                    db.execute(
                        "SELECT cycle_number,drop_date_ms FROM account_ranch_reward_batches "
                        "WHERE monster_uid=%s ORDER BY cycle_number",
                        (uid,),
                    )
                )
                self.assertEqual([row["cycle_number"] for row in rows], [1, 2, 3, 4, 5])
                deployment_ms = (
                    first_deployment_ms if uid == first_uid else second_deployment_ms
                )
                self.assertEqual(
                    [row["drop_date_ms"] for row in rows],
                    [
                        deployment_ms + day_seconds * 1000 * cycle
                        for cycle in range(1, 6)
                    ],
                )

    def test_active_time_is_queued_while_frozen_earned_cycles_drain(self):
        """Keep newly elapsed active time behind an older earned-cycle backlog."""
        from wakfu_server import (
            combat_terrain,
            haven_ranch_building_knowledge,
            haven_ranch_buildings,
            haven_ranch_herd,
            ranch_cycle_rewards,
        )
        from wakfu_server.inventory_items import grant

        bag_uid = self.character["inventory_containers"][0]["uid"]
        fence = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=33111,
            quantity=1,
            container=bag_uid,
            slot=8,
            allowed_references={33111},
        )
        self.assertTrue(
            haven_ranch_building_knowledge.learn(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">iq", 15153, fence["uid"]),
            )["applied"]
        )
        for x in range(4, 9):
            for y in range(4, 9):
                if x in (4, 8) or y in (4, 8):
                    self.assertTrue(
                        haven_ranch_buildings.operate(
                            self.store,
                            self.account,
                            self.generation,
                            self.ranch.inside,
                            12671,
                            struct.pack(">iBiii", 6, 1, 85, x, y),
                            session=self.ranch,
                        )["changed"]
                    )
        source = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=33032,
            quantity=1,
            container=bag_uid,
            slot=9,
            allowed_references={33032},
        )
        from wakfu_server import haven_ranch_herd

        with patch.object(
            haven_ranch_herd.secrets,
            "token_hex",
            return_value="00000000000000000000000000000001",
        ):
            acquired = haven_ranch_herd.use(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">iq", 15107, source["uid"]),
            )
        uid = acquired["creature"]["uid"]
        self.assertEqual(acquired["creature"]["definition"], 8)
        day_ms = ranch_cycle_rewards.catalog()[0][8]["cycle_seconds"] * 1000
        start_ms = int(self.store.now().timestamp() * 1000)
        geometry = combat_terrain.map_geometry(1440)

        def deploy():
            return haven_ranch_herd.deploy(
                self.store,
                self.account,
                self.generation,
                self.ranch.inside,
                struct.pack(">qii", uid, 6, 6),
                session=self.ranch,
                geometry=geometry,
            )

        def repack():
            return haven_ranch_herd.repack(
                self.store,
                self.account,
                self.generation,
                self.ranch.inside,
                struct.pack(">q", uid),
                session=self.ranch,
            )

        def settle():
            with self.store.connection() as db:
                return ranch_cycle_rewards.settle_account(
                    db,
                    self.store,
                    self.account,
                    now_ms=int(self.store.now().timestamp() * 1000),
                )

        def batches():
            with self.store.connection() as db:
                return list(
                    db.execute(
                        "SELECT cycle_number,drop_date_ms FROM account_ranch_reward_batches "
                        "WHERE monster_uid=%s ORDER BY cycle_number",
                        (uid,),
                    )
                )

        deploy()
        self.now[0] += 10 * 24 * 60 * 60
        self.assertTrue(repack()["applied"])
        settle()
        self.assertEqual([row["cycle_number"] for row in batches()], [1, 2, 3, 4, 5, 6])
        self.assertEqual(len(batches()), 6)
        # deploy() first drains three already-earned intervals while the
        # creature is still packed, then starts the new active interval.
        deploy()
        self.assertEqual(len(batches()), 9)
        # One fresh active day elapses while the last previously earned cycle
        # is still ahead of the settlement budget.
        self.now[0] += 24 * 60 * 60
        self.assertTrue(repack()["applied"])
        self.assertEqual(settle(), [])
        rows = batches()
        self.assertEqual([row["cycle_number"] for row in rows], list(range(1, 12)))
        self.assertEqual(
            [row["drop_date_ms"] for row in rows],
            [start_ms + day_ms * cycle for cycle in range(1, 12)],
        )

    def test_deployed_cycle_pause_pending_retrieval_release_and_snapshot(self):
        from wakfu_server import (
            haven_ranch_building_knowledge,
            haven_ranch_buildings,
            haven_ranch_furniture,
            haven_ranch_herd,
            heroes,
            ranch_cycle_rewards,
            ranch_reward_retrieval,
        )
        from wakfu_server import combat_terrain
        from wakfu_server.haven_ranch_herd_wire import encode_creature
        from wakfu_server.inventory_items import grant

        # Add an actual active same-account hero. 12068 may deliver to this
        # active recipient through the selected main's session lease.
        hero = self.store.create_character(self.account, "Ranch Reward Hero")
        heroes.add(
            self.store, self.account, self.generation, self.character["id"], hero["id"]
        )

        # Learn and place an original closed fence ring so the bHQ creature is
        # deployed by the real private-scene operation, not inserted as state.
        fence = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=33111,
            quantity=1,
            container=self.character["inventory_containers"][0]["uid"],
            slot=8,
            allowed_references={33111},
        )
        learned = haven_ranch_building_knowledge.learn(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", 15153, fence["uid"]),
        )
        self.assertTrue(learned["applied"])
        for x in range(4, 9):
            for y in range(4, 9):
                if x in (4, 8) or y in (4, 8):
                    placed = haven_ranch_buildings.operate(
                        self.store,
                        self.account,
                        self.generation,
                        self.ranch.inside,
                        12671,
                        struct.pack(">iBiii", 6, 1, 85, x, y),
                        session=self.ranch,
                    )
                    self.assertTrue(placed["changed"])

        # Action15107 has the original [8,10,11] candidate order. A fixed
        # cryptographic seed selects slot zero without manufacturing creature
        # fields, giving a 24-hour native cycle with guaranteed leaf products.
        source = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=33032,
            quantity=1,
            container=self.character["inventory_containers"][0]["uid"],
            slot=9,
            allowed_references={33032},
        )
        with patch.object(
            haven_ranch_herd.secrets,
            "token_hex",
            return_value="00000000000000000000000000000001",
        ):
            acquired = haven_ranch_herd.use(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">iq", 15107, source["uid"]),
            )
        creature_uid = acquired["creature"]["uid"]
        self.assertEqual(acquired["creature"]["definition"], 8)
        self.assertTrue(acquired["creature"]["native_tJT"])
        geometry = combat_terrain.map_geometry(1440)
        day_ms = ranch_cycle_rewards.catalog()[0][8]["cycle_seconds"] * 1000

        def deploy():
            return haven_ranch_herd.deploy(
                self.store,
                self.account,
                self.generation,
                self.ranch.inside,
                struct.pack(">qii", creature_uid, 6, 6),
                session=self.ranch,
                geometry=geometry,
            )

        def progress():
            with self.store.connection() as db:
                return db.execute(
                    "SELECT * FROM account_ranch_cycle_progress WHERE monster_uid=%s",
                    (creature_uid,),
                ).fetchone()

        deploy()
        self.now[0] += 12 * 60 * 60
        repacked = haven_ranch_herd.repack(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            struct.pack(">q", creature_uid),
            session=self.ranch,
        )
        self.assertTrue(repacked["applied"])
        with self.store.connection() as db:
            stored = db.execute(
                "SELECT native_tjr FROM account_ranch_creatures WHERE uid=%s",
                (creature_uid,),
            ).fetchone()
        self.assertEqual(stored["native_tjr"], day_ms // 2)
        self.now[0] += 2 * 24 * 60 * 60
        deploy()
        self.assertEqual(progress()["cycle_number"], 0)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT native_tjr FROM account_ranch_creatures WHERE uid=%s",
                    (creature_uid,),
                ).fetchone()["native_tjr"],
                day_ms // 2,
            )

        # Complete one cycle after redeployment. The pending batch is durable,
        # deterministic and identical on a same-clock settlement retry.
        self.now[0] += 12 * 60 * 60
        with self.store.connection() as db:
            first = ranch_cycle_rewards.settle_account(
                db,
                self.store,
                self.account,
                now_ms=int(self.store.now().timestamp() * 1000),
            )
        self.assertTrue(first)
        with self.store.connection() as db:
            again = ranch_cycle_rewards.settle_account(
                db,
                self.store,
                self.account,
                now_ms=int(self.store.now().timestamp() * 1000),
            )
            all_rows = ranch_reward_retrieval.records(
                db, self.account, pending_only=True
            )
            batches = list(
                db.execute(
                    "SELECT cycle_number,items FROM account_ranch_reward_batches "
                    "WHERE monster_uid=%s ORDER BY cycle_number",
                    (creature_uid,),
                )
            )
        self.assertTrue(first)
        self.assertEqual(again, [])  # A retry emits no new reward rows.
        self.assertEqual([row["cycle_number"] for row in batches], [1])
        self.assertEqual(
            {row["uid"] for row in all_rows}, {row["uid"] for row in first}
        )
        self.assertTrue(all(row["monster_uid"] == creature_uid for row in all_rows))

        def retrieve(opcode, body, *, character=None):
            return ranch_reward_retrieval.retrieve(
                self.store,
                self.account,
                self.generation,
                self.ranch.inside if character is None else character,
                opcode,
                body,
                session=self.ranch,
            )

        # Native12068 monster filter sends all pending rewards to the active
        # hero. Replaying returns status fBU records, never grants the products twice.
        hero_before = self.store.character(self.account, hero["id"])
        filter_body = struct.pack(">Bqq", 1, creature_uid, hero["id"])
        first_pickup = retrieve(12068, filter_body)
        self.assertTrue(first_pickup["applied"])
        self.assertEqual(first_pickup["recipient_character_id"], hero["id"])
        self.assertEqual(
            set(first_pickup["reward_uids"]), {row["uid"] for row in all_rows}
        )
        with self.store.connection() as db:
            delivered = list(
                db.execute(
                    "SELECT uid,retrieved_at,recipient_character_id FROM account_ranch_rewards "
                    "WHERE account_id=%s AND monster_uid=%s ORDER BY uid",
                    (self.account, creature_uid),
                )
            )
        self.assertTrue(
            all(
                row["retrieved_at"] is not None
                and row["recipient_character_id"] == hero["id"]
                for row in delivered
            )
        )
        hero_after = self.store.character(self.account, hero["id"])
        self.assertGreater(
            sum(item["quantity"] for item in hero_after["inventory_items"]),
            sum(item["quantity"] for item in hero_before["inventory_items"]),
        )
        before_replay = [dict(item) for item in hero_after["inventory_items"]]
        replay = retrieve(12068, filter_body)
        self.assertFalse(replay["applied"])
        self.assertEqual(
            [
                dict(item)
                for item in self.store.character(self.account, hero["id"])[
                    "inventory_items"
                ]
            ],
            before_replay,
        )
        replay_wire = b"".join(
            body for opcode, body in replay["packets"] if opcode == 13964
        )
        self.assertTrue(replay_wire)
        self.assertIn(struct.pack(">q", all_rows[0]["uid"]), replay_wire)

        # Complete a second native cycle, then prove a selected fBU cannot
        # overwrite an occupied ordinary destination. The first cycle already
        # delivered matching products, so a 12068 retry could legally merge;
        # this 12320 destination collision is the actual native rollback edge.
        self.now[0] += 24 * 60 * 60
        with self.store.connection() as db:
            ranch_cycle_rewards.settle_account(
                db,
                self.store,
                self.account,
                now_ms=int(self.store.now().timestamp() * 1000),
            )
            pending_two = ranch_reward_retrieval.records(
                db,
                self.account,
                pending_only=True,
            )
        self.assertTrue(pending_two)
        from wakfu_server.combat_drop_delivery import _container_can_hold
        from wakfu_server.inventory_move import ACQUISITION_STACKS

        with self.store.connection() as db:
            hero_bags = list(
                db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY uid",
                    (hero["id"],),
                )
            )
            hero_bags = [
                bag for bag in hero_bags if _container_can_hold(bag, hero["id"])
            ]
            self.assertTrue(hero_bags)
            filler_uids = []
            for bag in hero_bags:
                occupied = {
                    row["slot"]
                    for row in db.execute(
                        "SELECT slot FROM inventory_items WHERE container=%s",
                        (bag["uid"],),
                    )
                }
                for slot in range(bag["capacity"]):
                    if slot in occupied:
                        continue
                    item = grant(
                        self.store,
                        self.account,
                        self.generation,
                        hero["id"],
                        reference=1853,
                        quantity=1,
                        container=bag["uid"],
                        slot=slot,
                        allowed_references={1853},
                        db=db,
                    )
                    filler_uids.append(item["uid"])
            blocked_destination = db.execute(
                "SELECT container,slot,reference FROM inventory_items WHERE uid=ANY(%s) LIMIT 1",
                (filler_uids,),
            ).fetchone()
            self.assertIsNotNone(blocked_destination)
            self.assertNotEqual(
                blocked_destination["reference"], pending_two[0]["reference"]
            )
            # Cycle one already placed these same native products on the hero.
            # Fill those existing stacks to each item's real native maximum,
            # so the full-bag 12068 transaction cannot merge or place them.
            for reference in {row["reference"] for row in pending_two}:
                maximum = ACQUISITION_STACKS[reference]["maximum"]
                changed = db.execute(
                    "UPDATE inventory_items SET quantity=%s WHERE character_id=%s AND reference=%s",
                    (maximum, hero["id"], reference),
                )
                self.assertGreater(changed.rowcount, 0)
            inventory_before_capacity = [
                dict(row)
                for row in db.execute(
                    "SELECT uid,reference,quantity,container,slot FROM inventory_items "
                    "WHERE character_id=%s ORDER BY uid",
                    (hero["id"],),
                )
            ]
        with self.assertRaises(ValueError):
            retrieve(12068, struct.pack(">Bq", 0, hero["id"]))
        with self.store.connection() as db:
            self.assertEqual(
                [
                    dict(row)
                    for row in db.execute(
                        "SELECT uid,reference,quantity,container,slot FROM inventory_items "
                        "WHERE character_id=%s ORDER BY uid",
                        (hero["id"],),
                    )
                ],
                inventory_before_capacity,
            )
            self.assertEqual(
                {
                    row["uid"]
                    for row in ranch_reward_retrieval.records(
                        db,
                        self.account,
                        pending_only=True,
                    )
                },
                {row["uid"] for row in pending_two},
            )
        with self.assertRaises(ValueError):
            retrieve(
                12320,
                struct.pack(
                    ">hqqh",
                    1,
                    pending_two[0]["uid"],
                    blocked_destination["container"],
                    blocked_destination["slot"],
                ),
            )
        with self.store.connection() as db:
            after_failure = ranch_reward_retrieval.records(
                db,
                self.account,
                pending_only=True,
            )
        self.assertEqual(
            {row["uid"] for row in after_failure}, {row["uid"] for row in pending_two}
        )

        # Leave only the actual cycle-one reward products in the hero bag.
        # This gives native delivery enough room while retaining the capacity
        # failure witness above.
        with self.store.connection() as db:
            db.execute("DELETE FROM inventory_items WHERE uid=ANY(%s)", (filler_uids,))

        # Native12320 selects one real fBU identity and writes the whole stack
        # into an explicitly selected main-character bag slot.
        self.now[0] += 24 * 60 * 60
        with self.store.connection() as db:
            ranch_cycle_rewards.settle_account(
                db,
                self.store,
                self.account,
                now_ms=int(self.store.now().timestamp() * 1000),
            )
            pending = ranch_reward_retrieval.records(
                db, self.account, pending_only=True
            )
            main_bag = db.execute(
                "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s "
                "AND kind=0 ORDER BY uid LIMIT 1",
                (self.character["id"],),
            ).fetchone()
            occupied = {
                row["slot"]
                for row in db.execute(
                    "SELECT slot FROM inventory_items WHERE container=%s",
                    (main_bag["uid"],),
                )
            }
        selected = pending[0]
        selected_slot = next(
            slot for slot in range(main_bag["capacity"]) if slot not in occupied
        )
        selected_body = (
            struct.pack(">h", 1)
            + struct.pack(">q", selected["uid"])
            + struct.pack(">qh", main_bag["uid"], selected_slot)
        )
        selected_result = retrieve(12320, selected_body)
        self.assertEqual(selected_result["reward_uids"], [selected["uid"]])
        self.assertEqual(
            selected_result["recipient_character_id"], self.character["id"]
        )
        with self.store.connection() as db:
            moved = db.execute(
                "SELECT reference,quantity FROM inventory_items WHERE container=%s AND slot=%s",
                (main_bag["uid"], selected_slot),
            ).fetchone()
            selected_ledger = db.execute(
                "SELECT retrieved_at,recipient_character_id FROM account_ranch_rewards WHERE uid=%s",
                (selected["uid"],),
            ).fetchone()
        self.assertEqual(
            (moved["reference"], moved["quantity"]),
            (selected["reference"], selected["quantity"]),
        )
        self.assertIsNotNone(selected_ledger["retrieved_at"])
        self.assertEqual(
            selected_ledger["recipient_character_id"], self.character["id"]
        )

        # Foreign recipient and stale lease both fail before touching pending
        # ledger rows. These are real session/owner checks, not mocked policy.
        foreign = self.store.register("ranch-reward-foreign", "password-test")["id"]
        foreign_character = self.store.create_character(foreign, "Ranch Reward Foreign")
        with self.store.connection() as db:
            pending_before = ranch_reward_retrieval.records(
                db, self.account, pending_only=True
            )
        with self.assertRaises(ValueError):
            retrieve(12068, struct.pack(">Bq", 0, foreign_character["id"]))
        with self.assertRaises(ValueError):
            ranch_reward_retrieval.retrieve(
                self.store,
                self.account,
                "stale-ranch-generation",
                self.ranch.inside,
                12068,
                struct.pack(">Bq", 0, hero["id"]),
                session=self.ranch,
            )
        with self.store.connection() as db:
            self.assertEqual(
                {
                    row["uid"]
                    for row in ranch_reward_retrieval.records(
                        db,
                        self.account,
                        pending_only=True,
                    )
                },
                {row["uid"] for row in pending_before},
            )

        # Release settles only time already accrued, retains its acquisition
        # and earned pending records, and cannot create later cycles.
        released = haven_ranch_herd.release(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            struct.pack(">q", creature_uid),
            session=self.ranch,
        )
        self.assertTrue(released["applied"])
        self.now[0] += 24 * 60 * 60
        with self.store.connection() as db:
            before_cycle = db.execute(
                "SELECT cycle_number FROM account_ranch_cycle_progress WHERE monster_uid=%s",
                (creature_uid,),
            ).fetchone()["cycle_number"]
            accepted = ranch_cycle_rewards.settle_account(
                db,
                self.store,
                self.account,
                now_ms=int(self.store.now().timestamp() * 1000),
            )
            after_cycle = db.execute(
                "SELECT cycle_number FROM account_ranch_cycle_progress WHERE monster_uid=%s",
                (creature_uid,),
            ).fetchone()["cycle_number"]
            pending_rows = ranch_reward_retrieval.records(
                db, self.account, pending_only=True
            )
        self.assertEqual(accepted, [])
        self.assertEqual(after_cycle, before_cycle)
        self.assertTrue(pending_rows)

        # Pending fBU rows bootstrap into both the live scene and account
        # component18 after reopening the store; packet bytes share the exact
        # native serializer, and release removes only the fBQ actor.
        scene = haven_ranch_building_knowledge.scene_packet(
            self.store,
            self.account,
            biome_id=1,
        )
        snapshot = haven_ranch_furniture.snapshot(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            session=self.ranch,
            now_ms=int(self.store.now().timestamp() * 1000),
        )
        self.assertEqual(snapshot["packet"], scene)
        with self.store.connection() as db:
            scene_records = haven_ranch_herd.records(db, self.account, biome_id=1)
        self.assertEqual(scene_records, [])
        reloaded = self.ranch_case.reopen()
        reloaded.clock = lambda: self.now[0]
        owner_packet = haven_ranch_building_knowledge.packet(reloaded, self.account)
        with reloaded.connection() as db:
            encoded_rows = ranch_reward_retrieval.records(db, self.account)
        self.assertTrue(owner_packet[1])
        for row in encoded_rows:
            self.assertIn(ranch_reward_retrieval.encode_reward(row), owner_packet[1])

        # Release does not discard already earned rows; after the next native
        # time interval, 12068 retrieves the prior pending ledger without a new cycle.
        final = ranch_reward_retrieval.retrieve(
            reloaded,
            self.account,
            self.generation,
            self.ranch.inside,
            12068,
            struct.pack(">Bq", 0, hero["id"]),
            session=self.ranch,
        )
        self.assertTrue(final["applied"])
        self.assertEqual(final["recipient_character_id"], hero["id"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT cycle_number FROM account_ranch_cycle_progress WHERE monster_uid=%s",
                    (creature_uid,),
                ).fetchone()["cycle_number"],
                before_cycle,
            )
            history = db.execute(
                "SELECT count(*) AS count FROM ranch_creature_acquisitions WHERE creature_uid=%s",
                (creature_uid,),
            ).fetchone()["count"]
        self.assertEqual(history, 1)


if __name__ == "__main__":
    unittest.main()
