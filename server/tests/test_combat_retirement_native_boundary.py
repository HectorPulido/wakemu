"""Independent original cvK/state2 fixture binding; rendering remains unmodeled."""
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(
    os.environ.get("WAKFU_RETIREMENT_NATIVE_PROOF"),
    "original native retirement proof required",
)
class NativeRetirementBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof_path = Path(os.environ["WAKFU_RETIREMENT_NATIVE_PROOF"])
        cls.output = cls.proof_path.parent
        cls.proof = json.loads(cls.proof_path.read_text())
        cls.observations = json.loads((cls.output / "observations.json").read_text())

    def sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_native_fixture_provenance_matches_current_sources_and_installed_jar(self):
        self.assertTrue(self.proof["complete"])
        self.assertEqual(
            (self.proof["compile_returncode"], self.proof["returncode"]), (0, 0)
        )
        self.assertTrue(self.proof["source_stable"])
        self.assertEqual(self.proof["instrumentation"], "none")
        for path, expected in self.proof["source"].items():
            self.assertEqual(self.sha(ROOT / path), expected, path)
        self.assertEqual(
            self.sha(ROOT / "client/lib/wakfu-client.jar"),
            self.proof["classpath"]["client/lib/wakfu-client.jar"],
        )
        self.assertEqual(
            self.sha(self.output / "observations.json"),
            self.proof["observations_sha256"],
        )
        self.assertEqual(
            self.sha(self.output / "native-retirement-bytecode.txt"),
            self.proof["bytecode_sha256"],
        )
        self.assertEqual(
            self.sha(ROOT / "server/tools/verify_combat_retirement_native.py"),
            self.proof["runner_sha256"],
        )

    def test_independent_cvK_fields_preserve_status_without_assuming_entity_removal(
        self,
    ):
        for state in (0, 1, 2, 3, 7):
            with self.subTest(state=state):
                path = self.output / f"12727-state{state}.bin"
                self.assertEqual(self.sha(path), self.proof["fixtures"][path.name])
                fight, action, extra, actor, status = struct.unpack(
                    ">iiiqb", path.read_bytes()
                )
                self.assertEqual(
                    (fight, action, extra, actor, status), (99, 7, -1, 901, state)
                )
        self.assertIn("states1/3 and unknown statuses", self.observations["excluded"])

    def test_completed_state2_removes_physical_registration_but_retains_roster(self):
        observation = self.observations
        self.assertEqual(
            observation["prerequisite"],
            "actual fdt OFF_PLAY, registered QI and prior native fem.eT removal",
        )
        self.assertTrue(observation["before_completion_physical_registered"])
        self.assertTrue(observation["state2_completed"])
        self.assertTrue(observation["after_completion_out_of_play"])
        self.assertTrue(observation["after_completion_roster_retained"])
        self.assertFalse(observation["after_completion_physical_registered"])
        self.assertTrue(observation["after_completion_queue_empty"])
        self.assertTrue(observation["timeline_execution_active"])
        self.assertTrue(observation["initial_timeline_registered"])
        self.assertFalse(observation["before_completion_timeline_registered"])
        self.assertTrue(observation["before_completion_removed_timeline_record"])
        self.assertFalse(observation["after_completion_timeline_registered"])
        self.assertFalse(observation["after_completion_removed_timeline_record"])
        self.assertTrue(observation["completion_callback_successful"])
        self.assertTrue(observation["deliberate_failed_callback_detected"])
        self.assertIn("timeline removal timing", observation["excluded"])
        self.assertIn("aTS.cby animation and scheduler timing", observation["excluded"])

    def test_truncated_fixture_is_rejected_by_independent_layout(self):
        body = (self.output / "12727-state2.bin").read_bytes()
        for malformed in (body[:-1], body + b"\x00"):
            with self.subTest(length=len(malformed)), self.assertRaises(struct.error):
                struct.unpack(">iiiqb", malformed)
