"""Recovery witness search must remain explicit in activation plans."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import automate_monster_activation as automation


class MonsterActivationRecoveryPlanTests(unittest.TestCase):
    def plan(self, recovery):
        return dict(
            automation.pipeline_commands(
                SimpleNamespace(
                    output=automation.ROOT / ".runtime" / "recovery-plan-test",
                    coverage=Path("coverage.json"),
                    bundle=Path("native-bundle"),
                    dsn="host=127.0.0.1 dbname=wakemu_runtime user=wakemu",
                    password_file=Path("password-file"),
                    registry=Path("registry.json"),
                    setters=Path("setters.json"),
                    max_level=9,
                    only_ref=[39],
                    stage=False,
                    recovery_search=recovery,
                )
            )
        )

    def test_recovery_only_changes_native_preview_search(self):
        default, recovery = self.plan(False), self.plan(True)
        self.assertNotIn("--recovery-search", default["previews"])
        self.assertIn("--recovery-search", recovery["previews"])
        for phase in default:
            if phase != "previews":
                self.assertEqual(default[phase], recovery[phase])
        self.assertNotIn("--stage", recovery["stage"])


if __name__ == "__main__":
    unittest.main()
