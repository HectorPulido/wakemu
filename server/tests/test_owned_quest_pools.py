"""Focused policy and ordinary-group persistence coverage for quest pools."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server import owned_quest_pools as pools


PROFILE = (
    Path(__file__).resolve().parents[1]
    / "wakfu_server/maps/owned_story_profiles/wild-estate-brak-723.configuration.v2.json"
)


def _configuration():
    return json.loads(PROFILE.read_text())


class OwnedQuestPoolPolicyTests(unittest.TestCase):
    def test_pinned_723_pool_policy_rejects_drift_and_unsafe_rosters(self):
        configuration = _configuration()
        (selected,) = pools.policies(configuration)
        self.assertEqual(selected["declaration"]["id"], "wild-amulet-parts")
        self.assertEqual(selected["declaration"]["stop_quantity"], 3)
        self.assertEqual(
            selected["declaration"]["monsters"], [{"reference": 2779, "count": 1}]
        )
        self.assertGreaterEqual(len(selected["cells"]), 9)

        cases = []
        duplicate_reference = _configuration()
        duplicate_reference["topology"]["owned_quest_pools"][0]["monsters"].append(
            {"reference": 2779, "count": 1}
        )
        cases.append(duplicate_reference)

        boolean_quantity = _configuration()
        boolean_quantity["topology"]["owned_quest_pools"][0]["stop_quantity"] = True
        cases.append(boolean_quantity)

        missing_anchor = _configuration()
        missing_anchor["topology"]["owned_quest_pools"][0]["anchor"] = [999, 999, 0]
        cases.append(missing_anchor)

        changed_map = _configuration()
        changed_map["topology"]["exploration_geometry"]["map_id"] = 714
        cases.append(changed_map)

        disconnected_native_floor = _configuration()
        disconnected_native_floor["topology"]["exploration_geometry"]["edges"] = []
        cases.append(disconnected_native_floor)

        for malformed in cases:
            with self.subTest(case=len(cases)):
                with self.assertRaises(ValueError):
                    pools.policies(malformed)


class OwnedQuestPoolPersistenceTests(PostgresCase):
    def test_registered_group_receipts_reuse_loss_regenerate_defeat_and_stop_at_three(
        self,
    ):
        from wakfu_server.achievements import storage
        from wakfu_server.combat_group_store import PersistentGroups

        configuration = _configuration()
        geometry = configuration["topology"]["exploration_geometry"]
        account = self.store.register("quest-pool-test", "isolated-test-password")["id"]
        character = self.store.create_character(account, "Quest Pool Tester")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            party_id = db.execute(
                "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) RETURNING id",
                (character["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (character["id"], party_id),
            )
            instance_id = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id) "
                "VALUES(%s,1,%s,723,723,714,20427,723,723) RETURNING instance_id",
                (party_id, character["id"]),
            ).fetchone()["instance_id"]
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) "
                "VALUES(%s,%s,%s,%s,1,'leader')",
                (instance_id, party_id, character["id"], generation),
            )
            db.execute(
                "UPDATE characters SET map_id=723,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    instance_id,
                    *configuration["topology"]["owned_quest_pools"][0]["anchor"],
                    character["id"],
                ),
            )
            state = storage.load_locked(db, character["id"])
            state["running"] = [1677]
            state["completed"] = []
            state["objectives"] = []
            storage.store(db, character["id"], state)

        groups = PersistentGroups(self.store)

        def ensure_once():
            with self.store.connection() as db, db.transaction():
                return pools.ensure(db, groups, instance_id, configuration, geometry)

        with patch.object(pools, "_configuration", return_value=configuration):
            first = ensure_once()
            self.assertEqual(len(first), 1)
            first_key = (723, instance_id, first[0]["group_id"])
            with self.store.connection() as db:
                receipt = pools.group_receipt(
                    db, first_key, configuration=configuration
                )
                self.assertEqual(receipt["receipt"]["generation"], 1)
                self.assertEqual(
                    receipt["receipt"]["members"], receipt["group"]["members"]
                )
                self.assertEqual(
                    pools.ensure(db, groups, instance_id, configuration, geometry), ()
                )

                # A stale/forged head cannot name another group, even if its
                # payload otherwise looks well-formed.
                head_key = pools._key("head", f"{instance_id}:wild-amulet-parts")
                head = pools._read(db, character["id"], head_key)
                db.execute(
                    "UPDATE character_achievement_events SET payload=%s WHERE character_id=%s AND event_key=%s",
                    (
                        Jsonb(dict(head, group_id=head["group_id"] + 1)),
                        character["id"],
                        head_key,
                    ),
                )
                with self.assertRaises(ValueError):
                    pools.ensure(db, groups, instance_id, configuration, geometry)
                db.execute(
                    "UPDATE character_achievement_events SET payload=%s WHERE character_id=%s AND event_key=%s",
                    (Jsonb(head), character["id"], head_key),
                )

                # Re-signed forged owner facts and altered registered rosters
                # are rejected independently of receipt checksum validation.
                group_key = pools._key("group", f"{instance_id}:{first_key[2]}")
                group_payload = receipt["receipt"]
                forged_owner = dict(group_payload, owner_id=character["id"] + 1)
                db.execute(
                    "UPDATE character_achievement_events SET signature=%s,payload=%s WHERE character_id=%s AND event_key=%s",
                    (
                        pools.digest(forged_owner),
                        Jsonb(forged_owner),
                        character["id"],
                        group_key,
                    ),
                )
                with self.assertRaises(ValueError):
                    pools.group_receipt(db, first_key, configuration=configuration)
                db.execute(
                    "UPDATE character_achievement_events SET signature=%s,payload=%s WHERE character_id=%s AND event_key=%s",
                    (
                        pools.digest(group_payload),
                        Jsonb(group_payload),
                        character["id"],
                        group_key,
                    ),
                )
                members = receipt["group"]["members"]
                db.execute(
                    "UPDATE combat_groups SET members=%s WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    (Jsonb([]), *first_key),
                )
                with self.assertRaises(ValueError):
                    pools.group_receipt(db, first_key, configuration=configuration)
                db.execute(
                    "UPDATE combat_groups SET members=%s WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    (Jsonb(members), *first_key),
                )

            # Exercise the ordinary group lease's loss path: the same registered
            # native roster remains available and the quest-pool head is reused.
            with self.store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                    (fight_id, character["id"], account),
                )
            lease, _members = groups.claim(first_key, generation, fight_id)
            with self.store.connection() as db, db.transaction():
                bound = pools.bind(db, first_key, character["id"], fight_id)
                self.assertEqual(bound["members"], receipt["receipt"]["members"])
                self.assertEqual(bound["fight_id"], fight_id)
                self.assertTrue(groups.finish(lease, defeated=False, db=db))
                self.assertEqual(
                    pools.ensure(db, groups, instance_id, configuration, geometry), ()
                )
                reused = pools.group_receipt(db, first_key, configuration=configuration)
                self.assertEqual(reused["group"]["status"], "available")
                self.assertEqual(reused["receipt"]["generation"], 1)

            # A normal defeated group status permits a new generation, still
            # bounded by the actual carried fragment quantity.
            with self.store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
            lease, _members = groups.claim(first_key, generation, fight_id)
            with self.store.connection() as db, db.transaction():
                self.assertTrue(groups.finish(lease, defeated=True, db=db))
                second = pools.ensure(db, groups, instance_id, configuration, geometry)
                self.assertEqual(len(second), 1)
                self.assertEqual(second[0]["generation"], 2)
                second_key = (723, instance_id, second[0]["group_id"])
                second_receipt = pools.group_receipt(
                    db, second_key, configuration=configuration
                )
                self.assertEqual(
                    second_receipt["receipt"]["members"],
                    second_receipt["group"]["members"],
                )

                container = db.execute(
                    "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                    (character["id"],),
                ).fetchone()
                if container is None:
                    raise AssertionError("Character inventory was not initialized")
                db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,17851,3,%s,0)",
                    (character["id"], container["uid"]),
                )
            with self.store.connection() as db:
                third_fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
            third_lease, _members = groups.claim(second_key, generation, third_fight_id)
            with self.store.connection() as db, db.transaction():
                self.assertTrue(groups.finish(third_lease, defeated=True, db=db))
                stopped = pools.ensure(db, groups, instance_id, configuration, geometry)
                self.assertEqual(stopped, ())
                self.assertEqual(
                    pools.group_receipt(db, second_key, configuration=configuration)[
                        "group"
                    ]["status"],
                    "defeated",
                )
