"""Bulk candidates share one durable regional event across owned participants."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from test_environmental_durable_lifecycle import EnvironmentalDurableLifecycleTests
from wakfu_server.objectives import environmental_storage as storage


class EnvironmentalRegionalScheduleTests(EnvironmentalDurableLifecycleTests):
    def bulk_profiles(self, count=100, first_minimum=1, intermission_ms=0, modes=None):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,"
                "anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "SELECT 'bulk-'||lpad(n::text,3,'0'),1,-10000-n,'resource_collect','solo',527,17,60000,"
                "0,CASE WHEN n=0 THEN %s ELSE 1 END,245,'test-only bulk policy',%s,%s "
                "FROM generate_series(0,%s) n",
                (first_minimum, "0" * 64, "1" * 64, count - 1),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives "
                "SELECT profile_key,version,'collect','resource_collect',1337,3,1,'interaction',2 "
                "FROM environmental_runtime_profiles"
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards "
                "SELECT profile_key,version,0,'xp',NULL,100,'test-only' FROM environmental_runtime_profiles"
            )
            db.execute(
                "INSERT INTO environmental_profile_publication "
                "SELECT profile_key,version,native_scenario_id,0,17,NULL,'remaining_ms','test-only' "
                "FROM environmental_runtime_profiles"
            )
            for state, ordinal in (
                ("proposed", 0),
                ("active", 1),
                ("completed", 2),
                ("expired", 2),
                ("cancelled", 2),
            ):
                db.execute(
                    "INSERT INTO environmental_profile_publication_states "
                    "SELECT profile_key,version,%s,%s FROM environmental_runtime_profiles",
                    (state, ordinal),
                )
            for ordinal, mode in (modes or {}).items():
                key = "bulk-" + str(ordinal).zfill(3)
                db.execute(
                    "UPDATE environmental_runtime_profiles SET mode=%s WHERE profile_key=%s",
                    (mode, key),
                )
                if mode == "race":
                    db.execute(
                        "INSERT INTO environmental_profile_evaluation VALUES(%s,1,'first_completion',2,'commit_order','test-only two-place race')",
                        (key,),
                    )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true"
            )
        self.schedule_policy(intermission_ms=intermission_ms)

    def schedule_policy(self, intermission_ms=0):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "(policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256) "
                "VALUES('test-bulk',1,527,17,'wakemu_round_robin','occupied_sequential_windows',%s,'test-only',%s)",
                (intermission_ms, "0" * 64),
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_candidates "
                "SELECT 'test-bulk',1,row_number() OVER(ORDER BY profile_key)-1,profile_key,version "
                "FROM environmental_runtime_profiles"
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true"
            )

    def direct_refresh(self, account, character, now_ms):
        with self.store.connection() as db:
            return storage.refresh(
                db,
                account_id=account,
                character_id=character["id"],
                location=self.location,
                now_ms=now_ms,
            )

    def test_global_terminal_rotates_after_cleanup_but_personal_race_stays_until_global_settlement(
        self,
    ):
        from dataclasses import replace
        from psycopg.pq import TransactionStatus
        from wakfu_server.objectives.environmental_cleanup import release_memberships

        self.bulk_profiles(count=3, modes={0: "collaborative", 1: "race"})
        first = self.direct_refresh(self.account, self.character, self.now_ms)[
            "instances"
        ][0]
        self.roster(first["instance_id"], [801, 802])
        self.consume(self.fact(801))
        self.consume(self.fact(802))
        with self.store.connection() as db:
            settled = db.execute(
                "SELECT state,terminal_at_ms FROM environmental_event_instances WHERE instance_id=%s",
                (first["instance_id"],),
            ).fetchone()
            self.assertEqual(settled["state"], "completed")
            pending = db.execute(
                "SELECT count(*) AS n FROM environmental_cleanup_outbox WHERE instance_id=%s AND completed_at_ms IS NULL",
                (first["instance_id"],),
            ).fetchone()["n"]
            self.assertEqual(pending, 2)
            old_entitlements = db.execute(
                "SELECT entitlement_id FROM environmental_reward_entitlements WHERE instance_id=%s ORDER BY entitlement_id",
                (first["instance_id"],),
            ).fetchall()
            old_deliveries = db.execute(
                "SELECT delivery_id FROM environmental_publication_outbox WHERE instance_id=%s ORDER BY delivery_id",
                (first["instance_id"],),
            ).fetchall()
            self.assertEqual(len(old_entitlements), 1)
            self.assertTrue(old_deliveries)
        # The shared terminal state alone cannot remove live event entities.
        held = self.direct_refresh(self.account, self.character, self.now_ms + 2)[
            "instances"
        ]
        self.assertEqual([row["instance_id"] for row in held], [first["instance_id"]])
        with self.store.connection() as db:
            released = release_memberships(
                db, map_id=527, instance_id=0, now_ms=self.now_ms + 3
            )
            self.assertEqual(len(released), 2)
        race = self.direct_refresh(self.account, self.character, self.now_ms + 3)[
            "instances"
        ][0]
        self.assertEqual(race["profile_key"], "bulk-001")
        self.assertLess(race["started_at_ms"], first["deadline_ms"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT entitlement_id FROM environmental_reward_entitlements WHERE instance_id=%s ORDER BY entitlement_id",
                    (first["instance_id"],),
                ).fetchall(),
                old_entitlements,
            )
            self.assertEqual(
                db.execute(
                    "SELECT delivery_id FROM environmental_publication_outbox WHERE instance_id=%s ORDER BY delivery_id",
                    (first["instance_id"],),
                ).fetchall(),
                old_deliveries,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                0,
            )
        self.roster(race["instance_id"], [803, 804])
        for entity in (803, 804):
            self.consume(replace(self.fact(entity), occurred_at_ms=self.now_ms + 4))
        personal = self.direct_refresh(self.account, self.character, self.now_ms + 5)[
            "instances"
        ][0]
        self.assertEqual(
            (personal["instance_id"], personal["state"]),
            (race["instance_id"], "active"),
        )
        self.assertFalse(personal["available"])
        self.assertEqual(personal["native_publication"]["state_ordinal"], 2)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT state FROM environmental_event_instances WHERE instance_id=%s",
                    (race["instance_id"],),
                ).fetchone()["state"],
                "active",
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT completed_at_ms FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
                    (race["instance_id"], self.character["id"]),
                ).fetchone()["completed_at_ms"]
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_rankings WHERE instance_id=%s",
                    (race["instance_id"],),
                ).fetchone()["n"],
                1,
            )
            # Publish a new cadence without rewriting the active slot's policy.
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET enabled=false"
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "SELECT policy_key,2,map_id,region_id,selection_policy,cadence_policy,10000,authority,source_sha256,false,false "
                "FROM environmental_regional_schedule_policies WHERE version=1"
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_candidates "
                "SELECT policy_key,2,ordinal,profile_key,profile_version FROM environmental_regional_schedule_candidates WHERE version=1"
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true WHERE version=2"
            )
        still_personal = self.direct_refresh(
            self.account, self.character, self.now_ms + 6
        )["instances"][0]
        self.assertEqual(still_personal["instance_id"], race["instance_id"])
        with self.store.connection() as db:
            storage.cancel(
                db,
                race["instance_id"],
                reason="bounded global cancellation",
                now_ms=self.now_ms + 7,
            )
            self.assertEqual(
                len(
                    release_memberships(
                        db, map_id=527, instance_id=0, now_ms=self.now_ms + 8
                    )
                ),
                2,
            )
        next_cycle = self.direct_refresh(self.account, self.character, self.now_ms + 8)[
            "instances"
        ][0]
        self.assertNotEqual(next_cycle["instance_id"], first["instance_id"])
        self.assertEqual(next_cycle["profile_key"], "bulk-000")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT version FROM environmental_regional_schedule_slots"
                ).fetchone()["version"],
                2,
            )
            storage.cancel(
                db,
                next_cycle["instance_id"],
                reason="nonzero intermission boundary",
                now_ms=self.now_ms + 9,
            )
        self.assertEqual(
            self.direct_refresh(self.account, self.character, self.now_ms + 10)[
                "instances"
            ],
            [],
        )
        self.assertEqual(
            self.direct_refresh(self.account, self.character, self.now_ms + 10008)[
                "instances"
            ],
            [],
        )
        after_pause = self.direct_refresh(
            self.account, self.character, self.now_ms + 10009
        )["instances"][0]
        self.assertEqual(after_pause["profile_key"], "bulk-001")
        self.assertLess(after_pause["started_at_ms"], next_cycle["deadline_ms"])
        self.presence_world.leave(self.character["id"], self.generation)
        db = Mock()
        db.info.transaction_status = TransactionStatus.INTRANS
        self.assertTrue(
            storage.refresh(
                db,
                account_id=self.account,
                character_id=self.character["id"],
                location=self.location,
                now_ms=self.now_ms + 10010,
            )["inactive_scope"]
        )
        db.execute.assert_not_called()

    def test_bulk_100_profiles_share_selection_before_level_and_rotate_without_old_display(
        self,
    ):
        self.bulk_profiles(first_minimum=81)
        other_account, other_generation, other = self.owner()
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=81 WHERE id=%s", (other["id"],))
        low = self.direct_refresh(self.account, self.character, self.now_ms)
        self.assertEqual(low["instances"], [])
        admitted = self.direct_refresh(other_account, other, self.now_ms)["instances"]
        self.assertEqual(len(admitted), 1)
        event = admitted[0]
        self.assertEqual(event["profile_key"], "bulk-000")
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=81 WHERE id=%s", (self.character["id"],)
            )
        same = self.direct_refresh(self.account, self.character, self.now_ms)[
            "instances"
        ][0]
        self.assertEqual(same["instance_id"], event["instance_id"])
        self.roster(event["instance_id"], [101, 102])
        self.consume(self.fact(101))
        self.consume(self.fact(102))
        completed = self.direct_refresh(self.account, self.character, self.now_ms + 10)
        self.assertEqual(
            [(r["instance_id"], r["available"]) for r in completed["instances"]],
            [(event["instance_id"], False)],
        )
        next_event = self.direct_refresh(
            self.account, self.character, event["deadline_ms"]
        )
        self.assertEqual(
            [r["profile_key"] for r in next_event["instances"]], ["bulk-001"]
        )
        self.assertEqual(len(next_event["instances"]), 1)
        with self.store.connection() as db:
            claimed = storage.claim_pending(
                db,
                self.store,
                account_id=self.account,
                character_id=self.character["id"],
                now_ms=event["deadline_ms"],
            )
            self.assertEqual(len(claimed["delivered"]), 1)
        replay = self.direct_refresh(self.account, self.character, event["deadline_ms"])
        self.assertEqual(len(replay["instances"]), 1)
        self.assertTrue(
            any(
                r["instance_id"] == event["instance_id"] and r["kind"] == "claimed"
                for r in replay["deliveries"]
            )
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                100,
            )

    def test_simultaneous_owners_create_one_event_and_vacant_return_does_not_backfill(
        self,
    ):
        self.bulk_profiles()
        other_account, other_generation, other = self.owner()
        with ThreadPoolExecutor(max_workers=2) as executor:
            rows = list(
                executor.map(
                    lambda owner: self.direct_refresh(*owner, self.now_ms),
                    [(self.account, self.character), (other_account, other)],
                )
            )
        event = rows[0]["instances"][0]
        self.assertEqual(rows[1]["instances"][0]["instance_id"], event["instance_id"])
        self.presence_world.leave(self.character["id"], self.generation)
        self.presence_world.leave(other["id"], other_generation)
        db = Mock()
        from psycopg.pq import TransactionStatus

        db.info.transaction_status = TransactionStatus.INTRANS
        empty = storage.refresh(
            db,
            account_id=self.account,
            character_id=self.character["id"],
            location=self.location,
            now_ms=self.now_ms + 3600000,
        )
        self.assertTrue(empty["inactive_scope"])
        db.execute.assert_not_called()
        self.presence_world.join(self.generation, object(), self.character)
        resumed = self.direct_refresh(
            self.account, self.character, self.now_ms + 3600000
        )
        self.assertEqual([r["profile_key"] for r in resumed["instances"]], ["bulk-001"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                2,
            )

    def test_disabled_before_first_admission_and_version_change_keep_scope_reserved(
        self,
    ):
        self.bulk_profiles(count=3, intermission_ms=10000)
        with self.store.connection() as db:
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET enabled=false"
            )
        disabled = self.direct_refresh(self.account, self.character, self.now_ms)
        self.assertEqual(disabled["instances"], [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                0,
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET enabled=true"
            )
        first = self.direct_refresh(self.account, self.character, self.now_ms)[
            "instances"
        ][0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET enabled=false"
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "SELECT policy_key,2,map_id,region_id,selection_policy,cadence_policy,0,authority,source_sha256,false,false "
                "FROM environmental_regional_schedule_policies WHERE version=1"
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_candidates "
                "SELECT policy_key,2,ordinal,profile_key,profile_version "
                "FROM environmental_regional_schedule_candidates WHERE version=1"
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true WHERE version=2"
            )
            storage.cancel(
                db,
                first["instance_id"],
                reason="test early terminal",
                now_ms=self.now_ms + 1,
            )
        # No memberships were registered, so cancellation has no pending
        # physical cleanup. The frozen old policy counts from terminal time.
        terminal = self.now_ms + 1
        self.assertEqual(
            self.direct_refresh(self.account, self.character, terminal + 1)[
                "instances"
            ],
            [],
        )
        self.assertEqual(
            self.direct_refresh(self.account, self.character, terminal + 9999)[
                "instances"
            ],
            [],
        )
        next_event = self.direct_refresh(
            self.account, self.character, terminal + 10000
        )["instances"][0]
        self.assertNotEqual(next_event["instance_id"], first["instance_id"])
        with self.store.connection() as db:
            slot = db.execute(
                "SELECT * FROM environmental_regional_schedule_slots"
            ).fetchone()
            self.assertEqual(
                (slot["version"], slot["event_instance_id"]),
                (2, next_event["instance_id"]),
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET enabled=false"
            )
        self.assertEqual(
            self.direct_refresh(
                self.account, self.character, next_event["deadline_ms"]
            )["instances"],
            [],
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                2,
            )

    def test_native_rotation_failed_delivery_and_reconnect_preserve_old_claim_once(
        self,
    ):
        from types import SimpleNamespace
        import struct
        from unittest.mock import Mock
        from wakfu_server.objectives.environmental_world import (
            SelectedEnvironmentalEvents,
        )

        self.bulk_profiles(count=2)
        batches = []
        self.presence_world.join(
            self.generation, SimpleNamespace(shutdown=lambda *_: None), self.character
        )
        self.presence_world.deliver_batch = lambda peer, packets: batches.append(
            packets
        )
        connection = SelectedEnvironmentalEvents()
        self.assertTrue(
            connection.refresh(
                self.store,
                self.presence_world,
                self.account,
                self.generation,
                self.character["id"],
                location=self.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=self.now_ms,
            )
        )
        event = self.direct_refresh(self.account, self.character, self.now_ms)[
            "instances"
        ][0]
        self.roster(event["instance_id"], [101, 102])
        self.consume(self.fact(101))
        self.consume(self.fact(102))
        self.presence_world.deliver_batch = Mock(
            side_effect=OSError("injected rotated send failure")
        )
        self.assertFalse(
            connection.refresh(
                self.store,
                self.presence_world,
                self.account,
                self.generation,
                self.character["id"],
                location=self.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=event["deadline_ms"],
            )
        )
        with self.store.connection() as db:
            xp = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["xp"]
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertGreater(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_publication_outbox "
                    "WHERE kind='claimed' AND acknowledged_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )
        self.presence_world.deliver_batch = lambda peer, packets: batches.append(
            packets
        )
        reconnect = SelectedEnvironmentalEvents()
        self.assertTrue(
            reconnect.refresh(
                self.store,
                self.presence_world,
                self.account,
                self.generation,
                self.character["id"],
                location=self.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=event["deadline_ms"],
            )
        )
        snapshots = [body for opcode, body in batches[-1] if opcode == 12549]
        self.assertEqual(
            [struct.unpack_from(">i", body, 1)[0] for body in snapshots], [-10001]
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["xp"],
                xp,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_publication_outbox "
                    "WHERE acknowledged_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )

    def test_solo_global_physical_quantity_is_not_sum_or_personal_target_clipping(self):
        from dataclasses import replace

        self.profile(mode="solo", required=2, unit="quantity")
        other_account, other_generation, other = self.owner()
        event = self.direct_refresh(self.account, self.character, self.now_ms)[
            "instances"
        ][0]
        self.direct_refresh(other_account, other, self.now_ms)
        self.roster(event["instance_id"], [101])
        physical = replace(self.fact(101), quantity=5)
        self.consume(physical)
        self.consume(
            replace(physical, account_id=other_account, character_id=other["id"])
        )
        self.assertEqual(self.consume(physical), ())
        with self.store.connection() as db:
            self.assertEqual(
                storage._progress(db, event, self.character["id"]), {"collect": 2}
            )
            self.assertEqual(storage._progress(db, event, other["id"]), {"collect": 2})
            self.assertEqual(storage._progress(db, event), {"collect": 5})
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_shared_actions"
                ).fetchone()["n"],
                1,
            )
