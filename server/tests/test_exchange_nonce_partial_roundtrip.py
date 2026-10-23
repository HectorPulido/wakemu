"""Public exchange splits keep hidden custody state across a return transfer."""
import unittest
import test_player_exchanges as exchange_cases
from wakfu_server import player_exchanges


class ExchangeNoncePartialRoundtripTests(unittest.TestCase):
    def test_partial_cursor_and_recycling_survive_return_without_merging(self):
        fixture = exchange_cases.PlayerExchangeInvitationTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store = fixture.store
        left, right = fixture.player("cursor-left"), fixture.player("cursor-right")
        source = fixture.grant_item(left, 2297, quantity=3)
        bare = fixture.grant_item(right, 2297, quantity=2)
        with store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,false,false)",
                (source["uid"],),
            )
            db.execute(
                "INSERT INTO random_item_use_counters(source_uid,next_use) VALUES(%s,8)",
                (source["uid"],),
            )

        def transfer(sender, receiver, uid, quantity):
            exchange = fixture.active_exchange(sender, receiver)
            player_exchanges.offer_item(
                store,
                sender["account"],
                sender["generation"],
                sender["character"]["id"],
                exchange["id"],
                uid,
                quantity,
            )
            fixture.publish_current(exchange, sender, receiver)
            player_exchanges.confirm(
                store,
                sender["account"],
                sender["generation"],
                sender["character"]["id"],
                exchange["id"],
            )
            result = player_exchanges.confirm(
                store,
                receiver["account"],
                receiver["generation"],
                receiver["character"]["id"],
                exchange["id"],
            )
            self.assertTrue(result["applied"])
            return result

        def quantity(uid):
            return fixture.fetchone(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            )["quantity"]

        def hidden(uid):
            return (
                fixture.fetchone(
                    "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s",
                    (uid,),
                ),
                fixture.fetchone(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (uid,),
                ),
            )

        first = transfer(left, right, source["uid"], 1)
        moved_uid = first["receipt"]["transfers"]["items"][0]["received_uid"]
        self.assertNotIn(moved_uid, (source["uid"], bare["uid"]))
        expected = ({"unidentified": False, "socketed": False}, {"next_use": 8})
        self.assertEqual(hidden(source["uid"]), expected)
        self.assertEqual(hidden(moved_uid), expected)
        self.assertEqual(
            (quantity(source["uid"]), quantity(moved_uid), quantity(bare["uid"])),
            (2, 1, 2),
        )
        second = transfer(right, left, moved_uid, 1)
        self.assertEqual(
            second["receipt"]["transfers"]["items"][0]["received_uid"], moved_uid
        )
        self.assertEqual(hidden(source["uid"]), expected)
        self.assertEqual(hidden(moved_uid), expected)
        self.assertEqual(
            (quantity(source["uid"]), quantity(moved_uid), quantity(bare["uid"])),
            (2, 1, 2),
        )
        replay = player_exchanges.confirm(
            store,
            left["account"],
            left["generation"],
            left["character"]["id"],
            second["id"],
        )
        self.assertFalse(replay["applied"])
        reopened = fixture.reopen().character(left["account"], left["character"]["id"])
        received = next(
            item for item in reopened["inventory_items"] if item["uid"] == moved_uid
        )
        self.assertEqual(received["quantity"], 1)
        self.assertEqual(hidden(moved_uid), expected)
