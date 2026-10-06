"""Frozen placement timeout policy and session-dispatch regression checks."""
import ast
import copy
import dis
import os
from pathlib import Path
from types import SimpleNamespace
import types
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.placement_deadline import Deadline


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def extracted_apply_readiness(namespace):
    tree = ast.parse(SERVER_SOURCE.read_text(), filename=str(SERVER_SOURCE))
    session = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )
    readiness = next(
        node
        for node in ast.walk(session)
        if isinstance(node, ast.FunctionDef) and node.name == "apply_readiness"
    )
    current_stats = next(
        node
        for node in session.body
        if isinstance(node, ast.FunctionDef) and node.name == "current_combat_stats"
    )
    harness = ast.FunctionDef(
        name="run_apply_readiness",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="fight_arg"), ast.arg(arg="messages_arg")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(
                targets=[ast.Name(id="fight", ctx=ast.Store())],
                value=ast.Name(id="fight_arg", ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[ast.Name(id="fight_messages", ctx=ast.Store())],
                value=ast.Name(id="messages_arg", ctx=ast.Load()),
            ),
            copy.deepcopy(current_stats),
            copy.deepcopy(readiness),
            ast.Try(
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Name(id="apply_readiness", ctx=ast.Load()),
                            args=[ast.Constant(value=True)],
                            keywords=[],
                        )
                    )
                ],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id="BaseException", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Expr(
                                value=ast.Call(
                                    func=ast.Name(id="capture", ctx=ast.Load()),
                                    args=[
                                        ast.Name(id="fight", ctx=ast.Load()),
                                        ast.Name(id="fight_messages", ctx=ast.Load()),
                                    ],
                                    keywords=[],
                                )
                            ),
                            ast.Raise(exc=None, cause=None),
                        ],
                    )
                ],
                orelse=[],
                finalbody=[],
            ),
            ast.Return(
                value=ast.Tuple(
                    elts=[
                        ast.Name(id="fight", ctx=ast.Load()),
                        ast.Name(id="fight_messages", ctx=ast.Load()),
                    ],
                    ctx=ast.Load(),
                )
            ),
        ],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[harness], type_ignores=[]))
    exec(compile(module, str(SERVER_SOURCE), "exec"), namespace)
    return namespace["run_apply_readiness"]


class PlacementDeadlineTests(unittest.TestCase):
    def test_expiry_boundary_is_claimed_once(self):
        deadline = Deadline()
        deadline.start(42, 60_000, 100.0)
        fight = type("Fight", (), {"id": 42, "phase": "placement"})()

        self.assertFalse(deadline.take_expired(fight, 159.999))
        self.assertTrue(deadline.take_expired(fight, 160.0))
        self.assertFalse(deadline.take_expired(fight, 160.001))

    def test_nonplacement_or_switched_fight_discards_stale_deadline(self):
        deadline = Deadline()
        deadline.start(42, 1000, 5.0)
        self.assertFalse(deadline.take_expired(None, 8.0))
        self.assertIsNone(deadline.fight_id)
        self.assertIsNone(deadline.until)

        deadline.start(42, 1000, 5.0)
        other = type("Fight", (), {"id": 43, "phase": "placement"})()
        self.assertFalse(deadline.take_expired(other, 8.0))
        self.assertIsNone(deadline.fight_id)

        deadline.start(42, 1000, 5.0)
        active = type("Fight", (), {"id": 42, "phase": "active"})()
        self.assertFalse(deadline.take_expired(active, 8.0))
        self.assertIsNone(deadline.until)

    def test_deadline_rejects_invalid_identity_duration_and_clock(self):
        for fight_id, duration_ms, now in (
            (0, 1000, 0.0),
            (1, 999, 0.0),
            (1, 300001, 0.0),
            (True, 1000, 0.0),
            (1, True, 0.0),
            (1, 1000, float("nan")),
            (1, 1000, float("inf")),
        ):
            with self.subTest(fight_id=fight_id, duration=duration_ms, now=now):
                with self.assertRaises(ValueError):
                    Deadline().start(fight_id, duration_ms, now)

        deadline = Deadline()
        deadline.start(1, 1000, 0.0)
        fight = type("Fight", (), {"id": 1, "phase": "placement"})()
        with self.assertRaises(ValueError):
            deadline.take_expired(fight, float("nan"))


class PlacementDeadlinePolicyPostgresTests(PostgresCase):
    def test_database_policy_bounds_and_started_deadline_snapshot(self):
        from psycopg.types.json import Jsonb
        from wakfu_server.placement_deadline import duration

        self.assertEqual(duration(self.store), 60_000)
        started = Deadline()
        started.start(19, duration(self.store), 100.0)

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='combat_placement_duration_ms'",
                (Jsonb(1_000),),
            )
        self.assertEqual(duration(self.store), 1_000)
        self.assertEqual(started.until, 160.0)

        for value in (1_000, 300_000):
            with self.subTest(accepted=value):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE settings SET value=%s WHERE name='combat_placement_duration_ms'",
                        (Jsonb(value),),
                    )
                self.assertEqual(duration(self.store), value)

        for value in (True, 999, 300_001, 1.5, "60000", None, []):
            with self.subTest(rejected=value):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE settings SET value=%s WHERE name='combat_placement_duration_ms'",
                        (Jsonb(value),),
                    )
                with self.assertRaisesRegex(ValueError, "placement duration"):
                    duration(self.store)

    def test_failed_durable_activation_preserves_original_fight_and_sends_nothing(self):
        from psycopg.errors import RaiseException

        account = self.store.register("placement-owner", "local-password")["id"]
        character = self.store.create_character(account, "Placement Owner")
        generation = self.store.begin_session(account)
        character = self.store.select_character(account, generation, character["id"])
        from wakfu_server.fight_store import create as create_fight

        fight_id = create_fight(self.store, account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                """
                CREATE FUNCTION reject_active_fight_for_test() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    IF NEW.status = 'active' THEN
                        RAISE EXCEPTION 'injected placement activation failure';
                    END IF;
                    RETURN NEW;
                END $$
            """
            )
            db.execute(
                """
                CREATE TRIGGER reject_active_fight_for_test
                BEFORE UPDATE OF status ON combat_fights
                FOR EACH ROW EXECUTE FUNCTION reject_active_fight_for_test()
            """
            )

        original_fight = SimpleNamespace(id=fight_id, phase="placement")
        original_messages = SimpleNamespace(native_action_id=4)
        candidate = SimpleNamespace(id=fight_id, phase="active")
        candidate_messages = object()
        packets = ((13684, b"candidate packet"),)
        sent = []
        captured_state = []
        namespace = {
            "account_id": account,
            "generation": generation,
            "character": dict(character, builds={0: {"deck": "00"}}),
            "TEST_MONSTERS_BY_ID": {},
            "area_boundary_provider": lambda **kwargs: None,
            "STORE": self.store,
            "connection": object(),
            "service": "world",
            "send": lambda *args: sent.append(args),
            "record": lambda **kwargs: None,
            "capture": lambda *state: captured_state.append(state),
            "complete_test_fight": lambda: self.fail("candidate must not commit"),
            "pass_test_monster_turn": lambda: self.fail("candidate must not commit"),
            "os": os,
        }
        run = extracted_apply_readiness(namespace)
        with patch(
            "wakfu_server.combat_ready.prepare_ready",
            return_value=(candidate, candidate_messages, packets),
        ):
            with self.assertRaisesRegex(
                RaiseException, "injected placement activation failure"
            ):
                run(original_fight, original_messages)

        self.assertEqual(original_fight.phase, "placement")
        self.assertEqual(captured_state, [(original_fight, original_messages)])
        self.assertEqual(sent, [])
        with self.store.connection() as db:
            status = db.execute(
                "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
            ).fetchone()["status"]
        self.assertEqual(status, "placement")


class PlacementDeadlineWiringTests(unittest.TestCase):
    def test_source_compiles_and_timeout_cannot_bypass_session_lease_check(self):
        source = SERVER_SOURCE.read_text()
        tree = ast.parse(source, filename=str(SERVER_SOURCE))
        compile(tree, str(SERVER_SOURCE), "exec")

        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        nested = {
            node.name: node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("apply_readiness", nested)
        self.assertIn("idle", nested)
        self.assertIn("current_combat_stats", nested)

        idle_text = ast.get_source_segment(source, nested["idle"])
        lease_positions = [
            idle_text.find("STORE.heartbeat("),
            idle_text.find("STORE.current_session("),
            idle_text.find("if not valid:"),
            idle_text.find("placement_deadline.take_expired(fight, now)"),
            idle_text.find("apply_readiness(True)"),
        ]
        self.assertTrue(all(position >= 0 for position in lease_positions))
        self.assertEqual(lease_positions, sorted(lease_positions))

        loop = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.While)
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "idle"
                for statement in node.body
                for call in ast.walk(statement)
            )
        )
        idle_receive_calls = [
            node
            for node in ast.walk(loop)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "receive"
            and any(isinstance(arg, ast.Name) and arg.id == "idle" for arg in node.args)
        ]
        self.assertEqual(len(idle_receive_calls), 2)

    def test_manual_ready_dispatches_to_extracted_readiness_handler(self):
        tree = ast.parse(SERVER_SOURCE.read_text(), filename=str(SERVER_SOURCE))
        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        readiness_branch = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and any(
                isinstance(value, ast.Constant) and value.value == 12523
                for value in ast.walk(node.test)
            )
            and any(
                isinstance(value, ast.Name) and value.id == "opcode"
                for value in ast.walk(node.test)
            )
        )
        calls = [
            node
            for node in ast.walk(readiness_branch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "apply_readiness"
        ]
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(calls[0].args[0], ast.Call)
        self.assertEqual(calls[0].args[0].func.id, "bool")
        body_value = calls[0].args[0].args[0]
        self.assertIsInstance(body_value, ast.Subscript)
        self.assertEqual(body_value.value.id, "body")
        self.assertEqual(body_value.slice.value, 0)

    def test_readiness_and_commit_callbacks_share_session_stats_closure(self):
        source = SERVER_SOURCE.read_text()
        tree = ast.parse(source, filename=str(SERVER_SOURCE))
        module_code = compile(tree, str(SERVER_SOURCE), "exec")
        session_code = next(
            value
            for value in module_code.co_consts
            if isinstance(value, types.CodeType) and value.co_name == "session"
        )

        def code_objects(code):
            yield code
            for value in code.co_consts:
                if isinstance(value, types.CodeType):
                    yield from code_objects(value)

        functions = list(code_objects(session_code))
        readiness = next(
            code for code in functions if code.co_name == "apply_readiness"
        )
        callbacks = [
            code
            for code in functions
            if code.co_name == "<lambda>" and "current_combat_stats" in code.co_freevars
        ]
        session_node = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        callback_nodes = [
            node
            for node in ast.walk(session_node)
            if isinstance(node, ast.Lambda)
            and "current_combat_stats" in (ast.get_source_segment(source, node) or "")
        ]

        self.assertIn("current_combat_stats", session_code.co_cellvars)
        self.assertIn("current_combat_stats", readiness.co_freevars)
        self.assertEqual(len(callbacks), 3)
        self.assertEqual(
            {code.co_firstlineno for code in callbacks},
            {node.lineno for node in callback_nodes},
        )
        for callback in callbacks:
            operations = [
                instruction.opname for instruction in dis.get_instructions(callback)
            ]
            self.assertIn("LOAD_DEREF", operations)
            self.assertNotIn("LOAD_GLOBAL", operations)


if __name__ == "__main__":
    unittest.main()
