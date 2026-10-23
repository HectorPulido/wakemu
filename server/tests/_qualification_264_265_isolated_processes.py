"""Run focused isolated contracts without loading new combat code into paid Nox."""
import os, subprocess, sys, tempfile, unittest
from pathlib import Path

BASE = Path(
    ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components"
)


class Focused264(unittest.TestCase):
    def runTest(self):
        names = [
            "test_rushu_npc_start_binding.RushuNpcStartBindingTests",
            "test_rushu_npc_start_binding.RushuNpcStartReplayHookTests",
            "test_ordinary_encounter_policy_admission.OrdinaryEncounterPolicyAdmissionTests.test_prepare_scene_binds_ordinary_ombrage_policy_and_pins_absence_on_retry",
            "test_encounter_area_callback_programs.EncounterAreaCallbackProgramTests",
            "test_combat_encounter_area_callback_source.EncounterAreaCallbackSourceTests",
            "test_combat_encounter_area_seed_removal_selection.SeedRemovalSelectionTests",
        ]
        with tempfile.TemporaryDirectory(prefix="wakemu-focused264-") as folder:
            for source in Path("server/migrations").glob("*.sql"):
                if int(source.name.split("_", 1)[0]) <= 264:
                    Path(folder, source.name).symlink_to(source.resolve())
            env = dict(
                os.environ,
                PYTHONPATH="server:server/tests",
                WAKFU_MIGRATIONS_TEST_DIR=folder,
            )
            child = subprocess.run(
                [sys.executable, "-m", "unittest", "-v", *names],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=180,
            )
            BASE.joinpath("rushu264-twelve-isolated-child.log").write_text(child.stdout)
            self.assertEqual(child.returncode, 0, child.stdout[-12000:])


class Focused265(unittest.TestCase):
    def runTest(self):
        env = dict(os.environ, PYTHONPATH="server:server/tests")
        child = subprocess.run(
            [sys.executable, ".runtime/chest-activation-265/run_bulk_tests.py"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
        )
        BASE.joinpath("chest265-single-bulk-isolated-child.log").write_text(
            child.stdout
        )
        self.assertEqual(child.returncode, 0, child.stdout[-12000:])


def qualify264():
    return unittest.TestSuite([Focused264()])


def qualify265():
    return unittest.TestSuite([Focused265()])
