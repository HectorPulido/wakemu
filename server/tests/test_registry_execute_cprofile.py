import importlib.util
import ast
import json
import os
from pathlib import Path
import pstats
import tempfile
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).parent
PROBE_PATH = ROOT.parent / "tools" / "registry_execute_cprofile.py"
SPEC = importlib.util.spec_from_file_location(
    "registry_execute_cprofile",
    PROBE_PATH,
)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class Fight:
    def __init__(self, fight_id=71, wave=4):
        self.id = fight_id
        self.turn_id = 12
        self.rift_wave_state = {"wave": wave}


class Shared:
    def __init__(self, fight):
        self.fight = fight
        self.lock = threading.RLock()


class Registry:
    def __init__(self, shared):
        self.shared = shared
        self.calls = []

    def lookup(self, fight_id):
        assert fight_id == self.shared.fight.id
        return self.shared

    def execute(
        self,
        fight_id,
        session,
        actor_id,
        operation,
        *,
        expected_sequence=None,
        require_turn=True,
        incident_request=None
    ):
        self.calls.append((fight_id, incident_request.get("opcode")))
        if incident_request.get("opcode") == 12403:
            assert type(self).execute is original_execute
            assert self.shared.lock._is_owned()
        if operation == "raise":
            raise original_error
        return (fight_id, actor_id, incident_request.get("opcode"))


original_execute = Registry.execute
original_error = RuntimeError("selected original failure")


class RegistryExecuteCProfileTests(unittest.TestCase):
    def _install(self, directory, registry_type=Registry, fight_type=Fight):
        return PROBE.install(
            registry_type,
            fight_type,
            fight_id=71,
            wave=4,
            opcode=12403,
            profile_path=Path(directory) / "execute.prof",
            metadata_path=Path(directory) / "execute.json",
        )

    def test_profiles_only_matching_fight_wave_opcode_and_restores_method(self):
        registry = Registry(Shared(Fight()))
        with tempfile.TemporaryDirectory() as directory:
            self._install(directory)
            self.assertEqual(
                registry.execute(
                    71, object(), 9, "return", incident_request={"opcode": 13260}
                ),
                (71, 9, 13260),
            )
            self.assertNotEqual(type(registry).execute, original_execute)
            result = registry.execute(
                71,
                object(),
                9,
                "return",
                incident_request={"opcode": 12403, "body": b"private"},
            )
            self.assertEqual(result, (71, 9, 12403))
            self.assertIs(type(registry).execute, original_execute)
            metadata = json.loads((Path(directory) / "execute.json").read_text())
            profile_path = Path(directory) / "execute.prof"
            self.assertTrue(profile_path.is_file())
            self.assertEqual(profile_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                (Path(directory) / "execute.json").stat().st_mode & 0o777, 0o600
            )

        self.assertEqual(registry.calls, [(71, 13260), (71, 12403)])
        self.assertEqual(metadata["status"], "returned")
        self.assertEqual(
            (
                metadata["fight_id"],
                metadata["turn_id"],
                metadata["wave"],
                metadata["opcode"],
            ),
            (71, 12, 4, 12403),
        )
        self.assertTrue(metadata["started_utc"] and metadata["ended_utc"])
        self.assertNotIn("private", json.dumps(metadata))

    def test_original_exception_is_preserved_once_after_profile(self):
        registry = Registry(Shared(Fight()))
        with tempfile.TemporaryDirectory() as directory:
            self._install(directory)
            with self.assertRaises(RuntimeError) as raised:
                registry.execute(
                    71, object(), 9, "raise", incident_request={"opcode": 12403}
                )
            metadata = json.loads((Path(directory) / "execute.json").read_text())
        self.assertIs(raised.exception, original_error)
        self.assertEqual(len(registry.calls), 1)
        self.assertEqual(metadata["status"], "raised")
        self.assertIs(type(registry).execute, original_execute)

    def test_profile_excludes_work_on_concurrent_threads(self):
        case = self
        registry = Registry(Shared(Fight()))
        entered = threading.Event()
        other_done = threading.Event()

        def unrelated_worker():
            self.assertTrue(entered.wait(2))
            unrelated_work()
            other_done.set()

        def replacement_execute(
            self,
            fight_id,
            session,
            actor_id,
            operation,
            *,
            expected_sequence=None,
            require_turn=True,
            incident_request=None
        ):
            worker = threading.Thread(target=unrelated_worker)
            worker.start()
            entered.set()
            case.assertTrue(other_done.wait(2))
            worker.join(3)
            case.assertFalse(worker.is_alive())
            self.calls.append((fight_id, incident_request.get("opcode")))
            return (fight_id, actor_id, incident_request.get("opcode"))

        def unrelated_work():
            return sum(range(20))

        original = Registry.execute
        Registry.execute = replacement_execute
        try:
            with tempfile.TemporaryDirectory() as directory:
                self._install(directory)
                result = registry.execute(
                    71, object(), 9, "return", incident_request={"opcode": 12403}
                )
                metadata = json.loads((Path(directory) / "execute.json").read_text())
                stats = pstats.Stats(str(Path(directory) / "execute.prof"))
        finally:
            Registry.execute = original

        self.assertEqual(result, (71, 9, 12403))
        self.assertTrue(metadata["thread_isolated"])
        self.assertEqual(
            metadata["profiler_backend"], "cProfile/sys.monitoring/thread-filtered"
        )
        self.assertEqual(metadata["profiler_thread_id"], threading.get_ident())
        replacement_calls = [
            value[1]
            for key, value in stats.stats.items()
            if key[2] == "replacement_execute"
        ]
        self.assertEqual(sum(replacement_calls), 1)
        self.assertFalse(any(key[2] == "unrelated_work" for key in stats.stats))

        monitoring = PROBE.sys.monitoring
        profiler_id = monitoring.PROFILER_ID
        self.assertIsNone(monitoring.get_tool(profiler_id))
        tool_name = "existing-cprofile-tool"
        calls = [0]

        def callback(*args):
            calls[0] += 1

        monitoring.use_tool_id(profiler_id, tool_name)
        monitoring.register_callback(profiler_id, monitoring.events.CALL, callback)
        monitoring.set_events(profiler_id, monitoring.events.CALL)
        try:
            existing = Registry(Shared(Fight()))
            with tempfile.TemporaryDirectory() as directory:
                self._install(directory)
                existing.execute(
                    71, object(), 9, "return", incident_request={"opcode": 12403}
                )
                metadata = json.loads((Path(directory) / "execute.json").read_text())
                profile_path = Path(directory) / "execute.prof"
            self.assertEqual(metadata["status"], "skipped_existing_profiler")
            self.assertFalse(profile_path.exists())
            self.assertEqual(monitoring.get_tool(profiler_id), tool_name)
            self.assertEqual(monitoring.get_events(profiler_id), monitoring.events.CALL)
            previous_calls = calls[0]

            def monitored_owner_call():
                return "still-installed"

            self.assertEqual(monitored_owner_call(), "still-installed")
            self.assertGreater(calls[0], previous_calls)
        finally:
            monitoring.set_events(profiler_id, 0)
            monitoring.register_callback(profiler_id, monitoring.events.CALL, None)
            monitoring.free_tool_id(profiler_id)

    def test_existing_profiler_is_not_replaced(self):
        registry = Registry(Shared(Fight()))
        with tempfile.TemporaryDirectory() as directory:
            self._install(directory)
            sentinel = object()
            with patch.object(PROBE.sys, "getprofile", return_value=sentinel):
                result = registry.execute(
                    71, object(), 9, "return", incident_request={"opcode": 12403}
                )
            metadata = json.loads((Path(directory) / "execute.json").read_text())
            profile_path = Path(directory) / "execute.prof"
        self.assertEqual(result, (71, 9, 12403))
        self.assertEqual(metadata["status"], "skipped_existing_profiler")
        self.assertIsNone(metadata["profile_file"])
        self.assertFalse(profile_path.exists())

    def test_startup_install_is_disabled_by_default(self):
        old = os.environ.pop("WAKFU_REGISTRY_EXECUTE_CPROFILE", None)
        try:
            self.assertFalse(PROBE.install_from_environment(runtime_root=ROOT))
        finally:
            if old is not None:
                os.environ["WAKFU_REGISTRY_EXECUTE_CPROFILE"] = old

    def test_actual_endturn_incident_expression_has_three_capture_modes(self):
        repository = next(
            parent
            for parent in (ROOT, *ROOT.parents)
            if (parent / "server" / "local_game_server.py").is_file()
        )
        source_path = repository / "server" / "local_game_server.py"
        tree = ast.parse(source_path.read_text())
        expression = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if node.func.attr != "execute":
                continue
            keyword = next(
                (item for item in node.keywords if item.arg == "incident_request"), None
            )
            if keyword is None or not isinstance(keyword.value, ast.IfExp):
                continue
            body = keyword.value.body
            if (
                isinstance(body, ast.Call)
                and isinstance(body.func, ast.Name)
                and body.func.id == "dict"
                and any(item.arg == "body" for item in body.keywords)
                and any(
                    item.arg == "opcode"
                    and isinstance(item.value, ast.Constant)
                    and item.value.value == 12403
                    for item in body.keywords
                )
            ):
                expression = keyword.value
                break
        self.assertIsNotNone(expression, "end-turn capture expression was not found")

        compiled = compile(ast.Expression(expression), str(source_path), "eval")
        marker = object()
        cases = (
            ({}, None),
            (
                {"WAKFU_COMBAT_INCIDENT_DIR": "/private"},
                {"opcode": 12403, "body": marker},
            ),
            ({"WAKFU_REGISTRY_EXECUTE_CPROFILE": "1"}, {"opcode": 12403}),
            (
                {
                    "WAKFU_COMBAT_INCIDENT_DIR": "/private",
                    "WAKFU_REGISTRY_EXECUTE_CPROFILE": "1",
                },
                {"opcode": 12403, "body": marker},
            ),
        )
        for environment, expected in cases:
            with self.subTest(environment=tuple(sorted(environment))):
                with patch.dict(os.environ, environment, clear=True):
                    actual = eval(compiled, {"dict": dict, "os": os, "body": marker})
                if expected is None:
                    self.assertIsNone(actual)
                else:
                    self.assertEqual(set(actual), set(expected))
                    self.assertEqual(actual["opcode"], 12403)
                    if "body" in expected:
                        self.assertIs(actual["body"], marker)


if __name__ == "__main__":
    unittest.main()
