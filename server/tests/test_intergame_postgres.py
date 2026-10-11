import json
import socket
import ssl
import struct
import subprocess
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from postgres_case import PostgresCase
from wakfu_server import intergame_codec as codec
from wakfu_server.intergame_domain import Intergame, channel_id
from wakfu_server.intergame_transport import make_server
from wakfu_server.shop_domain import ShopService
from wakfu_server.shop_http import ShopAdapter


class IntergamePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        # Allows independent testing against the exact existing prefix while
        # unrelated reserved migrations are still being prepared.
        with self.store.connection() as db:
            if (
                db.execute(
                    "SELECT to_regclass('intergame_tokens') AS table_name"
                ).fetchone()["table_name"]
                is None
            ):
                db.execute(
                    (
                        Path(__file__).resolve().parents[1]
                        / "migrations/138_intergame_chat.sql"
                    ).read_text()
                )
        self.clock = [2_000_000_000.0]
        self.store.clock = lambda: self.clock[0]
        self.domain = Intergame(self.store)
        self.first = self.account()
        self.second = self.account()
        self.third = self.account()

    def account(self):
        result = self.store.register("inter" + uuid.uuid4().hex[:12], "test-password")
        generation = self.store.begin_session(result["id"], ttl=3600)
        result["generation"] = generation
        result["account_id"] = result["id"]
        result["api_key"] = self.store.issue_token(
            result["id"], "api", generation=generation, ttl=3600
        )
        return result

    def token(self, identity):
        return self.domain.issue_token(identity["api_key"])["token"]

    def friends(self, first=None, second=None):
        first, second = first or self.first, second or self.second
        with self.store.connection() as db:
            for owner, contact in (
                (first["id"], second["id"]),
                (second["id"], first["id"]),
            ):
                db.execute(
                    "INSERT INTO account_social_contacts(owner_account_id,contact_account_id,relation) VALUES(%s,%s,'friend')",
                    (owner, contact),
                )

    def send(self, identity=None, target=None, text="Native intergame"):
        identity, target = identity or self.first, target or self.second
        return self.domain.handle(
            identity,
            "channel.CreateChannelMessageCmd",
            {
                "author_user_id": identity["id"],
                "channel_id": channel_id(identity["id"], target["id"]),
                "content": text,
            },
        )

    def test_game99_native_http_issues_real_single_use_session_token(self):
        adapter = ShopAdapter(ShopService(self.store))
        response = adapter.dispatch(
            "GET",
            "/json/Ankama/v5/Account/CreateToken?game=99",
            {},
            "",
            self.first["api_key"],
        )
        identity = self.domain.authenticate(response["token"])
        self.assertEqual(identity["account_id"], self.first["id"])
        with self.assertRaises(PermissionError):
            self.domain.authenticate(response["token"])
        for method, path in [
            ("POST", "?game=99"),
            ("GET", "?game=3"),
            ("GET", "?game=99&game=99"),
        ]:
            with self.subTest(method=method, path=path), self.assertRaises(ValueError):
                adapter.dispatch(
                    method,
                    "/json/Ankama/v5/Account/CreateToken" + path,
                    {},
                    "",
                    self.first["api_key"],
                )
        with self.assertRaises(PermissionError):
            adapter.dispatch(
                "GET", "/json/Ankama/v5/Account/CreateToken?game=99", {}, "", "invalid"
            )

    def test_token_replay_race_expiry_and_replaced_session_are_rejected(self):
        token = self.token(self.first)

        def consume(_):
            try:
                self.domain.authenticate(token)
                return True
            except PermissionError:
                return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(consume, range(2))), [False, True])
        expired = self.token(self.first)
        self.clock[0] += 61
        with self.assertRaises(PermissionError):
            self.domain.authenticate(expired)
        pending = self.token(self.first)
        self.store.begin_session(self.first["id"])
        with self.assertRaises(PermissionError):
            self.domain.authenticate(pending)
        with self.assertRaises((PermissionError, ValueError)):
            self.domain.handle(
                self.first, "user.ListUserFriendsCmd", {"user_id": self.first["id"]}
            )

    def test_native_friend_invitation_acceptance_populates_authoritative_directory(
        self,
    ):
        name, value, events = self.domain.handle(
            self.first,
            "friend_invite.CreateFriendInviteCmd",
            {
                "inviter_user_id": self.first["id"],
                "recipient_user_id": self.second["id"],
            },
        )
        self.assertEqual(name, "friend_invite.FriendInvite")
        self.assertEqual(
            {row[0] for row in events}, {self.first["id"], self.second["id"]}
        )
        for _, event_name, body in events:
            codec.event(event_name, body)
        request = {
            "inviter_user_id": self.first["id"],
            "recipient_user_id": self.second["id"],
            "reason": 0,
        }
        with self.assertRaises(PermissionError):
            self.domain.handle(
                self.third, "friend_invite.DeleteFriendInviteCmd", request
            )
        _, _, events = self.domain.handle(
            self.second, "friend_invite.DeleteFriendInviteCmd", request
        )
        for _, event_name, body in events:
            codec.event(event_name, body)
        name, value, _ = self.domain.handle(
            self.first, "user.ListUserFriendsCmd", {"user_id": self.first["id"]}
        )
        self.assertEqual(name, "user.FriendList")
        self.assertEqual(value["values"][0]["user"]["user_id"], self.second["id"])
        self.assertEqual(value["values"][0]["user"]["tag"], str(self.second["id"]))

    def test_direct_messages_use_real_accounts_bounded_text_and_durable_history(self):
        self.friends()
        name, message, events = self.send(text="Español 🌱")
        self.assertEqual(name, "channel.ChannelMessage")
        self.assertEqual(message["author"]["user_id"], self.first["id"])
        self.assertEqual(
            {row[0] for row in events}, {self.first["id"], self.second["id"]}
        )
        for _, event_name, value in events:
            codec.event(event_name, value)
        with self.assertRaises(PermissionError):
            self.send()
        self.clock[0] += 61
        self.send(identity=self.second, target=self.first, text="Reply")
        name, history, _ = Intergame(self.reopen()).handle(
            self.first,
            "channel.ListChannelMessagesCmd",
            {
                "channel_id": message["channel_id"],
                "limit": 20,
            },
        )
        self.assertEqual(name, "channel.ChannelMessageList")
        self.assertEqual(
            [row["content"] for row in history["values"]], ["Español 🌱", "Reply"]
        )
        with self.assertRaises(PermissionError):
            self.domain.handle(
                self.third,
                "channel.ListChannelMessagesCmd",
                {"channel_id": message["channel_id"]},
            )
        with self.assertRaises(ValueError):
            self.send(text="ñ" * 1025)
        with self.assertRaises(ValueError):
            self.domain.handle(
                self.first,
                "channel.ListChannelMessagesCmd",
                {
                    "channel_id": message["channel_id"],
                    "before": str(1 << 63),
                },
            )

    def test_spoofed_accounts_unfriended_ignored_and_dnd_messages_are_rejected(self):
        with self.assertRaises(PermissionError):
            self.send()
        self.friends()
        with self.assertRaises(PermissionError):
            self.domain.handle(
                self.first,
                "channel.CreateChannelMessageCmd",
                {
                    "author_user_id": self.second["id"],
                    "channel_id": channel_id(self.first["id"], self.second["id"]),
                    "content": "spoof",
                },
            )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_social_preferences(account_id,do_not_disturb) VALUES(%s,true)",
                (self.second["id"],),
            )
        with self.assertRaises(PermissionError):
            self.send()
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_social_preferences SET do_not_disturb=false WHERE account_id=%s",
                (self.second["id"],),
            )
            db.execute(
                "UPDATE account_social_contacts SET relation='ignore' WHERE owner_account_id=%s AND contact_account_id=%s",
                (self.second["id"], self.first["id"]),
            )
        with self.assertRaises(PermissionError):
            self.send()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM intergame_messages"
                ).fetchone()["count"],
                0,
            )

    def test_real_tls_spin_auth_directory_and_two_account_message_delivery(self):
        self.friends()
        with tempfile.TemporaryDirectory() as temporary:
            cert, key = Path(temporary) / "cert.pem", Path(temporary) / "key.pem"
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-days",
                    "1",
                    "-subj",
                    "/CN=localhost",
                    "-keyout",
                    str(key),
                    "-out",
                    str(cert),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            server = make_server(self.domain, context, "127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            sockets = []
            try:

                def receive(peer):
                    def exact(size):
                        data = b""
                        while len(data) < size:
                            chunk = peer.recv(size - len(data))
                            if not chunk:
                                raise EOFError()
                            data += chunk
                        return data

                    size = struct.unpack(">I", exact(4))[0]
                    body = exact(size - 4)
                    return body[0], body[1:]

                def connect(identity):
                    context = ssl._create_unverified_context()
                    peer = context.wrap_socket(
                        socket.create_connection(server.server_address, timeout=5),
                        server_hostname="localhost",
                    )
                    sockets.append(peer)
                    peer.sendall(codec.spin(1))
                    self.assertEqual(receive(peer), (2, b""))
                    peer.sendall(
                        codec.spin(
                            0,
                            json.dumps(
                                {"token": self.token(identity), "clientType": 2}
                            ).encode(),
                        )
                    )
                    kind, body = receive(peer)
                    self.assertEqual(json.loads(body), {"success": True, "errCode": 0})
                    return peer

                first, second = connect(self.first), connect(self.second)

                def request(peer, name, value, correlation):
                    peer.sendall(
                        codec.spin(
                            0,
                            codec.encode(
                                "transport.Frame",
                                {
                                    "request": {
                                        "correlation_id": correlation,
                                        "payload": {
                                            "id": codec.IDS[name],
                                            "data": codec.encode(name, value),
                                        },
                                    }
                                },
                            ),
                        )
                    )

                request(
                    first, "user.ListUserFriendsCmd", {"user_id": self.first["id"]}, 7
                )
                response = codec.decode("transport.Frame", receive(first)[1])[
                    "response"
                ]
                self.assertEqual(response["status"], 1)
                self.assertEqual(
                    response["payload"]["id"], codec.IDS["user.FriendList"]
                )
                request(
                    first,
                    "channel.CreateChannelMessageCmd",
                    {
                        "author_user_id": self.first["id"],
                        "channel_id": channel_id(self.first["id"], self.second["id"]),
                        "content": "TLS native message",
                    },
                    8,
                )
                self.assertEqual(
                    codec.decode("transport.Frame", receive(first)[1])["response"][
                        "status"
                    ],
                    1,
                )
                for peer in (first, second):
                    event = codec.decode("transport.Frame", receive(peer)[1])["event"]
                    message = codec.decode(codec.NAMES[event["id"]], event["data"])[
                        "message"
                    ]
                    self.assertEqual(message["content"], "TLS native message")
            finally:
                server.close_peers()
                for peer in sockets:
                    peer.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
