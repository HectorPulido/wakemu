"""Logout barrier tests; extract the real finally block without importing server startup."""
import ast
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.session_cleanup import retry_step


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def extracted_session_finalizer(namespace):
    tree = ast.parse(SERVER_SOURCE.read_text())
    session = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "session"
    )
    candidates = [
        node
        for node in ast.walk(session)
        if isinstance(node, ast.Try)
        and any(
            isinstance(statement, ast.FunctionDef)
            and statement.name == "logout_barrier"
            for statement in node.finalbody
        )
    ]
    if len(candidates) != 1:
        raise AssertionError(
            f"expected one session logout finally block, found {len(candidates)}"
        )
    function = ast.FunctionDef(
        name="run_finally",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="connection_arg"), ast.arg(arg="active_request_arg")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(
                targets=[ast.Name(id="connection", ctx=ast.Store())],
                value=ast.Name(id="connection_arg", ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[ast.Name(id="active_request", ctx=ast.Store())],
                value=ast.Name(id="active_request_arg", ctx=ast.Load()),
            ),
            # The production session initializes this local before entering
            # the extracted finally block.
            ast.Assign(
                targets=[ast.Name(id="guild_chest_session", ctx=ast.Store())],
                value=ast.Constant(value=None),
            ),
            ast.Assign(
                targets=[ast.Name(id="flora_ticket", ctx=ast.Store())],
                value=ast.Constant(value=None),
            ),
            ast.Assign(
                targets=[ast.Name(id="combat_session", ctx=ast.Store())],
                value=ast.Constant(value=None),
            ),
            *candidates[0].finalbody,
        ],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(SERVER_SOURCE), "exec"), namespace)
    generated = namespace["run_finally"]
    namespace["run_finally"] = lambda connection: generated(
        connection, namespace.get("active_request")
    )
    return namespace["run_finally"]


class RetryStepTests(unittest.TestCase):
    def test_transient_retries_only_the_current_barrier_and_renews(self):
        attempts, failures, renewals, waits = [], [], [], []

        def operation():
            attempts.append("flush")
            if len(attempts) == 1:
                raise OSError("transient")
            return "complete"

        result = retry_step(
            operation,
            retry_errors=(OSError,),
            failed=failures.append,
            renew=lambda: renewals.append("heartbeat"),
            wait=waits.append,
        )
        self.assertEqual(result, "complete")
        self.assertEqual(attempts, ["flush", "flush"])
        self.assertEqual(len(failures), 1)
        self.assertEqual(renewals, ["heartbeat"])
        self.assertEqual(waits, [1])

    def test_invariant_error_propagates_without_renew_or_wait(self):
        failures, renewals, waits = [], [], []

        def invalid():
            raise ValueError("stale position lease")

        with self.assertRaisesRegex(ValueError, "stale position lease"):
            retry_step(
                invalid,
                retry_errors=(OSError,),
                failed=failures.append,
                renew=lambda: renewals.append(True),
                wait=waits.append,
            )
        self.assertEqual((failures, renewals, waits), ([], [], []))


class SessionCleanupFinallyTests(unittest.TestCase):
    class Calls:
        def __init__(self, events, name):
            self.events = events
            self.name = name

        def cancel(self, *args, **kwargs):
            self.events.append((self.name, "cancel", args, kwargs))

        def unregister(self, *args):
            self.events.append((self.name, "unregister", args))

        def release(self, *args):
            self.events.append((self.name, "release", args))

    def namespace(self, *, store=None, live=None, events=None, **overrides):
        events = [] if events is None else events

        class Store:
            def heartbeat(self, account, generation):
                events.append(("heartbeat", generation))
                return True

            def end_session(self, account, generation):
                events.append(("end_session", generation))

        class Groups:
            def finish(self, *args, **kwargs):
                events.append(("group_finish", args))

        class World:
            def leave(self, character_id, generation):
                events.append(("world_leave", character_id, generation))
                return True

        class Connections:
            def unregister(self, connection):
                events.append(("connection_unregister", connection))

        def checkpoint(status):
            events.append(("checkpoint", status))

        def release_groups(generation):
            events.append(("group_release", generation))

        def flush_positions(**scope):
            events.append(("position_flush", scope))

        def record(**data):
            events.append(("record", data))

        namespace = {
            "active_request": None,
            "PLANTINGS": self.Calls(events, "plantings"),
            "HARVESTS": self.Calls(events, "harvests"),
            "console_session": None,
            "TEST_CONSOLE": self.Calls(events, "test_console"),
            "character": {"id": 101, "account_id": 9001},
            "generation": "old-generation",
            "CONNECTIONS": Connections(),
            "service": "world",
            "checkpoint_fight": checkpoint,
            "CHECKPOINT_WRITER": SimpleNamespace(
                flush_fight=lambda *_args, **_kwargs: True
            ),
            "fight": None,
            "COMBAT_TEST": True,
            "group_lease": None,
            "account_id": 9001,
            "STORE": Store() if store is None else store,
            "record": record,
            "exception_frames": lambda _error: (),
            "redact": str,
            "flush_positions": flush_positions,
            "POSITIONS": self.Calls(events, "positions"),
            "COMBAT_GROUPS": Groups(),
            "COMBAT_SESSIONS": SimpleNamespace(
                registry=SimpleNamespace(
                    lease_generation_active=lambda _generation: True
                )
            ),
            "HAVEN_BAG_EXTERIORS": SimpleNamespace(discard=lambda *_args: None),
            "release_groups": release_groups,
            "WORLD": World(),
            "LOCK": threading.RLock(),
            "LIVE": {} if live is None else live,
        }
        namespace.update(overrides)
        return namespace, events

    def test_finally_retries_transient_failures_at_checkpoint_health_and_position_barriers(
        self,
    ):
        from psycopg import OperationalError
        from psycopg_pool import PoolTimeout
        from wakfu_server.position_redis import PositionJournalUnavailable
        import wakfu_server.session_cleanup as cleanup

        events = []
        namespace, _ = self.namespace(events=events)
        namespace["fight"] = SimpleNamespace(id=77, phase="active")
        # This retry scenario releases an obsolete generation. A still-active
        # generation deliberately retains its combat group in production.
        namespace[
            "COMBAT_SESSIONS"
        ].registry.lease_generation_active = lambda _generation: False
        checkpoint_calls = []

        def checkpoint(status):
            checkpoint_calls.append(status)
            events.append(("checkpoint", status))
            if len(checkpoint_calls) == 1:
                raise OperationalError("temporary checkpoint connection failure")

        namespace["checkpoint_fight"] = checkpoint
        flush_calls = []

        def flush_positions(**scope):
            flush_calls.append(scope)
            events.append(("position_flush", scope))
            if len(flush_calls) == 1:
                raise PositionJournalUnavailable("temporary Redis ack failure")

        namespace["flush_positions"] = flush_positions

        from wakfu_server import combat_health

        health_calls = []

        def health_exit(*args):
            health_calls.append(args)
            events.append(("fight_health",))
            if len(health_calls) == 1:
                raise PoolTimeout("temporary postgres pool timeout")
            return {"applied": True, "character": {"hp": 40}}

        failed_retry = cleanup.retry_step

        def fast_retry(operation, **kwargs):
            return failed_retry(
                operation,
                **kwargs,
                wait=lambda seconds: events.append(("wait", seconds)),
            )

        with (
            patch.object(cleanup, "retry_step", fast_retry),
            patch.object(
                combat_health, "persist_aborted_fight", side_effect=health_exit
            ),
        ):
            run_finally = extracted_session_finalizer(namespace)
            run_finally(object())

        self.assertEqual(checkpoint_calls, ["aborted", "aborted"])
        self.assertEqual(len(health_calls), 2)
        self.assertEqual(len(flush_calls), 2)
        positions = [
            index
            for index, event in enumerate(events)
            if event[:2] == ("positions", "release")
        ]
        self.assertEqual(len(positions), 1)
        self.assertLess(
            events.index(("fight_health",)),
            events.index(("group_release", "old-generation")),
        )
        self.assertLess(
            events.index(("group_release", "old-generation")),
            events.index(("world_leave", 101, "old-generation")),
        )
        self.assertEqual(sum(event[0] == "wait" for event in events), 3)
        self.assertEqual(sum(event[0] == "heartbeat" for event in events), 3)
        self.assertEqual(
            sum(
                event[0] == "record"
                and event[1].get("event") == "logout_barrier_failed"
                for event in events
            ),
            3,
        )
        self.assertEqual(sum(event[0] == "group_release" for event in events), 1)
        self.assertEqual(sum(event[0] == "world_leave" for event in events), 1)

    def test_finally_does_not_retry_position_revision_conflicts(self):
        from wakfu_server.position_redis import PositionJournalError
        from wakfu_server import combat_health

        namespace, events = self.namespace()
        namespace["flush_positions"] = lambda **scope: (_ for _ in ()).throw(
            PositionJournalError("Redis position revision conflict")
        )
        with patch.object(combat_health, "persist_aborted_fight", return_value=None):
            run_finally = extracted_session_finalizer(namespace)
            with self.assertRaisesRegex(PositionJournalError, "revision conflict"):
                run_finally(object())
        self.assertFalse(any(event[0] == "group_release" for event in events))


class SessionCleanupLeasePostgresTests(PostgresCase):
    def test_extracted_finally_does_not_remove_replacement_lease_or_live_peer(self):
        events = []
        account = self.store.register("cleanup-owner", "local-password")["id"]
        first = self.store.create_character(account, "Cleanup First")
        second = self.store.create_character(account, "Cleanup Second")
        old_generation = self.store.begin_session(account)
        self.store.select_character(account, old_generation, first["id"])
        new_generation = self.store.begin_session(account)
        self.store.select_character(account, new_generation, second["id"])
        new_peer = object()

        class Calls:
            def __init__(self, name):
                self.name = name

            def cancel(self, *args, **kwargs):
                events.append((self.name, "cancel", args, kwargs))

            def unregister(self, *args):
                events.append((self.name, "unregister", args))

            def release(self, *args):
                events.append((self.name, "release", args))

        class Connections:
            def unregister(self, connection):
                events.append(("connection_unregister", connection))

        class World:
            def leave(self, character_id, generation):
                events.append(("world_leave", character_id, generation))

        class Groups:
            def finish(self, *args, **kwargs):
                events.append(("group_finish", args))

        class Store:
            def heartbeat(self, account_id, generation):
                return self_store.heartbeat(account_id, generation)

            def end_session(self, account_id, generation):
                events.append(("end_session", generation))
                return self_store.end_session(account_id, generation)

        def checkpoint(status):
            events.append(("checkpoint", status))

        self_store = self.store

        def flush_positions(**scope):
            events.append(("position_flush", scope))

        def release_groups(generation):
            events.append(("group_release", generation))

        def record(**data):
            events.append(("record", data))

        namespace = {
            "active_request": None,
            "PLANTINGS": Calls("plantings"),
            "HARVESTS": Calls("harvests"),
            "console_session": None,
            "TEST_CONSOLE": Calls("test_console"),
            "character": {"id": first["id"], "account_id": account},
            "generation": old_generation,
            "CONNECTIONS": Connections(),
            "service": "world",
            "checkpoint_fight": checkpoint,
            "fight": None,
            "group_lease": None,
            "account_id": account,
            "STORE": Store(),
            "record": record,
            "redact": str,
            "flush_positions": flush_positions,
            "POSITIONS": Calls("positions"),
            "COMBAT_GROUPS": Groups(),
            "release_groups": release_groups,
            "WORLD": World(),
            "LOCK": threading.RLock(),
            "LIVE": {account: (new_generation, new_peer)},
            "COMBAT_SESSIONS": SimpleNamespace(
                registry=SimpleNamespace(
                    lease_generation_active=lambda _generation: False
                )
            ),
            "HAVEN_BAG_EXTERIORS": SimpleNamespace(discard=lambda *_args: None),
        }

        from wakfu_server import combat_health

        with patch.object(combat_health, "persist_aborted_fight", return_value=None):
            run_finally = extracted_session_finalizer(namespace)
            run_finally(object())

        self.assertEqual(namespace["LIVE"], {account: (new_generation, new_peer)})
        self.assertTrue(
            self.store.current_character_session(account, new_generation, second["id"])
        )
        self.assertIn(("world_leave", first["id"], old_generation), events)
        self.assertIn(("end_session", old_generation), events)
