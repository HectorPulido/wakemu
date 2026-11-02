"""Buyer-only prices through real HTTP clients, native peers and SQL settlement."""
import struct
import threading
import uuid
from unittest.mock import patch

from test_bots_postgres import BotExchangePostgresAcceptanceTests
from wakfu_server.api import serve_api
from wakfu_server.bots.bridge import BotWorldBridge
from wakfu_server import player_exchanges
from wakfu_bots.behaviors import BuyerBehavior
from wakfu_bots.clients import BuyerPriceClient, WorldClient


class BuyerNativeTransactionPostgresTests(BotExchangePostgresAcceptanceTests):
    def setUp(self):
        super().setUp()
        bridge = BotWorldBridge(self.runtime, "isolated-buyer-transaction-credential")
        original_emit = self.runtime.emit

        def emit(*event):
            original_emit(*event)
            bridge.emit(*event)

        self.runtime.emit = emit
        ready, servers = threading.Event(), []
        thread = threading.Thread(
            target=serve_api,
            args=(self.store, "127.0.0.1", 0),
            kwargs={
                "bots_bridge": bridge,
                "on_ready": lambda server: (servers.append(server), ready.set()),
            },
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(3))
        server = servers[0]

        def close():
            server.shutdown()
            server.server_close()
            thread.join(3)

        self.addCleanup(close)
        self.addCleanup(self.runtime.deactivate_all)
        self.client = WorldClient(
            f"http://127.0.0.1:{server.server_port}",
            "isolated-buyer-transaction-credential",
        )
        self.client.snapshot()
        self.price_client = BuyerPriceClient(self.client)
        self.seller = self.human()
        self.bot = self.command(
            "create",
            {
                "name": "QualifiedBuyer",
                "breed": 15,
                "sex": 0,
                "capabilities": ["exchange"],
                "initial_kamas": 1000000,
            },
        )["result"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO world_bot_purchase_sinks(bot_id,enabled) VALUES(%s,true)",
                ("qualified-buyer",),
            )
            db.execute(
                "INSERT INTO shop_categories(key,name,enabled) VALUES('buyer_fixture','Buyer fixture',false)"
            )
            db.execute(
                "INSERT INTO shop_articles(key,name,item_ref,quantity,price_kamas,category,enabled,buyer_enabled) "
                "VALUES('buyer_fixture_2865','Broche Tam fixture',2865,1,36000,'buyer_fixture',false,true)"
            )
        self.command("activate", {})
        self.assertTrue(self.runtime.active["qualified-buyer"]["peer"].is_bot_peer)
        from wakfu_server.inventory_items import grant

        container = self.one(
            "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
            (self.seller["character"]["id"],),
        )["uid"]
        self.item = grant(
            self.store,
            self.seller["account"],
            self.seller["generation"],
            self.seller["character"]["id"],
            reference=2865,
            quantity=8,
            container=container,
            slot=0,
            allowed_references={2865},
        )

    def command(self, action, args, *, request_id=None):
        return self.client.command(
            "qualified-buyer", action, args, request_id or uuid.uuid4().hex
        )

    def wallet(self, account_id):
        return self.one(
            "SELECT kamas FROM account_wallets WHERE account_id=%s", (account_id,)
        )["kamas"]

    def current_event(self):
        return next(
            row[2] for row in reversed(self.events) if row[1] == "exchange.updated"
        )

    def prepare_sale(self):
        invitation = self.request(
            self.seller, 13140, struct.pack(">q", self.bot["character_id"])
        )
        self.command("exchange.accept", {"exchange_id": invitation["id"]})
        # 12510 carries an item-entry count; its one UID offers the full stack.
        self.request(
            self.seller,
            12510,
            struct.pack(">qiq", invitation["id"], 1, self.item["uid"]),
        )
        event = self.current_event()
        self.assertEqual(self.price_client.quote(event["items"], 80), 230400)
        action, args = BuyerBehavior().decide(
            {"type": "exchange.updated", "payload": event},
            {"purchase_percent": 80},
            shop=self.price_client,
        )[0]
        self.assertEqual((action, args["amount"]), ("exchange.offer_kamas", 230400))
        self.command(action, args)
        action, args = BuyerBehavior().decide(
            {"type": "exchange.updated", "payload": self.current_event()},
            {"purchase_percent": 80},
            shop=self.price_client,
        )[0]
        self.assertEqual(action, "exchange.ready")
        request_id = uuid.uuid4().hex
        self.ready_response = self.command(action, args, request_id=request_id)
        self.ready_replay = (action, args, request_id)
        self.exchange_id = invitation["id"]

    def confirm_sale(self):
        return self.request(self.seller, 13406, struct.pack(">q", self.exchange_id))

    def assert_settled_once(self):
        self.assertEqual(self.wallet(self.seller["account"]), 230400)
        # The opted native SQL sink refunds only the buyer's own purchase.
        self.assertEqual(self.wallet(self.bot["account_id"]), 1000000)
        self.assertIsNone(
            self.one(
                "SELECT uid FROM inventory_items WHERE uid=%s", (self.item["uid"],)
            )
        )
        self.assertEqual(
            self.one(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (self.exchange_id,),
            )["n"],
            1,
        )
        receipt = self.one(
            "SELECT * FROM world_bot_purchase_sink_receipts WHERE exchange_id=%s",
            (self.exchange_id,),
        )
        self.assertEqual(receipt["refunded_kamas"], 230400)
        self.assertEqual(
            sum(row["removed_quantity"] for row in receipt["removed_items"]), 8
        )
        self.assertEqual(
            self.one(
                "SELECT count(*) AS n FROM world_bot_purchase_sink_receipts WHERE exchange_id=%s",
                (self.exchange_id,),
            )["n"],
            1,
        )
        self.assertEqual(
            self.one(
                "SELECT enabled,buyer_enabled,price_kamas FROM shop_articles WHERE key='buyer_fixture_2865'"
            ),
            {"enabled": False, "buyer_enabled": True, "price_kamas": 36000},
        )

    def test_buyer_only_article_real_http_peer_commit_and_replay_once(self):
        self.prepare_sale()
        self.assertEqual(self.confirm_sale()["state"], "committed")
        self.assert_settled_once()
        action, args, request_id = self.ready_replay
        self.assertEqual(
            self.command(action, args, request_id=request_id), self.ready_response
        )
        self.assertEqual(self.confirm_sale()["state"], "committed")
        self.assert_settled_once()
        self.assertTrue(
            all(
                row["delivered_at"] is not None
                for row in self._outbox(self.exchange_id)
            )
        )

    def test_late_failure_after_real_sink_rolls_back_and_retry_commits_once(self):
        self.prepare_sale()
        original = player_exchanges._outbox

        def fail_after_sink(store, db, saved, event, *args, **kwargs):
            if event == "committed":
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM world_bot_purchase_sink_receipts WHERE exchange_id=%s",
                        (self.exchange_id,),
                    ).fetchone()["n"],
                    1,
                )
                raise RuntimeError("isolated failure after real buyer sink")
            return original(store, db, saved, event, *args, **kwargs)

        with patch.object(player_exchanges, "_outbox", side_effect=fail_after_sink):
            with self.assertRaisesRegex(
                RuntimeError, "isolated failure after real buyer sink"
            ):
                self.confirm_sale()
        self.assertEqual(self.wallet(self.seller["account"]), 0)
        self.assertEqual(self.wallet(self.bot["account_id"]), 1000000)
        self.assertEqual(
            self.one(
                "SELECT character_id,quantity FROM inventory_items WHERE uid=%s",
                (self.item["uid"],),
            ),
            {"character_id": self.seller["character"]["id"], "quantity": 8},
        )
        self.assertEqual(
            self.one(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (self.exchange_id,),
            )["n"],
            0,
        )
        self.assertEqual(
            self.one(
                "SELECT count(*) AS n FROM world_bot_purchase_sink_receipts WHERE exchange_id=%s",
                (self.exchange_id,),
            )["n"],
            0,
        )
        self.assertEqual(self.confirm_sale()["state"], "committed")
        self.assert_settled_once()
