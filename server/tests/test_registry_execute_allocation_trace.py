import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import tracemalloc
import unittest


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "registry_execute_allocation_trace.py"
)
SPEC = importlib.util.spec_from_file_location("allocation_trace_candidate", SOURCE)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class Fight:
    def __init__(self, wave=1):
        self.id = 77
        self.phase = "active"
        self.rift_wave_state = {"wave": wave}


class Shared:
    def __init__(self, fight):
        self.fight = fight
        self.lock = threading.RLock()


class Registry:
    def __init__(self, shared):
        self.shared = shared

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


class AllocationTraceTests(unittest.TestCase):
    def setUp(self):
        if tracemalloc.is_tracing():
            self.skipTest("tracemalloc is already active")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fight = Fight()
        self.shared = Shared(self.fight)
        self.registry = Registry(self.shared)
        self.original = Registry.__dict__["execute"]

    def _execute(self, operation):
        return self.registry.execute(
            77, object(), 1, operation, incident_request={"opcode": 12403}
        )

    def _install(self, **kwargs):
        return PROBE.install(
            Registry,
            Fight,
            fight_id=77,
            output_path=Path(self.temp.name) / "allocation.json",
            **kwargs
        )

    def test_wave1_exception_restores_hook_and_tracing(self):
        state = self._install()
        failure = RuntimeError("fixture failure")

        def fail():
            raise failure

        with self.assertRaises(RuntimeError) as caught:
            self._execute(fail)
        self.assertIs(caught.exception, failure)
        self.assertFalse(tracemalloc.is_tracing())
        self.assertIs(Registry.__dict__["execute"], self.original)
        self.assertTrue(state["finished"])
        self.assertEqual(
            json.loads((Path(self.temp.name) / "allocation.json").read_text())[
                "status"
            ],
            "wave1_action_raised",
        )

    def test_wave1_to_wave2_samples_postcommit_fight_and_restores(self):
        state = self._install()

        def wave1():
            self.fight.rift_wave_state["wave"] = 2
            return "wave1-result"

        self.assertEqual(self._execute(wave1), "wave1-result")
        self.assertEqual(state["baseline_trace_count"] > 0, True)
        self.fight.rift_wave_state["wave"] = 2

        def wave2():
            self.fight.rift_wave_state["wave"] = 7
            return "wave2-result"

        self.assertEqual(self._execute(wave2), "wave2-result")
        self.assertFalse(tracemalloc.is_tracing())
        self.assertIs(Registry.__dict__["execute"], self.original)
        report = json.loads((Path(self.temp.name) / "allocation.json").read_text())
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["baseline_wave"], 1)
        self.assertEqual(report["sample_wave"], 2)
        self.assertEqual(report["post_operation_wave"], 7)
        self.assertTrue(report["process_global_tracemalloc"])
        self.assertTrue(report["traced_interval_excluded_from_performance_claims"])

    def test_cprofile_arms_only_after_trace_stops_and_hook_is_restored(self):
        state = self._install(
            cprofile_tool_path="unused-tool.py", arm_cprofile_after_sample=True
        )
        observed = []

        def arm(probe_state):
            observed.append((tracemalloc.is_tracing(), Registry.__dict__["execute"]))
            return True

        previous = PROBE._arm_cprofile_after_sample
        PROBE._arm_cprofile_after_sample = arm
        self.addCleanup(setattr, PROBE, "_arm_cprofile_after_sample", previous)
        self._execute(lambda: self.fight.rift_wave_state.__setitem__("wave", 2))
        self.fight.rift_wave_state["wave"] = 2
        self._execute(lambda: self.fight.rift_wave_state.__setitem__("wave", 7))
        self.assertEqual(observed, [(False, self.original)])
        arm_record = Path(self.temp.name) / "allocation-wave16-arm.json"
        self.assertEqual(json.loads(arm_record.read_text())["status"], "armed")


if __name__ == "__main__":
    unittest.main()
