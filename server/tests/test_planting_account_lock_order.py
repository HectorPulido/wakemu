"""Guard account -> group -> SQL lock order in the real dispatcher nodes."""
import ast
from contextlib import contextmanager
from pathlib import Path
import threading
import time
import unittest
from types import SimpleNamespace

from wakfu_server.combat_groups import Groups
from wakfu_server.position_buffer import Positions


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _parents(tree):
    result = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            result[child] = parent
    return result


def _node_for_call(tree, predicate):
    parents = _parents(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and predicate(node):
            current = node
            while current in parents and not isinstance(
                current, (ast.With, ast.AsyncWith)
            ):
                current = parents[current]
            if isinstance(current, ast.With):
                return current
    raise AssertionError("Expected dispatcher lock scope was not found")


def _with_chain_for_call(tree, predicate):
    parents = _parents(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and predicate(node):
            chain = []
            current = node
            while current in parents:
                current = parents[current]
                if isinstance(current, ast.With):
                    chain.append(current)
            if chain:
                return list(reversed(chain))
    raise AssertionError("Expected dispatcher call was not found")


def _is_planting_call(node, name):
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == name
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "PLANTINGS"
    )


class _ObservedLock:
    def __init__(self, event):
        self._lock = threading.RLock()
        self.event = event

    def __enter__(self):
        self._lock.acquire()
        self.event.set()
        return self

    def __exit__(self, *_):
        self._lock.release()

    def owned(self):
        return self._lock._is_owned()


class PlantingAccountLockOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SERVER.read_text())
        cls.challenge = _node_for_call(
            cls.tree,
            lambda call: isinstance(call.func, ast.Attribute)
            and call.func.attr == "enter_weekly",
        )

    def test_challenge_and_planting_nodes_order_account_before_groups_before_sql(self):
        challenge_chain = _with_chain_for_call(
            self.tree,
            lambda call: isinstance(call.func, ast.Attribute)
            and call.func.attr == "enter_weekly",
        )
        challenge_managers = [
            ast.unparse(item.context_expr)
            for scope in challenge_chain
            for item in scope.items
        ]
        self.assertEqual(
            challenge_managers,
            [
                "POSITIONS.account_barrier(account_id)",
                "COMBAT_GROUPS.lock",
                "STORE.connection()",
            ],
        )
        for operation in ("begin", "complete"):
            with self.subTest(operation=operation):
                node = _node_for_call(
                    self.tree, lambda call: _is_planting_call(call, operation)
                )
                managers = [ast.unparse(item.context_expr) for item in node.items]
                self.assertEqual(
                    managers,
                    ["POSITIONS.account_barrier(account_id)", "COMBAT_GROUPS.lock"],
                )

    def test_actual_begin_and_completion_nodes_wait_for_real_account_owner(self):
        source = SERVER.read_text()
        tree = ast.parse(source)
        account_id, generation, character, body = (
            71,
            "generation",
            {"id": 9},
            b"request",
        )

        for operation in ("begin", "complete"):
            with self.subTest(operation=operation):
                node = _node_for_call(
                    tree, lambda call: _is_planting_call(call, operation)
                )
                function = ast.FunctionDef(
                    name="invoke",
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[],
                        kwonlyargs=[],
                        kw_defaults=[],
                        defaults=[],
                    ),
                    body=[node],
                    decorator_list=[],
                )
                module = ast.fix_missing_locations(
                    ast.Module(body=[function], type_ignores=[])
                )
                group_entered = threading.Event()
                observed_group = _ObservedLock(group_entered)
                positions = Positions(SimpleNamespace(), lease_active=lambda *_: True)
                sql_calls = []

                def complete(*args, **kwargs):
                    self.assertTrue(positions.account_locks[account_id]._is_owned())
                    self.assertTrue(observed_group.owned())
                    sql_calls.append((operation, args, kwargs))
                    return {"packets": ()}

                plantings = SimpleNamespace(begin=complete, complete=complete)
                globals_ = {
                    "POSITIONS": positions,
                    "COMBAT_GROUPS": SimpleNamespace(lock=observed_group),
                    "PLANTINGS": plantings,
                    "account_id": account_id,
                    "generation": generation,
                    "character": character,
                    "body": body,
                    "authorize_planting": lambda *_: 0,
                }
                exec(compile(module, str(SERVER), "exec"), globals_)
                finished = threading.Event()
                failures = []

                def run_dispatch_node():
                    try:
                        globals_["invoke"]()
                    except BaseException as error:
                        failures.append(error)
                    finally:
                        finished.set()

                with positions.account_barrier(account_id):
                    worker = threading.Thread(target=run_dispatch_node)
                    worker.start()
                    time.sleep(0.05)
                    self.assertFalse(group_entered.is_set())
                    self.assertEqual(sql_calls, [])
                    self.assertFalse(finished.is_set())
                worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertEqual(failures, [])
                self.assertEqual(len(sql_calls), 1)


if __name__ == "__main__":
    unittest.main()
