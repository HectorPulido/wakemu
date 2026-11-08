"""A live connection releases its completed return closure, never pending work."""
import ast
from copy import deepcopy
import gc
from pathlib import Path
import unittest
import weakref

from wakfu_server.position_lifecycle import PendingPositionReturn
from wakfu_server.position_buffer import PositionOwnerBusy


class RetainedFight:
    pass


ALIASES = (
    "shared_state",
    "shared",
    "shared_selection",
    "shared_rift",
    "candidate",
    "hero_admission",
    "companion_admission",
    "selection_runtime",
    "orientation_runtime",
    "checkpoint_local_shared",
    "pending",
    "returned",
    "abandon_messages",
)


class TerminalReturnRetentionTests(unittest.TestCase):
    def callback(self, *, full_abandon=False, shared_return=True, fail_once=False):
        source = Path(__file__).parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        callback = deepcopy(
            next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "finish_return"
            )
        )
        factory = ast.parse(
            "def connection_scope(aliases, completion):\n"
            f" abandoned = {full_abandon!r}\n"
            f" shared_return = {shared_return!r}\n"
            " finish_combat_return_after_position_flush = completion\n"
        ).body[0]
        factory.body += ast.parse(
            "\n".join(name + " = aliases['" + name + "']" for name in ALIASES)
            + "\ndel aliases"
        ).body
        cleanup = deepcopy(
            next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "release_completed_combat_return_aliases"
            )
        )
        factory.body += [
            cleanup,
            callback,
            *ast.parse(
                "return finish_return, lambda: ("
                + ", ".join(ALIASES)
                + ", finish_return)"
            ).body,
        ]
        namespace = {}
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        shared = RetainedFight()
        shared.fight = RetainedFight()
        shared.runtime = RetainedFight()
        aliases = {name: shared for name in ALIASES}
        aliases["candidate"] = shared.fight
        aliases["hero_admission"] = {"fight": shared.fight}
        aliases["companion_admission"] = {"fight": shared.fight}
        aliases["selection_runtime"] = shared.runtime
        aliases["orientation_runtime"] = shared.runtime
        # Full shared abandon may replace shared.runtime after the old runtime
        # was assigned to the socket local. This distinct pre-abort graph must
        # also die, not merely the currently adopted shared Fight.
        abandon_runtime = RetainedFight()
        abandon_runtime.fight = RetainedFight()
        aliases["abandon_messages"] = abandon_runtime
        withdrawal = RetainedFight()
        withdrawal.fight = RetainedFight()
        withdrawal.runtime = RetainedFight()
        aliases["pending"] = {"withdrawal": withdrawal, "runtime": withdrawal.runtime}
        aliases["returned"] = {"withdrawal": withdrawal}
        refs = tuple(
            weakref.ref(value)
            for value in (
                shared,
                shared.fight,
                shared.runtime,
                withdrawal,
                withdrawal.fight,
                withdrawal.runtime,
                abandon_runtime,
                abandon_runtime.fight,
            )
        )
        completed = []
        failures = [True] if fail_once else []

        def finish(**kwargs):
            self.assertIs(kwargs["shared_state"], refs[0]())
            self.assertEqual(kwargs["abandoned"], full_abandon)
            self.assertIsNotNone(refs[-1]())
            self.assertEqual(kwargs["shared_return"], shared_return)
            if failures:
                failures.pop()
                raise ValueError("return completion failed")
            completed.append(True)

        callback, live_connection = namespace["connection_scope"](aliases, finish)
        return callback, live_connection, refs, completed

    def assert_released(self, live_connection, refs):
        gc.collect()
        self.assertEqual(live_connection(), (None,) * (len(ALIASES) + 1))
        self.assertTrue(all(reference() is None for reference in refs))

    def test_immediate_return_releases_graph_while_connection_stays_open(self):
        callback, live_connection, refs, completed = self.callback()
        callback()
        self.assertEqual(completed, [True])
        self.assert_released(live_connection, refs)

    def test_pending_position_keeps_graph_until_success_and_never_repeats_return(self):
        callback, live_connection, refs, completed = self.callback(full_abandon=True)
        pending = PendingPositionReturn(now=0)

        def busy_flush():
            raise PositionOwnerBusy("owned position is busy")

        self.assertFalse(
            pending.attempt(
                now=0, flush=busy_flush, complete=callback, busy=lambda *_: None
            )
        )
        gc.collect()
        self.assertTrue(all(reference() is not None for reference in refs))
        self.assertIs(live_connection()[-1], callback)
        self.assertEqual(completed, [])
        self.assertTrue(
            pending.attempt(
                now=1, flush=lambda: None, complete=callback, busy=lambda *_: None
            )
        )
        self.assert_released(live_connection, refs)
        self.assertTrue(
            pending.attempt(
                now=2, flush=busy_flush, complete=callback, busy=lambda *_: None
            )
        )
        self.assertEqual(completed, [True])

    def test_individual_withdrawal_cleanup_follows_last_pending_use_and_world_join(
        self,
    ):
        source = Path(__file__).parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test)
            == "opcode == 12925 and pve_withdrawal_pending is not None"
        )
        body = next(node for node in branch.body if isinstance(node, ast.Try))
        cleanup = body.body[-1]
        self.assertEqual(
            ast.unparse(cleanup), "release_completed_combat_return_aliases()"
        )
        calls = [
            node.value.func.id
            for node in body.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
        ]
        self.assertLess(calls.index("join_world"), calls.index("record"))
        self.assertLess(
            calls.index("record"),
            calls.index("release_completed_combat_return_aliases"),
        )
        self.assertFalse(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "release_completed_combat_return_aliases"
                for handler in body.handlers
                for node in ast.walk(handler)
            )
        )

    def test_last_owner_full_abandon_releases_pre_abort_runtime_after_return(self):
        callback, live_connection, refs, completed = self.callback(full_abandon=True)
        gc.collect()
        self.assertIsNotNone(refs[-2]())
        self.assertIsNotNone(refs[-1]())
        callback()
        self.assertEqual(completed, [True])
        self.assert_released(live_connection, refs)

    def test_solo_abandon_releases_runtime_after_return(self):
        callback, live_connection, refs, completed = self.callback(
            full_abandon=True, shared_return=False
        )
        callback()
        self.assertEqual(completed, [True])
        self.assert_released(live_connection, refs)

    def test_failed_return_completion_preserves_aliases_until_retry_succeeds(self):
        callback, live_connection, refs, completed = self.callback(
            full_abandon=True, fail_once=True
        )
        with self.assertRaisesRegex(ValueError, "return completion failed"):
            callback()
        gc.collect()
        self.assertTrue(all(reference() is not None for reference in refs))
        self.assertIs(live_connection()[-1], callback)
        self.assertEqual(completed, [])
        callback()
        self.assertEqual(completed, [True])
        self.assert_released(live_connection, refs)
