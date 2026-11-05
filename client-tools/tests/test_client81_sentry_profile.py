import importlib.util
import json
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
RUNNERS = (
    ROOT / "client-tools/dropin/run-client.py",
    ROOT / "client-tools/mini-launcher-desktop/run-client.py",
)
NATIVE_FACTORY = (
    "com.ankamagames.wakfu.client.core.sentry.WakfuSentryClientFactory"
)


class Client81SentryProfileTests(unittest.TestCase):
    def test_profile_blanks_dsn_and_preserves_native_factory_and_other_properties(self):
        for runner_path in RUNNERS:
            with (
                self.subTest(runner=runner_path.parent.name),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                source = root / "installed"
                source.mkdir()
                package = root / "launcher-package"
                package.mkdir()
                profiles = root / "profiles"
                package_config = package / "config.json"
                package_config.write_text(json.dumps({"game_ports": [15556]}))
                original_sentry = {
                    "environment": "prod",
                    "factory": NATIVE_FACTORY,
                    "release": "1.93.1+81",
                    "dsn": "https://private-dsn.example/123",
                    "stacktrace.app.packages": "com.ankama,com.ankamagames",
                    "io.sentry.ProguardUuids": "fixture-uuid",
                }
                (source / "sentry.properties").write_text(
                    "\n".join(f"{key}={value}" for key, value in original_sentry.items())
                    + "\n"
                )
                (source / "config.properties").write_text(
                    "dispatchAddresses=old.example:1\n"
                    "interChatUrl=old.example:2\n"
                    "bugReport.enable=true\n"
                )
                (source / "log4j.properties").write_text(
                    "INFO, stdout, mainLog, Sentry\n"
                )
                (source / "classpath").write_text("-cp lib/wakfu-client.jar\n")
                (source / "wakfu-client.jar").write_bytes(b"fixture")

                portable = types.ModuleType("portable_config")
                if runner_path.parent.name == "dropin":
                    config = {
                        "server_host": "127.0.0.1",
                        "http_port": 18080,
                        "dispatch_port": 15558,
                        "chat_port": 16337,
                        "api_port": 18081,
                    }
                else:
                    config = {
                        "server_host": "127.0.0.1",
                        "http_url": "http://127.0.0.1:18080",
                        "chat_host": "127.0.0.1",
                        "chat_port": 16337,
                        "dispatch_port": 15558,
                        "shop_url": "http://127.0.0.1:18083",
                        "allowed_endpoints": [
                            "127.0.0.1:15558",
                            "127.0.0.1:16337",
                            "127.0.0.1:18080",
                            "127.0.0.1:18081",
                            "127.0.0.1:18083",
                        ],
                    }
                portable.settings = lambda: config
                portable.client_root = lambda: source
                portable.profile_root = lambda name: profiles / name
                portable.package_root = lambda: package
                portable.pin_dns = lambda cfg: None
                portable.validated_resolved_hosts = lambda hosts: hosts

                spec = importlib.util.spec_from_file_location(
                    f"launcher_runner_{runner_path.parent.name}", runner_path
                )
                runner = importlib.util.module_from_spec(spec)
                with patch.dict(
                    sys.modules,
                    {"portable_config": portable},
                ), patch.dict(
                    "os.environ",
                    {"WAKFU_LAUNCHER_CONFIG": str(package_config)},
                ):
                    spec.loader.exec_module(runner)

                _, runtime, _ = runner.prepare("sentry-regression")
                generated = dict(
                    line.split("=", 1)
                    for line in (runtime / "client/sentry.properties")
                    .read_text()
                    .splitlines()
                    if line and not line.startswith("#")
                )
                self.assertEqual(generated["dsn"], "")
                self.assertEqual(generated["environment"], "private")
                self.assertEqual(generated["factory"], NATIVE_FACTORY)
                expected = dict(original_sentry)
                expected.update(dsn="", environment="private")
                self.assertEqual(generated, expected)
                self.assertNotIn(
                    "private-dsn.example",
                    (runtime / "client/sentry.properties").read_text(),
                )

    def test_runtime_profile_prepare_preserves_native_sentry_factory(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            profiles = types.ModuleType("wakfu_server.profiles")
            profiles.profile_root = lambda: runtime
            prepare = ROOT / "client-tools/runtime/prepare-local-client.py"
            with patch.dict(sys.modules, {"wakfu_server.profiles": profiles}):
                runpy.run_path(str(prepare))

            source = ROOT / "client/sentry.properties"
            original = dict(
                line.split("=", 1)
                for line in source.read_text().splitlines()
                if line and not line.startswith("#") and "=" in line
            )
            generated_text = (runtime / "client/sentry.properties").read_text()
            generated = dict(
                line.split("=", 1)
                for line in generated_text.splitlines()
                if line and not line.startswith("#") and "=" in line
            )
            expected = dict(original)
            expected.update(dsn="", environment="private")
            self.assertEqual(generated, expected)
            self.assertEqual(
                generated["factory"],
                "com.ankamagames.wakfu.client.core.sentry.WakfuSentryClientFactory",
            )
            self.assertEqual(generated["dsn"], "")


if __name__ == "__main__":
    unittest.main()
