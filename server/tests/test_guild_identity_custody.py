"""Guild identity costs must not consume items held by an active exchange.

The guild policy is an explicit isolated test fixture, not native activation.
"""
import os
import unittest
from unittest.mock import patch

import test_guild_service_postgres as guild_cases
from wakfu_server import player_exchanges


class GuildIdentityCustodyTests(unittest.TestCase):
    def test_creation_does_not_consume_offered_guildalogem_or_debit_wallet(self):
        fixture = guild_cases.GuildServicePostgresTests()
        self.addCleanup(fixture.doCleanups)
        with patch.dict(os.environ, {"WAKFU_RUN_GUILD_POSTGRES_TESTS": "1"}):
            fixture.setUp()
        owner = fixture._player("Guild Custody")
        other = fixture._player("Exchange Peer")
        with fixture.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET quantity=1 WHERE uid=%s", (owner["item"],)
            )
        exchange = player_exchanges.invite(
            fixture.store,
            owner["account"],
            owner["generation"],
            owner["character"],
            other["character"],
        )
        player_exchanges.answer(
            fixture.store,
            other["account"],
            other["generation"],
            other["character"],
            exchange["id"],
            True,
        )
        player_exchanges.offer_item(
            fixture.store,
            owner["account"],
            owner["generation"],
            owner["character"],
            exchange["id"],
            owner["item"],
            1,
        )
        wallet = fixture._wallet(owner["account"])
        with self.assertRaisesRegex(ValueError, "intercambio"):
            fixture._create(owner, "Protected Guild")
        self.assertEqual(fixture._wallet(owner["account"]), wallet)
        self.assertEqual(fixture._item_quantity(owner["item"]), 1)
        with fixture.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM player_exchange_items WHERE uid=%s",
                    (owner["item"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM guilds WHERE leader_id=%s", (owner["character"],)
                ).fetchone()
            )
