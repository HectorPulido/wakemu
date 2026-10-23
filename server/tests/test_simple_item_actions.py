"""PostgreSQL integration for native fixed, merge, kama and XP item actions."""
import struct
import unittest
from pathlib import Path

from postgres_case import PostgresCase
from wakfu_server.characters import heroes
from wakfu_server.inventory_items import grant
from wakfu_server.simple_item_actions import action_class, use
from wakfu_server.combat_drop_delivery import _container_can_hold
from wakfu_server.haven_bag_furniture_knowledge import _rules


class SimpleItemActionsPostgresTests(PostgresCase):
    def fixture(self, *, username="simple-item", hero=False):
        account = self.store.register(username, "local-password")["id"]
        main = self.store.create_character(account, "Simple Item Main")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        owner = main
        if hero:
            owner = self.store.create_character(account, "Simple Item Hero")
            heroes.add(self.store, account, generation, main["id"], owner["id"])
        return account, generation, main, owner

    def give(self, account, generation, character, reference, quantity=1, slot=0):
        character = self.store.character(account, character["id"])
        container = next(
            row for row in character["inventory_containers"] if row["kind"] == 0
        )
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=quantity,
            container=container["uid"],
            slot=slot,
            allowed_references={reference},
        )

    def body(self, reference, uid):
        return struct.pack(">iq", _rules()[reference]["use_action_id"], uid)

    def quantities(self, account, character):
        return sorted(
            (item["reference"], item["quantity"])
            for item in self.store.character(account, character["id"])[
                "inventory_items"
            ]
        )

    def test_fixed_pack_and_fragment_merge_consume_native_quantities_and_persist(self):
        account, generation, _, character = self.fixture()
        fixed = self.give(account, generation, character, 1853, quantity=2, slot=0)
        result = use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(1853, fixed["uid"]),
            in_fight=False,
        )
        self.assertEqual(
            (result["native_class"], result["consumed"], result["applied"]),
            ("bHI", 1, True),
        )
        self.assertCountEqual(
            self.quantities(account, character), [(1853, 1), (11484, 1)]
        )

        occupied = {
            item["slot"]
            for item in self.store.character(account, character["id"])[
                "inventory_items"
            ]
        }
        fragment_slot = next(slot for slot in range(30) if slot not in occupied)
        fragment = self.give(
            account, generation, character, 27526, quantity=100, slot=fragment_slot
        )
        result = use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(27526, fragment["uid"]),
            in_fight=False,
        )
        self.assertEqual((result["native_class"], result["consumed"]), ("bHS", 100))
        self.assertCountEqual(
            self.quantities(account, character), [(1853, 1), (11484, 1), (27354, 1)]
        )
        reopened = self.reopen()
        self.assertCountEqual(
            sorted(
                (item["reference"], item["quantity"])
                for item in reopened.character(account, character["id"])[
                    "inventory_items"
                ]
            ),
            [(1853, 1), (11484, 1), (27354, 1)],
        )

    def test_kama_and_xp_rewards_persist_for_active_hero_without_selecting_it(self):
        account, generation, main, hero = self.fixture(
            username="simple-hero", hero=True
        )
        kama = self.give(account, generation, hero, 8050)
        with self.store.connection() as db:
            kamas_before = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
            ).fetchone()["kamas"]
        result = use(
            self.store,
            account,
            generation,
            main["id"],
            self.body(8050, kama["uid"]),
            in_fight=False,
        )
        self.assertEqual(
            (result["native_class"], result["character"]["id"]), ("bHy", hero["id"])
        )
        with self.store.connection() as db:
            kamas_after = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
            ).fetchone()["kamas"]
        self.assertEqual(kamas_after, kamas_before + 150)
        self.assertEqual(self.quantities(account, hero), [])

        # Original template USE for scroll20026 requires real level40.
        from wakfu_server.progression import level_xp

        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=40 WHERE id=%s", (hero["id"],))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(40), hero["id"]),
            )
        xp_item = self.give(account, generation, hero, 20026)
        before = self.store.character(account, hero["id"])
        result = use(
            self.store,
            account,
            generation,
            main["id"],
            self.body(20026, xp_item["uid"]),
            in_fight=False,
        )
        after = self.reopen().character(account, hero["id"])
        self.assertEqual(
            (result["native_class"], result["character"]["id"]), ("bHK", hero["id"])
        )
        self.assertEqual(after["xp"], before["xp"] + 380000)
        self.assertEqual(after["inventory_items"], [])
        with self.store.connection() as db:
            selected = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (account,)
            ).fetchone()["character_id"]
        self.assertEqual(selected, main["id"])

    def test_admin_and_native_map_criteria_are_evaluated_before_consumption(self):
        account, generation, _, character = self.fixture()
        admin_pack = self.give(account, generation, character, 30804)
        with self.assertRaisesRegex(ValueError, "condiciones"):
            use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(30804, admin_pack["uid"]),
                in_fight=False,
            )
        self.assertEqual(self.quantities(account, character), [(30804, 1)])
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (account,))
        result = use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(30804, admin_pack["uid"]),
            in_fight=False,
        )
        self.assertTrue(result["applied"])
        self.assertCountEqual(
            self.quantities(account, character), [(30804, 1), (27083, 9999)]
        )

        map_item = self.give(account, generation, character, 17851, quantity=3, slot=2)
        with self.assertRaisesRegex(ValueError, "condiciones"):
            use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(17851, map_item["uid"]),
                in_fight=False,
                native_map_id=30804,
            )
        result = use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(17851, map_item["uid"]),
            in_fight=False,
            native_map_id=723,
        )
        self.assertTrue(result["applied"])
        self.assertEqual(
            next(
                row["quantity"]
                for row in result["character"]["quest_items"]
                if row["reference"] == 17821
            ),
            1,
        )

    def test_malformed_grammar_wrong_action_and_combat_leave_source_unchanged(self):
        account, generation, _, character = self.fixture()
        source = self.give(account, generation, character, 1853)
        good = self.body(1853, source["uid"])
        with self.assertRaises(ValueError):
            action_class(good + b"\x00")
        with self.assertRaises(ValueError):
            action_class(good[:11])
        with self.assertRaisesRegex(
            ValueError, "object does not correspond|corresponde"
        ):
            use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(2281, source["uid"]),
                in_fight=False,
            )
        with self.assertRaisesRegex(ValueError, "combate"):
            use(self.store, account, generation, character["id"], good, in_fight=True)
        self.assertEqual(self.quantities(account, character), [(1853, 1)])

    def test_active_database_fight_rejects_and_preserves_item(self):
        account, generation, _, character = self.fixture()
        source = self.give(account, generation, character, 1853)
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight, character["id"], account),
            )
        with self.assertRaisesRegex(ValueError, "combate"):
            use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(1853, source["uid"]),
                in_fight=False,
            )
        self.assertEqual(self.quantities(account, character), [(1853, 1)])

    def test_inactive_hero_and_foreign_account_items_are_rejected(self):
        account, generation, main, _ = self.fixture(
            username="inactive-simple-hero", hero=False
        )
        # The character exists under the account but is not in the active roster.
        hero = self.store.create_character(account, "Inactive Simple Hero")
        self.store.select_character(account, generation, hero["id"])
        hero_item = self.give(account, generation, hero, 1853)
        self.store.select_character(account, generation, main["id"])
        with self.assertRaises(ValueError):
            use(
                self.store,
                account,
                generation,
                main["id"],
                self.body(1853, hero_item["uid"]),
                in_fight=False,
            )
        self.assertEqual(self.quantities(account, hero), [(1853, 1)])

        foreign_account = self.store.register("foreign-simple-item", "local-password")[
            "id"
        ]
        foreign = self.store.create_character(foreign_account, "Foreign Simple Owner")
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(foreign_account, foreign_generation, foreign["id"])
        foreign_item = self.give(foreign_account, foreign_generation, foreign, 1853)
        with self.assertRaises(ValueError):
            use(
                self.store,
                account,
                generation,
                main["id"],
                self.body(1853, foreign_item["uid"]),
                in_fight=False,
            )
        self.assertEqual(self.quantities(foreign_account, foreign), [(1853, 1)])

    def test_delivery_uses_slot_freed_by_consumed_source(self):
        account, generation, _, character = self.fixture()
        source = self.give(account, generation, character, 1853)
        with self.store.connection() as db:
            containers = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=%s",
                    (character["id"],),
                ).fetchall()
            ]
            eligible = [
                row for row in containers if _container_can_hold(row, character["id"])
            ]
            source_container = next(
                row for row in eligible if row["uid"] == source["container"]
            )
            for bag in eligible:
                occupied = (
                    {source["slot"]} if bag["uid"] == source_container["uid"] else set()
                )
                for slot in range(bag["capacity"]):
                    if slot not in occupied:
                        db.execute(
                            "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,1,1,%s,%s)",
                            (character["id"], bag["uid"], slot),
                        )
        result = use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(1853, source["uid"]),
            in_fight=False,
        )
        self.assertTrue(result["applied"])
        self.assertEqual(self.quantities(account, character).count((11484, 1)), 1)

    def test_delivery_capacity_failure_rolls_back_source_consumption(self):
        account, generation, _, character = self.fixture()
        source = self.give(account, generation, character, 1853, quantity=2)
        with self.store.connection() as db:
            containers = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=%s",
                    (character["id"],),
                ).fetchall()
            ]
            eligible = [
                row for row in containers if _container_can_hold(row, character["id"])
            ]
            for bag in eligible:
                if bag["uid"] == source["container"]:
                    occupied = {source["slot"]}
                else:
                    occupied = set()
                for slot in range(bag["capacity"]):
                    if slot not in occupied:
                        db.execute(
                            "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,1853,1,%s,%s)",
                            (character["id"], bag["uid"], slot),
                        )
        before = self.quantities(account, character)
        with self.assertRaises(ValueError):
            use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(1853, source["uid"]),
                in_fight=False,
            )
        self.assertEqual(self.quantities(account, character), before)


class SimpleItemActionRouterSourceTests(unittest.TestCase):
    def test_native_simple_action_router_precedes_the_learning_dispatch_exactly_once(
        self,
    ):
        source = (
            Path(__file__).resolve().parents[1] / "local_game_server.py"
        ).read_text()
        branch = "elif opcode == 13220 and loaded:"
        self.assertEqual(source.count(branch), 1)
        route = source.index(branch)
        simple_dispatch = source.index("simple_item_action_class(body)", route)
        learning_dispatch = source.index("request_action_class(body)", route)
        self.assertLess(simple_dispatch, learning_dispatch)
