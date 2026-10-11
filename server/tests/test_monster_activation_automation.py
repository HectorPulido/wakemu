"""Unit tests for sequencing and safety boundaries of NPC activation automation."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime"
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import automate_monster_activation as automation


class MonsterActivationAutomationTests(unittest.TestCase):
    def args(self, output, *, stage=False):
        return SimpleNamespace(
            output=Path(output),
            coverage=Path("coverage.json"),
            bundle=Path("native-bundle"),
            dsn="host=127.0.0.1 dbname=wakemu_runtime user=wakemu",
            password_file=Path(".runtime/local/secrets/postgres-password"),
            registry=Path("registry.json"),
            setters=Path("setters.json"),
            max_level=9,
            only_ref=[39, 46],
            stage=stage,
        )

    def test_command_plan_orders_gates_and_reuses_one_candidate_and_validation_receipt(
        self,
    ):
        work = RUNTIME / "plan-only-test"
        phases = automation.pipeline_commands(self.args(work))

        self.assertEqual(
            [phase for phase, _ in phases],
            [
                "prepare",
                "previews",
                "commit_and_classes",
                "finalize",
                "stage",
            ],
        )
        commands = dict(phases)
        candidate = str(work / "candidate")
        self.assertIn(candidate, commands["prepare"])
        self.assertEqual(
            commands["previews"][commands["previews"].index("--candidate") + 1],
            candidate,
        )
        self.assertEqual(
            commands["commit_and_classes"][
                commands["commit_and_classes"].index("--candidate") + 1
            ],
            candidate,
        )
        self.assertEqual(
            commands["finalize"][-3:],
            [candidate, str(work / "validation.json"), str(work / "validated")],
        )
        self.assertIn(str(work / "previews.json"), commands["commit_and_classes"])
        self.assertEqual(
            commands["commit_and_classes"][
                commands["commit_and_classes"].index("--output") + 1
            ],
            str(work / "validation.json"),
        )
        self.assertIn("--skip-class-tests", commands["previews"])
        self.assertIn("--class-tests-only", commands["commit_and_classes"])
        self.assertNotIn("--stage", commands["stage"])
        for _, command in phases:
            self.assertNotIn("activate", " ".join(command).lower())
            self.assertNotIn("restart", " ".join(command).lower())

    def test_explicit_stage_is_the_only_plan_difference_that_publishes(self):
        work = RUNTIME / "plan-stage-test"
        default = automation.pipeline_commands(self.args(work))
        requested = automation.pipeline_commands(self.args(work, stage=True))

        self.assertEqual(default[:-1], requested[:-1])
        self.assertNotIn("--stage", default[-1][1])
        self.assertEqual(requested[-1][1][-1], "--stage")

    def test_work_directory_must_be_beneath_runtime(self):
        with self.assertRaisesRegex(ValueError, "beneath .runtime"):
            automation.pipeline_commands(self.args(ROOT / "outside-activation-test"))

    def test_inline_passwords_in_keyword_or_uri_dsn_are_rejected_before_planning(self):
        work = RUNTIME / "inline-password-test"
        for dsn in (
            "host=localhost user=test dbname=test password=do-not-leak",
            "postgresql://test:do-not-leak@localhost/test",
        ):
            with self.subTest(dsn=dsn), self.assertRaisesRegex(
                ValueError, "inline password"
            ):
                automation.pipeline_commands(
                    SimpleNamespace(
                        **{
                            **vars(self.args(work)),
                            "dsn": dsn,
                        }
                    )
                )

    def _run_main(self, returncodes):
        temp = tempfile.TemporaryDirectory(
            dir=RUNTIME, prefix="activation-automation-test-"
        )
        self.addCleanup(temp.cleanup)
        output = Path(temp.name) / "run"
        password_file = Path(temp.name) / "db-password"
        password_file.write_text("raw-test-password\n")
        argv = [
            "automate_monster_activation.py",
            "--coverage",
            str(ROOT / "coverage.json"),
            "--bundle",
            str(ROOT / "native-bundle"),
            "--output",
            str(output),
            "--dsn",
            "host=localhost user=test dbname=test",
            "--password-file",
            str(password_file),
            "--registry",
            str(ROOT / "registry.json"),
            "--setters",
            str(ROOT / "setters.json"),
        ]
        calls = []

        def fake_run(command, *, cwd, env, stdout, stderr, check):
            calls.append((command, cwd, env, stderr, check))
            return SimpleNamespace(returncode=returncodes[len(calls) - 1])

        return output, calls, argv, fake_run

    def test_main_uses_secret_only_in_child_environment_defaulting_to_dry_run(self):
        output, calls, argv, fake_run = self._run_main([0, 0, 0, 0, 0])
        conninfo = "host=localhost user=test dbname=test password=raw-test-password"
        with patch.object(sys, "argv", argv), patch.object(
            automation.subprocess, "run", side_effect=fake_run
        ), patch(
            "psycopg.conninfo.make_conninfo", return_value=conninfo
        ) as make_conninfo:
            automation.main()

        self.assertEqual(len(calls), 5)
        make_conninfo.assert_called_once_with(
            "host=localhost user=test dbname=test", password="raw-test-password"
        )
        for command, cwd, env, stderr, check in calls:
            self.assertEqual(cwd, ROOT)
            self.assertEqual(env["WAKFU_DATABASE_URL"], conninfo)
            self.assertNotIn("raw-test-password", " ".join(command))
            self.assertIs(stderr, __import__("subprocess").STDOUT)
            self.assertFalse(check)
        self.assertNotIn("--stage", calls[-1][0])
        receipt = json.loads((output / "pipeline.json").read_text())
        self.assertIs(receipt["activated"], False)
        self.assertEqual([row["returncode"] for row in receipt["phases"]], [0] * 5)
        self.assertNotIn("raw-test-password", (output / "pipeline.json").read_text())

    def test_main_stops_at_first_failed_phase_and_records_failure_receipt(self):
        output, calls, argv, fake_run = self._run_main([0, 1, 0, 0, 0])
        with patch.object(sys, "argv", argv), patch.object(
            automation.subprocess, "run", side_effect=fake_run
        ), patch(
            "psycopg.conninfo.make_conninfo",
            return_value="host=localhost password=secret",
        ):
            with self.assertRaises(SystemExit) as raised:
                automation.main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(len(calls), 2)
        receipt = json.loads((output / "pipeline.json").read_text())
        self.assertIs(receipt["activated"], False)
        self.assertEqual(
            receipt["phases"],
            [
                {"phase": "prepare", "returncode": 0},
                {"phase": "previews", "returncode": 1},
            ],
        )
        self.assertFalse((output / "commit_and_classes.log").exists())


if __name__ == "__main__":
    unittest.main()
