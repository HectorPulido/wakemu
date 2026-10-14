"""Durable boss-room stele authority, costs and immutable encounter receipts."""
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
import test_dungeon_progression as progression_fixture
from wakfu_server import dungeon_difficulty, dungeon_stele


class DungeonStelePersistenceTests(PostgresCase):
    install_context_policy = (
        progression_fixture.DungeonProgressionPostgresTests.install_context_policy
    )
    player = progression_fixture.DungeonProgressionPostgresTests.player
    party = progression_fixture.DungeonProgressionPostgresTests.party
    create = progression_fixture.DungeonProgressionPostgresTests.create
    make_fight = progression_fixture.DungeonProgressionPostgresTests.make_fight
    finish = progression_fixture.DungeonProgressionPostgresTests.finish

    # Installed placement 34851: map 1398, Stele 6, at (-27, 3, 0).
    MAP_ID = 1398
    OBJECT_ID = 34851
    STELE_ID = 6
    GROUP_ID = 991_398
    DIFFICULTY = 20
    REWARDS = (45, 51)
    OPTION_ITEM = 27093
    ACTIVATION_ITEM = 32964
    OPTION_COST = 338

    def setUp(self):
        super().setUp()
        from wakfu_server.dungeon_progression import initialize_run

        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members, self.party_id = self.party(2)
        self.instance_id = self.create(self.members[0])["instance_id"]
        monster = SimpleNamespace(
            ref_id=1,
            count=1,
            native_min_level=1,
            native_max_level=5,
            role="monster",
        )
        plan = progression_fixture._Plan(
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            )
        )
        leader_id = self.members[0]["character"]["id"]
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=ANY(%s)",
                (self.instance_id, [m["character"]["id"] for m in self.members]),
            )
            db.execute(
                "UPDATE dungeon_room_runs SET current_room=2 WHERE instance_id=%s",
                (self.instance_id,),
            )
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) "
                "VALUES(%s,%s,%s,'[]'::jsonb,'available')",
                (self.MAP_ID, self.instance_id, self.GROUP_ID),
            )
            db.execute(
                "INSERT INTO dungeon_room_spawn_receipts "
                "(instance_id,room_order,asset_map_id,group_id) VALUES(%s,2,%s,%s)",
                (self.instance_id, self.MAP_ID, self.GROUP_ID),
            )
            db.execute(
                "UPDATE characters SET map_id=%s,x=-27,y=3,z=0 WHERE id=%s",
                (self.MAP_ID, leader_id),
            )
        self.selection = self.select(stasis_level=5, competitive=True)
        self.member = self.members[0]

    def select(self, member=None, **options):
        member = self.members[0] if member is None else member
        return dungeon_difficulty.select(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            **options,
        )

    def request_body(self, difficulties=(DIFFICULTY,), rewards=REWARDS):
        import struct

        return (
            struct.pack(">qh", self.STELE_ID, len(difficulties))
            + b"".join(struct.pack(">i", value) for value in difficulties)
            + struct.pack(">h", len(rewards))
            + b"".join(struct.pack(">i", value) for value in rewards)
        )

    def browse(self, member=None, generation=None):
        member = self.member if member is None else member
        return dungeon_stele.browse(
            self.store,
            member["account"],
            member["generation"] if generation is None else generation,
            member["character"]["id"],
            self.OBJECT_ID,
        )

    def activate(self, body=None):
        return dungeon_stele.activate(
            self.store,
            self.member["account"],
            self.member["generation"],
            self.member["character"]["id"],
            self.request_body() if body is None else body,
        )

    def grant(self, reference, quantity, slot):
        from wakfu_server.inventory_items import grant

        return grant(
            self.store,
            self.member["account"],
            self.member["generation"],
            self.member["character"]["id"],
            reference=reference,
            quantity=quantity,
            container=self.member["character"]["inventory_containers"][0]["uid"],
            slot=slot,
            allowed_references={reference},
        )

    def quantity(self, reference):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT COALESCE(sum(quantity),0) AS quantity FROM inventory_items "
                "WHERE character_id=%s AND reference=%s",
                (self.member["character"]["id"], reference),
            ).fetchone()
        return row["quantity"]

    def bind_fight(self):
        from wakfu_server.maps.dungeon_fight_binding import bind_room_group

        fight_id = self.make_fight(self.member)
        with self.store.connection() as db:
            bind_room_group(
                db,
                (self.MAP_ID, self.instance_id, self.GROUP_ID),
                self.member["character"]["id"],
                fight_id,
                player_team=0,
            )
        return fight_id

    def test_activation_cost_is_exact_once_and_cumulative_until_encounter(self):
        self.grant(self.OPTION_ITEM, self.OPTION_COST, 0)
        self.grant(self.ACTIVATION_ITEM, 2, 1)
        self.browse()

        first = self.activate()
        self.assertEqual(self.quantity(self.OPTION_ITEM), 0)
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 1)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT revision,selection FROM dungeon_stele_selections "
                "WHERE instance_id=%s AND stele_id=%s",
                (self.instance_id, self.STELE_ID),
            ).fetchone()
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(saved["selection"]["difficulty_ids"], [self.DIFFICULTY])
        self.assertEqual(saved["selection"]["reward_ids"], list(self.REWARDS))

        replay = self.activate()
        self.assertEqual(replay, [first[-1]])
        self.assertEqual(self.quantity(self.OPTION_ITEM), 0)
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 1)

        self.activate(self.request_body(difficulties=(20, 21)))
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 0)
        self.assertEqual(self.quantity(self.OPTION_ITEM), 0)
        with self.assertRaisesRegex(ValueError, "cumulative"):
            self.activate(self.request_body(rewards=(45,)))
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 0)

    def test_insufficient_later_resource_rolls_back_prior_item_consumption(self):
        self.grant(self.OPTION_ITEM, self.OPTION_COST, 0)
        self.browse()

        with self.assertRaisesRegex(
            ValueError, "Insufficient stele activation resources"
        ):
            self.activate()

        self.assertEqual(self.quantity(self.OPTION_ITEM), self.OPTION_COST)
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 0)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM dungeon_stele_selections WHERE instance_id=%s",
                    (self.instance_id,),
                ).fetchone()
            )

    def test_browse_requires_live_leader_lease_and_current_boss_room(self):
        with self.assertRaisesRegex(ValueError, "Invalid inventory session"):
            self.browse(generation="stale-generation")
        with self.assertRaisesRegex(ValueError, "current dungeon leader"):
            self.browse(self.members[1])

        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_room_runs SET current_room=1 WHERE instance_id=%s",
                (self.instance_id,),
            )
        with self.assertRaisesRegex(ValueError, "active boss room"):
            self.browse()
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_room_runs SET current_room=2 WHERE instance_id=%s",
                (self.instance_id,),
            )

        fight_id = self.bind_fight()
        with self.assertRaisesRegex(ValueError, "frozen during the encounter"):
            self.browse()
        self.assertGreater(fight_id, 0)

    def test_frozen_stele_profile_is_immutable_and_freeze_replays(self):
        from wakfu_server.maps.dungeon_fight_binding import bind_room_group

        self.grant(self.OPTION_ITEM, self.OPTION_COST, 0)
        self.grant(self.ACTIVATION_ITEM, 1, 1)
        self.browse()
        self.activate()
        fight_id = self.make_fight(self.member)
        with self.store.connection() as db:
            first = bind_room_group(
                db,
                (self.MAP_ID, self.instance_id, self.GROUP_ID),
                self.member["character"]["id"],
                fight_id,
                player_team=0,
                expected_selection_revision=self.selection["revision"],
            )
            snapshot = dungeon_stele.encounter_snapshot(db, fight_id)
            replay = dungeon_stele.freeze_encounter(db, self.instance_id, fight_id)
            self.assertEqual(replay, snapshot)
            self.assertEqual(
                snapshot["difficulty_revision"], self.selection["revision"]
            )
            expected = dungeon_stele.plan(
                self.configuration(), (self.DIFFICULTY,), self.REWARDS
            )
            self.assertEqual(
                snapshot["selected_stele_item_references"], expected["item_references"]
            )
            self.assertEqual(snapshot["selections"][0]["stele_id"], self.STELE_ID)
            self.assertEqual(snapshot["selections"][0]["revision"], 1)
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM dungeon_stele_selections WHERE instance_id=%s",
                    (self.instance_id,),
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM dungeon_stele_leases WHERE character_id=%s",
                    (self.member["character"]["id"],),
                ).fetchone()
            )
        self.assertIsNotNone(first)
        with self.assertRaisesRegex(ValueError, "frozen during the encounter"):
            self.browse()
        with self.assertRaisesRegex(
            Exception, "stele encounter snapshots are immutable"
        ):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE dungeon_stele_encounters SET snapshot='{}'::jsonb WHERE fight_id=%s",
                    (fight_id,),
                )

    def test_legacy_room_without_native_difficulty_can_bind_without_steles(self):
        with self.store.connection() as db:
            # Miaubuelita's configured route 1000312 has no native catalog
            # entry. Other legacy routes must retain the same playable fallback.
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{definitions}','{}'::jsonb) "
                "WHERE name='dungeon_difficulty_catalog'"
            )
        fight_id = self.bind_fight()
        with self.store.connection() as db:
            self.assertIsNone(dungeon_stele.encounter_snapshot(db, fight_id))
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM dungeon_room_encounters WHERE fight_id=%s AND status='active'",
                    (fight_id,),
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM dungeon_encounter_difficulties WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()
            )

    def test_native_non_stasis_room_can_bind_without_stele_receipt(self):
        with self.store.connection() as db:
            definition_id = db.execute(
                "SELECT definition_id FROM dungeon_instances WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()["definition_id"]
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,%s,'false'::jsonb) "
                "WHERE name='dungeon_difficulty_catalog'",
                (["definitions", str(definition_id), "difficulty_available"],),
            )
        fight_id = self.bind_fight()
        with self.store.connection() as db:
            self.assertIsNone(dungeon_stele.encounter_snapshot(db, fight_id))

    def test_binding_rejects_stale_difficulty_revision_atomically(self):
        from wakfu_server.maps.dungeon_fight_binding import bind_room_group

        old_revision = self.selection["revision"]
        self.select(stasis_level=6, competitive=True)
        fight_id = self.make_fight(self.member)
        with self.assertRaisesRegex(ValueError, "selection revision changed"):
            with self.store.connection() as db:
                bind_room_group(
                    db,
                    (self.MAP_ID, self.instance_id, self.GROUP_ID),
                    self.member["character"]["id"],
                    fight_id,
                    player_team=0,
                    expected_selection_revision=old_revision,
                )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM dungeon_room_encounters WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM dungeon_stele_encounters WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()
            )

    def test_aborted_attempt_preserves_selection_and_charges_only_upgrade_delta(self):
        self.grant(self.OPTION_ITEM, self.OPTION_COST * 2, 0)
        self.grant(self.ACTIVATION_ITEM, 2, 1)
        self.browse()
        self.activate()
        first_fight = self.bind_fight()
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 1)
        self.assertEqual(self.quantity(self.OPTION_ITEM), self.OPTION_COST)

        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id=%s", (first_fight,)
            )
        # Browsing performs the owned aborted-encounter reconciliation before
        # checking the active-encounter fence and creates a fresh stele lease.
        self.browse()
        self.activate()
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 1)
        self.assertEqual(self.quantity(self.OPTION_ITEM), self.OPTION_COST)

        # A new difficulty and an extra tier-one reward add exactly one
        # activation token and one option cost; already-paid choices stay free.
        self.activate(
            self.request_body(difficulties=(20, 21), rewards=(45, 46, 51, 52))
        )
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 0)
        self.assertEqual(self.quantity(self.OPTION_ITEM), 0)
        second_fight = self.bind_fight()
        with self.store.connection() as db:
            previous = dungeon_stele.encounter_snapshot(db, first_fight)
            current = dungeon_stele.encounter_snapshot(db, second_fight)
            self.assertEqual(previous["selections"][0]["difficulty_ids"], [20])
            self.assertEqual(previous["selections"][0]["reward_ids"], [45, 51])
            self.assertEqual(current["selections"][0]["difficulty_ids"], [20, 21])
            self.assertEqual(current["selections"][0]["reward_ids"], [45, 46, 51, 52])
            self.assertNotEqual(previous["fight_id"], current["fight_id"])
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_room_encounters WHERE fight_id=%s",
                    (first_fight,),
                ).fetchone()["status"],
                "aborted",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_stele_encounters WHERE instance_id=%s",
                    (self.instance_id,),
                ).fetchone()["n"],
                2,
            )

    def test_defeat_retry_keeps_paid_selection_and_prior_receipt_immutable(self):
        self.grant(self.OPTION_ITEM, self.OPTION_COST, 0)
        self.grant(self.ACTIVATION_ITEM, 1, 1)
        self.browse()
        self.activate()
        first_fight = self.bind_fight()
        first_snapshot = dungeon_stele.encounter_snapshot
        result = self.finish(first_fight, winner=1)
        self.assertFalse(result["victory"])

        self.browse()
        self.activate()
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 0)
        self.assertEqual(self.quantity(self.OPTION_ITEM), 0)
        second_fight = self.bind_fight()
        with self.store.connection() as db:
            previous = first_snapshot(db, first_fight)
            current = first_snapshot(db, second_fight)
            self.assertEqual(previous["selections"], current["selections"])
            self.assertEqual(previous["selections"][0]["difficulty_ids"], [20])
            self.assertEqual(previous["selections"][0]["reward_ids"], [45, 51])
            self.assertEqual(previous["fight_id"], first_fight)
            self.assertNotEqual(current["fight_id"], first_fight)

    def test_low_stasis_keeps_paid_states_and_excludes_rewards_on_defeat_retry(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_stele_definitions "
                "SET configuration=jsonb_set(configuration,'{minimum_stasis}','2'::jsonb) "
                "WHERE stele_id=%s",
                (self.STELE_ID,),
            )
        self.select(stasis_level=2, competitive=True)
        self.grant(self.OPTION_ITEM, self.OPTION_COST, 0)
        self.grant(self.ACTIVATION_ITEM, 1, 1)
        self.browse()
        self.activate()
        paid_items = self.quantity(self.OPTION_ITEM)
        paid_activation = self.quantity(self.ACTIVATION_ITEM)
        expected = dungeon_stele.plan(
            self.configuration(), (self.DIFFICULTY,), self.REWARDS
        )

        self.select(stasis_level=1, competitive=True)
        low_stasis_fight = self.bind_fight()
        with self.store.connection() as db:
            low_stasis = dungeon_stele.encounter_snapshot(db, low_stasis_fight)
        self.assertEqual(self.finish(low_stasis_fight, winner=1)["victory"], False)

        with self.assertRaisesRegex(ValueError, "frozen except for reductions"):
            self.select(stasis_level=2, competitive=True)
        retry_fight = self.bind_fight()
        with self.store.connection() as db:
            retry = dungeon_stele.encounter_snapshot(db, retry_fight)

        self.assertEqual(low_stasis["selections"][0]["state_ids"], [8318])
        self.assertFalse(low_stasis["selections"][0]["eligible_rewards"])
        self.assertEqual(low_stasis["selected_stele_item_references"], [])
        self.assertEqual(retry["selections"], low_stasis["selections"])
        self.assertFalse(retry["selections"][0]["eligible_rewards"])
        self.assertEqual(retry["selected_stele_item_references"], [])
        self.assertNotEqual(retry["fight_id"], low_stasis["fight_id"])
        self.assertEqual(
            low_stasis["selections"][0]["item_references"], expected["item_references"]
        )
        self.assertEqual(self.quantity(self.OPTION_ITEM), paid_items)
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), paid_activation)

    def test_definition_classification_and_owned_close_preserve_newer_view(self):
        self.grant(self.OPTION_ITEM, self.OPTION_COST, 0)
        self.grant(self.ACTIVATION_ITEM, 1, 1)
        placement = dungeon_stele.definition(self.store, self.MAP_ID, self.OBJECT_ID)
        self.assertEqual(placement["stele_id"], self.STELE_ID)
        self.assertIsNone(dungeon_stele.definition(self.store, self.MAP_ID, 123456789))

        self.browse()
        stale_object_id = self.OBJECT_ID + 1
        self.assertEqual(
            dungeon_stele.close(
                self.store,
                self.member["account"],
                self.member["generation"],
                self.member["character"]["id"],
                stale_object_id,
            ),
            [],
        )
        with self.store.connection() as db:
            lease = db.execute(
                "SELECT object_id FROM dungeon_stele_leases WHERE character_id=%s",
                (self.member["character"]["id"],),
            ).fetchone()
        self.assertEqual(lease["object_id"], self.OBJECT_ID)

        self.assertEqual(
            dungeon_stele.close(
                self.store,
                self.member["account"],
                self.member["generation"],
                self.member["character"]["id"],
                self.OBJECT_ID,
            ),
            [],
        )
        with self.assertRaisesRegex(ValueError, "owned browse lease"):
            self.activate()
        self.assertEqual(self.quantity(self.ACTIVATION_ITEM), 1)
        self.assertEqual(self.quantity(self.OPTION_ITEM), self.OPTION_COST)

    def configuration(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT configuration FROM dungeon_stele_definitions WHERE stele_id=%s",
                (self.STELE_ID,),
            ).fetchone()["configuration"]


if __name__ == "__main__":
    unittest.main()
