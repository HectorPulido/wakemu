"""Preserve independent endpoint pins across sandboxed Python/JVM processes."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "desktop_portable_dns", SOURCE / "portable_config.py"
)
portable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portable)


class PortableDNSTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.pins = {
            "game.fixture": "203.0.113.1",
            "chat.fixture": "203.0.113.2",
            "auth.fixture": "203.0.113.3",
            "resources.fixture": "203.0.113.4",
            "shop.fixture": "203.0.113.5",
        }
        self.config = dict(
            server_host="game.fixture",
            chat_host="chat.fixture",
            api_url="https://auth.fixture:18443",
            http_url="https://resources.fixture",
            shop_url="https://shop.fixture:8443",
            dispatch_port=15558,
            game_ports=[15556],
            chat_port=16337,
            runtime_root=str(self.root / "profile"),
            install_root=str(self.root / "installed"),
        )
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps(self.config))
        self.env = {
            "WAKFU_LAUNCHER_CONFIG": str(self.config_path),
            "WAKFU_RESOLVED_HOSTS": json.dumps(self.pins),
        }
        self.patcher = patch.dict(os.environ, self.env)
        self.patcher.start()
        self.old = {
            name: os.environ.pop(name, None)
            for name in ("WAKFU_SERVER_IPV4", "WAKFU_SERVER_NAME")
        }

    def tearDown(self):
        self.patcher.stop()
        for name, value in self.old.items():
            if value is not None:
                os.environ[name] = value
        self.temp.cleanup()

    def runner(self):
        spec = importlib.util.spec_from_file_location(
            "desktop_dns_runner", SOURCE / "run-client.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"portable_config": portable}):
            spec.loader.exec_module(module)
        return module

    def installed_fixture(self):
        installed = self.root / "installed"
        for relative, value in {
            "lib/wakfu-client.jar": b"fixture-game-jar",
            "classpath": b"-cp lib/wakfu-client.jar",
            "config.properties": b"dispatchAddresses=old.invalid:1\ninterChatUrl=old.invalid:2\nshopiUrl=https://old.invalid/shop\nhaapiAnkamaUrl=https://old.invalid/haapi\n",
            "log4j.properties": b"INFO, stdout, mainLog, Sentry",
            "sentry.properties": b"dsn=unused",
            "jre/Contents/Home/bin/java": b"fixture-java",
        }.items():
            file = installed / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(value)
        agents = self.root / "agents"
        agents.mkdir()
        for name in ("network-guard.jar", "desktop-fix.jar", "open-planting.jar"):
            (agents / name).write_bytes(b"fixture-agent")
        return installed, agents

    def test_hosts_file_keeps_localhost_and_exact_independent_names_and_rejects_injection(
        self,
    ):
        runner = self.runner()
        cfg = portable.settings()
        runtime = self.root / "runtime"
        runtime.mkdir()
        options = runner.java_hosts_options(runtime, cfg)
        expected_path = runtime / "resolved-hosts.txt"
        self.assertEqual(options, ["-Djdk.net.hosts.file=" + str(expected_path)])
        rows = set(expected_path.read_text().splitlines())
        self.assertEqual(
            rows,
            {"127.0.0.1 localhost", "::1 localhost"}
            | {address + " " + name for name, address in self.pins.items()},
        )
        previous = expected_path.read_bytes()
        bad = dict(cfg, resolved_hosts={"game.fixture\nmalicious": "203.0.113.1"})
        with self.assertRaises(ValueError):
            runner.java_hosts_options(runtime, bad)
        self.assertEqual(expected_path.read_bytes(), previous)
        self.assertEqual(cfg["shop_url"], self.config["shop_url"])

    def test_check_bridge_and_game_commands_propagate_pins_and_jvm_hosts_without_changing_tls_urls(
        self,
    ):
        runner = self.runner()
        _, agents = self.installed_fixture()
        token = self.root / "fixture-session.json"
        token.write_text('{"api_token":"fixture-only"}')
        environment = {
            "WAKFU_AGENT_ROOT": str(agents),
            "ZAAP_PORT": "31337",
            "ZAAP_HASH": "fixture-bridge",
            "WAKFU_RESOLVED_HOSTS": json.dumps(self.pins),
        }
        cases = [
            (["--check"], "run"),
            (["--token-file", str(token)], "call"),
            (["--use-local-auth"], "call"),
        ]
        for arguments, operation in cases:
            with self.subTest(arguments=arguments), patch.dict(
                os.environ, environment
            ), patch.object(runner.sys, "platform", "darwin"), patch.object(
                runner.sys, "argv", ["run-client.py", *arguments]
            ), patch.object(
                portable.socket,
                "getaddrinfo",
                side_effect=AssertionError("DNS forbidden"),
            ), patch.object(
                runner.subprocess, "run", return_value=Mock(returncode=0)
            ) as run, patch.object(
                runner.subprocess, "call", return_value=0
            ) as call:
                self.assertEqual(runner.main(), 0)
            child = run if operation == "run" else call
            command = child.call_args.args[0]
            child_env = child.call_args.kwargs["env"]
            self.assertEqual(json.loads(child_env["WAKFU_RESOLVED_HOSTS"]), self.pins)
            self.assertEqual(command[:2], ["/usr/bin/sandbox-exec", "-f"])
            if arguments[0] != "--token-file":
                expected = "-Djdk.net.hosts.file=" + str(
                    self.root / "profile/resolved-hosts.txt"
                )
                self.assertIn(expected, command)
                guard = next(
                    value
                    for value in command
                    if value.startswith("-javaagent:") and "network-guard.jar" in value
                )
                for endpoint in portable.settings()["allowed_endpoints"]:
                    self.assertIn(endpoint, guard)
            else:
                self.assertTrue(command[-1].endswith("launcher-bridge.py"))
            runtime_config = (
                self.root / "profile/client/config.properties"
            ).read_text()
            self.assertIn("shopiUrl=https://shop.fixture:8443/shop", runtime_config)
            self.assertIn(
                "haapiAnkamaUrl=https://shop.fixture:8443/haapi", runtime_config
            )

    def test_fresh_python_child_resolves_all_configured_services_without_dns(self):
        code = """import json,socket,sys
sys.path.insert(0,sys.argv[1])
def forbidden(*args,**kwargs):
    raise OSError('Fixture sandbox denies all DNS')
socket.getaddrinfo=forbidden
import portable_config
cfg=portable_config.settings()
print(json.dumps({k:cfg[k] for k in ('resolved_hosts','allowed_endpoints','api_url','http_url','shop_url')}))
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(SOURCE)],
            env=dict(os.environ),
            text=True,
            capture_output=True,
            timeout=8,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = json.loads(result.stdout)
        self.assertEqual(cfg["resolved_hosts"], self.pins)
        for key in ("api_url", "http_url", "shop_url"):
            self.assertEqual(cfg[key], self.config[key])
        expected = {
            "game.fixture:15558",
            "203.0.113.1:15558",
            "game.fixture:15556",
            "203.0.113.1:15556",
            "chat.fixture:16337",
            "203.0.113.2:16337",
            "auth.fixture:18443",
            "203.0.113.3:18443",
            "resources.fixture:443",
            "203.0.113.4:443",
            "shop.fixture:8443",
            "203.0.113.5:8443",
        }
        self.assertEqual(set(cfg["allowed_endpoints"]), expected)

    def test_bad_pins_fail_closed_without_dns_or_hosts_injection(self):
        fixtures = [
            "not-json",
            "[]",
            json.dumps({"bad\nhost": "203.0.113.1"}),
            json.dumps({"game.fixture": "::1"}),
            json.dumps({"game.fixture": "203.0.113.1\n127.0.0.1 attacker"}),
            json.dumps({"192.168.0.7": "192.168.0.8"}),
            json.dumps({"game.fixture": 12345}),
        ]
        for raw in fixtures:
            with self.subTest(raw=raw), patch.dict(
                os.environ, {"WAKFU_RESOLVED_HOSTS": raw}
            ), patch.object(
                portable.socket,
                "getaddrinfo",
                side_effect=AssertionError(
                    "DNS must not be attempted for malformed inherited pins"
                ),
            ) as dns, self.assertRaises(
                ValueError
            ):
                portable.settings()
            dns.assert_not_called()

    def test_pin_dns_exports_full_mapping_and_retains_hostname_service_urls(self):
        cfg = portable.settings()
        os.environ.pop("WAKFU_RESOLVED_HOSTS")
        calls = []

        def resolver(host, port, family=0, type=0, proto=0, flags=0):
            calls.append((host, port, family, type, proto, flags))
            return [("fixture-result",)]

        with patch.object(portable.socket, "getaddrinfo", resolver):
            portable.pin_dns(cfg)
            self.assertEqual(json.loads(os.environ["WAKFU_RESOLVED_HOSTS"]), self.pins)
            self.assertEqual(
                socket.getaddrinfo(
                    b"SHOP.FIXTURE.", 8443, socket.AF_INET, socket.SOCK_STREAM
                ),
                [("fixture-result",)],
            )
        self.assertEqual(
            calls, [("203.0.113.5", 8443, socket.AF_INET, socket.SOCK_STREAM, 0, 0)]
        )
        for key in ("api_url", "http_url", "shop_url"):
            self.assertEqual(cfg[key], self.config[key])


if __name__ == "__main__":
    unittest.main(verbosity=2)
