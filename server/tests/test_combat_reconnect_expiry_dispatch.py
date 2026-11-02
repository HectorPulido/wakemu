"""Execute the real socket expiry boundary without starting the World process."""
import ast
from copy import deepcopy
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from psycopg import DatabaseError
from psycopg_pool import PoolTimeout

from wakfu_server.combat_reconnect_birth_stage import (
    BirthPresentation,
    PendingBirthPresentation,
    ReconnectPresentationExpired,
)
from wakfu_server.combat_shared import Session


SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def extract(names, namespace):
    tree = ast.parse(SOURCE.read_text())
    nodes = [
        deepcopy(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    for node in nodes:
        node.decorator_list = [
            decorator
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Name)
            and decorator.id == "combat_reconnect_expiry_boundary"
        ]
        node.body = [
            ast.Global(names=statement.names)
            if isinstance(statement, ast.Nonlocal)
            else statement
            for statement in node.body
        ]
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
            str(SOURCE),
            "exec",
        ),
        namespace,
    )


class ReconnectExpiryDispatchTests(unittest.TestCase):
    def fixture(self):
        owner = Session(1, 100, "current", 527, 0)
        pending = PendingBirthPresentation.bind(
            owner, BirthPresentation(13, (300,), ((12053, b"actual-timeline"),))
        )
        pending.overflowed = True
        shared = SimpleNamespace(
            fight=SimpleNamespace(id=44, phase="active"),
            participants={1: owner},
            reconnect_presentations={1: pending},
            lock=threading.RLock(),
        )
        namespace = dict(
            reconnect_expiry_recovery=dict(running=False, notice=None, due=0.0),
            combat_session=owner,
            fight=shared.fight,
            generation=owner.generation,
            account_id=owner.account_id,
            character=dict(id=owner.character_id),
            COMBAT_SESSIONS=SimpleNamespace(
                registry=SimpleNamespace(lookup=Mock(return_value=shared))
            ),
            time=SimpleNamespace(monotonic=Mock(return_value=10.0)),
            record=Mock(),
            send=Mock(),
            information=lambda message: (674, message),
            connection=object(),
            service="world",
            emergency_exit_current_combat=Mock(return_value=True),
            continue_aborted_publication_recovery=Mock(return_value=True),
            DatabaseError=DatabaseError,
            PoolTimeout=PoolTimeout,
        )
        extract(
            {
                "recover_expired_combat_presentation",
                "combat_reconnect_expiry_boundary",
                "refresh_shared_combat",
                "drain_shared_combat",
            },
            namespace,
        )
        return namespace, shared, pending

    def test_refresh_and_delivery_recover_before_native_dispatch(self):
        for entry in ("refresh_shared_combat", "drain_shared_combat"):
            with self.subTest(entry=entry):
                ns, shared, pending = self.fixture()

                def cancel(**kwargs):
                    self.assertIs(kwargs["expired_presentation"], pending)
                    # Duel settlement can refresh internally; do not recurse
                    # into a second cancellation while finishing the first.
                    self.assertFalse(ns["recover_expired_combat_presentation"]())
                    return True

                ns["emergency_exit_current_combat"].side_effect = cancel
                self.assertIs(ns[entry](blocking=False), False)
                ns["emergency_exit_current_combat"].assert_called_once_with(
                    expired_presentation=pending
                )
                ns["continue_aborted_publication_recovery"].assert_called_once_with()
                self.assertFalse(ns["reconnect_expiry_recovery"]["running"])
                self.assertIs(shared.reconnect_presentations[1], pending)

    def test_database_retry_keeps_socket_and_reports_once(self):
        ns, shared, pending = self.fixture()
        ns["emergency_exit_current_combat"].side_effect = DatabaseError("busy")
        for now in (10.0, 10.5, 11.0):
            ns["time"].monotonic.return_value = now
            self.assertTrue(ns["recover_expired_combat_presentation"]())
        self.assertEqual(ns["emergency_exit_current_combat"].call_count, 2)
        ns["send"].assert_called_once()
        ns["continue_aborted_publication_recovery"].assert_not_called()
        self.assertIs(shared.reconnect_presentations[1], pending)
        self.assertEqual(shared.fight.phase, "active")

    def test_expiry_racing_delivery_recovers_but_other_connection_errors_propagate(
        self,
    ):
        ns, shared, pending = self.fixture()
        pending.overflowed, pending.deadline = False, float("inf")

        def expired_delivery(*args, **kwargs):
            pending.overflowed = True
            raise ReconnectPresentationExpired("presentation_buffer_overflow")

        ns["COMBAT_SESSIONS"].dispatch_connected = expired_delivery
        self.assertIs(ns["drain_shared_combat"](), False)
        ns["emergency_exit_current_combat"].assert_called_once_with(
            expired_presentation=pending
        )
        pending.overflowed = False
        ns["COMBAT_SESSIONS"].dispatch_connected = Mock(
            side_effect=ConnectionError("actual broken socket")
        )
        with self.assertRaisesRegex(ConnectionError, "actual broken socket"):
            ns["drain_shared_combat"]()

    def test_healthy_waiting_and_stale_owners_never_cancel(self):
        for case in ("healthy", "generation", "character", "membership", "retired"):
            with self.subTest(case=case):
                ns, shared, pending = self.fixture()
                if case == "healthy":
                    pending.overflowed, pending.deadline = False, float("inf")
                elif case == "generation":
                    ns["generation"] = "replacement"
                elif case == "character":
                    ns["character"] = dict(id=101)
                elif case == "membership":
                    shared.participants.clear()
                else:
                    ns["COMBAT_SESSIONS"].registry.lookup.side_effect = ValueError(
                        "retired"
                    )
                self.assertFalse(ns["recover_expired_combat_presentation"]())
                ns["emergency_exit_current_combat"].assert_not_called()
                ns["send"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
