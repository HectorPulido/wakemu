"""Transactional publication and live inventory guards for native pickups."""

from copy import deepcopy
import json
from pathlib import Path
import struct

from postgres_case import PostgresCase
from tools import publish_native_generic_rewards as publisher
from wakfu_server import native_generic_rewards as rewards
from wakfu_server.achievements import storage
from wakfu_server.dungeon_entry_payment import consume
from wakfu_server.items import quest_inventory, account_quest_inventory


ROOT = Path(__file__).parents[1] / "wakfu_server/maps/native_generic_profiles"


def _documents():
    return [
        json.loads((ROOT / name).read_text())
        for name in (
            "huppermage-registration-pickups.json",
            "wild-estate-clue-feedback.json",
        )
    ]


class NativeGenericProfilesPostgresTests(PostgresCase):
    def test_publish_idempotence_rollback_exact_school_rewards_and_script_only_clues(
        self,
    ):
        documents = _documents()
        combined = dict(
            schema=publisher.SCHEMA,
            entries=[entry for document in documents for entry in document["entries"]],
        )
        with self.store.connection() as db:
            baseline = db.execute(
                "SELECT count(*) AS n FROM native_generic_reward_programs"
            ).fetchone()["n"]
            with db.transaction(force_rollback=True):
                result = publisher.install(db, combined)
                self.assertEqual((result["programs"], result["inserted"]), (9, 9))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_generic_reward_programs"
                ).fetchone()["n"],
                baseline,
            )
        with self.store.connection() as db:
            first = publisher.install(db, combined)
            self.assertEqual((first["programs"], first["inserted"]), (9, 9))
        with self.store.connection() as db:
            retry = publisher.install(db, combined)
            self.assertEqual((retry["programs"], retry["inserted"]), (9, 0))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_generic_reward_programs WHERE sealed"
                ).fetchone()["n"],
                baseline + 9,
            )
            changed = deepcopy(combined)
            changed["entries"][0]["authority"] += " changed"
            with self.assertRaisesRegex(ValueError, "Immutable native generic"):
                publisher.install(db, changed)
            changed_hash = deepcopy(combined)
            changed_hash["entries"][0]["source_sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "Immutable native generic"):
                publisher.install(db, changed_hash)

        account = self.store.register(
            "native-school-pickups", "isolated-test-password"
        )["id"]
        generation = self.store.begin_session(account)
        expected = {
            983: (26212, 2542, 20035),
            984: (26215, 2541, 20037),
            985: (26216, 2540, 20036),
        }
        names = {983: "School One", 984: "School Two", 985: "School Three"}

        def amount(actor_id, reference):
            with self.store.connection() as db:
                if reference in account_quest_inventory.REFERENCES:
                    rows = account_quest_inventory.load(db, account)
                elif reference in quest_inventory.REFERENCES:
                    rows = quest_inventory.load(db, actor_id)
                else:
                    rows = self.store.character(account, actor_id, db)[
                        "inventory_items"
                    ]
                return sum(
                    row["quantity"] for row in rows if row["reference"] == reference
                )

        for descriptor, (object_id, table_id, item_id) in expected.items():
            actor = self.store.create_character(account, names[descriptor])
            self.store.select_character(account, generation, actor["id"])
            rule = rewards.definition(self.store, 1018, object_id)
            self.assertEqual(rule["descriptor_id"], descriptor)
            self.assertEqual(rule["effects"][-1]["loot_list_id"], table_id)
            with self.store.connection() as db:
                current = storage.load_locked(db, actor["id"])
                current["running"] = [2776]
                current["objectives"] = [5596]
                storage.store(db, actor["id"], current)
                db.execute(
                    "UPDATE characters SET map_id=1018,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (*rule["approaches"][0], actor["id"]),
                )
            current = self.store.character(account, actor["id"])
            request = struct.pack(">qHH", object_id, 0, 0)
            first = rewards.claim(
                self.store, account, generation, current, request, loaded=True
            )
            self.assertEqual(
                first["granted"],
                [
                    dict(
                        effect_reference=rule["effects"][-1]["effect_reference"],
                        reference=item_id,
                        quantity=1,
                    )
                ],
            )
            self.assertEqual(amount(actor["id"], item_id), 1)
            duplicate = rewards.claim(
                self.store, account, generation, current, request, loaded=True
            )
            self.assertTrue(duplicate["replay"])
            self.assertEqual(duplicate["granted"], [])
            self.assertEqual(amount(actor["id"], item_id), 1)
            with self.store.connection() as db:
                consume(db, (actor["id"],), item_id, 1)
            reacquired = rewards.claim(
                self.store,
                account,
                generation,
                self.store.character(account, actor["id"]),
                request,
                loaded=True,
            )
            self.assertEqual(amount(actor["id"], item_id), 1)
            self.assertEqual(reacquired["granted"][0]["reference"], item_id)

        clues = documents[1]["entries"]
        actor = self.store.create_character(account, "Wild Estate clues")
        self.store.select_character(account, generation, actor["id"])
        for entry in clues:
            object_id = entry["source"]["id"]
            rule = rewards.definition(self.store, 711, object_id)
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=711,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (*rule["approaches"][0], actor["id"]),
                )
            before = self.store.character(account, actor["id"])["inventory_items"]
            result = rewards.claim(
                self.store,
                account,
                generation,
                self.store.character(account, actor["id"]),
                struct.pack(">qHH", object_id, 0, 0),
                loaded=True,
            )
            self.assertEqual(result["granted"], [])
            self.assertTrue(result["replay"])
            self.assertTrue(result["visual_packets"])
            self.assertEqual(
                self.store.character(account, actor["id"])["inventory_items"], before
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
