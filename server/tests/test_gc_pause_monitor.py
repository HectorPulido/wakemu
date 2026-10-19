"""GC callbacks record bounded facts without calling lock-taking diagnostics."""
import gc
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from wakfu_server.storage.gc_pause_monitor import GCPauseMonitor
from wakfu_server.storage.performance_monitor import write_report


class GCPauseMonitorTests(unittest.TestCase):
    def test_callback_records_timing_but_observes_only_during_drain(self):
        wall, cpu = iter((10.0, 10.25)), iter((5.0, 5.1))
        callbacks = []
        monitor = GCPauseMonitor(
            callbacks=callbacks,
            wall_clock=lambda: next(wall),
            cpu_clock=lambda: next(cpu),
        )
        profiler = Mock()
        monitor.install()
        monitor.callback("start", {"generation": 1})
        monitor.callback("stop", {"generation": 1, "collected": 42})
        profiler.observe.assert_not_called()
        monitor.drain(profiler)
        label, elapsed, cpu_elapsed = profiler.observe.call_args.args
        self.assertEqual(label, "diagnostics.gc.gen1")
        self.assertAlmostEqual(elapsed, 0.25)
        self.assertAlmostEqual(cpu_elapsed, 0.1)
        monitor.drain(profiler)
        self.assertEqual(profiler.observe.call_count, 1)

    def test_queue_capacity_idempotent_install_and_safe_uninstall(self):
        callbacks = []
        clock = iter(range(100))
        monitor = GCPauseMonitor(
            capacity=2,
            callbacks=callbacks,
            wall_clock=lambda: next(clock),
            cpu_clock=lambda: 0,
        )
        self.assertIs(monitor.install().install(), monitor)
        self.assertEqual(callbacks, [monitor.callback])
        for generation in (0, 1, 2):
            monitor.callback("start", {"generation": generation})
            monitor.callback("stop", {"generation": generation})
        self.assertEqual([record[0] for record in monitor.records], [1, 2])
        monitor.uninstall()
        monitor.uninstall()
        self.assertEqual(callbacks, [])
        self.assertEqual(monitor.starts, {})

    def test_real_collection_callback_is_deferred_and_generation_labeled(self):
        monitor = GCPauseMonitor()
        profiler = Mock()
        try:
            monitor.install()
            gc.collect(2)
            profiler.observe.assert_not_called()
            self.assertTrue(any(record[0] == 2 for record in monitor.records))
            monitor.drain(profiler)
            self.assertIn(
                "diagnostics.gc.gen2",
                [call.args[0] for call in profiler.observe.call_args_list],
            )
        finally:
            monitor.uninstall()
        self.assertNotIn(monitor.callback, gc.callbacks)

    def test_bad_phases_missing_starts_and_faulty_clocks_do_not_escape(self):
        monitor = GCPauseMonitor(callbacks=[], wall_clock=lambda: 1 / 0)
        monitor.callback("stop", {"generation": 0})
        monitor.callback("start", {"generation": 0})
        monitor.callback("start", {"generation": 100})
        monitor.callback("other", {"generation": 0})
        self.assertEqual(list(monitor.records), [])

    def test_long_generation_two_pause_survives_short_collection_queue_overflow(self):
        clock = iter((0, 25, 26, 26.01, 27, 27.01, 28, 28.01))
        monitor = GCPauseMonitor(
            capacity=2,
            callbacks=[],
            wall_clock=lambda: next(clock),
            cpu_clock=lambda: 0,
        )
        for generation in (2, 0, 0, 0):
            monitor.callback("start", {"generation": generation})
            monitor.callback("stop", {"generation": generation})
        self.assertEqual(len(monitor.records), 2)
        self.assertEqual(len(monitor.longest), 2)
        profiler = Mock()
        profiler.observe.assert_not_called()
        monitor.drain(profiler)
        pauses = [call.args for call in profiler.observe.call_args_list]
        self.assertEqual(pauses.count(("diagnostics.gc.gen2", 25, 0)), 1)
        count = profiler.observe.call_count
        monitor.drain(profiler)
        self.assertEqual(profiler.observe.call_count, count)

    def test_timestamped_history_is_bounded_and_survives_drains(self):
        wall = itertools.count(0.0)
        cpu = itertools.count(10.0)
        utc = itertools.count(1_800_000_000.0)
        monitor = GCPauseMonitor(
            capacity=2,
            callbacks=[],
            wall_clock=lambda: next(wall),
            cpu_clock=lambda: next(cpu),
            utc_clock=lambda: next(utc),
        )
        profiler = Mock()
        for index in range(monitor.history.maxlen + 3):
            monitor.callback("start", {"generation": 2})
            monitor.callback("stop", {"generation": 2})
            if index % 4 == 3:
                monitor.drain(profiler)

        history = monitor.history_snapshot()
        self.assertEqual(len(history), monitor.history.maxlen)
        self.assertEqual(history[0]["generation"], 2)
        self.assertEqual(history[0]["started_at_utc_epoch_seconds"], 1_800_000_006.0)
        self.assertEqual(history[0]["ended_at_utc_epoch_seconds"], 1_800_000_007.0)
        self.assertEqual(history[-1]["started_at_utc_epoch_seconds"], 1_800_000_068.0)
        self.assertEqual(history[-1]["ended_at_utc_epoch_seconds"], 1_800_000_069.0)
        self.assertEqual(history[-1]["duration_seconds"], 1.0)
        self.assertEqual(history[-1]["thread_cpu_seconds"], 1.0)
        self.assertGreaterEqual(profiler.observe.call_count, 1)

    def test_timestamped_history_is_included_in_atomic_performance_report(self):
        utc = iter((1_800_000_100.0, 1_800_000_100.5))
        wall = iter((3.0, 3.25))
        cpu = iter((7.0, 7.1))
        monitor = GCPauseMonitor(
            callbacks=[],
            wall_clock=lambda: next(wall),
            cpu_clock=lambda: next(cpu),
            utc_clock=lambda: next(utc),
        )
        monitor.callback("start", {"generation": 1})
        monitor.callback("stop", {"generation": 1})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "performance.json"
            write_report(
                Mock(snapshot=lambda: {"features": []}), path, gc_monitor=monitor
            )
            payload = json.loads(path.read_text())
        history = payload["gc_pause_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["generation"], 1)
        self.assertEqual(history[0]["started_at_utc_epoch_seconds"], 1_800_000_100.0)
        self.assertEqual(history[0]["ended_at_utc_epoch_seconds"], 1_800_000_100.5)
        self.assertAlmostEqual(history[0]["duration_seconds"], 0.25)
        self.assertAlmostEqual(history[0]["thread_cpu_seconds"], 0.1)


if __name__ == "__main__":
    unittest.main()
