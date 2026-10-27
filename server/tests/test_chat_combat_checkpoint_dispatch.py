"""Chat must not wait for another actor's native combat persistence lock."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from threading import Event, Thread
from types import SimpleNamespace
import time

from postgres_case import PostgresCase
from protocol_codec import decode_body
from wakfu_server.combat_shared import SharedFight
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.world import World
from wakfu_server import wire


SOURCE = Path(__file__).parents[1] / "local_game_server.py"


def reader_harness(namespace):
    tree = ast.parse(SOURCE.read_text())
    branches = []
    for opcode in (13917, 12366):
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == f"opcode == {opcode} and loaded"
        )
        branch = deepcopy(branch)
        branch.orelse = []
        branches.append(branch)
    tail = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and ast.unparse(node.test.left) == "opcode"
        and isinstance(node.test.ops[0], ast.NotIn)
        and isinstance(node.test.comparators[0], ast.Tuple)
        and {13917, 12366}.issubset(
            {
                value.value
                for value in node.test.comparators[0].elts
                if isinstance(value, ast.Constant)
            }
        )
    )
    function = ast.parse(
        "def dispatch(opcode, body):\n last_chat = 0\n active_request = request_trace\n while True:\n  pass\n"
    ).body[0]
    loop = function.body[-1]
    loop.body = (
        branches
        + [deepcopy(tail)]
        + ast.parse("active_request.finish()\nactive_request = None\nbreak").body
    )

    class RequestBoundary(ast.NodeTransformer):
        def visit_Continue(self, node):
            # This harness supplies one received frame, rather than receiving
            # the next socket frame at the top of the production outer loop.
            return ast.copy_location(ast.Break(), node)

    RequestBoundary().visit(function)
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["dispatch"]


class ChatCombatCheckpointDispatchTests(PostgresCase):
    def test_native_private_chat_ignores_busy_fight_but_actions_stay_durable(self):
        self.store.clock = lambda: 2_000_000_000.0
        sent = []
        world = World(
            lambda _: b"",
            lambda _: b"",
            lambda peer, opcode, body: sent.append((peer, opcode, body)),
        )
        players = []
        for account_name, name in (("sender", "Sender"), ("target", "Target")):
            account = self.store.register(account_name, "test-password")["id"]
            character = self.store.create_character(account, name)
            generation = self.store.begin_session(account)
            character = self.store.select_character(
                account, generation, character["id"]
            )
            character = dict(character, map_id=1134, instance_id=0)
            world.join(generation, name, character)
            players.append((account, generation, character))
        account, generation, character = players[0]
        pc = Actor(character["id"], 0, (0, 0, 0), 60, 6, 3, 10, 1, account, True)
        npc = Actor(-200, 1, (1, 0, 0), 12, 6, 3, 5, 1)
        fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        fight.ready(account)
        shared = SharedFight(fight, 1134, 0, None)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(77,'active')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(77,%s,%s,0)",
                (character["id"], account),
            )
        checkpoints = Checkpoints(self.store)
        checkpoint_calls = []
        status = [None]

        def checkpoint_fight():
            checkpoint_calls.append(status[0])
            return checkpoints.save_shared(
                shared, account, generation, status=status[0]
            )

        finished = Event()
        namespace = dict(
            loaded=True,
            WORLD=world,
            STORE=self.store,
            character=character,
            account_id=account,
            generation=generation,
            decode_body=decode_body,
            SOCIAL_CONTACTS=SimpleNamespace(private_chat_block_reason=lambda *_: None),
            time=time,
            wire=wire,
            record=lambda **_: None,
            send=lambda *args: self.fail("Unexpected private chat rejection"),
            checkpoint_fight=checkpoint_fight,
            request_trace=SimpleNamespace(finish=finished.set),
            connection=object(),
            service="world",
        )
        dispatch = reader_harness(namespace)
        target = players[1][2]["name"].encode()
        text = "hola".encode()
        body = bytes([len(target)]) + target + struct.pack(">H", len(text)) + text
        locked, release, completed = Event(), Event(), Event()
        errors = []

        def combat_owner():
            with shared.lock:
                locked.set()
                release.wait(3)

        def chat_reader():
            try:
                dispatch(13917, body)
            except Exception as error:
                errors.append(error)
            finally:
                completed.set()

        owner = Thread(target=combat_owner)
        reader = Thread(target=chat_reader)
        sent.clear()
        owner.start()
        self.assertTrue(locked.wait(1))
        reader.start()
        try:
            self.assertTrue(
                completed.wait(1), "Chat reader waited for a fight checkpoint"
            )
            self.assertEqual(errors, [])
            self.assertTrue(finished.is_set())
            self.assertEqual(checkpoint_calls, [])
            self.assertEqual(
                [message[:2] for message in sent], [("Target", 720), ("Sender", 720)]
            )
        finally:
            release.set()
            owner.join(3)
            reader.join(3)
        # The same production request tail still persists accepted actions,
        # unknown requests, and explicit terminal barriers against real SQL.
        dispatch(13260, b"")
        self.assertEqual(shared.checkpoint_revision, 1)
        pc.hp = 55
        dispatch(65535, b"")
        saved = checkpoints.read(account, 77)
        self.assertEqual(saved["snapshot"]["actors"][str(pc.id)]["hp"], 55)
        self.assertEqual(saved["revision"], 2)
        status[0] = "aborted"
        dispatch(13952, b"")
        self.assertTrue(shared.checkpoint_terminal)
        self.assertEqual(checkpoints.read(account, 77)["status"], "aborted")
        self.assertEqual(checkpoint_calls, [None, None, "aborted"])
        commands = []
        namespace["os"] = SimpleNamespace(environ={"WAKFU_TEST_CONSOLE": "1"})
        namespace["execute_test_command"] = commands.append
        command = b"!astrub"
        dispatch(12366, struct.pack(">H", len(command)) + command)
        self.assertEqual(commands, ["!astrub"])
        self.assertEqual(checkpoint_calls, [None, None, "aborted"])
