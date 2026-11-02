"""Committed travel retries only its position attachment after contention."""

from __future__ import annotations

import ast
import sys
from contextlib import nullcontext
import pathlib
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from psycopg.errors import LockNotAvailable


ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER_SOURCE = ROOT / "server" / "local_game_server.py"


def _load_travel_closures(globals_ns):
    """Compile the exact nested World functions with a small isolated closure."""
    tree = ast.parse(SERVER_SOURCE.read_text())
    session = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )
    wanted = {
        "queue_committed_travel_resume",
        "continue_committed_travel",
        "committed_travel_holds_request",
        "execute_objectives_travel",
    }
    functions = [
        node
        for node in session.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    assert {node.name for node in functions} == wanted

    # Every direct free variable becomes a local in this synthetic enclosing
    # function, as it is in the actual session() closure.
    import symtable

    symbols = symtable.symtable(SERVER_SOURCE.read_text(), str(SERVER_SOURCE), "exec")
    session_symbols = next(
        child for child in symbols.get_children() if child.get_name() == "session"
    )
    local_names = sorted(
        {
            symbol.get_name()
            for child in session_symbols.get_children()
            if child.get_name() in wanted
            for symbol in child.get_symbols()
            if symbol.is_free()
        }
    )
    build = ast.FunctionDef(
        name="_build",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="values")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="values", ctx=ast.Load()),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(name)],
                    keywords=[],
                ),
            )
            for name in local_names
        ]
        + functions
        + [
            ast.Return(
                value=ast.Dict(
                    keys=[ast.Constant(name) for name in wanted],
                    values=[ast.Name(id=name, ctx=ast.Load()) for name in wanted],
                )
            )
        ],
        decorator_list=[],
    )
    state_helpers = ast.parse(
        """
def _set_identity(new_character, new_generation):
    nonlocal character, generation
    character = new_character
    generation = new_generation
def _identity():
    return character, generation
"""
    ).body
    module = ast.fix_missing_locations(
        ast.Module(
            body=[
                ast.FunctionDef(
                    name="_build",
                    args=build.args,
                    body=build.body[:-1]
                    + state_helpers
                    + [
                        ast.Return(
                            value=ast.Dict(
                                keys=[ast.Constant(name) for name in wanted]
                                + [
                                    ast.Constant("_set_identity"),
                                    ast.Constant("_identity"),
                                ],
                                values=[
                                    ast.Name(id=name, ctx=ast.Load()) for name in wanted
                                ]
                                + [
                                    ast.Name(id="_set_identity", ctx=ast.Load()),
                                    ast.Name(id="_identity", ctx=ast.Load()),
                                ],
                            )
                        )
                    ],
                    decorator_list=[],
                )
            ],
            type_ignores=[],
        )
    )
    exec(compile(module, str(SERVER_SOURCE), "exec"), globals_ns)
    return globals_ns["_build"]


class _DB:
    def __init__(self, events):
        self.events = events

    def execute(self, sql, params=()):
        self.events.append(("sql", " ".join(sql.split())[:40]))
        if "SELECT 1 FROM combat_fight_participants" in sql:
            return SimpleNamespace(fetchone=lambda: None)
        if "SELECT character_id FROM account_hero_slots" in sql:
            return SimpleNamespace(fetchall=lambda: [])
        if "SELECT id FROM accounts" in sql:
            return SimpleNamespace(fetchall=lambda: [])
        return SimpleNamespace(fetchone=lambda: (1,), fetchall=lambda: [])


class _Store:
    def __init__(self, events):
        self.events = events

    def connection(self):
        store = self

        class Connection:
            def __enter__(self):
                return _DB(store.events)

            def __exit__(self, *_args):
                return False

        return Connection()

    def lock_character(self, *_args, **_kwargs):
        self.events.append(("selected-lock",))

    def transition_map_in_transaction(
        self, db, account_id, generation, character_id, character, destination
    ):
        self.events.append(("transition", destination))
        saved = dict(character, map_id=destination, x=4, y=5, z=0)
        return saved


class _Positions:
    def __init__(self, events):
        self.events = events
        self.fail_once = True

    def account_barrier(self, _account_id):
        return nullcontext()

    def release(self, account_id, generation, character_id):
        self.events.append(("release", account_id, generation, character_id))

    def attach(self, account_id, generation, saved):
        self.events.append(("attach", account_id, generation, saved["id"]))
        if self.fail_once:
            self.fail_once = False
            raise LockNotAvailable("isolated position lock contention")


class CommittedTravelResumeTests(unittest.TestCase):
    def test_committed_travel_retries_attach_without_recharging_or_retransitioning(
        self,
    ):
        events = []
        counters = {"charge": 0, "finish": 0, "publish": 0}
        character = {
            "id": 78,
            "account_id": 6,
            "generation": 4,
            "map_id": 1134,
            "x": 1,
            "y": 2,
            "z": 0,
            "instance_id": 0,
        }
        clock = SimpleNamespace(value=100.0)

        class Clock:
            @staticmethod
            def monotonic():
                clock.value += 1.0
                return clock.value

        class Move:
            def __init__(self, position):
                self.position = position

        positions = _Positions(events)
        store = _Store(events)

        def charge(_db, _action, cost):
            counters["charge"] += 1
            events.append(("charge", cost))
            return 500

        def finish(_db, _action, result):
            counters["finish"] += 1
            events.append(("finish", result["success"]))
            return True

        player_actions = SimpleNamespace(
            lock_running=lambda *_args: events.append(("action-lock",)),
            charge_travel=charge,
            finish=finish,
        )
        player_travel = SimpleNamespace(
            resolve=lambda *_args: {"target": 910, "cost_kamas": 500}
        )

        globals_ns = {
            "time": Clock,
            "redact": str,
            "record": lambda **row: events.append(("record", row["event"])),
            "send": lambda *_args: events.append(("send",)),
            "Movement": Move,
            "wire": SimpleNamespace(account_kamas_update=lambda _kamas: b"kamas"),
            "STORE": store,
            "POSITIONS": positions,
            "flush_positions": lambda **_kwargs: None,
            "owned_native_bootstrap": lambda _character: [(1, b"bootstrap")],
            "join_world": lambda *_args, **_kwargs: events.append(("join",)),
            "mark_static_sync_pending": lambda: events.append(("static-sync",)),
            "cancel_crafting": lambda: events.append(("cancel-crafting",)),
            "WORLD": SimpleNamespace(leave=lambda *_args: events.append(("leave",))),
        }
        # The extracted production function performs normal imports; replace
        # only its collaborators, leaving the travel/queue/continue bodies exact.
        import wakfu_server.custom_tasks as custom_tasks_package
        import wakfu_server.objectives as objectives_package

        actual_player_actions = ModuleType("wakfu_server.custom_tasks.player_actions")
        actual_player_travel = ModuleType("wakfu_server.objectives.player_travel")
        actual_player_actions.lock_running = player_actions.lock_running
        actual_player_actions.charge_travel = charge
        actual_player_actions.finish = finish
        actual_player_travel.resolve = player_travel.resolve

        build = _load_travel_closures(globals_ns)
        values = {
            "character": character,
            "position": {"x": 1, "y": 2, "z": 0},
            "movement_state": None,
            "pending_travel_resume": None,
            "account_id": 6,
            "generation": 4,
            "bag_session": None,
            "ranch_session": None,
            "connection": object(),
            "service": object(),
            "queue_committed_travel_resume": None,
            "publish_entry_inventory": lambda *_args: None,
            "mark_static_sync_pending": lambda: events.append(("static-sync",)),
            "cancel_crafting": lambda: events.append(("cancel-crafting",)),
            "owned_native_bootstrap": lambda _character: [(1, b"bootstrap")],
            "join_world": lambda *_args, **_kwargs: events.append(("join",)),
        }
        functions = build(values)
        # Execute resolves its production imports. Patch the called methods so
        # the counters observe payment and receipt without a database write.
        with (
            patch.dict(
                sys.modules,
                {
                    "wakfu_server.custom_tasks.player_actions": actual_player_actions,
                    "wakfu_server.objectives.player_travel": actual_player_travel,
                },
            ),
            patch.object(
                custom_tasks_package,
                "player_actions",
                actual_player_actions,
                create=True,
            ),
            patch.object(
                objectives_package, "player_travel", actual_player_travel, create=True
            ),
            patch.object(
                actual_player_actions, "lock_running", player_actions.lock_running
            ),
            patch.object(actual_player_actions, "charge_travel", charge),
            patch.object(actual_player_actions, "finish", finish),
            patch.object(actual_player_travel, "resolve", player_travel.resolve),
        ):
            action = {
                "id": 123,
                "account_id": 6,
                "character_id": 78,
                "generation": 4,
                "action_key": "route-a",
                "target": {"kind": "travel", "destination": 910, "cost_kamas": 500},
            }
            result = functions["execute_objectives_travel"](action)

            self.assertTrue(result["success"])
            saved_character, saved_generation = functions["_identity"]()
            self.assertEqual(
                (saved_character["map_id"], saved_character["id"], saved_generation),
                (910, 78, 4),
            )
            self.assertEqual(functions["committed_travel_holds_request"](314), False)
            self.assertEqual(functions["committed_travel_holds_request"](23354), False)
            self.assertEqual(functions["committed_travel_holds_request"](77), True)
            self.assertEqual(counters, {"charge": 1, "finish": 1, "publish": 0})
            self.assertEqual(sum(event[0] == "transition" for event in events), 1)
            self.assertEqual(events.count(("attach", 6, 4, 78)), 0)

            # The first attach hit the native lock error. Retry uses only the
            # stored post-commit callbacks and cannot execute the paid path.
            functions["continue_committed_travel"]()
            self.assertEqual(counters, {"charge": 1, "finish": 1, "publish": 0})
            self.assertEqual(sum(event[0] == "transition" for event in events), 1)
            self.assertEqual(events.count(("attach", 6, 4, 78)), 1)
            functions["continue_committed_travel"]()
            self.assertEqual(counters, {"charge": 1, "finish": 1, "publish": 0})
            self.assertEqual(sum(event[0] == "transition" for event in events), 1)
            self.assertEqual(events.count(("attach", 6, 4, 78)), 2)
            self.assertEqual(sum(event[0] == "join" for event in events), 1)
            self.assertEqual(events.count(("leave",)), 1)

    def test_stale_selection_and_noncontention_errors_propagate_without_publish(self):
        events = []
        positions = _Positions(events)
        values = {
            "character": {"id": 78},
            "generation": 4,
            "account_id": 6,
            "pending_travel_resume": None,
        }
        functions = _load_travel_closures(
            {
                "time": SimpleNamespace(monotonic=lambda: 100.0),
                "redact": str,
                "record": lambda **row: events.append(("record", row["event"])),
                "POSITIONS": positions,
            }
        )(values)
        saved = {"id": 78, "map_id": 910}
        functions["queue_committed_travel_resume"](
            saved, lambda: events.append(("published",)), "a-1"
        )
        functions["_set_identity"]({"id": 79}, 4)
        with self.assertRaisesRegex(ValueError, "selection changed"):
            functions["continue_committed_travel"]()
        self.assertNotIn(("published",), events)

        events.clear()
        functions = _load_travel_closures(
            {
                "time": SimpleNamespace(monotonic=lambda: 100.0),
                "redact": str,
                "record": lambda **row: events.append(("record", row["event"])),
                "POSITIONS": positions,
            }
        )(values | {"character": {"id": 78}, "pending_travel_resume": None})

        def fail_noncontention(*_args):
            raise RuntimeError("checkpoint failed")

        positions.attach = fail_noncontention
        functions["queue_committed_travel_resume"](
            saved, lambda: events.append(("published",)), "a-2"
        )
        with self.assertRaisesRegex(RuntimeError, "checkpoint failed"):
            functions["continue_committed_travel"]()
        self.assertNotIn(("published",), events)

    def test_source_guards_stop_objective_and_idle_work_while_travel_is_pending(self):
        tree = ast.parse(SERVER_SOURCE.read_text())
        session = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        nested = {
            node.name: node
            for node in session.body
            if isinstance(node, ast.FunctionDef)
        }
        poll = nested["poll_external_objectives"]
        pending_return = next(
            index
            for index, node in enumerate(poll.body)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "pending_travel_resume is not None"
            and any(isinstance(child, ast.Return) for child in ast.walk(node))
        )
        drain = next(
            index
            for index, node in enumerate(poll.body)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "drain_objectives_player_actions"
        )
        self.assertGreater(pending_return, drain)

        idle = nested["idle"]
        invalid_health_return = next(
            node
            for node in ast.walk(idle)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "not session_health['valid']"
            and any(isinstance(child, ast.Return) for child in ast.walk(node))
        )
        continue_call = next(
            node
            for node in ast.walk(idle)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "continue_committed_travel"
        )
        self.assertGreater(continue_call.lineno, invalid_health_return.lineno)


if __name__ == "__main__":
    unittest.main()
