"""Focused tests for native exchange-machine decoding and purchases."""
import copy
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server.items import exchange_machine, quest_inventory


CATALOG = {
    "version": 1,
    "machines": [
        {
            "id": 265,
            "offers": [
                {
                    "id": 10176,
                    "kamas_cost": 0,
                    "alternate_currency_cost": 0,
                    "offer_flag": 0,
                    "criteria": "",
                    "costs": [{"reference": 12686, "quantity": 30}],
                    "rewards": [
                        {
                            "reference": 12827,
                            "quantity": 1,
                            "binding_id": 0,
                            "raw_cnH": False,
                        }
                    ],
                }
            ],
        }
    ],
    "placements": [
        {"id": 34600, "map_id": 527, "machine_id": 265, "x": -1, "y": 27, "z": 0}
    ],
}


def body(actor_id, *, quantity=1, offer_id=10176, catalog_id=265, object_id=34600):
    return struct.pack(">iqihq", catalog_id, object_id, offer_id, quantity, actor_id)


class ExchangeMachineWireTests(unittest.TestCase):
    def test_decode_exact_native_fields_and_reject_malformed_values(self):
        decoded = exchange_machine.decode(body(29, quantity=2))
        self.assertEqual(
            decoded,
            {
                "catalog_id": 265,
                "object_id": 34600,
                "offer_id": 10176,
                "quantity": 2,
                "actor_id": 29,
            },
        )
        for malformed in (
            b"",
            body(29)[:-1],
            body(29, quantity=0),
            body(29, catalog_id=0),
            body(29, offer_id=0),
            body(29, object_id=0),
        ):
            with self.subTest(payload=malformed), self.assertRaises(ValueError):
                exchange_machine.decode(malformed)

    def test_station_uses_registered_machine_and_shared_interaction_policy(self):
        request = exchange_machine.decode(body(29))
        actor = {"map_id": 527, "instance_id": 0, "x": 0, "y": 27, "z": 0}
        station = exchange_machine.station(actor, request, document=CATALOG)
        self.assertEqual(
            station,
            {
                "object_id": 34600,
                "catalog_id": 265,
                "map_id": 527,
                "instance_id": 0,
                "in_range": True,
            },
        )
        instance_station = exchange_machine.station(
            {**actor, "instance_id": 1}, request, document=CATALOG
        )
        self.assertEqual(instance_station["instance_id"], 1)
        for changed in (
            {**actor, "x": 10},
            {**actor, "map_id": 9},
            {**actor, "instance_id": -1},
            {**actor, "z": 4},
        ):
            with self.subTest(actor=changed), self.assertRaises(ValueError):
                exchange_machine.station(changed, request, document=CATALOG)
        with self.assertRaises(ValueError):
            exchange_machine.station(
                actor, {**request, "catalog_id": 44}, document=CATALOG
            )


class ExchangeMachinePurchaseTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("croupier-owner", "local-password")["id"]
        self.main = self.store.create_character(self.account, "Croupier Main")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=0,y=27,z=0 WHERE id=%s",
                (self.main["id"],),
            )
        self.main = self.store.character(self.account, self.main["id"])
        self.location = self.main

    def grant_tokens(self, character_id, quantity):
        with self.store.connection() as db:
            quest_inventory.grant(db, character_id, 12686, quantity)

    def grant_item(self, character_id, reference, quantity, slot):
        from wakfu_server.inventory_items import grant

        character = self.store.character(self.account, character_id)
        return grant(
            self.store,
            self.account,
            self.generation,
            character_id,
            reference=reference,
            quantity=quantity,
            container=character["inventory_containers"][0]["uid"],
            slot=slot,
            allowed_references={reference},
        )

    def set_wallet(self, kamas):
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
                (kamas, self.account),
            )

    def buy(
        self,
        actor_id,
        *,
        quantity=1,
        offer=None,
        location=None,
        station=None,
        document=None,
        catalog_id=265,
        object_id=34600
    ):
        selected_document = copy.deepcopy(CATALOG) if document is None else document
        request_body = body(
            actor_id,
            quantity=quantity,
            offer_id=offer or 10176,
            catalog_id=catalog_id,
            object_id=object_id,
        )
        resolved_station = (
            exchange_machine.station(
                self.location,
                exchange_machine.decode(request_body),
                document=selected_document,
            )
            if station is None
            else station
        )
        return exchange_machine.purchase(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            request_body,
            location=self.location if location is None else location,
            document=selected_document,
            station=resolved_station,
        )

    def test_personal_token_purchase_and_repeated_identical_purchase_are_distinct(self):
        self.grant_tokens(self.main["id"], 60)
        first = self.buy(self.main["id"])
        second = self.buy(self.main["id"])
        saved = self.store.character(self.account, self.main["id"])
        self.assertEqual(first["request"]["offer_id"], 10176)
        self.assertEqual(second["request"], first["request"])
        self.assertEqual(saved["quest_items"], [])
        rewards = [row for row in saved["inventory_items"] if row["reference"] == 12827]
        self.assertEqual(sum(row["quantity"] for row in rewards), 2)
        self.assertEqual([packet[0] for packet in first["packets"]], [13879])
        self.assertEqual([packet[0] for packet in second["packets"]], [13879])

    def test_active_hero_can_spend_its_quest_items_without_switching_main(self):
        from wakfu_server.characters import heroes

        hero = self.store.create_character(self.account, "Croupier Hero")
        heroes.add(
            self.store, self.account, self.generation, self.main["id"], hero["id"]
        )
        self.grant_tokens(hero["id"], 30)
        result = self.buy(hero["id"])
        self.assertEqual(result["character"]["id"], hero["id"])
        saved_hero = self.store.character(self.account, hero["id"])
        self.assertEqual(saved_hero["quest_items"], [])
        self.assertEqual(
            sum(
                row["quantity"]
                for row in saved_hero["inventory_items"]
                if row["reference"] == 12827
            ),
            1,
        )
        self.assertEqual(
            self.store.character(self.account, self.main["id"])["inventory_items"], []
        )
        with self.store.connection() as db:
            selected = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (self.account,)
            ).fetchone()["character_id"]
        self.assertEqual(selected, self.main["id"])

    def test_multi_cost_purchase_splits_physical_stacks_and_multiplies_every_cost(self):
        self.grant_item(self.main["id"], 12237, 1, 0)
        self.grant_item(self.main["id"], 12237, 3, 1)
        self.grant_item(self.main["id"], 26555, 1, 2)
        self.grant_item(self.main["id"], 26555, 1, 3)
        self.grant_tokens(self.main["id"], 10)
        self.set_wallet(1000)
        document = copy.deepcopy(CATALOG)
        offer = document["machines"][0]["offers"][0]
        offer.update(
            kamas_cost=250,
            costs=[
                {"reference": 12237, "quantity": 2},
                {"reference": 26555, "quantity": 1},
                {"reference": 12686, "quantity": 5},
            ],
            # Native catalog override 4 is ignored; ordinary item template binding applies.
            rewards=[
                {"reference": 12827, "quantity": 1, "binding_id": 4, "raw_cnH": False}
            ],
        )
        result = self.buy(self.main["id"], quantity=2, document=document)
        saved = self.store.character(self.account, self.main["id"])
        self.assertEqual(saved["quest_items"], [])
        self.assertFalse(
            any(row["reference"] in (12237, 26555) for row in saved["inventory_items"])
        )
        reward_rows = [
            row for row in saved["inventory_items"] if row["reference"] == 12827
        ]
        self.assertEqual(sum(row["quantity"] for row in reward_rows), 2)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                500,
            )
        self.assertEqual([opcode for opcode, _ in result["packets"]], [13879, 12753])
        self.assertEqual(struct.unpack(">q", result["packets"][1][1])[0], 500)

    def test_insufficient_wallet_rejects_without_cost_or_reward_mutation(self):
        self.set_wallet(499)
        document = copy.deepcopy(CATALOG)
        offer = document["machines"][0]["offers"][0]
        offer.update(kamas_cost=500, costs=[])
        with self.assertRaisesRegex(ValueError, "Insufficient kamas"):
            self.buy(self.main["id"], document=document)
        saved = self.store.character(self.account, self.main["id"])
        self.assertEqual(saved["inventory_items"], [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                499,
            )

    def test_insufficient_cost_and_untrusted_station_leave_tokens_and_inventory_unchanged(
        self,
    ):
        self.grant_tokens(self.main["id"], 29)
        with self.assertRaisesRegex(ValueError, "Insufficient native quest-item"):
            self.buy(self.main["id"])
        self.assertEqual(
            self.store.character(self.account, self.main["id"])["quest_items"][0][
                "quantity"
            ],
            29,
        )
        with self.assertRaisesRegex(ValueError, "Missing authorized"):
            self.buy(self.main["id"], station={"in_range": False})
        saved = self.store.character(self.account, self.main["id"])
        self.assertEqual(saved["quest_items"][0]["quantity"], 29)
        self.assertFalse(
            any(row["reference"] == 12827 for row in saved["inventory_items"])
        )

    def test_full_inventory_rolls_back_spent_quest_tokens(self):
        self.grant_tokens(self.main["id"], 1)
        self.set_wallet(100)
        with self.store.connection() as db:
            bags = db.execute(
                "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s "
                "AND kind IN (0,1,2,3) ORDER BY uid",
                (self.main["id"],),
            ).fetchall()
            for bag in bags:
                for slot in range(bag["capacity"]):
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,2021,1,%s,%s)",
                        (self.main["id"], bag["uid"], slot),
                    )
                    db.execute(
                        "UPDATE inventory_items SET quantity=2 WHERE character_id=%s "
                        "AND container=%s AND slot=%s",
                        (self.main["id"], bag["uid"], slot),
                    )
        document = copy.deepcopy(CATALOG)
        offer = document["machines"][0]["offers"][0]
        offer.update(
            kamas_cost=20,
            costs=[
                {"reference": 2021, "quantity": 1},
                {"reference": 12686, "quantity": 1},
            ],
        )
        before = self.store.character(self.account, self.main["id"])
        with self.assertRaisesRegex(ValueError, "inventory capacity"):
            self.buy(self.main["id"], document=document)
        after = self.store.character(self.account, self.main["id"])
        self.assertEqual(after["quest_items"][0]["quantity"], 1)
        before_physical = [
            (row["uid"], row["quantity"]) for row in before["inventory_items"]
        ]
        after_physical = [
            (row["uid"], row["quantity"]) for row in after["inventory_items"]
        ]
        self.assertEqual(after_physical, before_physical)
        self.assertFalse(
            any(row["reference"] == 12827 for row in after["inventory_items"])
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                100,
            )

    def test_foreign_and_inactive_hero_actors_are_rejected(self):
        self.grant_tokens(self.main["id"], 30)
        inactive = self.store.create_character(self.account, "Inactive Croupier Hero")
        with self.assertRaisesRegex(ValueError, "unavailable or foreign|inactive hero"):
            self.buy(inactive["id"])
        foreign_account = self.store.register("foreign-croupier", "local-password")[
            "id"
        ]
        foreign = self.store.create_character(foreign_account, "Foreign Croupier")
        with self.assertRaises(ValueError):
            self.buy(foreign["id"])
        self.assertEqual(
            self.store.character(self.account, self.main["id"])["quest_items"][0][
                "quantity"
            ],
            30,
        )
        self.assertFalse(
            any(
                row["reference"] == 12827
                for row in self.store.character(self.account, self.main["id"])[
                    "inventory_items"
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
