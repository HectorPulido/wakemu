"""Real socket framing and exact selection branch over an isolated PostgreSQL Store.

This is a bounded dispatcher regression, not a full World/TLS/native UI test.
Absolute bootstrap/inventory publication boundaries are spies; Store selection,
lease fencing, achievement reward drain and native UID reservations are real.
"""
import ast
import copy
import hashlib
import os
from pathlib import Path
import queue
import socket
import struct
import threading
import traceback
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase, isolated_test_url
from protocol_codec import decode_body
from wakfu_server import builds, health_store
from wakfu_server.achievements import storage


class SelectionStoreSpy:
    def __init__(self, store):
        self.actual = store
        self.selection_calls = []

    def __getattr__(self, name):
        return getattr(self.actual, name)

    def select_character(self, account, generation, character):
        self.selection_calls.append((account, generation, character))
        return self.actual.select_character(account, generation, character)


def compile_dispatcher(source, namespace):
    """Use complete production23664 and33 bodies, including the retry continue."""
    tree = ast.parse(source.read_text())
    selection = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and ast.unparse(node.test) == "opcode == 23664"
    )
    ping = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and ast.unparse(node.test) == "opcode == 33"
    )
    receive = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "receive"
    )
    worker = ast.parse(
        """def dispatch(connection):
    selected = False
    character = None
    while True:
        length = struct.unpack(">I", receive(connection, 4))[0]
        if not 7 <= length <= 327670:
            raise ValueError("Invalid native frame size")
        route, opcode = struct.unpack(">BH", receive(connection, 3))
        if route != 3:
            raise ValueError("Invalid native route")
        body = receive(connection, length - 7)
"""
    ).body[0]
    branch = copy.deepcopy(selection)
    branch.orelse = [
        ast.If(
            test=copy.deepcopy(ping.test),
            body=copy.deepcopy(ping.body),
            orelse=[
                ast.Raise(
                    exc=ast.Call(
                        func=ast.Name(id="ValueError", ctx=ast.Load()),
                        args=[ast.Constant("Unsupported scoped opcode")],
                        keywords=[],
                    ),
                    cause=None,
                )
            ],
        )
    ]
    worker.body[-1].body.append(branch)
    module = ast.fix_missing_locations(
        ast.Module(body=[copy.deepcopy(receive), worker], type_ignores=[])
    )
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["dispatch"]


class CharacterSelectionSocketPostgresTests(PostgresCase):
    def setUp(self):
        # Fail explicitly rather than introducing an unexecuted skip as success.
        isolated_test_url()
        source_name = os.environ.get("WAKFU_SELECTION_DISPATCH_SOURCE") or str(
            Path(__file__).resolve().parents[1] / "local_game_server.py"
        )
        self.source = Path(source_name).resolve()
        super().setUp()
        self.account = self.store.register(
            "selection-socket-owner", "isolated-test-password"
        )["id"]
        self.actor = self.store.create_character(
            self.account, "Selection Socket", breed=8
        )
        self.other = self.store.create_character(
            self.account, "Selection Other", breed=8
        )
        self.generation = self.store.begin_session(self.account)
        self.spy = SelectionStoreSpy(self.store)
        self.events = queue.Queue()
        self.failures = queue.Queue()
        self.calls = []
        client, server = socket.socketpair()
        client.settimeout(10)
        server.settimeout(10)
        self.client, self.server = client, server
        self.addCleanup(client.close)
        self.addCleanup(server.close)

        def send(connection, service, opcode, body):
            connection.sendall(struct.pack(">IH", 6 + len(body), opcode) + body)

        def record(**event):
            self.events.put(event)

        def publication_replay(*args, **kwargs):
            self.calls.append(("absolute_bootstrap_boundary", args[1:3]))

        def rich_inventory(character):
            self.calls.append(("rich_inventory_boundary", character["id"]))
            return (
                65001,
                b"",
            )  # Explicit fixture boundary marker, never a client oracle.

        self.namespace = dict(
            socket=socket,
            struct=struct,
            decode_body=decode_body,
            STORE=self.spy,
            account_id=self.account,
            generation=self.generation,
            service="world",
            record=record,
            send=send,
            builds=builds,
            health_store=health_store,
            is_dungeon_run=lambda identity: False,
            COMBAT_GROUPS=object(),  # Existing group-store boundary, no encounter here.
            COMBAT_SESSIONS=SimpleNamespace(
                session=lambda *args: args,
                live_reconnect_available=lambda session: False,
                reconcile_disconnected_pve=lambda *args, **kwargs: None,
                recover_withdrawn_pve=lambda session: None,
            ),
            deliver_custom_task_rewards=lambda **kwargs: self.calls.append(
                ("custom_task_boundary", kwargs)
            ),
            POSITIONS=SimpleNamespace(
                attach=lambda *args: self.calls.append(
                    ("position_attach", args[2]["id"])
                )
            ),
            Movement=lambda position: dict(position),
            replay=publication_replay,
            rich_inventory_packet=rich_inventory,
        )
        dispatch = compile_dispatcher(self.source, self.namespace)

        def run():
            try:
                dispatch(server)
            except EOFError:
                pass
            except BaseException as error:
                self.failures.put(error)
            finally:
                server.close()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_worker)

    def stop_worker(self):
        self.client.close()
        self.thread.join(5)
        self.assertFalse(self.thread.is_alive(), "Scoped dispatcher failed to stop")

    def send(self, opcode, body=b""):
        self.client.sendall(struct.pack(">IBH", 7 + len(body), 3, opcode) + body)

    def exact(self, count):
        data = bytearray()
        while len(data) < count:
            part = self.client.recv(count - len(data))
            if not part:
                raise EOFError("Scoped server closed the real socket")
            data.extend(part)
        return bytes(data)

    def receive(self):
        length = struct.unpack(">I", self.exact(4))[0]
        frame = self.exact(length - 4)
        return struct.unpack(">H", frame[:2])[0], frame[2:]

    def select_body(self, actor=None, name=None):
        actor = self.actor if actor is None else actor
        value = actor["name"] if name is None else name
        raw = value.encode("utf-8")
        return struct.pack(">qI", actor["id"], len(raw)) + raw

    def first_selection(self):
        self.send(23664, self.select_body())
        # Real initialize_pool is the last outgoing message in the exact branch.
        try:
            while self.receive()[0] != 13778:
                pass
        except EOFError:
            self.thread.join(5)
            try:
                error = self.failures.get_nowait()
            except queue.Empty:
                raise
            details = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            raise AssertionError(
                "First selection worker failed before13778:\n" + details
            ) from error
        event = self.events.get(timeout=10)
        self.assertEqual(event["event"], "character_selected")
        self.assertEqual(event["character_id"], self.actor["id"])
        self.assertEqual(len(self.spy.selection_calls), 1)

    def uid_and_xp(self):
        with self.store.connection() as db:
            uids = [
                row["uid"]
                for row in db.execute(
                    "SELECT uid FROM inventory_reserved_uids WHERE account_id=%s ORDER BY uid",
                    (self.account,),
                )
            ]
            sequence = db.execute("SELECT last_value FROM inventory_uid").fetchone()[
                "last_value"
            ]
            xp = self.store.character(self.account, self.actor["id"], db)["xp"]
            pending = storage.pending_rewards(db, self.actor["id"])
        return uids, sequence, xp, pending

    def assert_closed_for_invalid_selection(self, body):
        self.send(23664, body)
        with self.assertRaises(EOFError):
            self.receive()
        error = self.failures.get(timeout=10)
        self.assertIsInstance(error, ValueError)
        self.assertEqual(
            str(error), "Authentication required or character already selected"
        )
        self.assertEqual(len(self.spy.selection_calls), 1)

    def test_same_owned_retry_keeps_socket_and_does_not_reselect_republish_or_reallocate(
        self,
    ):
        original_xp = self.actor["xp"]
        with self.store.connection() as db:
            storage.claim_reward(
                db, self.actor["id"], 3800, "once", 2, dict(aeV=6, ckl=[100])
            )
        self.first_selection()
        before = self.uid_and_xp()
        self.assertEqual(len(before[0]), 32)
        self.assertEqual(before[2], original_xp + 100)
        self.assertEqual(before[3], [])
        before_calls = list(self.calls)
        self.send(23664, self.select_body())
        # Exact production33 ping body executes next, proving continued socket use.
        # The original unpatched branch instead closes this actual socket here.
        self.send(33, b"retry-alive")
        self.assertEqual(self.receive(), (23, b"\x01retry-alive"))
        self.assertEqual(self.receive(), (309, struct.pack(">I", 12345)))
        event = self.events.get(timeout=10)
        self.assertEqual(
            event,
            {
                "event": "character_selection_retry_ignored",
                "character_id": self.actor["id"],
            },
        )
        self.assertEqual(self.uid_and_xp(), before)
        self.assertEqual(self.calls, before_calls)
        self.assertEqual(len(self.spy.selection_calls), 1)
        self.assertEqual(
            sum(call[0] == "absolute_bootstrap_boundary" for call in self.calls), 1
        )
        self.assertTrue(self.failures.empty())

    def test_other_owned_character_cannot_switch_through_a_retry(self):
        self.first_selection()
        self.assert_closed_for_invalid_selection(self.select_body(self.other))

    def test_name_mismatch_cannot_be_accepted_as_an_idempotent_retry(self):
        self.first_selection()
        self.assert_closed_for_invalid_selection(self.select_body(name="Wrong Name"))

    def test_replaced_generation_does_not_receive_retry_acceptance(self):
        self.first_selection()
        self.store.begin_session(self.account)
        self.assert_closed_for_invalid_selection(self.select_body())

    def test_missing_authentication_cannot_receive_retry_acceptance(self):
        self.first_selection()
        self.namespace["account_id"] = None
        self.assert_closed_for_invalid_selection(self.select_body())


if __name__ == "__main__":
    unittest.main()
