"""One isolated PostgreSQL acceptance flow across native exchange and bot policy."""

import struct
import sys
import threading
import uuid
from pathlib import Path

from postgres_case import PostgresCase

BOT_SERVICE_ROOT = Path(__file__).resolve().parents[1] / "bot-service"
if str(BOT_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_SERVICE_ROOT))

from wakfu_bots.behaviors import BuyerBehavior

from wakfu_server import exchange_dispatch
from wakfu_server.bots.bridge import BotConflict
from wakfu_server.bots.runtime import BotsRuntime
from wakfu_server.inventory_items import grant


class BotExchangePostgresAcceptanceTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.world = FakeWorld(self.store)
        self.exchanges = exchange_dispatch.Exchanges(self.store, self.world)
        self.positions = FakePositions()
        self.events = []
        self.runtime = BotsRuntime(
            self.store,
            self.world,
            self.exchanges,
            self.positions,
            say=lambda *_args: None,
            emit=lambda *event: self.events.append(event),
        )
        self.exchanges.bot_delivery = self.runtime.handle_exchange

    def human(self):
        account = self.store.register(
            "human_" + uuid.uuid4().hex[:12], "bot-acceptance-test-password"
        )["id"]
        character = self.store.create_character(
            account,
            "BuyerTest"
            + uuid.uuid4().hex[:8].translate(str.maketrans("0123456789", "abcdefghij")),
        )
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        value = {"account": account, "generation": generation, "character": character}
        self.world.add(value)
        return value

    def request(self, player, opcode, body):
        return self.exchanges.handle(
            opcode,
            body,
            player["account"],
            player["generation"],
            player["character"]["id"],
        )

    def one(self, statement, params=()):
        with self.store.connection() as db:
            return db.execute(statement, params).fetchone()

    def test_dedicated_bot_completes_priced_native_exchange_once(self):
        buyer = self.human()
        created = self.runtime.execute(
            "market-bot",
            "create",
            {
                "name": "MarketBot",
                "breed": 15,
                "sex": 0,
                "capabilities": ["chat", "exchange"],
                "initial_kamas": 1000,
            },
        )
        bot_account, bot_character = created["account_id"], created["character_id"]
        self.assertNotEqual(buyer["account"], bot_account)
        self.assertEqual(
            1000,
            self.one(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (bot_account,)
            )["kamas"],
        )
        repeated = self.runtime.execute(
            "market-bot",
            "create",
            {
                "name": "MarketBot",
                "breed": 15,
                "sex": 0,
                "capabilities": ["chat", "exchange"],
                "initial_kamas": 1000,
            },
        )
        self.assertEqual(repeated["account_id"], bot_account)
        self.assertEqual(
            1000,
            self.one(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (bot_account,)
            )["kamas"],
        )
        self.runtime.execute("market-bot", "activate", {})

        container = self.one(
            "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
            (buyer["character"]["id"],),
        )["uid"]
        item = grant(
            self.store,
            buyer["account"],
            buyer["generation"],
            buyer["character"]["id"],
            reference=12,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={12},
        )

        invite = self.request(buyer, 13140, struct.pack(">q", bot_character))
        invitation = self.events[-1][2]
        self.assertEqual("exchange.invited", self.events[-1][1])
        self.runtime.execute(
            "market-bot", "exchange.accept", {"exchange_id": invite["id"]}
        )

        offered = self.request(
            buyer, 12510, struct.pack(">qiq", invite["id"], 1, item["uid"])
        )
        active_event = next(
            event
            for event in reversed(self.events)
            if event[1] == "exchange.updated"
            and event[2]["revision"] == offered["revision"]
        )[2]
        self.assertEqual(invitation["exchange_id"], active_event["exchange_id"])

        class ShopQuote:
            def quote(self, items, purchase_percent):
                self.items, self.purchase_percent = items, purchase_percent
                return 80

        shop = ShopQuote()
        action, arguments = BuyerBehavior().decide(
            {"type": "exchange.updated", "payload": active_event},
            {"purchase_percent": 80},
            shop=shop,
        )[0]
        self.assertEqual("exchange.offer_kamas", action)
        self.assertEqual(80, arguments["amount"])
        self.assertEqual(80, shop.purchase_percent)
        amount = arguments["amount"]
        self.runtime.execute("market-bot", action, arguments)
        current = next(
            event
            for event in reversed(self.events)
            if event[1] == "exchange.updated"
            and event[2]["exchange_id"] == invite["id"]
        )[2]
        with self.assertRaises(BotConflict):
            self.runtime.execute(
                "market-bot",
                "exchange.ready",
                {"exchange_id": invite["id"], "revision": active_event["revision"]},
            )
        self.runtime.execute(
            "market-bot",
            "exchange.ready",
            {"exchange_id": invite["id"], "revision": current["revision"]},
        )
        completed = self.request(buyer, 13406, struct.pack(">q", invite["id"]))
        self.assertEqual("committed", completed["state"])
        self.assertEqual(
            920,
            self.one(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (bot_account,)
            )["kamas"],
        )
        self.assertEqual(
            80,
            self.one(
                "SELECT kamas FROM account_wallets WHERE account_id=%s",
                (buyer["account"],),
            )["kamas"],
        )
        self.assertEqual(
            bot_character,
            self.one(
                "SELECT character_id FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["character_id"],
        )
        self.assertEqual(
            1,
            self.one(
                "SELECT count(*) AS count FROM player_exchange_receipts WHERE exchange_id=%s",
                (invite["id"],),
            )["count"],
        )
        self.assertTrue(
            all(row["delivered_at"] is not None for row in self._outbox(invite["id"]))
        )
        self.runtime.execute("market-bot", "deactivate", {})

    def _outbox(self, exchange_id):
        with self.store.connection() as db:
            return db.execute(
                "SELECT delivered_at FROM player_exchange_outbox WHERE exchange_id=%s",
                (exchange_id,),
            ).fetchall()


class FakePositions:
    def attach(self, *_args):
        pass

    def release(self, *_args, **_kwargs):
        pass

    def flush(self, **_kwargs):
        pass


class FakeWorld:
    def __init__(self, store):
        self.store = store
        self.players = {}
        self.sent = []
        self.lock = threading.RLock()

    def add(self, player):
        self.players[player["character"]["id"]] = (
            player["generation"],
            dict(
                player["character"],
                account_id=player["account"],
                map_id=1134,
                instance_id=0,
            ),
        )

    def join(self, generation, _peer, character):
        with self.store.connection() as db:
            account = db.execute(
                "SELECT account_id FROM world_bots WHERE character_id=%s",
                (character["id"],),
            ).fetchone()["account_id"]
        self.players[character["id"]] = (
            generation,
            dict(character, account_id=account, map_id=1134, instance_id=0),
        )

    def live_identity(self, *, character_id=None):
        entry = self.players.get(character_id)
        return None if entry is None else (entry[0], dict(entry[1]))

    def send_to(self, character_id, generation, opcode, body):
        self.sent.append((character_id, generation, opcode, body))
        entry = self.players.get(character_id)
        return entry is not None and entry[0] == generation

    def deactivate_ecology(self, *_args):
        pass

    def leave(self, character_id, generation):
        entry = self.players.get(character_id)
        if entry is not None and entry[0] == generation:
            self.players.pop(character_id, None)


if __name__ == "__main__":
    import unittest

    unittest.main()
