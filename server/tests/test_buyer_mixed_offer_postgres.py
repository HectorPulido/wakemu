"""Actual trade86 reference set through HTTP, BotPeer and isolated native SQL."""
import json
import struct
import threading
import uuid
from pathlib import Path
from unittest.mock import patch
from test_bots_postgres import BotExchangePostgresAcceptanceTests
from wakfu_server.api import serve_api
from wakfu_server.bots.bridge import BotWorldBridge
from wakfu_server import player_exchanges
from wakfu_server.inventory_items import grant
from wakfu_bots.behaviors import BuyerBehavior
from wakfu_bots.clients import BuyerPriceClient, WorldClient, RemoteError


class ActualBuyerMixedTests(BotExchangePostgresAcceptanceTests):
    def setUp(self):
        super().setUp()
        self.bridge = BotWorldBridge(self.runtime, "isolated-actual-buyer-credential")
        old_emit = self.runtime.emit

        def emit(*args):
            old_emit(*args)
            self.bridge.emit(*args)

        self.runtime.emit = emit
        ready, servers = threading.Event(), []
        thread = threading.Thread(
            target=serve_api,
            args=(self.store, "127.0.0.1", 0),
            kwargs=dict(
                bots_bridge=self.bridge,
                on_ready=lambda server: (servers.append(server), ready.set()),
            ),
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(3))
        server = servers[0]
        self.addCleanup(
            lambda: (server.shutdown(), server.server_close(), thread.join(3))
        )
        self.addCleanup(self.runtime.deactivate_all)
        self.client = WorldClient(
            "http://127.0.0.1:" + str(server.server_port),
            "isolated-actual-buyer-credential",
        )
        self.client.snapshot()
        self.prices = BuyerPriceClient(self.client)
        self.behavior = BuyerBehavior()
        self.seller = self.human()
        self.bot = self.command(
            "create",
            dict(
                name="ActualBuyer",
                breed=15,
                sex=0,
                capabilities=["exchange"],
                initial_kamas=1000000,
            ),
        )["result"]
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures" / "buyer_mixed_offer_catalog.json"
            ).read_text()
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO world_bot_purchase_sinks(bot_id,enabled) VALUES(%s,true)",
                ("actual-buyer",),
            )
            for row in fixture["articles"]:
                db.execute(
                    "INSERT INTO shop_categories(key,name,enabled) VALUES(%s,%s,true) ON CONFLICT(key) DO NOTHING",
                    (row["category"], row["category"]),
                )
                db.execute(
                    "INSERT INTO shop_articles(key,name,item_ref,quantity,price_kamas,category,enabled,buyer_enabled) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        "actual_" + str(row["item_ref"]),
                        row["name"],
                        row["item_ref"],
                        row["quantity"],
                        row["price_kamas"],
                        row["category"],
                        row["enabled"],
                        row["buyer_enabled"],
                    ),
                )
        self.command("activate", {})
        container = self.one(
            "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
            (self.seller["character"]["id"],),
        )["uid"]
        self.items = {}
        for slot, row in enumerate(fixture["offer"]):
            self.items[row["reference"]] = grant(
                self.store,
                self.seller["account"],
                self.seller["generation"],
                self.seller["character"]["id"],
                reference=row["reference"],
                quantity=row["quantity"],
                container=container,
                slot=slot,
                allowed_references={r["reference"] for r in fixture["offer"]},
            )
        self.held = self.items[30723]

    def command(self, action, args, request_id=None):
        return self.client.command(
            "actual-buyer", action, args, request_id or uuid.uuid4().hex
        )

    def event(self):
        return next(
            row[2] for row in reversed(self.events) if row[1] == "exchange.updated"
        )

    def decision(self, shop=None):
        return self.behavior.decide(
            dict(type="exchange.updated", payload=self.event()),
            dict(purchase_percent=80),
            shop=shop or self.prices,
        )

    def execute_decision(self, shop=None):
        actions = self.decision(shop)
        for action, args in actions:
            self.assertNotEqual(action, "exchange.cancel")
            self.command(action, args)
        return actions

    def open(self, valid=True):
        self.exchange = self.request(
            self.seller, 13140, struct.pack(">q", self.bot["character_id"])
        )["id"]
        self.command("exchange.accept", dict(exchange_id=self.exchange))
        selected = (
            [v["uid"] for r, v in self.items.items() if r != 30723]
            if valid
            else [self.held["uid"]]
        )
        self.request(
            self.seller,
            12510,
            struct.pack(">qi", self.exchange, len(selected))
            + b"".join(struct.pack(">q", uid) for uid in selected),
        )
        if valid:
            self.assertEqual(self.prices.quote(self.event()["items"], 80), 422728)
            self.execute_decision()
            self.execute_decision()
        return self.exchange

    def economic_state(self):
        with self.store.connection() as db:
            return dict(
                items=[
                    dict(r)
                    for r in db.execute(
                        "SELECT uid,character_id,reference,quantity FROM inventory_items WHERE character_id=ANY(%s) ORDER BY uid",
                        ([self.seller["character"]["id"], self.bot["character_id"]],),
                    ).fetchall()
                ],
                wallets=[
                    dict(r)
                    for r in db.execute(
                        "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s) ORDER BY account_id",
                        ([self.seller["account"], self.bot["account_id"]],),
                    ).fetchall()
                ],
            )

    def quote_state(self):
        with self.store.connection() as db:
            return dict(
                exchange=dict(
                    db.execute(
                        "SELECT * FROM player_exchanges WHERE id=%s", (self.exchange,)
                    ).fetchone()
                ),
                members=[
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM player_exchange_members WHERE exchange_id=%s ORDER BY character_id",
                        (self.exchange,),
                    ).fetchall()
                ],
                outbox=[
                    dict(r)
                    for r in db.execute(
                        "SELECT id,revision,delivery_sequence,payload FROM player_exchange_outbox WHERE exchange_id=%s ORDER BY id",
                        (self.exchange,),
                    ).fetchall()
                ],
            )

    def feedback(self):
        return [
            row
            for row in self.world.sent
            if row[0] == self.seller["character"]["id"] and b"Retira" in row[3]
        ]

    def add_held(self):
        self.request(
            self.seller, 13037, struct.pack(">qqh", self.held["uid"], self.exchange, 1)
        )

    def test_actual86_mixed_decline_replay_stale_ready_remove_and_commit(self):
        self.open()
        old = self.event()["revision"]
        economy = self.economic_state()
        self.add_held()
        self.assertTrue(
            all(m["confirmed_revision"] is None for m in self.quote_state()["members"])
        )
        binding = self.one(
            "SELECT * FROM inventory_item_bindings WHERE uid=%s", (self.held["uid"],)
        )
        self.assertIs(binding["bound"], False)
        with self.assertRaises(RemoteError) as stale:
            self.command(
                "exchange.ready", dict(exchange_id=self.exchange, revision=old)
            )
        self.assertEqual(stale.exception.code, "exchange_revision_stale")
        self.assertEqual(self.decision()[0][0], "exchange.decline_quote")
        self.execute_decision()
        state = self.quote_state()
        self.assertEqual(state["exchange"]["state"], "active")
        self.assertTrue(all(m["confirmed_revision"] is None for m in state["members"]))
        self.assertEqual(self.economic_state(), economy)
        self.assertEqual(len(self.feedback()), 1)
        self.assertIn("Restos de diario".encode(), self.feedback()[0][3])
        self.execute_decision()
        self.assertEqual(self.quote_state(), state)
        self.assertEqual(len(self.feedback()), 1)
        # A human's confirmation cannot cause free acceptance or duplicate advice.
        self.request(self.seller, 13406, struct.pack(">q", self.exchange))
        self.execute_decision()
        self.assertEqual(self.quote_state()["exchange"]["state"], "active")
        self.assertEqual(self.economic_state(), economy)
        self.assertEqual(len(self.feedback()), 1)
        self.request(
            self.seller, 13113, struct.pack(">qiq", self.exchange, 1, self.held["uid"])
        )
        self.assertEqual(self.prices.quote(self.event()["items"], 80), 422728)
        self.execute_decision()
        result = self.request(self.seller, 13406, struct.pack(">q", self.exchange))
        self.assertEqual(result["state"], "committed")
        receipt = self.one(
            "SELECT * FROM player_exchange_receipts WHERE exchange_id=%s",
            (self.exchange,),
        )
        self.assertIsNotNone(receipt)
        self.assertEqual(
            self.one(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (self.held["uid"],)
            )["quantity"],
            1,
        )
        self.assertEqual(
            self.one(
                "SELECT kamas FROM account_wallets WHERE account_id=%s",
                (self.seller["account"],),
            )["kamas"],
            economy["wallets"][0]["kamas"] + 422728,
        )
        self.request(self.seller, 13406, struct.pack(">q", self.exchange))
        self.assertEqual(
            self.one(
                "SELECT count(*) n FROM player_exchange_receipts WHERE exchange_id=%s",
                (self.exchange,),
            )["n"],
            1,
        )
        self.assertEqual(
            self.one(
                "SELECT count(*) n FROM world_bot_purchase_sink_receipts WHERE exchange_id=%s",
                (self.exchange,),
            )["n"],
            1,
        )
        self.assertEqual(
            self.one(
                "SELECT enabled,buyer_enabled FROM shop_articles WHERE item_ref=30723"
            ),
            dict(enabled=False, buyer_enabled=False),
        )

    def test_all_unpriced_late_failure_rollback_retry_cancel_and_worker_idle(self):
        self.open(valid=False)
        before = self.quote_state()
        economy = self.economic_state()
        original = player_exchanges._outbox

        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("late quote feedback failure")

        with patch.object(player_exchanges, "_outbox", fail):
            with self.assertRaises(RemoteError):
                self.execute_decision()
        self.assertEqual(self.quote_state(), before)
        self.assertEqual(self.economic_state(), economy)
        self.execute_decision()
        self.assertEqual(self.quote_state()["exchange"]["state"], "active")
        self.assertEqual(len(self.feedback()), 1)
        self.bridge.last_worker = -1000000
        self.bridge.tick()
        self.assertIn("actual-buyer", self.runtime.active)
        self.assertEqual(self.quote_state()["exchange"]["state"], "active")
        self.assertEqual(self.economic_state(), economy)
        from wakfu_server.bots.bridge import BotConflict

        for stop in (
            lambda: self.command("deactivate", {}),
            self.runtime.deactivate_all,
        ):
            with self.assertRaises((RemoteError, BotConflict)):
                stop()
            self.assertIn("actual-buyer", self.runtime.active)
            self.assertEqual(self.quote_state()["exchange"]["state"], "active")
            self.assertTrue(
                all(
                    m["confirmed_revision"] is None
                    for m in self.quote_state()["members"]
                )
            )
            self.assertEqual(self.economic_state(), economy)
        # Genuine native user cancellation remains available.
        self.request(self.seller, 12027, struct.pack(">q", self.exchange))
        self.assertEqual(self.quote_state()["exchange"]["state"], "canceled")

    def test_invitation_survives_admin_and_shutdown_deactivation(self):
        from wakfu_server.bots.bridge import BotConflict

        self.exchange = self.request(
            self.seller, 13140, struct.pack(">q", self.bot["character_id"])
        )["id"]
        before = self.quote_state()
        economy = self.economic_state()
        peer = self.runtime.active["actual-buyer"]["peer"]
        with patch.object(peer, "shutdown", wraps=peer.shutdown) as shutdown:
            for stop in (
                lambda: self.command("deactivate", {}),
                self.runtime.deactivate_all,
            ):
                with self.assertRaises((RemoteError, BotConflict)):
                    stop()
                self.assertEqual(self.quote_state(), before)
                self.assertEqual(self.economic_state(), economy)
                self.assertIn("actual-buyer", self.runtime.active)
            shutdown.assert_not_called()
        self.request(self.seller, 12027, struct.pack(">q", self.exchange))
        self.command("deactivate", {})
        self.assertNotIn("actual-buyer", self.runtime.active)


def load_tests(loader, tests, pattern):
    """Run the three new journeys without duplicating inherited base coverage."""
    import unittest

    return unittest.TestSuite(
        ActualBuyerMixedTests(name)
        for name in (
            "test_actual86_mixed_decline_replay_stale_ready_remove_and_commit",
            "test_all_unpriced_late_failure_rollback_retry_cancel_and_worker_idle",
            "test_invitation_survives_admin_and_shutdown_deactivation",
        )
    )
