import json
import struct
import threading
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase

from wakfu_server import exchange_dispatch, exchange_wire, player_exchanges, wire
from wakfu_server.inventory_items import grant
from wakfu_server.inventory import bags


class FakeWorld:
    def __init__(self):
        self.players = {}
        self.attempts = []
        self.sent = []
        self.fail_once = None
        self._failed = False
        self.lock = threading.RLock()

    def add(self, player, *, generation=None):
        generation = generation or player["generation"]
        info = dict(
            player["character"],
            account_id=player["account"],
            map_id=1134,
            instance_id=0,
        )
        with self.lock:
            self.players[player["character"]["id"]] = (generation, info)

    def live_identity(self, *, character_id=None):
        with self.lock:
            entry = self.players.get(character_id)
            return None if entry is None else (entry[0], dict(entry[1]))

    def send_to(self, character_id, generation, opcode, body):
        entry = self.players.get(character_id)
        attempt = (character_id, generation, opcode, body)
        self.attempts.append(attempt)
        if entry is None or entry[0] != generation:
            return False
        if (
            self.fail_once is not None
            and not self._failed
            and (character_id, generation, opcode) == self.fail_once
        ):
            self._failed = True
            return False
        self.sent.append(attempt)
        return True


class ExchangeDispatchTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = 2_000_000_000.0
        self.store.clock = lambda: self.now
        self.world = FakeWorld()
        self.exchanges = exchange_dispatch.Exchanges(self.store, self.world)

    def player(self, label):
        account = self.store.register(
            f"xd{uuid.uuid4().hex[:12]}", "exchange-dispatch-test-password"
        )["id"]
        letters = str.maketrans("0123456789", "abcdefghij")
        name = "Trade" + uuid.uuid4().hex[:8].translate(letters)
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        player = {"account": account, "generation": generation, "character": character}
        self.world.add(player)
        return player

    def request(self, player, opcode, body):
        return self.exchanges.handle(
            opcode,
            body,
            player["account"],
            player["generation"],
            player["character"]["id"],
        )

    def invite(self, inviter, invitee):
        return self.request(
            inviter, 13140, struct.pack(">q", invitee["character"]["id"])
        )

    def grant_item(self, player, quantity=4):
        container = self.fetchone(
            "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
            (player["character"]["id"],),
        )["uid"]
        return grant(
            self.store,
            player["account"],
            player["generation"],
            player["character"]["id"],
            reference=12,
            quantity=quantity,
            container=container,
            slot=0,
            allowed_references={12},
        )

    def fetchone(self, statement, params=()):
        with self.store.connection() as db:
            return db.execute(statement, params).fetchone()

    def fetchall(self, statement, params=()):
        with self.store.connection() as db:
            return db.execute(statement, params).fetchall()

    @staticmethod
    def item_delta(row):
        return [
            (opcode, struct.unpack_from(">h", body, 17)[0])
            for character_id, generation, opcode, body in row
            if opcode in (13084, 13636)
        ]

    def test_invite_accept_quantity_edit_zero_and_confirm_reconcile_receipt(self):
        inviter, invitee = self.player("flow-inviter"), self.player("flow-invitee")
        item = self.grant_item(inviter)

        exchange = self.invite(inviter, invitee)

        self.assertEqual("invitation", exchange["state"])
        self.assertEqual({13535, 12538}, {entry[2] for entry in self.world.sent})
        answer = self.request(invitee, 12997, struct.pack(">qB", exchange["id"], 0))
        self.assertEqual("active", answer["state"])
        self.assertEqual(
            2,
            len(
                self.fetchall(
                    "SELECT * FROM player_exchange_outbox WHERE exchange_id=%s AND event='snapshot' "
                    "AND payload->>'state'='active' AND delivered_at IS NOT NULL",
                    (exchange["id"],),
                )
            ),
        )

        self.world.sent.clear()
        self.request(
            inviter, 13037, struct.pack(">qqh", item["uid"], exchange["id"], 4)
        )
        self.assertCountEqual(
            [(13636, 4), (13636, 4)], self.item_delta(self.world.sent)
        )
        self.world.sent.clear()
        self.request(
            inviter, 12203, struct.pack(">qqh", item["uid"], exchange["id"], 2)
        )
        self.assertCountEqual(
            [(13084, 2), (13084, 2)], self.item_delta(self.world.sent)
        )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT quantity FROM player_exchange_items WHERE exchange_id=%s AND uid=%s",
                (exchange["id"], item["uid"]),
            )["quantity"],
        )
        self.world.sent.clear()
        with self.assertRaisesRegex(ValueError, "must be positive"):
            self.request(
                inviter, 12203, struct.pack(">qqh", item["uid"], exchange["id"], 0)
            )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT quantity FROM player_exchange_items WHERE exchange_id=%s AND uid=%s",
                (exchange["id"], item["uid"]),
            )["quantity"],
        )
        self.request(
            inviter, 12203, struct.pack(">qqh", item["uid"], exchange["id"], 2)
        )
        self.assertCountEqual(
            [(13084, 2), (13084, 2)], self.item_delta(self.world.sent)
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_items WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )

        self.world.sent.clear()
        self.request(
            inviter, 13037, struct.pack(">qqh", item["uid"], exchange["id"], 1)
        )
        self.request(inviter, 13406, struct.pack(">q", exchange["id"]))
        committed = self.request(invitee, 13406, struct.pack(">q", exchange["id"]))
        self.assertEqual("committed", committed["state"])
        receipt = self.fetchone(
            "SELECT transfers FROM player_exchange_receipts WHERE exchange_id=%s",
            (exchange["id"],),
        )["transfers"]
        self.assertEqual(1, len(receipt["items"]))
        self.assertEqual(item["uid"], receipt["items"][0]["source_uid"])

        for player in (inviter, invitee):
            actor_id = player["character"]["id"]
            actor_events = [entry for entry in self.world.sent if entry[0] == actor_id]
            opcodes = [entry[2] for entry in actor_events]
            self.assertIn(12235, opcodes)
            self.assertIn(13713, opcodes)
            self.assertIn(13078, opcodes)
            self.assertIn(12753, opcodes)
            self.assertNotIn(13021, opcodes)
            self.assertIn(13873, opcodes)
            self.assertNotIn(12919, opcodes)
            self.assertNotIn(12471, opcodes)

            current = self.store.character(player["account"], actor_id)
            bag_event = next(entry for entry in actor_events if entry[2] == 13713)
            self.assertEqual((actor_id, 35), struct.unpack_from(">qB", bag_event[3]))
            self.assertEqual(bags(current), bag_event[3][9:])
            registry_event = next(entry for entry in actor_events if entry[2] == 13078)
            registry_owner, registry_length, compressed = struct.unpack_from(
                ">qIB", registry_event[3]
            )
            self.assertEqual((actor_id, 0), (registry_owner, compressed))
            self.assertEqual(registry_length, len(registry_event[3]) - 13)
            registry_uids = {
                dict(wire.proto_fields(proto))[8]
                for tag, proto in wire.proto_fields(registry_event[3][13:])
                if tag == 10
            }
            self.assertEqual(
                {unit["uid"] for unit in current["inventory_items"]}, registry_uids
            )
            if actor_id == invitee["character"]["id"]:
                self.assertIn(receipt["items"][0]["received_uid"], registry_uids)

            balance = self.fetchone(
                "SELECT kamas FROM account_wallets WHERE account_id=%s",
                (player["account"],),
            )["kamas"]
            cash_index = opcodes.index(12753)
            cache_index = opcodes.index(13873)
            self.assertLess(cash_index, cache_index)
            self.assertEqual(
                wire.account_kamas_update(balance), actor_events[cash_index][3]
            )
            self.assertEqual(wire.account_kamas(balance), actor_events[cache_index][3])
        self.assertTrue(
            all(
                row["delivered_at"] is not None
                for row in self.fetchall(
                    "SELECT delivered_at FROM player_exchange_outbox WHERE exchange_id=%s",
                    (exchange["id"],),
                )
            )
        )

    def test_rejection_and_active_cancel_publish_reason_and_restore_owned_inventory(
        self,
    ):
        inviter, invitee = self.player("reject-inviter"), self.player("reject-invitee")
        rejected = self.invite(inviter, invitee)
        self.world.sent.clear()
        self.request(invitee, 12997, struct.pack(">qB", rejected["id"], 1))
        rows = self.fetchall(
            "SELECT character_id,payload FROM player_exchange_outbox WHERE exchange_id=%s "
            "AND event='canceled' ORDER BY character_id",
            (rejected["id"],),
        )
        self.assertEqual(2, len(rows))
        self.assertTrue(
            all(
                row["payload"]["canceled_by"] == invitee["character"]["id"]
                for row in rows
            )
        )
        rejection_statuses = [
            struct.unpack(">qBqq", entry[3])
            for entry in self.world.sent
            if entry[2] == 13535
        ]
        self.assertEqual(2, len(rejection_statuses))
        self.assertTrue(all(status[1] == 2 for status in rejection_statuses))
        self.assertCountEqual(
            [
                (
                    rejected["id"],
                    2,
                    invitee["character"]["id"],
                    inviter["character"]["id"],
                ),
                (
                    rejected["id"],
                    2,
                    inviter["character"]["id"],
                    invitee["character"]["id"],
                ),
            ],
            rejection_statuses,
        )

        active_inviter, active_invitee = self.player("cancel-inviter"), self.player(
            "cancel-invitee"
        )
        exchange = self.invite(active_inviter, active_invitee)
        self.request(active_invitee, 12997, struct.pack(">qB", exchange["id"], 0))
        item = self.grant_item(active_inviter, 2)
        self.request(
            active_inviter, 13037, struct.pack(">qqh", item["uid"], exchange["id"], 2)
        )
        with self.assertRaisesRegex(ValueError, "respondida"):
            self.request(active_inviter, 12997, struct.pack(">qB", exchange["id"], 4))
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        inventory_before = self.fetchone(
            "SELECT uid,character_id,quantity FROM inventory_items WHERE uid=%s",
            (item["uid"],),
        )
        self.request(active_inviter, 12027, struct.pack(">q", exchange["id"]))
        canceled_rows = self.fetchall(
            "SELECT character_id,payload FROM player_exchange_outbox WHERE exchange_id=%s "
            "AND event='canceled' ORDER BY character_id",
            (exchange["id"],),
        )
        self.assertEqual(2, len(canceled_rows))
        self.assertTrue(
            all(
                row["payload"]["canceled_by"] == active_inviter["character"]["id"]
                for row in canceled_rows
            )
        )
        self.assertTrue(
            all(
                [item["uid"] for item in row["payload"]["items"]] == [item["uid"]]
                for row in canceled_rows
            )
        )
        self.assertEqual(
            inventory_before,
            self.fetchone(
                "SELECT uid,character_id,quantity FROM inventory_items WHERE uid=%s",
                (item["uid"],),
            ),
        )
        self.assertEqual(
            "canceled",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )

    def test_inviter_cancels_pending_invitation_with_captured_result1(self):
        inviter, invitee = self.player("cancel-pending-inviter"), self.player(
            "cancel-pending-invitee"
        )
        exchange = self.invite(inviter, invitee)
        self.world.sent.clear()

        # The captured invitation-window cancel uses result1 for the inviter;
        # result0 is still reserved for the invitee's accept action.
        with self.assertRaisesRegex(ValueError, "destinatario"):
            self.request(inviter, 12997, struct.pack(">qB", exchange["id"], 0))
        with self.assertRaisesRegex(ValueError, "inició"):
            self.request(invitee, 12997, struct.pack(">qB", exchange["id"], 4))
        self.assertEqual(
            "invitation",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        canceled = self.request(inviter, 12997, struct.pack(">qB", exchange["id"], 1))
        self.assertEqual("canceled", canceled["state"])
        stored = self.fetchone(
            "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
        )
        self.assertEqual("canceled", stored["state"])

        rows = self.fetchall(
            "SELECT character_id,payload,delivered_at FROM player_exchange_outbox "
            "WHERE exchange_id=%s AND event='canceled' ORDER BY character_id",
            (exchange["id"],),
        )
        self.assertEqual(2, len(rows))
        self.assertTrue(
            all(
                row["payload"]["canceled_by"] == inviter["character"]["id"]
                for row in rows
            )
        )
        self.assertTrue(
            all(row["payload"]["previous_state"] == "invitation" for row in rows)
        )
        self.assertTrue(all(row["delivered_at"] is not None for row in rows))

        statuses = {
            entry[0]: struct.unpack(">qBqq", entry[3])
            for entry in self.world.sent
            if entry[2] == 13535
        }
        self.assertEqual(
            {inviter["character"]["id"], invitee["character"]["id"]}, set(statuses)
        )
        for actor in (inviter, invitee):
            peer = invitee if actor is inviter else inviter
            packet = statuses[actor["character"]["id"]]
            self.assertEqual(
                (exchange["id"], 2, peer["character"]["id"], actor["character"]["id"]),
                packet,
            )
        self.assertFalse(any(entry[2] == 12235 for entry in self.world.sent))
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_members WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )

        sent_after_cancel = len(self.world.sent)
        with self.assertRaisesRegex(ValueError, "already answered"):
            self.request(invitee, 12997, struct.pack(">qB", exchange["id"], 0))
        self.assertEqual(sent_after_cancel, len(self.world.sent))
        self.assertEqual(
            "canceled",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_members WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )

    def test_retry_after_ack_failure_does_not_repeat_packets_or_lose_last_snapshot(
        self,
    ):
        inviter, invitee = self.player("ack-retry-inviter"), self.player(
            "ack-retry-invitee"
        )
        exchange = self.invite(inviter, invitee)
        self.request(invitee, 12997, struct.pack(">qB", exchange["id"], 0))
        item = self.grant_item(inviter, 4)
        next_revision = self.fetchone(
            "SELECT revision+1 AS next FROM player_exchanges WHERE id=%s",
            (exchange["id"],),
        )["next"]
        original_ack = self.exchanges._ack
        failed = {"once": False}

        def fail_one_ack(row):
            if (
                not failed["once"]
                and row["exchange_id"] == exchange["id"]
                and row["revision"] == next_revision
                and row["character_id"] == inviter["character"]["id"]
            ):
                failed["once"] = True
                return False
            return original_ack(row)

        with patch.object(self.exchanges, "_ack", side_effect=fail_one_ack):
            self.request(
                inviter, 13037, struct.pack(">qqh", item["uid"], exchange["id"], 4)
            )
        self.assertTrue(failed["once"])
        after_first_send = len(
            [
                entry
                for entry in self.world.attempts
                if entry[0] == inviter["character"]["id"]
            ]
        )
        self.exchanges.drain()
        after_ack_retry = len(
            [
                entry
                for entry in self.world.attempts
                if entry[0] == inviter["character"]["id"]
            ]
        )
        self.assertEqual(after_first_send, after_ack_retry)
        self.world.sent.clear()
        self.request(
            inviter, 12203, struct.pack(">qqh", item["uid"], exchange["id"], 2)
        )
        self.assertCountEqual(
            [(13084, 2), (13084, 2)], self.item_delta(self.world.sent)
        )

    def test_ack_commit_then_client_exception_recovers_snapshot_before_next_delta(self):
        inviter, invitee = self.player("ack-commit-inviter"), self.player(
            "ack-commit-invitee"
        )
        exchange = self.invite(inviter, invitee)
        self.request(invitee, 12997, struct.pack(">qB", exchange["id"], 0))
        item = self.grant_item(inviter, 4)
        revision = self.fetchone(
            "SELECT revision+1 AS next FROM player_exchanges WHERE id=%s",
            (exchange["id"],),
        )["next"]
        original_ack = self.exchanges._ack
        raised = {"once": False}

        def commit_then_raise(row):
            result = original_ack(row)
            if (
                result
                and not raised["once"]
                and row["exchange_id"] == exchange["id"]
                and row["revision"] == revision
                and row["character_id"] == inviter["character"]["id"]
            ):
                raised["once"] = True
                raise RuntimeError("simulated client error after committed outbox ack")
            return result

        with patch.object(self.exchanges, "_ack", side_effect=commit_then_raise):
            with self.assertRaisesRegex(RuntimeError, "after committed outbox ack"):
                self.request(
                    inviter, 13037, struct.pack(">qqh", item["uid"], exchange["id"], 4)
                )
        self.assertTrue(raised["once"])
        delivered = self.fetchone(
            "SELECT delivered_at FROM player_exchange_outbox WHERE exchange_id=%s "
            "AND revision=%s AND character_id=%s",
            (exchange["id"], revision, inviter["character"]["id"]),
        )
        self.assertIsNotNone(delivered["delivered_at"])
        self.world.sent.clear()

        self.request(
            inviter, 12203, struct.pack(">qqh", item["uid"], exchange["id"], 2)
        )

        deltas_by_character = {}
        for character_id, _generation, opcode, body in self.world.sent:
            if opcode in (13084, 13636):
                deltas_by_character.setdefault(character_id, []).append(
                    (opcode, struct.unpack_from(">h", body, 17)[0])
                )
        # The inviter already received the quantity-4 delta before its ACK
        # response was lost. The invitee's previous quantity-4 snapshot was
        # still pending, so it must receive that snapshot and then the newer
        # quantity-2 removal to reach the same final UI state.
        self.assertEqual([(13084, 2)], deltas_by_character[inviter["character"]["id"]])
        self.assertEqual(
            [(13636, 4), (13084, 2)], deltas_by_character[invitee["character"]["id"]]
        )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT quantity FROM player_exchange_items WHERE exchange_id=%s AND uid=%s",
                (exchange["id"], item["uid"]),
            )["quantity"],
        )

    def test_partial_send_failure_is_not_replayed_to_same_generation(self):
        inviter, invitee = self.player("partial-inviter"), self.player(
            "partial-invitee"
        )
        exchange = self.invite(inviter, invitee)
        self.request(invitee, 12997, struct.pack(">qB", exchange["id"], 0))
        item = self.grant_item(inviter, 3)
        self.world.sent.clear()
        self.world.attempts.clear()
        self.world.fail_once = (
            inviter["character"]["id"],
            inviter["generation"],
            13486,
        )

        self.request(
            inviter, 13037, struct.pack(">qqh", item["uid"], exchange["id"], 3)
        )

        self.assertTrue(self.world._failed)
        first_attempts = list(self.world.attempts)
        inviter_attempts = [
            entry for entry in first_attempts if entry[0] == inviter["character"]["id"]
        ]
        self.assertIn(13636, [entry[2] for entry in inviter_attempts])
        self.assertIn(13486, [entry[2] for entry in inviter_attempts])
        self.exchanges.drain()
        self.assertEqual(first_attempts, self.world.attempts)
        pending = self.fetchone(
            "SELECT delivered_at FROM player_exchange_outbox WHERE exchange_id=%s "
            "AND character_id=%s AND revision=(SELECT revision FROM player_exchanges WHERE id=%s) "
            "ORDER BY id LIMIT 1",
            (exchange["id"], inviter["character"]["id"], exchange["id"]),
        )
        self.assertIsNone(pending["delivered_at"])

    def test_replaced_generation_never_receives_old_exchange_outbox(self):
        inviter, invitee = self.player("generation-inviter"), self.player(
            "generation-invitee"
        )
        self.world.fail_once = (
            invitee["character"]["id"],
            invitee["generation"],
            12538,
        )
        exchange = self.invite(inviter, invitee)
        self.assertTrue(self.world._failed)
        old_generation = invitee["generation"]
        new_generation = self.store.begin_session(invitee["account"], ttl=10_000)
        character = self.store.select_character(
            invitee["account"], new_generation, invitee["character"]["id"]
        )
        replacement = dict(invitee, generation=new_generation, character=character)
        self.world.add(replacement)
        self.world.attempts.clear()

        self.exchanges.drain()

        self.assertEqual(
            [],
            [
                entry
                for entry in self.world.attempts
                if entry[0] == invitee["character"]["id"] and entry[1] == new_generation
            ],
        )
        self.assertIsNotNone(
            self.fetchone(
                "SELECT delivered_at FROM player_exchange_outbox WHERE exchange_id=%s "
                "AND character_id=%s AND generation=%s",
                (exchange["id"], invitee["character"]["id"], old_generation),
            )["delivered_at"]
        )
