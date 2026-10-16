"""UID-only item actions mutate the active hero without selecting it as main."""
import struct

from postgres_case import PostgresCase
from wakfu_server.characters import heroes
from wakfu_server.inventory_items import grant
from wakfu_server.shard_identification import identify
from wakfu_server.element_selection import select
from wakfu_server.recycling import recycle
from wakfu_server.recycling_wire import request


class HeroInventoryMutationTests(PostgresCase):
    def fixture(self, *, reference=2869, quantity=5, active=True):
        account = self.store.register("hero-item-mutations", "local-password")["id"]
        main = self.store.create_character(account, "Mutation Main")
        hero = self.store.create_character(account, "Mutation Hero")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, hero["id"])
        unit = grant(
            self.store,
            account,
            generation,
            hero["id"],
            reference=reference,
            quantity=quantity,
            container=hero["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={reference},
        )
        self.store.select_character(account, generation, main["id"])
        if active:
            heroes.add(self.store, account, generation, main["id"], hero["id"])
        return account, generation, main, hero, unit

    def assert_main_selected(self, account, main):
        with self.store.connection() as db:
            selected = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (account,)
            ).fetchone()["character_id"]
        self.assertEqual(selected, main["id"])
        self.assertEqual(
            self.store.character(account, main["id"])["inventory_items"], []
        )

    def test_identification_and_elements_target_hero_and_split_one_only(self):
        account, generation, main, hero, unit = self.fixture()
        body = struct.pack(">q", unit["uid"])
        result = identify(
            self.store, account, generation, main["id"], body, randbelow=lambda _: 0
        )
        self.assertEqual(result["character_id"], hero["id"])
        self.assertTrue(result["applied"])
        items = self.store.character(account, hero["id"])["inventory_items"]
        self.assertEqual(sorted(item["quantity"] for item in items), [1, 4])
        self.assertEqual(
            next(item["quantity"] for item in items if item["uid"] == unit["uid"]), 1
        )
        repeated = identify(
            self.store,
            account,
            generation,
            main["id"],
            body,
            randbelow=lambda _: self.fail("Identification retry rerolled"),
        )
        self.assertFalse(repeated["applied"])
        chosen = select(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">qBB", unit["uid"], 26, 0),
        )
        self.assertEqual(chosen["character_id"], hero["id"])
        self.assertEqual(chosen["damage_elements"], 26)
        items = self.reopen().character(account, hero["id"])["inventory_items"]
        self.assertEqual(sorted(item["quantity"] for item in items), [1, 4])
        self.assert_main_selected(account, main)

    def test_inactive_owned_hero_identification_rejected_without_split(self):
        account, generation, main, hero, unit = self.fixture(active=False)
        with self.assertRaisesRegex(ValueError, "inactive hero"):
            identify(
                self.store,
                account,
                generation,
                main["id"],
                struct.pack(">q", unit["uid"]),
            )
        items = self.store.character(account, hero["id"])["inventory_items"]
        self.assertEqual(
            [(item["uid"], item["quantity"]) for item in items], [(unit["uid"], 5)]
        )
        self.assert_main_selected(account, main)

    def test_foreign_account_uid_is_rejected_without_mutation(self):
        account, generation, main, _, _ = self.fixture()
        other_account = self.store.register("foreign-item-owner", "local-password")[
            "id"
        ]
        other = self.store.create_character(other_account, "Foreign Item Owner")
        with self.store.connection() as db:
            uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,2869,3,%s,0) RETURNING uid",
                (other["id"], other["inventory_containers"][0]["uid"]),
            ).fetchone()["uid"]
        with self.assertRaisesRegex(ValueError, "inactive hero"):
            identify(
                self.store, account, generation, main["id"], struct.pack(">q", uid)
            )
        self.assertEqual(
            self.store.character(other_account, other["id"])["inventory_items"][0][
                "quantity"
            ],
            3,
        )
        self.assert_main_selected(account, main)

    def test_hero_recycling_products_and_receipt_replay_keep_owner(self):
        account, generation, main, hero, unit = self.fixture(
            reference=27083, quantity=3
        )
        body = request([unit["uid"]])[1]
        result = recycle(
            self.store,
            account,
            generation,
            main["id"],
            body,
            rng=lambda: self.fail("Fixed yield must not draw RNG"),
        )
        self.assertEqual(result["character"]["id"], hero["id"])
        self.assertEqual(result["receipt"]["character_id"], hero["id"])
        self.assertTrue(result["applied"])
        items = self.reopen().character(account, hero["id"])["inventory_items"]
        self.assertEqual(
            [(item["reference"], item["quantity"]) for item in items], [(27093, 3)]
        )
        repeated = recycle(
            self.store,
            account,
            generation,
            main["id"],
            body,
            rng=lambda: self.fail("Receipt retry rerolled"),
        )
        self.assertFalse(repeated["applied"])
        self.assertEqual(repeated["character"]["id"], hero["id"])
        self.assertEqual(
            items, self.store.character(account, hero["id"])["inventory_items"]
        )
        self.assert_main_selected(account, main)

    def test_recycling_mixed_owner_selection_rolls_back_all_units(self):
        account, generation, main, hero, unit = self.fixture(
            reference=27083, quantity=3
        )
        main_unit = grant(
            self.store,
            account,
            generation,
            main["id"],
            reference=27083,
            quantity=2,
            container=main["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={27083},
        )
        with self.assertRaisesRegex(ValueError, "multiple characters"):
            recycle(
                self.store,
                account,
                generation,
                main["id"],
                request([unit["uid"], main_unit["uid"]])[1],
            )
        self.assertEqual(
            self.store.character(account, hero["id"])["inventory_items"][0]["quantity"],
            3,
        )
        self.assertEqual(
            self.store.character(account, main["id"])["inventory_items"][0]["quantity"],
            2,
        )

    def test_resolved_hero_durable_combat_blocks_identification(self):
        account, generation, main, hero, unit = self.fixture()
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight, hero["id"], account),
            )
        for action, body in (
            (identify, struct.pack(">q", unit["uid"])),
            (select, struct.pack(">qBB", unit["uid"], 26, 0)),
        ):
            with self.subTest(action=action.__name__), self.assertRaisesRegex(
                ValueError, "during combat"
            ):
                action(self.store, account, generation, main["id"], body)
        self.assertEqual(
            self.store.character(account, hero["id"])["inventory_items"][0]["quantity"],
            5,
        )
