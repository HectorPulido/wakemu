"""Transactional random-box ownership, delivery, rollback and empty outcomes."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.characters import heroes
from wakfu_server.haven_bag_furniture_knowledge import _rules
from wakfu_server.inventory_items import grant
from wakfu_server.random_item_actions import use


class RandomItemActionsPostgresTests(PostgresCase):
    def fixture(self, hero=False):
        account = self.store.register("random-box-test", "local-password")["id"]
        main = self.store.create_character(account, "Random Box Main")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        owner = main
        if hero:
            owner = self.store.create_character(account, "Random Box Hero")
            heroes.add(self.store, account, generation, main["id"], owner["id"])
        return account, generation, main, owner

    def give(self, account, generation, character, reference, quantity=1, slot=0):
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

    def test_active_hero_box_consumes_one_and_typed_reward_persists(self):
        account, generation, main, owner = self.fixture(hero=True)
        box = self.give(account, generation, owner, 12408, 1)
        result = use(
            self.store,
            account,
            generation,
            main["id"],
            self.body(12408, box["uid"]),
            in_fight=False,
        )
        self.assertEqual(owner["id"], result["character"]["id"])
        self.assertEqual(("bHJ", 1), (result["native_class"], result["consumed"]))
        items = self.reopen().character(account, owner["id"])["inventory_items"]
        self.assertEqual(1, len(items))
        self.assertIn(items[0]["reference"], {12127, 12131, 12130})
        self.assertEqual(1, items[0]["quantity"])
        self.assertIn(
            (13817, struct.pack(">i", items[0]["reference"])), result["packets"]
        )
        with self.assertRaises(ValueError):
            use(
                self.store,
                account,
                generation,
                main["id"],
                self.body(12408, box["uid"]),
                in_fight=False,
            )

    def test_failed_delivery_replays_same_draw_and_preserves_source_and_counter(self):
        account, generation, main, owner = self.fixture()
        box = self.give(account, generation, owner, 12408, 2)
        from wakfu_server.item_action_delivery import grant_outputs

        outcomes = []

        def fail(*args):
            outcomes.append(dict(args[-1]))
            raise ValueError("Inventory capacity fixture")

        with patch("wakfu_server.item_action_delivery.grant_outputs", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "capacity"):
                use(
                    self.store,
                    account,
                    generation,
                    main["id"],
                    self.body(12408, box["uid"]),
                    in_fight=False,
                )
        with self.store.connection() as db:
            self.assertEqual(
                2,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (box["uid"],)
                ).fetchone()["quantity"],
            )
            self.assertIsNone(
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (box["uid"],),
                ).fetchone()
            )

        def deliver(*args):
            outcomes.append(dict(args[-1]))
            return grant_outputs(*args)

        with patch(
            "wakfu_server.item_action_delivery.grant_outputs", side_effect=deliver
        ):
            use(
                self.store,
                account,
                generation,
                main["id"],
                self.body(12408, box["uid"]),
                in_fight=False,
            )
        self.assertEqual(outcomes[0], outcomes[1])
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (box["uid"],),
                ).fetchone()["next_use"],
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (box["uid"],)
                ).fetchone()["quantity"],
            )

    def test_empty_outcome_consumes_without_grant_and_unavailable_box_is_preserved(
        self,
    ):
        account, generation, main, owner = self.fixture()
        box = self.give(account, generation, owner, 19310, 1)
        with patch("wakfu_server.random_item_actions.draw_products", return_value={}):
            result = use(
                self.store,
                account,
                generation,
                main["id"],
                self.body(19310, box["uid"]),
                in_fight=False,
            )
        self.assertTrue(result["applied"])
        self.assertEqual([], result["character"]["inventory_items"])
        self.assertEqual([12470], [opcode for opcode, _ in result["packets"]])
        unavailable = self.give(account, generation, owner, 14060, 1)
        with self.assertRaisesRegex(ValueError, "datos nativos"):
            use(
                self.store,
                account,
                generation,
                main["id"],
                self.body(14060, unavailable["uid"]),
                in_fight=False,
            )
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (unavailable["uid"],),
                ).fetchone()["quantity"],
            )

    def test_native_use_criterion_denies_before_draw_and_stale_lease_without_mutation(
        self,
    ):
        from unittest.mock import patch

        account, generation, main, owner = self.fixture()
        denied = self.give(account, generation, owner, 18015, 1)
        before_character = self.reopen().character(account, main["id"])
        with self.store.connection() as db:
            before_nonce = db.execute(
                "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                (denied["uid"],),
            ).fetchone()
            before_money = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
            ).fetchone()["kamas"]
            before_xp = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (main["id"],),
            ).fetchone()["xp"]
        with patch(
            "wakfu_server.random_item_actions.PrivateDraw",
            side_effect=AssertionError("draw must not happen"),
        ):
            with self.assertRaisesRegex(ValueError, "condiciones"):
                use(
                    self.store,
                    account,
                    generation,
                    main["id"],
                    self.body(18015, denied["uid"]),
                    in_fight=False,
                )
        after_character = self.reopen().character(account, main["id"])
        self.assertEqual(
            before_character["inventory_items"], after_character["inventory_items"]
        )
        with self.store.connection() as db:
            self.assertEqual(
                before_money,
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
                ).fetchone()["kamas"],
            )
            self.assertEqual(
                before_xp,
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (main["id"],),
                ).fetchone()["xp"],
            )
            self.assertEqual(
                before_nonce,
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (denied["uid"],),
                ).fetchone(),
            )

        winning = self.give(account, generation, owner, 12408, 1, slot=1)
        accepted = use(
            self.store,
            account,
            generation,
            main["id"],
            self.body(12408, winning["uid"]),
            in_fight=False,
        )
        dialog = next(
            payload for opcode, payload in accepted["packets"] if opcode == 13817
        )
        product_reference = struct.unpack(">i", dialog)[0]
        self.assertTrue(
            any(
                row["reference"] == product_reference
                for row in accepted["character"]["inventory_items"]
            )
        )

        stale_source = self.give(account, generation, owner, 12408, 1, slot=2)
        fresh_generation = self.store.begin_session(account)
        with patch(
            "wakfu_server.random_item_actions.PrivateDraw",
            side_effect=AssertionError("stale lease must not draw"),
        ):
            with self.assertRaises(ValueError):
                use(
                    self.store,
                    account,
                    generation,
                    main["id"],
                    self.body(12408, stale_source["uid"]),
                    in_fight=False,
                )
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (stale_source["uid"],),
                ).fetchone()["quantity"],
            )
            self.assertIsNone(
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (stale_source["uid"],),
                ).fetchone()
            )
        self.assertGreater(fresh_generation, generation)
