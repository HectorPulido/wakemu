"""Verify platform launch arguments without requiring a graphical client."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

DROPIN = Path(__file__).resolve().parents[1] / "dropin"
sys.path.insert(0, str(DROPIN))
spec = importlib.util.spec_from_file_location("dropin_runner", DROPIN / "run-client.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class LinuxClientTests(unittest.TestCase):
    def run_client(self, platform, arguments, display=True):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, runtime, agents = root / "source", root / "runtime", root / "agents"
            java = source / (
                "jre/Contents/Home/bin/java" if platform == "darwin" else "jre/bin/java"
            )
            java.parent.mkdir(parents=True)
            java.touch()
            agents.mkdir()
            for agent in ("network-guard.jar", "open-planting.jar", "desktop-fix.jar"):
                (agents / agent).touch()
            (runtime / "logs").mkdir(parents=True)
            cfg = dict(
                server_name="127.0.0.1",
                server_host="127.0.0.1",
                open_planting=True,
                open_dungeon_missions=False,
            )
            env = dict(
                WAKFU_AGENT_ROOT=str(agents),
                ZAAP_PORT="1234",
                ZAAP_HASH="test",
                WAKFU_CAPTURE_AGENT=str(root / "capture-agent.jar"),
            )
            if display:
                env["DISPLAY"] = ":0"
            warning = io.StringIO()
            with patch.dict(os.environ, env, clear=True), patch.object(
                sys, "platform", platform
            ), patch.object(sys, "argv", ["run-client.py", *arguments]), patch.object(
                runner, "settings", return_value=cfg
            ), patch.object(
                runner, "pin_dns"
            ), patch.object(
                runner, "prepare", return_value=(source, runtime, {15556})
            ), patch.object(
                Path, "is_file", return_value=True
            ), patch.object(
                subprocess, "call", return_value=0
            ) as call, patch.object(
                subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
            ) as run, contextlib.redirect_stderr(
                warning
            ):
                result = runner.main()
                command = (run if "--check" in arguments else call).call_args.args[0]
            return result, command, warning.getvalue()

    def test_linux_guard_check_uses_bundled_java_and_reports_isolation(self):
        result, command, warning = self.run_client("linux", ["--check"])
        self.assertEqual(result, 0)
        self.assertTrue(command[0].endswith("jre/bin/java"))
        self.assertIn("DropinNetworkGuardTest", command)
        self.assertTrue(any("network-guard.jar=" in arg for arg in command))
        self.assertIn("no OS network sandbox", warning)

    def test_linux_launch_preserves_capture_planting_and_telemetry_guard(self):
        _, command, _ = self.run_client("linux", ["--use-local-auth"])
        self.assertTrue(any("capture-agent.jar=" in arg for arg in command))
        self.assertTrue(any("open-planting.jar" in arg for arg in command))
        self.assertTrue(any("desktop-fix.jar" in arg for arg in command))
        self.assertFalse(any("com.apple" in arg for arg in command))

    def test_linux_launch_requires_desktop(self):
        with self.assertRaisesRegex(ValueError, "requires DISPLAY"):
            self.run_client("linux", ["--use-local-auth"], display=False)

    def test_macos_keeps_sandbox_and_desktop_agent(self):
        _, command, warning = self.run_client("darwin", ["--use-local-auth"])
        self.assertEqual(command[0], "/usr/bin/sandbox-exec")
        self.assertTrue(any("desktop-fix.jar" in arg for arg in command))
        self.assertTrue(any("com.apple.eawt" in arg for arg in command))
        self.assertEqual(warning, "")


if __name__ == "__main__":
    unittest.main()
