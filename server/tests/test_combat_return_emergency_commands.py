"""Run the actual pending-return request gate with real retry contention."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import threading
from types import SimpleNamespace
import unittest

from wakfu_server.combat_return_command import PendingEmergencyCommand
from wakfu_server.position_buffer import PositionOwnerBusy
from wakfu_server.position_lifecycle import PendingPositionReturn
from postgres_case import PostgresCase


class PendingReturnEmergencyTests(unittest.TestCase):
    @staticmethod
    def idle_return(state):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        idle = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "idle"
        )
        branch = next(
            node
            for node in ast.walk(idle)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "pending_combat_return is not None"
        )
        function = ast.FunctionDef(
            name="retry_actual_return",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[ast.Global(names=["pending_combat_return"]), deepcopy(branch)],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, "<actual idle pending-return branch>", "exec"), state)
        return state["retry_actual_return"]()

    def guard(self, queue, opcode, text):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        gate = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "pending_combat_return is not None" in ast.unparse(node.test)
            and any(isinstance(child, ast.Continue) for child in ast.walk(node))
        )
        loop = ast.For(
            target=ast.Name(id="unused", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[deepcopy(gate), ast.parse("dispatched.append(opcode)").body[0]],
            orelse=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        raw = text.encode()
        state = dict(
            pending_combat_return=dict(held_requests=0, fight_id=99),
            pending_return_command=queue,
            opcode=opcode,
            body=struct.pack(">H", len(raw)) + raw,
            account_id=1,
            generation="current",
            character=dict(id=11),
            record=lambda **kwargs: None,
            information=lambda text: (674, b""),
            send=lambda *args: None,
            connection=None,
            service="world",
            dispatched=[],
        )
        exec(compile(module, "<actual pending-return gate>", "exec"), state)
        return state

    def test_busy_return_retains_one_emergency_and_holds_gameplay_until_flush(self):
        for command in ("!astrub", "!exitdungeon", "!winfight", "!losefight"):
            with self.subTest(command=command):
                retry, queue, completed = (
                    PendingPositionReturn(now=0),
                    PendingEmergencyCommand(),
                    [],
                )

                def busy_flush():
                    raise PositionOwnerBusy("real return-position contention")

                self.assertFalse(
                    retry.attempt(
                        now=0,
                        flush=busy_flush,
                        complete=lambda: completed.append(True),
                        busy=lambda *args: None,
                    )
                )
                state = self.guard(queue, 12366, command)
                self.assertEqual(state["dispatched"], [])
                self.assertEqual(queue.pending, ((1, "current", 11), command))
                self.guard(queue, 13260, "")
                self.guard(queue, 12366, "!losefight")
                self.assertEqual(queue.pending, ((1, "current", 11), command))
                self.assertFalse(completed)
                self.assertTrue(
                    retry.attempt(
                        now=1,
                        flush=lambda: None,
                        complete=lambda: completed.append(True),
                        busy=lambda *args: None,
                    )
                )
                self.assertEqual(completed, [True])
                self.assertEqual(
                    queue.take((1, "current", 11), valid_session=lambda: True), command
                )
                self.assertIsNone(
                    queue.take((1, "current", 11), valid_session=lambda: True)
                )

    def test_replaced_or_expired_lease_cannot_replay_and_other_chat_is_not_retained(
        self,
    ):
        for identity, live in (
            ((1, "new", 11), True),
            ((1, "current", 12), True),
            ((1, "current", 11), False),
        ):
            queue = PendingEmergencyCommand()
            self.guard(queue, 12366, "!astrub")
            self.assertIsNone(queue.take(identity, valid_session=lambda: live))
            self.assertIsNone(queue.pending)
        for text in ("hello", "!astrub someone", "!tp 527 0 32 0"):
            queue = PendingEmergencyCommand()
            self.guard(queue, 12366, text)
            self.assertIsNone(queue.pending)

    def test_actual_idle_replay_requires_completed_flush_and_discards_uncertain_return(
        self,
    ):
        for failed, live in ((False, True), (False, False), (True, True)):
            with self.subTest(failed=failed, live=live):
                queue, calls = PendingEmergencyCommand(), []
                self.guard(queue, 12366, "!astrub")

                def flush(**scope):
                    calls.append("flush")
                    if failed:
                        raise ValueError("return invariant changed")

                state = dict(
                    pending_combat_return=dict(
                        retry=PendingPositionReturn(now=0),
                        scope={},
                        complete=lambda: calls.append("complete"),
                        fight_id=99,
                        started_at=0,
                    ),
                    pending_return_command=queue,
                    account_id=1,
                    generation="current",
                    character=dict(id=11),
                    time=SimpleNamespace(monotonic=lambda: 1),
                    flush_positions=flush,
                    record=lambda **kwargs: None,
                    redact=str,
                    STORE=SimpleNamespace(current_character_session=lambda *args: live),
                    execute_test_command=lambda text: calls.append(text),
                    execute_dungeon_exit_command=lambda: calls.append("!exitdungeon"),
                )
                self.idle_return(state)
                self.assertIsNone(state["pending_combat_return"])
                self.assertIsNone(queue.pending)
                self.assertEqual(
                    calls,
                    ["flush"]
                    if failed
                    else ["flush", "complete"] + (["!astrub"] if live else []),
                )


class PendingReturnCommandPostgresTests(PostgresCase):
    def test_contended_position_return_replays_normal_commands_then_allows_new_selection(
        self,
    ):
        from psycopg import Error as DatabaseError
        from psycopg_pool import PoolTimeout
        from test_astrub_dispatch import AstrubDispatcherTests
        from wakfu_server.command_permissions import set_admin
        from wakfu_server.position_buffer import Positions

        for suffix, command in zip(
            ("Astrub", "Dungeon", "Victory", "Defeat"),
            ("!astrub", "!exitdungeon", "!winfight", "!losefight"),
        ):
            with self.subTest(command=command):
                self.account = self.store.register(
                    "return-command-" + suffix, "password"
                )["id"]
                set_admin(
                    self.store,
                    self.account,
                    True,
                    operator="fixture",
                    reason="isolated authorized pending-return command QA",
                )
                self.saved = self.store.create_character(
                    self.account, "Return " + suffix
                )
                self.generation = self.store.begin_session(self.account)
                self.store.select_character(
                    self.account, self.generation, self.saved["id"]
                )
                state, sent, actor = AstrubDispatcherTests.dispatcher(
                    self, complete=True
                )
                positions = Positions(
                    self.store, lease_active=self.store.current_character_session
                )
                positions.attach(self.account, self.generation, self.saved)
                moved = positions.move(
                    self.account,
                    self.generation,
                    self.saved["id"],
                    self.saved,
                    dict(x=self.saved["x"] + 1, y=self.saved["y"], z=self.saved["z"]),
                )
                queue = PendingEmergencyCommand()
                raw = command.encode()
                self.assertTrue(
                    queue.retain(
                        12366,
                        struct.pack(">H", len(raw)) + raw,
                        (self.account, self.generation, self.saved["id"]),
                    )
                )
                finished = []
                state.update(
                    character=moved,
                    POSITIONS=positions,
                    pending_return_command=queue,
                    pending_combat_return=dict(
                        retry=PendingPositionReturn(now=0),
                        scope=dict(account_id=self.account),
                        complete=lambda: finished.append(True),
                        fight_id=99,
                        started_at=0,
                    ),
                    flush_positions=positions.flush,
                    redact=str,
                    DatabaseError=DatabaseError,
                    PoolTimeout=PoolTimeout,
                )
                # The handler is the exact same extracted production helper as
                # incoming chat, including native exit then administrative fallback.
                tree = ast.parse(
                    (
                        Path(__file__).resolve().parents[1] / "local_game_server.py"
                    ).read_text()
                )
                helper = deepcopy(
                    next(
                        node
                        for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "execute_dungeon_exit_command"
                    )
                )
                exec(
                    compile(
                        ast.fix_missing_locations(
                            ast.Module(body=[helper], type_ignores=[])
                        ),
                        "<actual dungeon exit handler>",
                        "exec",
                    ),
                    state,
                )
                acquired, release = threading.Event(), threading.Event()

                def hold_real_position_owner():
                    with positions.account_barrier(self.account):
                        acquired.set()
                        release.wait(10)

                worker = threading.Thread(target=hold_real_position_owner)
                worker.start()
                self.assertTrue(acquired.wait(2))
                try:
                    PendingReturnEmergencyTests.idle_return(state)
                    self.assertFalse(finished)
                    self.assertFalse(sent)
                    self.assertIsNotNone(queue.pending)
                    self.assertEqual(
                        self.store.character(self.account, self.saved["id"])["x"],
                        self.saved["x"],
                    )
                finally:
                    release.set()
                    worker.join(2)
                state["pending_combat_return"]["retry"].next_attempt_at = 0
                PendingReturnEmergencyTests.idle_return(state)
                self.assertEqual(finished, [True])
                self.assertIsNone(queue.pending)
                self.assertIsNone(state["pending_combat_return"])
                stored = self.store.character(self.account, self.saved["id"])
                if command in ("!astrub", "!exitdungeon"):
                    self.assertEqual(
                        (
                            stored["map_id"],
                            stored["instance_id"],
                            stored["x"],
                            stored["y"],
                        ),
                        (527, 0, 0, 32),
                    )
                else:
                    self.assertTrue(
                        any(
                            "No hay ningún combate pendiente" in str(body)
                            for _, body in sent
                        )
                    )
                    self.assertEqual(stored["x"], moved["x"])
                created = self.store.create_character(
                    self.account,
                    "After " + suffix,
                    selection_generation=self.generation,
                )
                self.store.select_character(
                    self.account, self.generation, created["id"]
                )
                self.assertTrue(
                    self.store.current_character_session(
                        self.account, self.generation, created["id"]
                    )
                )
