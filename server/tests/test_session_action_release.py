"""Compile actual socket completion statements without starting World."""
import ast
from copy import deepcopy
from dataclasses import dataclass
import gc
import os
from pathlib import Path
import unittest
import weakref

from wakfu_server.position_lifecycle import PendingPositionReturn
from wakfu_server.position_buffer import PositionOwnerBusy


class Fight:
    pass


class Snapshot(dict):
    pass


class SessionActionReleaseTests(unittest.TestCase):
    def setup_scope(self, *, pending=False):
        server_root = Path(__file__).resolve().parents[1]
        source = Path(
            os.environ.get(
                "SESSION_ACTION_SOURCE", server_root / "local_game_server.py"
            )
        )
        tree = ast.parse(source.read_text())
        cleanup = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "release_completed_combat_action_results"
            ),
            None,
        )
        loop = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.While)
            and ast.unparse(node.test) == "not STOPPING.is_set()"
        )
        prefix = []
        for node in loop.body:
            if isinstance(node, ast.If) and ast.unparse(node.test) == "not idle()":
                break
            prefix.append(deepcopy(node))
        transaction_source = Path(
            os.environ.get(
                "SPELL_TRANSACTION_SOURCE",
                server_root / "wakfu_server/combat/combat_spell_transaction.py",
            )
        )
        transaction_tree = ast.parse(transaction_source.read_text())
        definition = deepcopy(
            next(
                node
                for node in transaction_tree.body
                if isinstance(node, ast.ClassDef) and node.name == "SpellTransaction"
            )
        )
        namespace = {"dataclass": dataclass}
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=[definition], type_ignores=[])
                ),
                "real-spell-transaction",
                "exec",
            ),
            namespace,
        )
        fight, snapshot = Fight(), Snapshot(before=True)
        transaction = namespace["SpellTransaction"](
            fight, {}, 0, (), (), (), snapshot, 1
        )
        refs = tuple(weakref.ref(value) for value in (transaction, fight, snapshot))
        factory = ast.parse(
            """
def connection_scope(value, request, preserve_return):
    transaction = value
    action_results = {'transaction': value}
    delivery = ()
    shared_cast = lambda: action_results
    shared_weapon = lambda: action_results
    active_request = request
    return_owner = value.fight if preserve_return else None
    del value
    def finish_return():
        nonlocal return_owner
        return_owner = None
"""
        ).body[0]
        if cleanup is not None:
            factory.body.append(deepcopy(cleanup))
        completion = ast.parse(
            "def finish_request():\n    nonlocal active_request\n    pass"
        ).body[0]
        completion.body = completion.body[:1] + prefix
        factory.body.append(completion)
        factory.body += ast.parse(
            "return finish_request, finish_return, lambda: (transaction, action_results, shared_cast, shared_weapon)"
        ).body
        namespace = {}
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        calls = []

        class Trace:
            def finish(self):
                if not all(ref() is not None for ref in refs):
                    raise AssertionError(
                        "Action results released before request diagnostics"
                    )
                calls.append("finished")

        return (
            *namespace["connection_scope"](transaction, Trace(), pending),
            refs,
            calls,
        )

    def test_completed_request_releases_action_graph_before_socket_wait(self):
        finish, _, connection, refs, calls = self.setup_scope()
        finish()
        gc.collect()
        self.assertEqual(calls, ["finished"])
        self.assertTrue(all(ref() is None for ref in refs))
        self.assertEqual(connection(), (None, None, None, None))

    def test_rejected_request_cleanup_preserves_pending_world_return_retry(self):
        finish, complete_return, connection, refs, calls = self.setup_scope(
            pending=True
        )
        # Rejected synchronous handlers continue to this exact loop prefix.
        pending = PendingPositionReturn(now=0)

        def busy():
            raise PositionOwnerBusy("position pending")

        self.assertFalse(
            pending.attempt(
                now=0, flush=busy, complete=complete_return, busy=lambda *_: None
            )
        )
        finish()
        gc.collect()
        self.assertIsNone(refs[0]())
        self.assertIsNone(refs[2]())
        self.assertIsNotNone(refs[1]())
        self.assertTrue(
            pending.attempt(
                now=1,
                flush=lambda: None,
                complete=complete_return,
                busy=lambda *_: None,
            )
        )
        gc.collect()
        self.assertIsNone(refs[1]())
        self.assertEqual(calls, ["finished"])
        self.assertEqual(connection(), (None, None, None, None))


if __name__ == "__main__":
    unittest.main()
