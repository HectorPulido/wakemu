"""Ready waits for its already-published owner's socket attachment."""
import ast
from copy import deepcopy
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).parents[1] / "local_game_server.py"


class InitialAttachmentDispatchTests(unittest.TestCase):
    def test_received_ready_waits_for_attachment_and_bypasses_idle_retry_throttle(self):
        tree = ast.parse(SOURCE.read_text())
        helper = deepcopy(
            next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "attempt_shared_combat_attachment"
            )
        )
        helper.body = [
            ast.Global(names=node.names) if isinstance(node, ast.Nonlocal) else node
            for node in helper.body
        ]
        # Exercise the actual received-request branch as well as the helper.
        dispatch_attach = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.BoolOp)
            and "combat_session is None" in ast.unparse(node.test)
            and "fight is None" in ast.unparse(node.test)
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "attempt_shared_combat_attachment"
                for call in ast.walk(node)
            )
        )
        ready = deepcopy(
            next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.If)
                and ast.unparse(node.test) == "opcode == 12523 and fight is not None"
            )
        )
        ready.orelse = []
        dispatch = ast.parse("def dispatch():\n pass\n").body[0]
        dispatch.body = [deepcopy(dispatch_attach), ready]
        module = ast.fix_missing_locations(
            ast.Module(body=[helper, dispatch], type_ignores=[])
        )

        for throttled in (False, True):
            with self.subTest(throttled=throttled):
                entered_wait = threading.Event()
                gate = threading.Lock()
                gate.acquire()

                class ObservedLock:
                    def acquire(self, *, blocking=True):
                        if blocking:
                            entered_wait.set()
                        return gate.acquire(blocking=blocking)

                    def release(self):
                        gate.release()

                owner = SimpleNamespace(
                    account_id=60, character_id=122, generation="unchanged"
                )
                shared = SimpleNamespace(lock=ObservedLock(), fight=object())
                apply_readiness = Mock()
                namespace = dict(
                    COMBAT_TEST=True,
                    loaded=True,
                    character={"id": 122},
                    combat_session=None,
                    fight=None,
                    opcode=12523,
                    body=b"\x01",
                    account_id=60,
                    generation=owner.generation,
                    publication_recovery_shared=None,
                    publication_recovery_attempt_token=("source", "lease")
                    if throttled
                    else None,
                    publication_recovery_attempt_due=100.0,
                    publication_recovery_notice_token=None,
                    continue_aborted_publication_recovery=lambda: False,
                    COMBAT_SESSIONS=SimpleNamespace(lookup_character=lambda _: shared),
                    connection=SimpleNamespace(
                        instance_publications=SimpleNamespace(
                            lease=SimpleNamespace(current="lease")
                        )
                    ),
                    time=SimpleNamespace(monotonic=lambda: 1.0),
                    deferred_native_combat_attachment=lambda: None,
                    record=Mock(),
                    apply_readiness=apply_readiness,
                )

                def adopt():
                    namespace["fight"] = shared.fight
                    namespace["combat_session"] = owner
                    return True

                namespace["adopt_shared_duel"] = Mock(side_effect=adopt)
                exec(compile(module, str(SOURCE), "exec"), namespace)
                failures = []

                def received_ready():
                    try:
                        namespace["dispatch"]()
                    except BaseException as error:
                        failures.append(error)

                with patch(
                    "wakfu_server.combat_instance_publication_recovery.requires_publication_recovery",
                    return_value=True,
                ), patch(
                    "wakfu_server.combat_instance_publication_recovery.publication_recovery_token",
                    return_value="source",
                ):
                    self.assertFalse(namespace["attempt_shared_combat_attachment"]())
                    namespace["adopt_shared_duel"].assert_not_called()
                    worker = threading.Thread(target=received_ready, daemon=True)
                    worker.start()
                    try:
                        self.assertTrue(
                            entered_wait.wait(2),
                            "Received Ready did not wait for attachment",
                        )
                        apply_readiness.assert_not_called()
                    finally:
                        gate.release()
                        worker.join(2)
                    self.assertFalse(worker.is_alive())
                self.assertEqual(failures, [])
                namespace["adopt_shared_duel"].assert_called_once_with()
                apply_readiness.assert_called_once_with(True)
                self.assertIs(namespace["combat_session"], owner)
                self.assertEqual(namespace["generation"], "unchanged")
