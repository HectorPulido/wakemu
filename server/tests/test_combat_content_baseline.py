"""Supervisor and provenance regressions; native workers are measured separately."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "combat_content_baseline",
    Path(__file__).resolve().parents[1] / "tools/combat_content_baseline.py",
)
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)


class ContentBaselineTests(unittest.TestCase):
    def test_player_observation_uses_actual_actor_fields_without_invented_wp(self):
        from wakfu_server.combat_state import Actor

        caster = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 20, 3, True)
        target = Actor(-7, 1, (1, 0, 0), 200, 6, 3, 5, 1)
        self.assertFalse(hasattr(caster, "wp"))
        result = baseline.initial_player_observation(
            SimpleNamespace(actors={7: caster, -7: target})
        )
        self.assertEqual(result["ap"], caster.ap)
        self.assertEqual(result["target_hp"], target.hp)
        self.assertEqual(result["target_position"], target.position)

    def test_nested_catalog_calls_are_counted_once(self):
        class Catalog:
            def load(self, value):
                return self.read_bytes(value)

            def read_bytes(self, value):
                return b"catalog"

            record = exists = open = read_text = read_bytes

        catalog = Catalog()
        timing = baseline.CatalogTiming(catalog)
        timing.install()
        with patch.object(baseline.time, "perf_counter", side_effect=[10.0, 10.25]):
            self.assertEqual(catalog.load("fixture"), b"catalog")
        self.assertEqual(timing.calls, 1)
        self.assertEqual(timing.elapsed, 0.25)

    def test_source_comparison_handles_native_server_relative_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            path = bundle / "player-spell.json"
            path.write_text(
                json.dumps({"source": {"files": {"wakfu_server/combat.py": "a" * 64}}})
            )
            current = {"files": {"server/wakfu_server/combat.py": "a" * 64}}
            matching = baseline.source_comparison(bundle, current)
            self.assertEqual(matching["status"], "matching")
            self.assertEqual(matching["python_status"], "unknown-legacy")
            self.assertIsNone(matching["python_matches"])
            current["files"]["server/wakfu_server/combat.py"] = "b" * 64
            report = baseline.source_comparison(bundle, current)
            self.assertEqual(report["status"], "different")
            self.assertEqual(report["mismatched_files"], 1)

    def test_interpreter_evidence_is_separate_from_source_file_equality(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.json"
            source = {
                "files": {"server/module.py": "a" * 64},
                "python": {
                    "implementation": sys.implementation.name,
                    "version": list(sys.version_info[:3]),
                },
            }
            path.write_text(json.dumps(source))
            current = {"files": source["files"]}
            matching = baseline.source_comparison(directory, current, path)
            self.assertTrue(matching["python_matches"])
            self.assertEqual(matching["python_status"], "matching")
            source["python"]["version"][1] += 1
            path.write_text(json.dumps(source))
            different = baseline.source_comparison(directory, current, path)
            self.assertEqual(different["status"], "matching")
            self.assertFalse(different["python_matches"])
            self.assertEqual(different["python_status"], "different")

    def test_source_comparison_accepts_checkout_relative_oracle_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.json"
            path.write_text(
                json.dumps({"files": {"sniffer/java/Oracle.java": "a" * 64}})
            )
            report = baseline.source_comparison(
                directory, {"files": {"sniffer/java/Oracle.java": "a" * 64}}, path
            )
            self.assertEqual(report["status"], "matching")

    def test_timeouts_and_failed_workers_cannot_become_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outcomes = [
                subprocess.TimeoutExpired("worker", 1),
                SimpleNamespace(
                    returncode=2,
                    stdout=json.dumps({"error_type": "MissingReproductionCatalog"}),
                ),
                SimpleNamespace(returncode=0, stdout="invalid output"),
            ]
            with patch.object(baseline.subprocess, "run", side_effect=outcomes) as run:
                report = baseline.supervise(
                    root,
                    root / ".runtime/results",
                    root,
                    timeout=1,
                    expected_catalog_revision="test",
                )
            self.assertFalse(report["complete"])
            self.assertFalse(report["human_authoring_time_measured"])
            self.assertEqual(
                [case["status"] for case in report["cases"]],
                ["timeout", "worker-failed", "invalid-worker-output"],
            )
            self.assertEqual(
                report["cases"][1]["error_type"], "MissingReproductionCatalog"
            )
            self.assertEqual(run.call_count, 3)
            for call in run.call_args_list:
                self.assertEqual(call.kwargs["timeout"], 1)

    def test_supervisor_requires_private_output_and_bounded_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for output, timeout in (
                (root / "public", 1),
                (root / ".runtime/private", 601),
            ):
                with self.subTest(output=output, timeout=timeout), self.assertRaises(
                    ValueError
                ):
                    baseline.supervise(
                        root,
                        output,
                        root,
                        timeout=timeout,
                        expected_catalog_revision="test",
                    )

    def test_unknown_case_fails_before_loading_engine_or_catalog(self):
        with self.assertRaisesRegex(ValueError, "Unknown fixed"):
            baseline.execute_worker("invented-attack", "missing", baseline.ROOT, "test")


if __name__ == "__main__":
    unittest.main()
