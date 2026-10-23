import struct
import unittest
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from protocol_codec import decode_body
from wakfu_server import chat_channels, player_parties
from wakfu_server.world import World


class Peer:
    def __init__(self, name):
        self.name = name
        self.closed = False

    def shutdown(self, _how):
        self.closed = True


class ChatChannelTests(PostgresCase):
    def test_native_political_and_pvp_requests_require_native_sender_authority(self):
        from wakfu_server.native_world_context import battleground_worlds

        sender = self.player("sender")
        same = self.player("same", map_id=527)
        foreign = self.player("foreign")
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_chat_nations(character_id,nation_id) VALUES(%s,30)",
                (foreign["character"]["id"],),
            )
        # World membership publishes native roster snapshots independently of chat.
        self.sent.clear()
        for opcode in (12387, 13702):
            with self.assertRaisesRegex(ValueError, "requiere"):
                self.send(sender, opcode, {"text": "forged", "government_office": 1})
        self.assertEqual(self.sent, [])
        # A genuine native battleground map enables the existing same-nation
        # fanout, without granting any political office or PvP character rank.
        arena = self.player("arena", map_id=min(battleground_worlds()))
        self.sent.clear()
        self.assertEqual(self.send(arena, 13702, {"text": "hola"}), 3)
        self.assertEqual(
            {peer for peer, code, _ in self.sent},
            {p["peer"].name for p in (sender, same, arena)},
        )
        self.assertTrue(all(code == 632 for _, code, _ in self.sent))
        self.sent.clear()
        with self.assertRaisesRegex(ValueError, "too long"):
            self.send(arena, 13702, {"text": "ñ" * 2048})
        self.assertEqual(self.sent, [])

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.sent = []
        self.world = World(lambda c: b"", lambda c: b"", self._deliver)
        self.channels = chat_channels.Channels(self.store, self.world)

    def _deliver(self, peer, opcode, body):
        if peer.closed:
            raise BrokenPipeError("peer is disconnected")
        self.sent.append((peer.name, opcode, body))

    def player(self, label, *, map_id=1134, instance_id=0):
        account = self.store.register("cc" + uuid.uuid4().hex[:10], "test-password")[
            "id"
        ]
        letters = str.maketrans("0123456789", "abcdefghij")
        name = (label[:5] + uuid.uuid4().hex[:8]).translate(letters)
        # Keep account and character identity namespaces distinct even when
        # their independent sequences would otherwise both begin at 1.
        self.store.create_character(account, name + "B")
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        character.update(map_id=map_id, instance_id=instance_id)
        peer = Peer(name)
        self.world.join(generation, peer, character)
        return {
            "account": account,
            "generation": generation,
            "character": character,
            "peer": peer,
        }

    def preference(self, player, *, mask, community):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_chat_preferences(account_id,language_mask,community) "
                "VALUES(%s,%s,%s) ON CONFLICT(account_id) DO UPDATE SET "
                "language_mask=EXCLUDED.language_mask,community=EXCLUDED.community",
                (player["account"], mask, community),
            )

    def send(self, player, opcode, request):
        return self.channels.handle(
            opcode,
            request,
            player["account"],
            player["generation"],
            player["character"]["id"],
        )

    @staticmethod
    def native_request(opcode, text, *, language=1, group_id=0):
        encoded = text.encode("utf-8")
        string = struct.pack(">H", len(encoded)) + encoded
        if opcode == 13224:
            body = struct.pack(">q", group_id) + string
        elif opcode in (13188, 13831):
            body = bytes((language,)) + string
        else:
            body = string
        return decode_body("out", opcode, body)

    def test_trade_channel_payload_uses_account_id_and_reaches_public_peers_across_maps(
        self,
    ):
        sender = self.player("sender", map_id=1134, instance_id=0)
        remote = self.player("remote", map_id=527, instance_id=9)
        other = self.player("other", map_id=32, instance_id=1)
        self.preference(sender, mask=5, community=2)
        self.sent.clear()

        delivered = self.send(
            sender, 13074, self.native_request(13074, "  hola comercio  ")
        )

        self.assertEqual(delivered, 3)
        self.assertEqual(
            {(peer, opcode) for peer, opcode, _ in self.sent},
            {(p["peer"].name, 626) for p in (sender, remote, other)},
        )
        packet = self.sent[0][2]
        name_length = packet[0]
        offset = 1 + name_length
        mask, community, account_id, reserved = struct.unpack_from(
            ">BBqB", packet, offset
        )
        text_length = struct.unpack_from(">h", packet, offset + 11)[0]
        text = packet[offset + 13 : offset + 13 + text_length].decode()
        self.assertEqual(
            (mask, community, account_id, reserved, text),
            (5, 2, sender["account"], 0, "hola comercio"),
        )
        self.assertNotEqual(account_id, sender["character"]["id"])
        self.assertEqual(text_length, len(text.encode("utf-8")))

    def test_language_channels_filter_sender_authorization_and_recipient_masks(self):
        sender = self.player("sender")
        allowed = self.player("allowed", map_id=527)
        blocked = self.player("blocked", map_id=42)
        self.preference(sender, mask=0b0010, community=4)
        self.preference(allowed, mask=0b0010, community=1)
        self.preference(blocked, mask=0b0100, community=3)
        self.sent.clear()

        request = self.native_request(13188, "reclutamiento", language=1)
        self.assertEqual(self.send(sender, 13188, request), 2)
        self.assertEqual(
            {(peer, opcode) for peer, opcode, _ in self.sent},
            {(sender["peer"].name, 769), (allowed["peer"].name, 769)},
        )
        packet = next(
            body for peer, _, body in self.sent if peer == sender["peer"].name
        )
        self.assertEqual(packet[0], 1)
        name_length = packet[1]
        offset = 2 + name_length
        self.assertEqual(
            struct.unpack_from(">BBqB", packet, offset),
            (0b0010, 4, sender["account"], 0),
        )

        for invalid_language in (-1, 4, True):
            with self.subTest(language=invalid_language), self.assertRaisesRegex(
                ValueError, "idioma"
            ):
                self.send(
                    sender,
                    13188,
                    {"language_id": invalid_language, "text": "no permitido"},
                )
        self.preference(sender, mask=0b0001, community=4)
        with self.assertRaisesRegex(ValueError, "idioma"):
            self.send(sender, 13831, {"language_id": 1, "text": "fuera de cuenta"})

    def test_admin_channel_requires_admin_and_reaches_only_current_admins(self):
        sender, receiver, outsider = (
            self.player("sender"),
            self.player("receiver", map_id=527),
            self.player("outsider"),
        )
        request = {"text": "administration"}
        with self.assertRaisesRegex(ValueError, "administradora"):
            self.send(sender, 12116, request)
        with self.store.connection() as db:
            db.execute(
                "UPDATE accounts SET is_admin=true WHERE id=ANY(%s)",
                ([sender["account"], receiver["account"]],),
            )
        self.sent.clear()
        self.assertEqual(self.send(sender, 12116, request), 2)
        self.assertEqual(
            {peer for peer, _, _ in self.sent},
            {sender["peer"].name, receiver["peer"].name},
        )
        for _, opcode, body in self.sent:
            self.assertEqual(opcode, 762)
            self.assertEqual(body[:4], struct.pack(">i", 0))
            self.assertEqual(
                body[5 : 5 + body[4]].decode(), sender["character"]["name"]
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE accounts SET is_admin=false WHERE id=%s", (receiver["account"],)
            )
        self.sent.clear()
        self.assertEqual(self.send(sender, 12116, request), 1)
        self.assertEqual(self.sent[0][0], sender["peer"].name)

    def test_pvp_channel_uses_database_nation_across_maps_and_isolates_neutral(self):
        sender, same, other, neutral, second_neutral = (
            self.player("sender"),
            self.player("same", map_id=527, instance_id=8),
            self.player("other"),
            self.player("neutral"),
            self.player("neutral", map_id=777),
        )
        with self.store.connection() as db:
            for player, nation in ((sender, 30), (same, 30), (other, 31)):
                db.execute(
                    "INSERT INTO character_chat_nations(character_id,nation_id) VALUES(%s,%s)",
                    (player["character"]["id"], nation),
                )
        # Neither stale world metadata nor a forged request may choose the nation.
        request = {"text": "nation chat", "nation_id": 31}
        sender["character"]["nation_id"] = 31
        self.sent.clear()
        self.assertEqual(self.send(sender, 13702, request), 2)
        self.assertEqual(
            {(peer, opcode) for peer, opcode, _ in self.sent},
            {(p["peer"].name, 632) for p in (sender, same)},
        )
        self.sent.clear()
        self.assertEqual(self.send(neutral, 13702, request), 2)
        self.assertEqual(
            {peer for peer, _, _ in self.sent},
            {p["peer"].name for p in (neutral, second_neutral)},
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_chat_nations SET nation_id=31 WHERE character_id=%s",
                (same["character"]["id"],),
            )
        self.assertEqual(self.send(sender, 13702, request), 1)

    def test_political_channel_uses_database_nation_across_maps_and_isolates_neutral(
        self,
    ):
        sender, same, other, neutral, second_neutral = (
            self.player("sender"),
            self.player("same", map_id=527, instance_id=8),
            self.player("other"),
            self.player("neutral"),
            self.player("neutral", map_id=777),
        )
        with self.store.connection() as db:
            for player, nation in ((sender, 30), (same, 30), (other, 31)):
                db.execute(
                    "INSERT INTO character_chat_nations(character_id,nation_id) VALUES(%s,%s)",
                    (player["character"]["id"], nation),
                )
        # Neither stale world metadata nor a forged request may choose the nation.
        request = {"text": "nation chat", "nation_id": 31, "public": False}
        sender["character"]["nation_id"] = 31
        self.sent.clear()
        self.assertEqual(self.send(sender, 12387, request), 2)
        self.assertEqual(
            {(peer, opcode) for peer, opcode, _ in self.sent},
            {(p["peer"].name, 758) for p in (sender, same)},
        )
        self.sent.clear()
        self.assertEqual(self.send(neutral, 12387, request), 2)
        self.assertEqual(
            {peer for peer, _, _ in self.sent},
            {p["peer"].name for p in (neutral, second_neutral)},
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_chat_nations SET nation_id=31 WHERE character_id=%s",
                (same["character"]["id"],),
            )
        self.assertEqual(self.send(sender, 12387, request), 1)

    def test_party_channel_is_private_to_members_even_across_maps(self):
        leader = self.player("leader", map_id=1134)
        member = self.player("member", map_id=527, instance_id=15)
        outsider = self.player("outsider", map_id=1134)
        token = player_parties.invite(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            member["character"]["id"],
        )
        party_id = player_parties.answer(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            token,
            True,
        )
        self.sent.clear()

        delivered = self.send(
            leader,
            13224,
            self.native_request(13224, "mensaje privado", group_id=party_id),
        )

        self.assertEqual(delivered, 2)
        self.assertEqual(
            {(peer, opcode) for peer, opcode, _ in self.sent},
            {(leader["peer"].name, 606), (member["peer"].name, 606)},
        )
        self.assertNotIn(outsider["peer"].name, {peer for peer, _, _ in self.sent})
        body = self.sent[0][2]
        name_length = body[0]
        offset = name_length + 1
        self.assertEqual(
            struct.unpack_from(">q", body, offset + 2)[0], leader["account"]
        )
        self.assertNotEqual(
            struct.unpack_from(">q", body, offset + 2)[0], leader["character"]["id"]
        )

        with self.assertRaisesRegex(ValueError, "No perteneces"):
            self.send(
                leader,
                13224,
                self.native_request(13224, "spoof", group_id=party_id + 1),
            )

    def test_malformed_stale_identity_and_invalid_text_never_deliver(self):
        sender, other = self.player("sender"), self.player("other")
        self.sent.clear()
        with self.assertRaisesRegex(ValueError, "stale"):
            self.channels.handle(
                13074,
                {"text": "spoof"},
                other["account"],
                sender["generation"],
                sender["character"]["id"],
            )
        with self.assertRaisesRegex(ValueError, "comandos"):
            self.send(sender, 13074, {"text": "!give-admin"})
        with self.assertRaisesRegex(ValueError, "Invalid channel"):
            self.send(sender, 13074, {"text": "\x00hello"})
        with self.assertRaisesRegex(ValueError, "Invalid channel"):
            self.send(sender, 13074, {"text": "   "})
        with self.assertRaisesRegex(ValueError, "long"):
            self.send(sender, 13074, {"text": "é" * 1025})
        sender["generation"] = self.store.begin_session(sender["account"], ttl=10_000)
        with self.assertRaisesRegex(ValueError, "stale"):
            self.channels.handle(
                13074,
                {"text": "obsoleto"},
                sender["account"],
                sender["generation"],
                sender["character"]["id"],
            )
        self.assertEqual(self.sent, [])

    def test_preferences_and_database_rate_policy_are_read_on_each_call(self):
        sender, other = self.player("sender"), self.player("other", map_id=9)
        self.assertAlmostEqual(self.channels.minimum_interval(), 0.2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='chat_channel_policy'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "language_mask": 6,
                            "community": 4,
                            "maximum_bytes": 2048,
                            "minimum_interval_ms": 777,
                        }
                    ),
                ),
            )
        self.assertAlmostEqual(self.channels.minimum_interval(), 0.777)
        self.sent.clear()
        self.send(sender, 13074, self.native_request(13074, "primero"))
        self.preference(sender, mask=1, community=2)
        self.preference(other, mask=1, community=3)
        self.sent.clear()
        self.send(sender, 13074, self.native_request(13074, "actualizado"))
        self.assertTrue(
            all(
                struct.unpack_from(">BB", body, 1 + body[0]) == (1, 2)
                for _, _, body in self.sent
            )
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='chat_channel_policy'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "language_mask": 6,
                            "community": 4,
                            "maximum_bytes": True,
                            "minimum_interval_ms": True,
                        }
                    ),
                ),
            )
        with self.assertRaisesRegex(ValueError, "rate policy"):
            self.channels.minimum_interval()
        self.sent.clear()
        with self.assertRaisesRegex(ValueError, "policy"):
            self.send(sender, 13074, {"text": "policy inválida"})
        self.assertEqual(self.sent, [])

    def test_community_native_language_prefix_and_language_selection_decoder(self):
        sender, receiver = self.player("sender"), self.player("receiver", map_id=777)
        self.preference(sender, mask=0b0100, community=2)
        self.preference(receiver, mask=0b0100, community=1)
        self.sent.clear()
        request_body = b"\x02" + struct.pack(">H", len("bonjour")) + b"bonjour"
        request = decode_body("out", 13831, request_body)
        self.assertEqual(request, {"language_id": 2, "text": "bonjour"})
        self.assertEqual(self.send(sender, 13831, request), 2)
        for _peer, opcode, body in self.sent:
            self.assertEqual(opcode, 655)
            self.assertEqual(body[0], 2)
            length = body[1]
            offset = 2 + length
            self.assertEqual(
                struct.unpack_from(">BBqB", body, offset),
                (0b0100, 2, sender["account"], 0),
            )

    def test_protocol_decoder_rejects_truncated_or_trailing_channel_bodies(self):
        valid = struct.pack(">H", 2) + b"ok"
        for opcode, body in (
            (13074, valid[:-1]),
            (13074, valid + b"x"),
            (13188, b"\x01" + valid[:-1]),
            (13224, struct.pack(">q", 1) + valid[:-1]),
        ):
            with self.subTest(opcode=opcode, body=body.hex()), self.assertRaises(
                ValueError
            ):
                decode_body("out", opcode, body)


if __name__ == "__main__":
    unittest.main()


class ChatSenderEligibilityTests(unittest.TestCase):
    def test_native_office_and_world_flags_gate_only_their_original_channels(self):
        from wakfu_server import chat_sender_eligibility as eligibility
        from wakfu_server.native_world_context import battleground_worlds

        actor = dict(map_id=1134, government_office=1, is_admin=True)
        # Forged projection fields cannot override the native synchronized state.
        with patch.object(eligibility.nation_state, "synchro", return_value=bytes(27)):
            with self.assertRaisesRegex(ValueError, "cargo"):
                eligibility.require(12387, character=actor, nation_id=30)
        # This is an authoritative native synchronization fixture, not a new
        # government assignment producer. Production ordinary state stays zero.
        for office in (1, 10):
            with patch.object(
                eligibility.nation_state,
                "synchro",
                return_value=struct.pack(">q", office) + bytes(19),
            ):
                eligibility.require(12387, character=actor, nation_id=30)
                with self.assertRaisesRegex(ValueError, "cargo"):
                    eligibility.require(12387, character=actor, nation_id=0)
        for office in (-1, 11):
            with patch.object(
                eligibility.nation_state,
                "synchro",
                return_value=struct.pack(">q", office) + bytes(19),
            ):
                with self.assertRaisesRegex(ValueError, "cargo"):
                    eligibility.require(12387, character=actor, nation_id=30)
        for world in (1134, 999999):
            with self.assertRaisesRegex(ValueError, "mapa"):
                eligibility.require(13702, character=dict(map_id=world), nation_id=0)
        eligibility.require(
            13702, character=dict(map_id=min(battleground_worlds())), nation_id=0
        )
        # Other channels retain their own existing authority and routing.
        for opcode in (12116, 13074, 13224, 13188, 13831, 13744, 13917):
            eligibility.require(opcode, character={}, nation_id=0)
