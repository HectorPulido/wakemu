import hashlib
import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "server/tools/run_dungeon_tls_acceptance.py"


class RunDungeonTlsAcceptanceTests(unittest.TestCase):
    def run_script(
        self, temp_root, config, bundle=None, *, fail_smoke=False, bundle_hash=None
    ):
        artifact_dir = temp_root / ".runtime/local/dungeon-tls-gate"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        config_path = temp_root / "selected-config.json"
        config_bytes = json.dumps(config, separators=(",", ":")).encode()
        config_path.write_bytes(config_bytes)
        args = [
            str(SCRIPT),
            "--image",
            "wakemu-candidate:test",
            "--candidate-db",
            "wakemu_candidate_smoke_unit",
            "--config",
            str(config_path),
            "--config-sha256",
            hashlib.sha256(config_bytes).hexdigest(),
        ]
        bundle_path = None
        if bundle is not None:
            bundle_path = temp_root / "bundle.json"
            bundle_bytes = json.dumps(bundle, separators=(",", ":")).encode()
            bundle_path.write_bytes(bundle_bytes)
            args.extend(
                [
                    "--bundle",
                    str(bundle_path),
                    "--bundle-sha256",
                    bundle_hash
                    if bundle_hash is not None
                    else hashlib.sha256(bundle_bytes).hexdigest(),
                ]
            )

        baseline = {
            "services": {
                "world": {
                    "image": "wakemu:test-r19",
                    "environment": {"BASELINE": "preserved"},
                }
            }
        }
        calls = []
        smoke_failed = False

        def fake_run(command, **kwargs):
            nonlocal smoke_failed
            command = list(command)
            calls.append((command, kwargs))
            if (
                command[:2] == ["docker", "exec"]
                and any(
                    item.endswith("candidate_dungeon_socket_smoke.py")
                    for item in command
                )
                and fail_smoke
                and not smoke_failed
            ):
                smoke_failed = True
                raise subprocess.CalledProcessError(17, command)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(sys, "argv", args), patch(
            "subprocess.check_output", return_value=json.dumps(baseline).encode()
        ), patch("subprocess.run", side_effect=fake_run), patch(
            "pathlib.Path.cwd", return_value=temp_root
        ):
            if fail_smoke:
                with self.assertRaises(subprocess.CalledProcessError):
                    runpy.run_path(str(SCRIPT), run_name="__main__")
            else:
                runpy.run_path(str(SCRIPT), run_name="__main__")
        return calls, artifact_dir, bundle_path

    def test_verified_bundle_hash_and_selected_config_reach_same_world_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = {"slug": "sample", "route": {"key": "custom_route"}}
            bundle = {"configurations": [selected]}
            calls, artifacts, bundle_path = self.run_script(
                root, selected, bundle, fail_smoke=True
            )

            docker_commands = [command for command, _ in calls]
            self.assertTrue(
                any(
                    command[:3] == ["docker", "compose", "-f"]
                    and "up" in command
                    and command[-1] == "world"
                    for command in docker_commands
                )
            )
            self.assertTrue(
                any(
                    command[:2] == ["docker", "cp"]
                    and str(bundle_path.resolve()) in command
                    for command in docker_commands
                )
            )
            self.assertTrue(
                any(
                    "install_bundle" in " ".join(command) for command in docker_commands
                )
            )

            result = json.loads((artifacts / "entry-tls-result.json").read_text())
            self.assertFalse(result["passed"])
            self.assertEqual(
                result["bundle_hash"],
                hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(result["phase_error"]["returncode"], 17)
            self.assertTrue(result["restore_requested"])
            restore_path = artifacts / "restore-compose.json"
            restore = json.loads(restore_path.read_text())
            self.assertEqual(
                restore,
                {
                    "services": {
                        "world": {
                            "image": "wakemu:test-r19",
                            "environment": {"BASELINE": "preserved"},
                        }
                    }
                },
            )
            restore_calls = [
                command
                for command in docker_commands
                if any("restore-compose.json" in item for item in command)
            ]
            self.assertEqual(1, len(restore_calls))
            self.assertEqual("world", restore_calls[0][-1])
            self.assertTrue(
                all(
                    command[-1] == "world"
                    for command in docker_commands
                    if command[:2] == ["docker", "compose"]
                    and ("up" in command or "restart" in command)
                )
            )

    def test_bad_bundle_hash_is_rejected_before_any_docker_orchestration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = {"slug": "sample", "route": {"key": "custom_route"}}
            bundle = {"configurations": [selected]}
            config_path = root / "selected-config.json"
            config_bytes = json.dumps(selected, separators=(",", ":")).encode()
            config_path.write_bytes(config_bytes)
            bundle_path = root / "bundle.json"
            bundle_path.write_text(json.dumps(bundle))
            args = [
                str(SCRIPT),
                "--image",
                "candidate",
                "--candidate-db",
                "wakemu_candidate_smoke_bad_hash",
                "--config",
                str(config_path),
                "--config-sha256",
                hashlib.sha256(config_bytes).hexdigest(),
                "--bundle",
                str(bundle_path),
                "--bundle-sha256",
                "0" * 64,
            ]
            with patch.object(sys, "argv", args), patch(
                "subprocess.run"
            ) as run_mock, patch("subprocess.check_output") as output_mock:
                with self.assertRaisesRegex(
                    ValueError, "Bundle artifact hash mismatch"
                ):
                    runpy.run_path(str(SCRIPT), run_name="__main__")
            run_mock.assert_not_called()
            output_mock.assert_not_called()

    def test_selected_configuration_hash_is_checked_before_docker_orchestration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = {"slug": "sample", "route": {"key": "custom_route"}}
            config_path = root / "selected-config.json"
            config_bytes = json.dumps(selected, separators=(",", ":")).encode()
            config_path.write_bytes(config_bytes)
            args = [
                str(SCRIPT),
                "--image",
                "candidate",
                "--candidate-db",
                "wakemu_candidate_smoke_bad_config",
                "--config",
                str(config_path),
                "--config-sha256",
                "0" * 64,
            ]
            with patch.object(sys, "argv", args), patch(
                "subprocess.run"
            ) as run_mock, patch("subprocess.check_output") as output_mock:
                with self.assertRaisesRegex(
                    ValueError, "Selected configuration artifact hash mismatch"
                ):
                    runpy.run_path(str(SCRIPT), run_name="__main__")
            run_mock.assert_not_called()
            output_mock.assert_not_called()

    def test_selected_configuration_must_be_member_of_hash_verified_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = {"slug": "selected", "route": {"key": "custom_route"}}
            config_path = root / "selected-config.json"
            config_bytes = json.dumps(selected, separators=(",", ":")).encode()
            config_path.write_bytes(config_bytes)
            bundle = {
                "configurations": [
                    {"slug": "different", "route": {"key": "other_route"}}
                ]
            }
            bundle_path = root / "bundle.json"
            bundle_bytes = json.dumps(bundle, separators=(",", ":")).encode()
            bundle_path.write_bytes(bundle_bytes)
            args = [
                str(SCRIPT),
                "--image",
                "candidate",
                "--candidate-db",
                "wakemu_candidate_smoke_not_selected",
                "--config",
                str(config_path),
                "--config-sha256",
                hashlib.sha256(config_bytes).hexdigest(),
                "--bundle",
                str(bundle_path),
                "--bundle-sha256",
                hashlib.sha256(bundle_bytes).hexdigest(),
            ]
            with patch.object(sys, "argv", args), patch(
                "subprocess.run"
            ) as run_mock, patch("subprocess.check_output") as output_mock:
                with self.assertRaisesRegex(ValueError, "not in the verified bundle"):
                    runpy.run_path(str(SCRIPT), run_name="__main__")
            run_mock.assert_not_called()
            output_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
