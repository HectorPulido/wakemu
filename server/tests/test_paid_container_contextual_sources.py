"""One isolated PG qualification for contextual data over the existing271 engine."""
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import struct
from unittest.mock import patch

from psycopg import DatabaseError
from postgres_case import PostgresCase


class ContextualPaidContainerTests(PostgresCase):
    def test_nine_sources_native_provenance_and_shared_exclusive_settlement(self):
        from wakfu_server import native_catalog, paid_containers as service
        from wakfu_server.inventory_items import grant
        from wakfu_server.paths import DATA_ROOT

        prefix = "wakemu.contextual.%"
        with self.store.connection() as db:
            locations = db.execute(
                "SELECT map_id,object_id FROM paid_container_locations "
                "WHERE policy_id LIKE %s ORDER BY map_id,object_id",
                (prefix,),
            ).fetchall()
            policies = db.execute(
                "SELECT * FROM paid_container_policies WHERE policy_id LIKE %s",
                (prefix,),
            ).fetchall()
            provenance = db.execute(
                "SELECT * FROM paid_container_contextual_item_sources "
                "ORDER BY policy_id,ordinal"
            ).fetchall()
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM paid_container_outcomes "
                    "WHERE policy_id LIKE %s",
                    (prefix,),
                ).fetchone()["n"],
                10,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM paid_container_approaches a "
                    "JOIN paid_container_locations l USING(map_id,object_id) WHERE l.policy_id LIKE %s",
                    (prefix,),
                ).fetchone()["n"],
                26,
            )
            # Extend271 rather than replacing its qualified data.
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM paid_container_locations "
                    "WHERE policy_id LIKE 'wakemu.mimik.%'"
                ).fetchone()["n"],
                8,
            )
        self.assertEqual((len(locations), len(policies), len(provenance)), (9, 5, 10))
        self.assertEqual({r["map_id"] for r in locations}, {301, 901, 909, 1458, 1460})
        for policy in policies:
            self.assertTrue(policy["sealed"])
            self.assertIn("Wakemu custom", policy["reconstruction_label"])
            self.assertIn("exclusive", policy["reconstruction_label"])
            self.assertIn("not recovered chest odds", policy["reconstruction_label"])

        rules = [
            service.definition(self.store, r["map_id"], r["object_id"])
            for r in locations
        ]
        for rule in rules:
            service._source(rule)
            self.assertEqual(sum(o["weight"] for o in rule["outcomes"]), 100)
            self.assertEqual(len(rule["outcomes"]), 2)
            self.assertEqual(rule["outcomes"][0]["quantity"], rule["qty"])
            self.assertEqual(rule["outcomes"][1]["quantity"], 1)
            self.assertEqual(rule["criterion"], "not IsHero()")
            self.assertTrue(
                {o["itemref"] for o in rule["outcomes"]}.isdisjoint({12325, 26554})
            )

        original = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "paid_container_contextual_native_dungeons.json"
            ).read_text()
        )
        dungeons = {r["id"]: r for r in original["definitions"]}
        monsters = {}
        for source in provenance:
            self.assertEqual(source["catalog_revision"], native_catalog.release())
            dungeon = dungeons[source["dungeon_id"]]
            associated = [r for r in rules if r["policy_id"] == source["policy_id"]]
            self.assertTrue(associated)
            self.assertTrue(all(r["map_id"] in dungeon["aHA"] for r in associated))
            self.assertIn(source["monster_reference"], dungeon["cno"])
            key = source["monster_reference"]
            if key not in monsters:
                monsters[key] = native_catalog.record(
                    DATA_ROOT / source["native_document"],
                    source["native_collection"],
                    str(key),
                )
            self.assertIsNotNone(monsters[key])
            matches = [
                d
                for d in monsters[key]["combat_drops"]
                if d["reference_id"] == source["item_reference"]
                and not d["is_loot_table"]
                and not d["complex_criteria"]
                and not d["conditions"]
                and Decimal(str(d["probability"])) == source["native_probability"]
                and (d["quantity_min"], d["quantity_max"])
                == (source["native_quantity_min"], source["native_quantity_max"])
            ]
            self.assertTrue(matches, (key, source["item_reference"]))
            outcome = next(
                o
                for o in associated[0]["outcomes"]
                if o["ordinal"] == source["ordinal"]
            )
            self.assertEqual(outcome["itemref"], source["item_reference"])
            if source["item_equipment_level"] is not None:
                equipment = native_catalog.record(
                    DATA_ROOT / "item-equipment-rules.json",
                    "items",
                    str(source["item_reference"]),
                )
                self.assertEqual(
                    equipment["minimum_level"], source["item_equipment_level"]
                )
                self.assertEqual(
                    Decimal(outcome["weight"]) / 100, source["native_probability"]
                )
        with self.assertRaises(DatabaseError):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE paid_container_contextual_item_sources SET native_probability=1 "
                    "WHERE policy_id=%s",
                    (policies[0]["policy_id"],),
                )

        account = self.store.register(
            "contextual-container-contract", "local-test-password"
        )["id"]
        character = self.store.create_character(account, "Contextual Container")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        bag = character["inventory_containers"][0]
        with self.store.connection() as db:
            grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=12324,
                quantity=20,
                container=bag["uid"],
                slot=0,
                allowed_references={12324},
                db=db,
            )

        def current():
            return self.store.character(account, character["id"])

        def quantity(reference):
            return sum(
                i["quantity"]
                for i in current()["inventory_items"]
                if i["reference"] == reference
            )

        def settle(rule, draw):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (rule["map_id"], *rule["approaches"][0], character["id"]),
                )
            started = service.begin(
                self.store,
                account,
                generation,
                current(),
                struct.pack(">qHH", rule["object_id"], 22, 0),
                loaded=True,
                is_hero=False,
                choose=lambda total: draw,
            )
            self.assertNotIn("selected_ordinal", started)
            due = self.store.now() + timedelta(seconds=2)
            with patch.object(self.store, "now", return_value=due):
                return service.finish(
                    self.store,
                    account,
                    generation,
                    current(),
                    started["token"],
                    struct.pack(">bh", 2, 28),
                    loaded=True,
                    is_hero=False,
                )

        # Higher-level Riktus: native five-input cost, one equipment reward,
        # no simultaneous resource. The same271 transaction is exercised.
        riktus = next(r for r in rules if r["map_id"] == 301)
        result = settle(riktus, 99)
        self.assertEqual(result["state"], "completed")
        self.assertEqual(
            (result["receipt"]["reference"], result["receipt"]["quantity"]), (26037, 1)
        )
        self.assertEqual(quantity(12324), 15)
        self.assertEqual(quantity(26037), 1)
        self.assertEqual(quantity(26584), 0)
        admitted = next(
            i for i in current()["inventory_items"] if i["reference"] == 26037
        )
        self.assertGreater(admitted["uid"], 0)
        # A Neo source uses its own original family and a stackable material,
        # rather than inheriting an ordinary Piou observed-family reward.
        neo = next(r for r in rules if r["map_id"] == 1460)
        result = settle(neo, 0)
        self.assertEqual(
            (result["receipt"]["reference"], result["receipt"]["quantity"]), (2702, 2)
        )
        self.assertEqual(quantity(12324), 13)
        self.assertEqual(quantity(2702), 2)
        self.assertEqual(quantity(9552), 0)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM paid_container_attempts "
                    "WHERE character_id=%s AND state='completed'",
                    (character["id"],),
                ).fetchone()["n"],
                2,
            )
