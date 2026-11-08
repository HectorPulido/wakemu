import json
from pathlib import Path
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

import importlib.util

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "registry_execute_allocation_trace.py"
)
SPEC = importlib.util.spec_from_file_location("allocation_trace_boundaries", SOURCE)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class Fight:
    def __init__(self):
        self.id = 77
        self.phase = "active"
        self.rift_wave_state = {"wave": 1}


class Shared:
    def __init__(self, fight):
        self.fight = fight
        self.lock = __import__("threading").RLock()


class Registry:
    def __init__(self, fight):
        self.shared = Shared(fight)

    def lookup(self, fight_id):
        assert fight_id == 77
        return self.shared

    def execute(
        self,
        fight_id,
        session,
        actor_id,
        operation,
        *,
        expected_sequence=None,
        require_turn=True,
        incident_request=None
    ):
        return operation()


class TimerStub:
    def __init__(self, interval, function, args=(), kwargs=None):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs or {}
        self.daemon = False
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


class AllocationTraceBoundaryTests(unittest.TestCase):
    def setUp(self):
        if tracemalloc.is_tracing():
            self.skipTest("tracemalloc is already active")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def make_registry(self):
        return Registry(Fight())

    def execute(self, registry, operation):
        return registry.execute(
            77, object(), 1, operation, incident_request={"opcode": 12403}
        )

    def install(self, registry, name):
        return probe.install(
            Registry,
            Fight,
            fight_id=77,
            output_path=Path(self.temp.name) / name,
        )

    def test_snapshot_failure_existing_tracer_and_timeout_restore(self):
        original = Registry.__dict__["execute"]

        # A failure after the successful action must fail open while stopping
        # tracing and restoring the class method.
        registry = self.make_registry()
        state = self.install(registry, "snapshot-failure.json")
        real_snapshot = tracemalloc.take_snapshot
        calls = []

        def fail_post_action_snapshot():
            calls.append(None)
            if len(calls) == 2:
                raise RuntimeError("snapshot failure")
            return real_snapshot()

        sentinel = object()
        with patch.object(
            probe.tracemalloc, "take_snapshot", side_effect=fail_post_action_snapshot
        ):
            result = self.execute(
                registry,
                lambda: registry.shared.fight.rift_wave_state.__setitem__("wave", 2)
                or sentinel,
            )
        report = json.loads(
            (Path(self.temp.name) / "snapshot-failure.json").read_text()
        )
        self.assertIs(result, sentinel)
        self.assertEqual(report["status"], "baseline_failed")
        self.assertFalse(tracemalloc.is_tracing())
        self.assertTrue(state["finished"])
        self.assertIs(Registry.__dict__["execute"], original)

        # If another tool already owns tracemalloc, the probe must leave that
        # session and its Registry method untouched.
        registry = self.make_registry()
        state = self.install(registry, "existing-tracer.json")
        tracemalloc.start(1)
        try:
            marker = object()
            result = self.execute(
                registry,
                lambda: registry.shared.fight.rift_wave_state.__setitem__("wave", 2)
                or marker,
            )
            self.assertIs(result, marker)
            self.assertTrue(tracemalloc.is_tracing())
            self.assertIs(Registry.__dict__["execute"], original)
            self.assertTrue(state["finished"])
            self.assertFalse((Path(self.temp.name) / "existing-tracer.json").exists())
        finally:
            tracemalloc.stop()

        # Drive the timeout callback synchronously with a fake timer so the
        # cleanup path is deterministic and does not wait 30 minutes.
        registry = self.make_registry()
        state = self.install(registry, "timeout.json")
        with patch.object(probe.threading, "Timer", TimerStub):
            marker = object()
            result = self.execute(
                registry,
                lambda: registry.shared.fight.rift_wave_state.__setitem__("wave", 2)
                or marker,
            )
            timer = state["timer"]
            self.assertIs(result, marker)
            self.assertTrue(tracemalloc.is_tracing())
            self.assertTrue(timer.started)
            self.assertIsNot(Registry.__dict__["execute"], original)
            timer.function(*timer.args, **timer.kwargs)
        report = json.loads((Path(self.temp.name) / "timeout.json").read_text())
        self.assertEqual(report["status"], "timeout_before_sample")
        self.assertFalse(tracemalloc.is_tracing())
        self.assertTrue(timer.cancelled)
        self.assertTrue(state["finished"])
        self.assertIs(Registry.__dict__["execute"], original)


if __name__ == "__main__":
    unittest.main()
