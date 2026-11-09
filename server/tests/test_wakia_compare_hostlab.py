import json
from pathlib import Path
import subprocess
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[1] / "tools/wakia_compare_hostlab.py"


class CompareHostLabTests(unittest.TestCase):
    def compare(self, baseline, current):
        with tempfile.TemporaryDirectory() as directory:
            old, new = Path(directory) / "old.jsonl", Path(directory) / "new.jsonl"
            old.write_text(baseline)
            new.write_text(current)
            return subprocess.run(
                ["python3", str(TOOL), str(old), str(new)],
                capture_output=True,
                text=True,
            )

    @staticmethod
    def row(name, action, passed=True, milliseconds=1):
        return (
            json.dumps(
                {
                    "scenario": name,
                    "passed": passed,
                    "action": action,
                    "milliseconds": {"min": milliseconds},
                }
            )
            + "\n"
        )

    def test_ignores_timings_and_compares_complete_action(self):
        baseline = self.row("test", {"type": "cast", "targetId": 1})
        unchanged = self.compare(
            baseline,
            self.row("test", {"targetId": 1, "type": "cast"}, milliseconds=800),
        )
        self.assertEqual(unchanged.returncode, 0, unchanged.stderr)
        changed = self.compare(
            baseline, self.row("test", {"type": "cast", "targetId": 2})
        )
        self.assertEqual(changed.returncode, 1, changed.stderr)
        self.assertEqual(
            json.loads(changed.stdout)["changes"][0]["change"], "outcome_changed"
        )

    def test_missing_scenarios_and_existing_failures_fail(self):
        baseline = self.row("first", None, passed=False)
        result = self.compare(baseline, baseline + self.row("second", None))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["currentFailures"], ["first"])
        self.assertEqual(
            json.loads(result.stdout)["changes"][0]["change"], "new_scenario"
        )

    def test_duplicate_scenarios_and_malformed_results_rejected(self):
        row = self.row("test", {"type": "end_turn"})
        self.assertEqual(self.compare(row + row, row).returncode, 2)
        self.assertEqual(self.compare(row, '{"scenario":"test"}\n').returncode, 2)

    def test_missing_private_path_is_not_printed(self):
        result = subprocess.run(
            ["python3", str(TOOL), "/private/secret-player-baseline", "/missing"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("secret-player-baseline", result.stderr)

    def test_identical_partial_batches_only_compare_supplied_rows(self):
        partial = self.row("one-of-many", {"type": "end_turn"})
        result = self.compare(partial, partial)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["currentScenarios"], 1)

    def test_private_request_outputs_compare_status_action_and_samples(self):
        def row(sample, status, action):
            return (
                json.dumps(
                    {"sample": sample, "status": status, "response": {"action": action}}
                )
                + "\n"
            )

        baseline = row(1, 200, {"type": "cast", "targetId": 7}) + row(
            2, 200, {"type": "end_turn"}
        )
        self.assertEqual(self.compare(baseline, baseline).returncode, 0)
        changed = self.compare(
            baseline,
            row(1, 200, {"type": "cast", "targetId": 8})
            + row(2, 200, {"type": "end_turn"}),
        )
        self.assertEqual(changed.returncode, 1)
        self.assertEqual(
            json.loads(changed.stdout)["changes"][0]["scenario"], "sample:1"
        )
        self.assertEqual(self.compare(baseline, row(1, 503, None)).returncode, 1)
        self.assertEqual(self.compare(baseline, self.row("one", None)).returncode, 2)

    def test_mixed_or_duplicate_request_samples_are_rejected(self):
        request = (
            json.dumps(
                {
                    "sample": 1,
                    "status": 200,
                    "response": {"action": {"type": "end_turn"}},
                }
            )
            + "\n"
        )
        self.assertEqual(self.compare(request + request, request).returncode, 2)
        self.assertEqual(
            self.compare(request + self.row("one", None), request).returncode, 2
        )


if __name__ == "__main__":
    unittest.main()
