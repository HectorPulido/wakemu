"""Regression checks for mistakes in host-lab scenario expectations."""

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "WakIA.HostLab.csproj"
DLL = ROOT / "bin/Release/net8.0/WakIA.HostLab.dll"


class HostLabValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.scenario = json.loads((ROOT / "Scenarios/basic.json").read_text())[0]

    def run_scenario(self, expectations):
        scenario = copy.deepcopy(self.scenario)
        scenario["expect"] = expectations
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "scenario.json").write_text(json.dumps([scenario]))
            return subprocess.run(
                ["dotnet", str(DLL), "--dir", directory], capture_output=True, text=True
            )

    def test_valid_expectations_are_checked(self):
        passed = self.run_scenario({"types": ["cast"], "spellId": 101})
        self.assertEqual(passed.returncode, 0, passed.stderr + passed.stdout)
        failed = self.run_scenario({"types": ["cast"], "spellId": 999})
        self.assertEqual(failed.returncode, 1, failed.stderr + failed.stdout)

    def test_unknown_or_empty_expectations_are_rejected(self):
        for expectations in ({"spellID": 999}, {}, {"types": []}):
            with self.subTest(expectations=expectations):
                result = self.run_scenario(expectations)
                self.assertEqual(result.returncode, 2, result.stderr + result.stdout)

    def test_non_success_cannot_hide_action_expectations(self):
        result = self.run_scenario({"status": 400, "spellId": 999})
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)

    def test_replay_raw_request_without_scenario_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            request = Path(directory) / "request.json"
            request.write_text(json.dumps(self.scenario["request"]))
            result = subprocess.run(
                ["dotnet", str(DLL), "--request", str(request), "--repeat", "2"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            rows = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row["status"], 200)
                self.assertEqual(row["response"]["action"]["type"], "cast")
            request.write_text("[]")
            invalid = subprocess.run(
                ["dotnet", str(DLL), "--request", str(request)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(invalid.returncode, 2)

    def test_area_empty_target_and_invalid_expectations(self):
        self.assertEqual(self.run_scenario({"targetIdAbsent": True}).returncode, 1)
        scenario = json.loads((ROOT / "Scenarios/area-empty-center.json").read_text())[
            0
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenario.json"

            def run(expect):
                scenario["expect"] = expect
                path.write_text(json.dumps([scenario]))
                return subprocess.run(
                    ["dotnet", str(DLL), "--dir", directory],
                    capture_output=True,
                    text=True,
                )

            self.assertEqual(
                run(
                    {"types": ["cast"], "targetCell": [1, 0, 0], "targetIdAbsent": True}
                ).returncode,
                0,
            )
            self.assertEqual(run({"targetCell": [0, 0, 0]}).returncode, 1)
            self.assertEqual(run({"targetId": 2}).returncode, 1)
            for invalid in (
                {"targetCell": [1, 0]},
                {"targetIdAbsent": False},
                {"targetIdAbsent": True, "targetId": 2},
            ):
                self.assertEqual(run(invalid).returncode, 2)

    def test_continuation_revalidated_when_movement_consumes_mp(self):
        steps = json.loads((ROOT / "Sequences/resource-revalidation.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sequence.json"

            def run():
                path.write_text(json.dumps(steps))
                return subprocess.run(
                    ["dotnet", str(DLL), "--sequence", str(path)],
                    capture_output=True,
                    text=True,
                )

            rejected = run()
            self.assertEqual(rejected.returncode, 0, rejected.stderr + rejected.stdout)
            second = json.loads(rejected.stdout.splitlines()[1])["response"]
            self.assertEqual(second["action"]["spellId"], 1)
            self.assertFalse(second["planReused"])
            steps[1]["request"]["board"]["actors"][0]["mp"] = 1
            steps[1]["expect"] = {"type": "cast", "spellId": 2, "planReused": True}
            reused = run()
            self.assertEqual(reused.returncode, 0, reused.stderr + reused.stdout)
            steps[1]["expect"]["planReused"] = False
            self.assertEqual(run().returncode, 1)
            steps[1]["expect"] = {"typo": "cast"}
            self.assertEqual(run().returncode, 2)

    def test_hazard_change_invalidates_plan_and_changes_path(self):
        steps = json.loads((ROOT / "Sequences/hazard-revalidation.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sequence.json"

            def run():
                path.write_text(json.dumps(steps))
                return subprocess.run(
                    ["dotnet", str(DLL), "--sequence", str(path)],
                    capture_output=True,
                    text=True,
                )

            passed = run()
            self.assertEqual(passed.returncode, 0, passed.stderr + passed.stdout)
            rows = [json.loads(line) for line in passed.stdout.splitlines()]
            self.assertEqual(
                [row["response"]["planReused"] for row in rows], [False, True, False]
            )
            steps[2]["expect"]["pathFirst"] = [1, 0, 0]
            self.assertEqual(run().returncode, 1)
            steps[2]["expect"]["pathFirst"] = [0, 1]
            self.assertEqual(run().returncode, 2)


if __name__ == "__main__":
    unittest.main()
