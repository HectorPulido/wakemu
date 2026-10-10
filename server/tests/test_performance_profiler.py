import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from wakfu_server.storage.performance_profiler import PerformanceProfiler


class PerformanceProfilerTests(unittest.TestCase):
    def test_observe_aggregates_wall_cpu_and_errors_and_reset_clears(self):
        profiler = PerformanceProfiler()
        profiler.observe("request", 0.1, 0.03)
        profiler.observe("request", 0.3, 0.07, error=True)

        snapshot = profiler.snapshot()
        self.assertEqual(len(snapshot["features"]), 1)
        feature = snapshot["features"][0]
        self.assertEqual(feature["name"], "request")
        self.assertEqual(feature["count"], 2)
        self.assertAlmostEqual(feature["total_wall_seconds"], 0.4)
        self.assertAlmostEqual(feature["total_cpu_seconds"], 0.1)
        self.assertAlmostEqual(feature["mean_wall_seconds"], 0.2)
        self.assertAlmostEqual(feature["max_wall_seconds"], 0.3)
        self.assertEqual(feature["errors"], 1)
        self.assertGreaterEqual(feature["p95_wall_seconds"], 0.1)
        self.assertEqual(snapshot["dropped_features"], 0)

        reset_snapshot = profiler.snapshot(reset=True)
        self.assertEqual(reset_snapshot["features"], snapshot["features"])
        self.assertEqual(profiler.snapshot()["features"], [])
        profiler.observe("after-reset", 0.01)
        profiler.reset()
        self.assertEqual(profiler.snapshot()["features"], [])

    def test_wait_and_cpu_coverage_exclude_observations_without_cpu_measurement(self):
        profiler = PerformanceProfiler()
        profiler.observe("mixed-work", 10.0)
        profiler.observe("mixed-work", 0.2, 0.05)
        profiler.observe("unknown-work", 3.0)

        features = {
            feature["name"]: feature for feature in profiler.snapshot()["features"]
        }
        mixed = features["mixed-work"]
        self.assertAlmostEqual(mixed["total_wall_seconds"], 10.2)
        self.assertAlmostEqual(mixed["total_cpu_seconds"], 0.05)
        self.assertEqual(mixed["cpu_measured_calls"], 1)
        self.assertAlmostEqual(mixed["known_wall_seconds"], 0.2)
        self.assertEqual(mixed["unknown_cpu_calls"], 1)
        self.assertAlmostEqual(mixed["wait_ms"], 150.0, places=5)

        unknown = features["unknown-work"]
        self.assertEqual(unknown["cpu_measured_calls"], 0)
        self.assertEqual(unknown["unknown_cpu_calls"], 1)
        self.assertEqual(unknown["wait_ms"], 0)
        self.assertEqual(unknown["cpu_coverage_percent"], 0)

        cleared = profiler.snapshot(reset=True)
        self.assertEqual(len(cleared["features"]), 2)
        self.assertEqual(profiler.snapshot()["features"], [])
        profiler.observe("mixed-work", 0.4, 0.1)
        fresh = profiler.snapshot()["features"][0]
        self.assertEqual(fresh["cpu_measured_calls"], 1)
        self.assertAlmostEqual(fresh["known_wall_seconds"], 0.4)
        self.assertEqual(fresh["unknown_cpu_calls"], 0)

    def test_span_and_profile_preserve_return_and_exception(self):
        profiler = PerformanceProfiler()
        with profiler.span("span-work"):
            time.sleep(0.005)

        @profiler.profile("decorated-work")
        def returns_value():
            return 37

        @profiler.profile("decorated-error")
        def raises_error():
            raise LookupError("original failure")

        self.assertEqual(returns_value(), 37)
        with self.assertRaisesRegex(LookupError, "original failure"):
            raises_error()

        by_name = {
            feature["name"]: feature for feature in profiler.snapshot()["features"]
        }
        self.assertEqual(by_name["span-work"]["count"], 1)
        self.assertEqual(by_name["decorated-work"]["count"], 1)
        self.assertEqual(by_name["decorated-error"]["errors"], 1)

    def test_feature_cardinality_is_bounded_under_concurrent_observation(self):
        profiler = PerformanceProfiler(max_features=8)
        errors = []

        def worker(worker_id):
            try:
                for index in range(100):
                    profiler.observe(f"worker-{worker_id}-feature-{index}", 0.001)
            except Exception as error:  # surfaced in the test thread
                errors.append(error)

        threads = [
            threading.Thread(target=worker, args=(worker_id,)) for worker_id in range(6)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(2)

        self.assertEqual(errors, [])
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertLessEqual(len(profiler.snapshot()["features"]), 8)

    def test_sampling_writes_safe_aggregate_metadata_and_stops_early(self):
        with tempfile.TemporaryDirectory() as directory:
            profiler = PerformanceProfiler()
            profiler.observe("sampled-operation", 0.02, 0.01)
            self.assertTrue(
                profiler.start_sampling(
                    duration=30, interval=0.02, output_dir=Path(directory)
                )
            )
            time.sleep(0.08)
            status = profiler.status()
            self.assertTrue(status["sampling"])
            self.assertTrue(profiler.stop_sampling())

            deadline = time.monotonic() + 2
            while profiler.status()["sampling"] and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(profiler.status()["sampling"])
            paths = list(Path(directory).iterdir())
            self.assertTrue(paths, "sampling should emit an output artifact")
            content = "\n".join(path.read_text() for path in paths if path.is_file())
            self.assertTrue(content.strip())
            self.assertNotIn("locals", content.lower())
            self.assertNotIn("local_variables", content.lower())
            self.assertNotIn("password", content.lower())

            # Sampling artifacts describe aggregate/profile metadata rather than
            # retaining application frame values or arbitrary object reprs.
            for path in paths:
                if path.suffix == ".json":
                    json.loads(path.read_text())

    def test_sampling_rejects_out_of_range_parameters(self):
        profiler = PerformanceProfiler()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                profiler.start_sampling(
                    duration=4.99, interval=0.02, output_dir=Path(directory)
                )
            with self.assertRaises(ValueError):
                profiler.start_sampling(
                    duration=5, interval=0.01, output_dir=Path(directory)
                )


if __name__ == "__main__":
    unittest.main()
