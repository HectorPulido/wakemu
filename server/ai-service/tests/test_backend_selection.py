"""Backend changes are atomic configuration, effective at actor-turn boundaries."""
import ast
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sys
import socket
import struct
import tempfile
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


selector = module("selection_under_test", ROOT / "wakfu_ai/bridge/backend_selection.py")
cli = module("selection_cli_under_test", ROOT / "scripts/ai_backend.py")


def runtime():
    result = SimpleNamespace(
        fight=SimpleNamespace(
            id=263, phase="active", current=SimpleNamespace(id=-7), turn_id=1
        ),
        awaiting_ack=None,
        pending=[],
    )
    result.end_server_turn = lambda *args: ["native_end"]
    result.end_automatic_npc_turn = lambda *args: ["automatic_end"]
    return result


class BackendSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = Path(temporary.name) / "ai-backend.json"

    def test_absent_configuration_preserves_current_endpoint(self):
        pin = selector.pin_backend(runtime(), config_path=self.config)
        self.assertEqual(
            (pin["backend"], pin["endpoint"]), ("current", "tcp://ai:8090")
        )
        self.assertFalse(self.config.exists())

    def test_switch_pins_existing_turn_and_changes_only_next_actor_turn(self):
        native = runtime()
        old = selector.pin_backend(native, config_path=self.config)
        selector.write_config(self.config, "jondo")
        with patch.object(
            selector, "read_config", side_effect=AssertionError("reread pinned turn")
        ):
            self.assertEqual(selector.pin_backend(native), old)
            copied = deepcopy(native)
            self.assertEqual(selector.pin_backend(copied), old)
            self.assertEqual(
                selector.pinned_endpoint(copied, expected_backend="current"),
                "tcp://ai:8090",
            )
        native.fight.turn_id += 1
        self.assertEqual(
            selector.pin_backend(native, config_path=self.config)["backend"], "jondo"
        )
        selector.write_config(self.config, "current")
        native.fight.current.id = -8
        self.assertEqual(
            selector.pin_backend(native, config_path=self.config)["backend"], "current"
        )

    def test_changed_config_does_not_interrupt_inflight_jondo(self):
        native = runtime()
        selector.write_config(self.config, "jondo")
        selector.pin_backend(native, config_path=self.config)
        self.config.write_text("invalid JSON")
        self.assertEqual(
            selector.pinned_endpoint(native, expected_backend="jondo"),
            "tcp://ai-jondo:8091",
        )
        native.fight.turn_id += 1
        with self.assertRaises(ValueError):
            selector.pin_backend(native, config_path=self.config)

    def test_unknown_or_malformed_configuration_never_routes_to_current(self):
        for raw in (
            "{}",
            '{"version":1,"backend":"unknown"}',
            '{"version":true,"backend":"jondo"}',
            '{"version":1,"backend":"current","endpoint":"evil"}',
            "null",
            "bad",
        ):
            with self.subTest(raw=raw):
                self.config.write_text(raw)
                native = runtime()
                with self.assertRaises(ValueError):
                    selector.pin_backend(native, config_path=self.config)
                self.assertFalse(hasattr(native, "native_ai_backend_pin"))

    def test_pin_is_plain_owned_metadata_and_adapter_requires_matching_turn(self):
        native = runtime()
        pin = selector.pin_backend(native, config_path=self.config)
        pin["identity"][1] = 900
        self.assertEqual(native.native_ai_backend_pin["identity"][1], -7)
        with self.assertRaises(ValueError):
            selector.pinned_endpoint(native, expected_backend="jondo")
        native.fight.turn_id += 1
        with self.assertRaises(ValueError):
            selector.pinned_endpoint(native, expected_backend="current")

    def test_failed_atomic_write_preserves_existing_file(self):
        selector.write_config(self.config, "current")
        original = self.config.read_bytes()
        with patch.object(
            selector.os, "replace", side_effect=OSError("rename rejected")
        ):
            with self.assertRaises(OSError):
                selector.write_config(self.config, "jondo")
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(list(self.config.parent.iterdir()), [self.config])

    def test_cli_checks_reachability_before_write_and_preserves_failure(self):
        selector.write_config(self.config, "current")
        output, errors = io.StringIO(), io.StringIO()
        args = [
            "--use",
            "jondo",
            "--config",
            str(self.config),
            "--health-host",
            "ai-jondo",
        ]
        with patch.object(cli, "_selector", return_value=selector), redirect_stdout(
            output
        ), redirect_stderr(errors):
            with patch.object(cli, "check_health", side_effect=OSError("offline")):
                self.assertEqual(cli.main(args), 1)
            self.assertEqual(selector.read_config(self.config)["backend"], "current")

            def reachable(host, port, backend, timeout):
                self.assertEqual((host, port, backend), ("ai-jondo", 8091, "jondo"))
                self.assertEqual(
                    selector.read_config(self.config)["backend"], "current"
                )
                return MagicMock()

            with patch.object(cli, "check_health", side_effect=reachable):
                self.assertEqual(cli.main(args), 0)
            self.assertEqual(selector.read_config(self.config)["backend"], "jondo")
            with patch.object(
                cli, "check_health", side_effect=AssertionError("status opens socket")
            ):
                self.assertEqual(
                    cli.main(["--status", "--config", str(self.config)]), 0
                )

    def patched_dispatch(self, *, automatic=False):
        repository = next(p for p in ROOT.parents if (p / "server/ai-service").is_dir())
        source = (
            repository / "server/ai-service/wakfu_ai/bridge/world_entry.py"
        ).read_text()
        source = source.replace(
            "    try:\n        yield from _run_npc_turn(\n            runtime,\n",
            (
                "    try:\n        from .backend_selection import pin_backend\n\n"
                "        backend = pin_backend(runtime)\n        runner = _run_npc_turn\n"
                '        if backend["backend"] == "jondo":\n'
                "            from .jondo_entry import run_npc_turn as runner\n"
                "        yield from runner(\n            runtime,\n"
            ),
        )
        function = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and node.name == "run_npc_turn"
        )
        namespace = dict(
            __package__="selector_dispatch_test",
            time=__import__("time"),
            effective_server_controlled=lambda *args: True,
        )

        def chosen(name):
            def run(*args, **kwargs):
                yield [name], dict(chosen=name)

            return run

        namespace["_run_npc_turn"] = chosen("current")
        modules = {}

        def stub(name, **attrs):
            result = ModuleType(name)
            vars(result).update(attrs)
            modules[name] = result

        stub(
            "selector_dispatch_test.backend_selection",
            pin_backend=lambda native: selector.pin_backend(
                native, config_path=self.config
            ),
        )
        stub("selector_dispatch_test.jondo_entry", run_npc_turn=chosen("jondo"))
        stub("selector_dispatch_test.world_host", execute=chosen("world_host"))
        stub(
            "selector_dispatch_test.world_shared",
            run_shared_turn=chosen("world_shared"),
        )
        stub(
            "wakfu_server.combat_automatic_npc_turn",
            requires_automatic_npc_turn_end=lambda *args: automatic,
        )
        stub("psycopg", Error=type("DatabaseError", (Exception,), {}))
        self.enterContext(patch.dict(sys.modules, modules))
        exec(
            compile(
                ast.Module(body=[function], type_ignores=[]),
                "world_entry.patch",
                "exec",
            ),
            namespace,
        )
        return namespace["run_npc_turn"]

    def test_thin_patch_preserves_default_and_boundary_dispatch(self):
        dispatch, native = self.patched_dispatch(), runtime()
        kwargs = dict(
            store=None, viewer_character=None, monsters=None, stats_serializer=None
        )
        self.assertEqual(list(dispatch(native, **kwargs))[0][0], ["current"])
        selector.write_config(self.config, "jondo")
        self.assertEqual(list(dispatch(native, **kwargs))[0][0], ["current"])
        native.fight.turn_id += 1
        self.assertEqual(list(dispatch(native, **kwargs))[0][0], ["jondo"])

    def test_automatic_guard_and_pending_actions_do_not_read_selector(self):
        native = runtime()
        dispatch = self.patched_dispatch(automatic=True)
        kwargs = dict(
            store=None, viewer_character=None, monsters=None, stats_serializer=None
        )
        self.config.write_text("invalid config must not be consulted")
        self.assertEqual(list(dispatch(native, **kwargs))[0][0], ["automatic_end"])
        self.assertFalse(hasattr(native, "native_ai_backend_pin"))
        native.pending = ["published_action"]
        self.assertEqual(list(dispatch(native, **kwargs)), [])

    def test_existing_host_and_shared_wrappers_run_before_dispatch(self):
        native = runtime()
        dispatch = self.patched_dispatch()
        self.config.write_text("invalid config must not precede wrappers")
        self.assertEqual(
            list(dispatch(native, world_context={"globals": {}}))[0][0], ["world_host"]
        )
        self.assertEqual(
            list(dispatch(native, session=object(), shared_adapter=object()))[0][0],
            ["world_shared"],
        )
        self.assertFalse(hasattr(native, "native_ai_backend_pin"))

    @contextmanager
    def framed_peer(
        self, *, service="wakfu-ai-jondo", oversized=False, incomplete=False
    ):
        requests = []
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            server.settimeout(2)

            def respond():
                with server.accept()[0] as peer:
                    peer.settimeout(2)

                    def read(size):
                        data = b""
                        while len(data) < size:
                            part = peer.recv(size - len(data))
                            if not part:
                                raise ConnectionError("Missing health request")
                            data += part
                        return data

                    size = struct.unpack("!I", read(4))[0]
                    requests.append(json.loads(read(size)))
                    if oversized:
                        peer.sendall(struct.pack("!I", 4 * 1024 * 1024 + 1))
                    elif incomplete:
                        peer.sendall(struct.pack("!I", 50) + b"{")
                    else:
                        reply = json.dumps(
                            dict(
                                id=1,
                                status=200,
                                payload=dict(
                                    status="ok", service=service, transport="tcp"
                                ),
                            )
                        ).encode()
                        frame = struct.pack("!I", len(reply)) + reply
                        peer.sendall(frame[:2])
                        peer.sendall(frame[2:])

            thread = threading.Thread(target=respond, daemon=True)
            thread.start()
            try:
                yield server.getsockname()[1], requests
            finally:
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())

    def test_real_framed_health_accepts_only_expected_services(self):
        for backend, service in (("jondo", "wakfu-ai-jondo"), ("current", "wakfu-ai")):
            with self.subTest(backend=backend), self.framed_peer(service=service) as (
                port,
                requests,
            ):
                cli.check_health("127.0.0.1", port, backend, 1)
            self.assertEqual(requests, [dict(id=1, endpoint="/health", payload={})])

    def test_real_wrong_service_does_not_replace_existing_configuration(self):
        selector.write_config(self.config, "current")
        with self.framed_peer(service="wakfu-ai") as (port, _), patch.object(
            cli, "_selector", return_value=selector
        ), redirect_stderr(io.StringIO()):
            result = cli.main(
                [
                    "--use",
                    "jondo",
                    "--config",
                    str(self.config),
                    "--health-host",
                    "127.0.0.1",
                    "--health-port",
                    str(port),
                ]
            )
        self.assertEqual(result, 1)
        self.assertEqual(selector.read_config(self.config)["backend"], "current")

    def test_health_rejects_oversized_and_incomplete_real_frames(self):
        for fields in (dict(oversized=True), dict(incomplete=True)):
            with self.subTest(fields=fields), self.framed_peer(**fields) as (port, _):
                with self.assertRaises((ValueError, ConnectionError)):
                    cli.check_health("127.0.0.1", port, "jondo", 1)

    def test_health_uses_one_absolute_deadline_across_partial_reads(self):
        elapsed = [0.0]
        peer = MagicMock()
        peer.__enter__.return_value = peer

        def delayed_byte(size):
            elapsed[0] += 0.4
            return b"\x00"

        peer.recv.side_effect = delayed_byte
        with patch.object(
            cli.time, "monotonic", side_effect=lambda: elapsed[0]
        ), patch.object(cli.socket, "create_connection", return_value=peer):
            with self.assertRaises(TimeoutError):
                cli.check_health("ai-jondo", 8091, "jondo", 1)
        self.assertEqual(peer.recv.call_count, 3)

    def test_flat_world_sdk_layout_resolves_without_repository(self):
        flat = self.config.parent / "app" / "ai-service"
        script = flat / "scripts" / "ai_backend.py"
        backend = flat / "wakfu_ai" / "bridge" / "backend_selection.py"
        script.parent.mkdir(parents=True)
        backend.parent.mkdir(parents=True)
        script.write_bytes((ROOT / "scripts/ai_backend.py").read_bytes())
        backend.write_bytes(
            (ROOT / "wakfu_ai/bridge/backend_selection.py").read_bytes()
        )
        flat_cli = module("flat_world_cli", script)
        self.assertIsNone(flat_cli._repository())
        self.assertEqual(
            flat_cli._selector().CONFIG_PATH, Path("/data/ai-backend.json")
        )
        fake_selector = MagicMock(BACKENDS=("current", "jondo"))
        fake_selector.read_config.return_value = dict(version=1, backend="current")
        fake_selector.endpoint_for.return_value = "tcp://ai:8090"
        with patch.object(
            flat_cli, "_selector", return_value=fake_selector
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(flat_cli.main(["--status"]), 0)
        fake_selector.read_config.assert_called_once_with(Path("/data/ai-backend.json"))

    def test_host_launcher_executes_existing_world_without_restart(self):
        host = module("host_ai_cli", ROOT.parent / "tools/ai_backend.py")
        with patch.object(
            host.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ) as run:
            self.assertEqual(host.main(["--use", "jondo"]), 0)
            command = run.call_args.args[0]
            self.assertIn("exec", command)
            self.assertNotIn("up", command)
            self.assertEqual(
                command[command.index("world") + 1 :],
                [
                    "python3",
                    "/app/ai-service/scripts/ai_backend.py",
                    "--config",
                    "/data/ai-backend.json",
                    "--use",
                    "jondo",
                    "--health-host",
                    "ai-jondo",
                    "--timeout",
                    "2.0",
                ],
            )
            self.assertEqual(host.main(["--status"]), 0)
            self.assertNotIn("--health-host", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
