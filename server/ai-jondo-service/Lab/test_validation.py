"""Focused checks for ordered multi-action assertions."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "WakIA.Lab.csproj"
DLL = ROOT / "bin/Release/net8.0/WakIA.Lab.dll"


class ActionPrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.scenario = next(
            x
            for x in json.loads((ROOT / "Scenarios/basic.json").read_text())
            if x["name"] == "ap-preparation"
        )

    def run_with_prefix(self, prefix):
        scenario = dict(self.scenario, expect={"actionPrefix": prefix})
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "case.json").write_text(json.dumps([scenario]))
            return subprocess.run(
                [
                    "dotnet",
                    str(DLL),
                    "--dir",
                    directory,
                    "--repeat",
                    "1",
                    "--warmup",
                    "0",
                ],
                capture_output=True,
                text=True,
            )

    def test_boost_must_precede_attack(self):
        buff = {"actor": 1, "spell": 3, "target": 1}
        attack = {"actor": 1, "spell": 4, "target": 2}
        self.assertEqual(self.run_with_prefix([buff, attack]).returncode, 0)
        self.assertEqual(self.run_with_prefix([attack, buff]).returncode, 1)
        self.assertEqual(
            self.run_with_prefix([buff, attack, attack, attack]).returncode, 1
        )

    def test_rejects_empty_and_unknown_action_references(self):
        for prefix in ([], [{"actor": 99, "spell": 3}], [{"actor": 1, "spell": 99}]):
            with self.subTest(prefix=prefix):
                self.assertEqual(self.run_with_prefix(prefix).returncode, 2)

    def test_reported_jalato_route_patterns(self):
        source = ROOT / "Scenarios/jalato-movement.json"
        scenarios = json.loads(source.read_text())
        expected = {
            "reported-jalato-shortest-route-when-viable": [0, 1],
            "reported-jalato-follows-viable-detour-when-short-route-is-absent": [
                0,
                3,
                4,
                5,
            ],
            "reported-jalato-spends-three-mp-approaching-a-distant-target": [
                0,
                1,
                2,
                3,
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "jalato-movement.json").write_text(json.dumps(scenarios))
            result = subprocess.run(
                [
                    "dotnet",
                    str(DLL),
                    "--dir",
                    directory,
                    "--category",
                    "movement",
                    "--repeat",
                    "1",
                    "--warmup",
                    "0",
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual({row["scenario"] for row in rows}, set(expected))
        for row in rows:
            self.assertTrue(row["passed"], row)
            self.assertEqual(
                row["actions"][0]["path"][: len(expected[row["scenario"]])],
                expected[row["scenario"]],
            )


if __name__ == "__main__":
    unittest.main()
