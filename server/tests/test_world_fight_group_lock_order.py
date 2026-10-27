"""Actual World settlement dispatch preserves Fight -> Group lock ordering."""
import ast
from copy import deepcopy
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest

from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight


class _ObservedLock:
    def __init__(self, waiting):
        self.actual = threading.RLock()
        self.waiting = waiting

    def acquire(self, *args, **kwargs):
        if threading.current_thread().name == "world-settlement":
            self.waiting.set()
        return self.actual.acquire(*args, **kwargs)

    def release(self):
        self.actual.release()

    def _is_owned(self):
        return self.actual._is_owned()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


class WorldFightGroupLockOrderTests(unittest.TestCase):
    def test_marker_fight_owner_can_take_group_while_world_settlement_waits(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "group_lease is None"
            and any(
                isinstance(row, ast.Expr)
                and isinstance(row.value, ast.Call)
                and isinstance(row.value.func, ast.Attribute)
                and row.value.func.attr == "settle_finished"
                for row in node.body
            )
        )
        code = compile(
            ast.fix_missing_locations(
                ast.Module(body=[deepcopy(branch)], type_ignores=[])
            ),
            "actual World group settlement branch",
            "exec",
        )
        session = Session(1, 10, "owner", 1134, 0)
        fight = Fight(
            99,
            [
                Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (3, 0, 0), 20, 4, 2, 1, 1),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        registry = Registry(lambda candidate: candidate == session)
        shared = registry.register(fight, session)
        # Finished is the lock-boundary premise; this test creates no victory,
        # health change, SQL settlement, gameplay reward or native cast.
        fight.phase = "finished"
        fight.winner = 0
        waiting, held = threading.Event(), threading.Event()
        shared.lock = _ObservedLock(waiting)
        group = threading.RLock()
        errors, committed, stages = [], [], []

        def prepare(current):
            self.assertIs(current, shared)
            self.assertTrue(shared.lock._is_owned())
            self.assertTrue(group._is_owned())
            committed.append("existing atomic settlement callback returned")
            return {session.account_id: ()}

        def settle(owner, identity, callback):
            return registry.settle_finished(identity, owner, callback)

        namespace = dict(
            group_lease=("actual owned group",),
            fight=fight,
            combat_session=session,
            COMBAT_GROUPS=SimpleNamespace(lock=group),
            COMBAT_SESSIONS=SimpleNamespace(settle_finished=settle),
            prepare_shared_packets=prepare,
            time=time,
            record=lambda **row: stages.append(row["stage"]),
        )

        def marker():
            try:
                with shared.lock:
                    held.set()
                    if not waiting.wait(3):
                        raise AssertionError("Settlement did not reach the Fight lock")
                    if not group.acquire(timeout=1):
                        raise AssertionError(
                            "Settlement retained Group while awaiting Fight"
                        )
                    group.release()
            except BaseException as error:
                errors.append(error)

        def settlement():
            try:
                if not held.wait(3):
                    raise AssertionError("Marker did not acquire Fight")
                exec(code, namespace)
            except BaseException as error:
                errors.append(error)

        marker_thread = threading.Thread(
            target=marker, name="terminal-marker", daemon=True
        )
        settle_thread = threading.Thread(
            target=settlement, name="world-settlement", daemon=True
        )
        marker_thread.start()
        settle_thread.start()
        marker_thread.join(5)
        settle_thread.join(5)
        self.assertFalse(marker_thread.is_alive())
        self.assertFalse(settle_thread.is_alive())
        if errors:
            raise errors[0]
        self.assertEqual(committed, ["existing atomic settlement callback returned"])
        self.assertEqual(stages, ["group_lock_wait", "group_lock_acquired"])
        self.assertTrue(shared.settlement_ready)
        self.assertEqual(len(shared.outboxes[session.account_id]), 1)
        # The already committed result never invokes the callback twice.
        exec(code, namespace)
        self.assertEqual(len(committed), 1)

        # Guard the actual World callers, including aliases/comma-with locks.
        for node in ast.walk(tree):
            if not isinstance(node, ast.With):
                continue
            locks = [ast.unparse(item.context_expr) for item in node.items]
            if any(
                lock.endswith(".lock") and ("shared" in lock or "orphan" in lock)
                for lock in locks
            ):
                self.assertFalse(
                    any(
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Name)
                        and call.func.id in ("checkpoint_fight", "drain_shared_combat")
                        for call in ast.walk(node)
                    ),
                    "World must not enter checkpoint/drain while retaining Fight",
                )
            if "COMBAT_SESSIONS.registry.lock" in locks and any(
                "shared_rift.lock" == lock for lock in locks
            ):
                self.assertLess(
                    locks.index("shared_rift.lock"),
                    locks.index("COMBAT_SESSIONS.registry.lock"),
                )
