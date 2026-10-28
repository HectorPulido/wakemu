"""Opted buyer purchases dispose and replenish inside the real exchange commit."""
import struct
from unittest.mock import patch

from psycopg.errors import RaiseException
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from test_player_exchanges import PlayerExchangeInvitationTests as Fixtures
from wakfu_server import player_exchanges


class BotPurchaseSinkPostgresTests(PostgresCase):
    player = Fixtures.player
    invite = Fixtures.invite
    active_exchange = Fixtures.active_exchange
    publish_current = Fixtures.publish_current
    inventory_rows = Fixtures.inventory_rows
    set_wallets = Fixtures.set_wallets
    grant_item = Fixtures.grant_item
    fetchone = Fixtures.fetchone
    fetchall = Fixtures.fetchall

    def setUp(self):
        super().setUp()
        self.now = 2_000_000_000.0
        self.store.clock = lambda: self.now

    def bot(self, bot_id, *, opted=True):
        owner = self.player(bot_id)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO world_bots(bot_id,account_id,character_id,capabilities) "
                "VALUES(%s,%s,%s,%s)",
                (
                    bot_id,
                    owner["account"],
                    owner["character"]["id"],
                    Jsonb(["exchange"]),
                ),
            )
            if opted:
                before = db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY uid",
                    (owner["character"]["id"],),
                ).fetchall()
                db.execute(
                    "INSERT INTO world_bot_purchase_sinks(bot_id,enabled) VALUES(%s,true)",
                    (bot_id,),
                )
                self.assertEqual(
                    db.execute(
                        "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY uid",
                        (owner["character"]["id"],),
                    ).fetchall(),
                    before,
                )
        self.set_wallets((owner, 1000))
        return owner

    def wallet(self, owner):
        return self.fetchone(
            "SELECT kamas FROM account_wallets WHERE account_id=%s", (owner["account"],)
        )["kamas"]

    def audit(self):
        return self.fetchall(
            "SELECT * FROM world_bot_purchase_sink_receipts ORDER BY exchange_id,bot_id"
        )

    def offer_sale(self, seller, buyer, items, *, price=80):
        exchange = self.active_exchange(seller, buyer)
        for item, quantity in items:
            player_exchanges.offer_item(
                self.store,
                seller["account"],
                seller["generation"],
                seller["character"]["id"],
                exchange["id"],
                item["uid"],
                quantity,
            )
        player_exchanges.offer_kamas(
            self.store,
            buyer["account"],
            buyer["generation"],
            buyer["character"]["id"],
            exchange["id"],
            price,
        )
        self.publish_current(exchange, seller, buyer)
        first = self.confirm(seller, exchange)
        self.assertFalse(first["applied"])
        return exchange

    def confirm(self, owner, exchange):
        return player_exchanges.confirm(
            self.store,
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
            exchange["id"],
        )

    def apply_sink(self, exchange, bot_id):
        return self.fetchone(
            "SELECT apply_world_bot_purchase_sink(%s,%s) AS result",
            (exchange["id"], bot_id),
        )["result"]

    def test_repeated_sales_retry_cancel_and_unopted_bot_preserve_humans(self):
        seller = self.player("seller")
        buyer = self.bot("buyer")
        other_bot = self.bot("other-bot", opted=False)
        original = self.grant_item(buyer, 12, quantity=5)
        human_keep = self.grant_item(seller, 12, quantity=7, slot=1)

        for number in range(2):
            incoming = self.grant_item(seller, 12, quantity=3)
            exchange = self.offer_sale(seller, buyer, [(incoming, 3)])
            self.assertTrue(self.confirm(buyer, exchange)["applied"])
            self.assertEqual(self.wallet(buyer), 1000)
            self.assertEqual(self.wallet(seller), 80 * (number + 1))
            self.assertEqual(
                self.fetchone(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (original["uid"],),
                )["quantity"],
                5,
            )
            self.assertIsNone(
                self.fetchone(
                    "SELECT uid FROM inventory_items WHERE uid=%s", (incoming["uid"],)
                )
            )
            before = self.audit()
            self.assertFalse(self.confirm(buyer, exchange)["applied"])
            self.apply_sink(exchange, "buyer")
            self.assertEqual(self.audit(), before)
            self.assertEqual(self.wallet(buyer), 1000)

        self.assertEqual(len(self.audit()), 2)
        self.assertEqual([row["refunded_kamas"] for row in self.audit()], [80, 80])
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations/331_world_bot_purchase_sinks.sql"
        )
        before_replay = self.audit()
        with self.store.connection() as db:
            db.execute(migration.read_text(), prepare=False)
        self.assertEqual(self.audit(), before_replay)
        self.assertEqual(self.wallet(buyer), 1000)
        incoming = self.grant_item(seller, 12, quantity=3)
        canceled = self.offer_sale(seller, buyer, [(incoming, 3)])
        player_exchanges.cancel(
            self.store,
            seller["account"],
            seller["generation"],
            seller["character"]["id"],
            canceled["id"],
        )
        self.assertEqual(self.wallet(seller), 160)
        self.assertEqual(self.wallet(buyer), 1000)
        self.assertEqual(len(self.audit()), 2)
        ordinary = self.offer_sale(seller, other_bot, [(incoming, 3)])
        self.confirm(other_bot, ordinary)
        self.assertEqual(self.wallet(other_bot), 920)
        self.assertEqual(
            self.fetchone(
                "SELECT character_id FROM inventory_items WHERE uid=%s",
                (incoming["uid"],),
            )["character_id"],
            other_bot["character"]["id"],
        )
        self.assertEqual(len(self.audit()), 2)
        self.assertEqual(
            self.fetchone(
                "SELECT character_id,quantity FROM inventory_items WHERE uid=%s",
                (human_keep["uid"],),
            ),
            {"character_id": seller["character"]["id"], "quantity": 7},
        )

    def test_failure_after_sink_rolls_back_entire_sale_then_retry_commits_once(self):
        seller, buyer = self.player("seller"), self.bot("buyer")
        incoming = self.grant_item(seller, 12, quantity=3)
        exchange = self.offer_sale(seller, buyer, [(incoming, 3)])
        before = self.inventory_rows(seller, buyer)
        real_outbox = player_exchanges._outbox

        def fail_after_trigger(store, db, saved, event, *args, **kwargs):
            if event == "committed":
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM world_bot_purchase_sink_receipts"
                    ).fetchone()["n"],
                    1,
                )
                raise RuntimeError("rollback after buyer settlement")
            return real_outbox(store, db, saved, event, *args, **kwargs)

        with patch.object(player_exchanges, "_outbox", side_effect=fail_after_trigger):
            with self.assertRaisesRegex(
                RuntimeError, "rollback after buyer settlement"
            ):
                self.confirm(buyer, exchange)
        self.assertEqual(self.inventory_rows(seller, buyer), before)
        self.assertEqual((self.wallet(seller), self.wallet(buyer)), (0, 1000))
        self.assertEqual(self.audit(), [])
        self.assertEqual(
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
            0,
        )
        self.assertTrue(self.confirm(buyer, exchange)["applied"])
        self.assertEqual((self.wallet(seller), self.wallet(buyer)), (80, 1000))
        self.assertEqual(len(self.audit()), 1)

    def test_historical_backfill_rejects_missing_foreign_and_insufficient_items(self):
        seller, buyer = self.player("seller"), self.bot("buyer", opted=False)
        incoming = self.grant_item(seller, 12, quantity=3)
        exchange = self.offer_sale(seller, buyer, [(incoming, 3)])
        self.confirm(buyer, exchange)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO world_bot_purchase_sinks(bot_id,enabled) VALUES('buyer',true)"
            )
        seller_bag = self.fetchone(
            "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
            (seller["character"]["id"],),
        )["uid"]
        mutations = [
            ("DELETE FROM inventory_items WHERE uid=%s", (incoming["uid"],)),
            (
                "UPDATE inventory_items SET character_id=%s,container=%s,slot=0 WHERE uid=%s",
                (seller["character"]["id"], seller_bag, incoming["uid"]),
            ),
            ("UPDATE inventory_items SET quantity=2 WHERE uid=%s", (incoming["uid"],)),
        ]
        before = self.inventory_rows(seller, buyer)
        for statement, values in mutations:
            with self.subTest(statement=statement):
                with self.assertRaises(RaiseException):
                    with self.store.connection() as db:
                        db.execute(statement, values)
                        db.execute(
                            "SELECT apply_world_bot_purchase_sink(%s,'buyer')",
                            (exchange["id"],),
                        )
                self.assertEqual(self.inventory_rows(seller, buyer), before)
                self.assertEqual(self.audit(), [])
                self.assertEqual((self.wallet(seller), self.wallet(buyer)), (80, 920))
        self.apply_sink(exchange, "buyer")
        self.assertEqual((self.wallet(seller), self.wallet(buyer)), (80, 1000))
        self.assertEqual(self.inventory_rows(buyer), [])
        self.assertEqual(len(self.audit()), 1)

    def test_native_sadida_bags_accept_more_than_old_full_inventory_without_capacity_overrides(
        self,
    ):
        from wakfu_server import (
            inventory_bags,
            quest_inventory,
            account_quest_inventory,
        )
        from wakfu_server.exchange_rules import ITEMS, eligibility
        from wakfu_server.inventory_move import STACKS

        seller, buyer = self.player("seller"), self.bot("buyer")
        for owner in (seller, buyer):
            character_id = owner["character"]["id"]
            bags = self.fetchall(
                "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind",
                (character_id,),
            )
            base = next(bag for bag in bags if bag["kind"] == 0)
            for bag in bags:
                if bag["kind"] in (1, 2, 3):
                    inventory_bags.remove(
                        self.store,
                        owner["account"],
                        owner["generation"],
                        character_id,
                        struct.pack(
                            ">qqqqb",
                            base["uid"],
                            bag["uid"],
                            bag["uid"],
                            base["uid"],
                            -1,
                        ),
                    )
            for kind in (1, 2, 3):
                occupied = {
                    row["slot"]
                    for row in self.inventory_rows(owner)
                    if row["container"] == base["uid"]
                }
                slot = next(
                    index for index in range(base["capacity"]) if index not in occupied
                )
                bag = self.grant_item(owner, 12491, slot=slot)
                inventory_bags.equip(
                    self.store,
                    owner["account"],
                    owner["generation"],
                    character_id,
                    struct.pack(">qqqb", bag["uid"], base["uid"], character_id, kind),
                )
            actual = self.fetchall(
                "SELECT reference,kind,capacity FROM inventory_containers WHERE character_id=%s ORDER BY kind",
                (character_id,),
            )
            self.assertEqual(actual[0]["capacity"], base["capacity"])
            self.assertEqual(
                [(row["reference"], row["capacity"]) for row in actual[1:]],
                [(12491, 30)] * 3,
            )
            self.assertEqual(sum(row["capacity"] for row in actual), 120)

        references = []
        for reference, rule in sorted(STACKS.items()):
            if (
                str(reference) not in ITEMS
                or reference in quest_inventory.REFERENCES
                or reference in account_quest_inventory.REFERENCES
            ):
                continue
            try:
                eligible = eligibility(reference)
            except ValueError:
                continue
            if eligible:
                references.append(reference)
            if len(references) == 35:
                break
        self.assertEqual(len(references), 35)
        occupied = {
            (row["container"], row["slot"]) for row in self.inventory_rows(seller)
        }
        available = [
            (bag["kind"], slot)
            for bag in self.fetchall(
                "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind",
                (seller["character"]["id"],),
            )
            for slot in range(bag["capacity"])
            if (bag["uid"], slot) not in occupied
        ]
        items = [
            (self.grant_item(seller, reference, slot=slot, kind=kind), 1)
            for reference, (kind, slot) in zip(references, available)
        ]
        original_buyer_items = self.inventory_rows(buyer)
        exchange = self.offer_sale(seller, buyer, items, price=350)
        self.assertTrue(self.confirm(buyer, exchange)["applied"])
        self.assertEqual(self.inventory_rows(buyer), original_buyer_items)
        self.assertEqual((self.wallet(seller), self.wallet(buyer)), (350, 1000))
        self.assertEqual(len(self.audit()[0]["removed_items"]), 35)


def load_tests(loader, _tests, _pattern):
    return loader.loadTestsFromTestCase(BotPurchaseSinkPostgresTests)
