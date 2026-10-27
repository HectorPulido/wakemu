"""Native login/renewal keys authenticate through the real local shop HTTP path."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import struct
import threading
from types import SimpleNamespace
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

from psycopg import Error as DatabaseError
from psycopg_pool import PoolTimeout
from postgres_case import PostgresCase
from protocol_codec import Reader, decode_body
from wakfu_server.shop_domain import ShopService
from wakfu_server.shop_http import make_server


class ShopNativeAuthenticationTests(PostgresCase):
    def test_initial_and_renewed_native_keys_real_http_and_rejection_fences(self):
        clock = [2_000_000_000.0]
        self.store.clock = lambda: clock[0]
        account = self.store.register("native-shop-auth", "local-password")["id"]
        generation = self.store.begin_session(account)
        service = ShopService(self.store)
        server = make_server(service, host="127.0.0.1", port=0)
        worker = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.01), daemon=True
        )
        worker.start()

        def close_http():
            server.shutdown()
            server.server_close()
            worker.join(timeout=1)

        self.addCleanup(close_http)
        endpoint = f"http://127.0.0.1:{server.server_port}/json/Ankama/v5/Shop/GetAccessTokenFromAnkamaApiKey"

        def http_auth(key):
            request = urllib.request.Request(endpoint, headers={"APIKEY": key})
            try:
                with urllib.request.urlopen(request, timeout=2) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        functions = [
            next(
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == name
            )
            for name in ("pack_text", "send_shop_authentication")
        ]
        sent, records = [], []
        namespace = dict(
            STORE=self.store,
            struct=struct,
            account_id=None,
            generation=None,
            service="world",
            connection=object(),
            LOCK=threading.RLock(),
            LIVE={},
            decode_body=decode_body,
            DatabaseError=DatabaseError,
            PoolTimeout=PoolTimeout,
            replay=Mock(),
            wire=SimpleNamespace(
                account_kamas=lambda amount: struct.pack(">q", amount)
            ),
            send=lambda peer, channel, opcode, body: sent.append((opcode, body)),
            record=lambda **row: records.append(row),
        )
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"),
            namespace,
        )

        def dispatch(opcode, body):
            sent.clear()
            branch = deepcopy(
                next(
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.If)
                    and ast.unparse(node.test) == f"opcode == {opcode}"
                )
            )
            branch.orelse = []
            loop = ast.For(
                target=ast.Name(id="_request", ctx=ast.Store()),
                iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                body=[branch],
                orelse=[],
            )
            namespace.update(opcode=opcode, body=body)
            exec(
                compile(
                    ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])),
                    str(source),
                    "exec",
                ),
                namespace,
            )
            return list(sent)

        def token_count():
            with self.store.connection() as db:
                return db.execute(
                    "SELECT count(*) AS n FROM tokens WHERE account_id=%s AND kind='api'",
                    (account,),
                ).fetchone()["n"]

        def native_key(packets):
            payloads = [body for opcode, body in packets if opcode == 22995]
            self.assertEqual(len(payloads), 1)
            reader = Reader(payloads[0])
            key, expires_ms = reader.text(), reader.number("q")
            reader.finish()
            self.assertEqual(expires_ms, int((clock[0] + 86400) * 1000))
            self.assertEqual(service.authenticate(key)["account_id"], account)
            status, result = http_auth(key)
            self.assertEqual(status, 200)
            self.assertTrue(result["token"] == key)
            return key

        ticket = self.store.issue_token(
            account, "ticket", generation=generation, realm_id=10
        )
        packets = dispatch(
            426, namespace["pack_text"](ticket) + namespace["pack_text"]("test-machine")
        )
        initial = native_key(packets)
        self.assertEqual(namespace["generation"], generation)
        self.assertEqual(records[-1]["renewal"], False)
        self.assertEqual(token_count(), 1)
        clock[0] += 30
        renewed = native_key(dispatch(22954, namespace["pack_text"]("es_ES")))
        self.assertNotEqual(self.store.digest(initial), self.store.digest(renewed))
        self.assertEqual(service.authenticate(renewed)["generation"], generation)
        self.assertEqual(http_auth(initial)[0], 200)
        self.assertTrue(records[-1]["renewal"])
        self.assertEqual(token_count(), 2)

        invalid = [
            b"",
            b"\x00\x00\x00\x02e",
            b"\x00\x00\x00\x01\xff",
            namespace["pack_text"]("es") + b"trailing",
            *[
                namespace["pack_text"](locale)
                for locale in ("", "e", "es/../private", "es-", "es-123456789", "☃☃")
            ],
        ]
        for body in invalid:
            with self.subTest(malformed_packet=body):
                before = token_count()
                packets = dispatch(22954, body)
                self.assertEqual([opcode for opcode, _ in packets], [349])
                subtype, size = struct.unpack(">hh", packets[0][1][:4])
                self.assertEqual((subtype, size), (4, len(packets[0][1][4:])))
                self.assertIn("tienda", packets[0][1][4:].decode("utf-8"))
                self.assertEqual(token_count(), before)
                self.assertEqual(records[-1]["event"], "shop_authentication_rejected")

        replacement = self.store.begin_session(account)
        self.assertEqual(http_auth(initial)[0], 401)
        self.assertEqual(http_auth(renewed)[0], 401)
        before = token_count()
        self.assertEqual(
            [opcode for opcode, _ in dispatch(22954, namespace["pack_text"]("en-US"))],
            [349],
        )
        self.assertEqual(token_count(), before)
        namespace["generation"] = replacement
        fresh = native_key(dispatch(22954, namespace["pack_text"]("en-US")))
        self.assertEqual(service.authenticate(fresh)["generation"], replacement)

        issued = []
        issue = self.store.issue_token

        def replace_during_issue(*args, **kwargs):
            key = issue(*args, **kwargs)
            issued.append(key)
            self.store.begin_session(account)
            return key

        before = token_count()
        with patch.object(self.store, "issue_token", side_effect=replace_during_issue):
            packets = dispatch(22954, namespace["pack_text"]("es"))
        self.assertEqual([opcode for opcode, _ in packets], [349])
        self.assertEqual(token_count(), before)
        self.assertEqual(http_auth(issued[0])[0], 401)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM tokens WHERE digest=%s",
                    (self.store.digest(issued[0]),),
                ).fetchone()
            )
        for row in records:
            self.assertFalse({"token", "shop_key", "api_key"}.intersection(row))
