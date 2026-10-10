"""AST projections for entrance-only native mission override resources."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.build_dungeon_entry_overrides import build, projected_criterion


ROOT = Path(__file__).resolve().parents[2]
NATIVE_TRUE = "(IsNeoServer() or not IsNeoServer())"


def inventory(*routes):
    return {"records": [{"native_entry_routes": list(routes)}]}


def route(destination, criterion):
    return {"destination_id": destination, "criterion": criterion}


class DungeonEntryOverrideProjectionTests(unittest.TestCase):
    def test_positive_and_negated_mission_only_expressions_become_true(self):
        for expression in (
            "IsAchievementComplete(100)",
            "not IsAchievementRunning(100)",
            "not (IsAchievementRunning(100) and "
            "IsAchievementObjectiveComplete(101) and "
            "not IsAchievementObjectiveComplete(102))",
            "HasState(103)",
        ):
            with self.subTest(expression=expression):
                self.assertEqual(projected_criterion(expression), NATIVE_TRUE)

    def test_nonmission_requirements_survive_and_or_projections(self):
        self.assertIn(
            "GetRealLevel() >= 50",
            projected_criterion("IsAchievementComplete(100) and GetRealLevel() >= 50"),
        )
        self.assertIn(
            "IsNeoServer()",
            projected_criterion("IsNeoServer() and not IsAchievementComplete(100)"),
        )
        self.assertIn(
            'GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 8',
            projected_criterion(
                'IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 8 '
                "and not IsAchievementComplete(100)"
            ),
        )
        self.assertEqual(
            projected_criterion("IsAchievementComplete(100) or GetRealLevel() >= 50"),
            NATIVE_TRUE,
        )

    def test_only_mission_state_predicates_are_projected(self):
        with self.assertRaisesRegex(ValueError, "Malformed mission prerequisite"):
            projected_criterion("IsAchievementComplete(0)")
        with self.assertRaisesRegex(ValueError, "Malformed mission prerequisite"):
            projected_criterion("HasState(true)")

    def test_build_uses_native_entry_routes_and_rejects_conflicting_destinations(self):
        result = build(
            inventory(
                route(4689, "IsAchievementComplete(100)"),
                route(200, "GetRealLevel() >= 50"),
            )
        )
        self.assertEqual(result, {4689: NATIVE_TRUE})
        with self.assertRaisesRegex(ValueError, "Conflicting native destination"):
            build(
                inventory(
                    route(4689, "IsAchievementComplete(100)"),
                    route(4689, "IsAchievementComplete(101) and GetRealLevel() >= 50"),
                )
            )

    def test_generated_resource_is_version_bound_and_contains_five_native_entries(self):
        rows = build(
            json.loads((ROOT / "docs/reports/dungeons/inventory.json").read_text())
        )
        self.assertEqual(set(rows), {720, 4578, 4689, 4714, 4751})
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "overrides.properties"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "server/tools/build_dungeon_entry_overrides.py"),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            content = output.read_text()
        digest = hashlib.sha256(
            (ROOT / "client/lib/wakfu-client.jar").read_bytes()
        ).hexdigest()
        self.assertIn("native_sha256=" + digest, content)
        for identity in rows:
            self.assertRegex(content, rf"(?m)^{identity}=.+$")
        self.assertNotIn("26873=", content)  # Internal Tofu door is not an entrance.

    def test_cli_rejects_stale_source_pin_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            native_jar = root / "client.jar"
            native_jar.write_bytes(b"test native client")
            digest = hashlib.sha256(native_jar.read_bytes()).hexdigest()
            inventory_path = root / "inventory.json"
            inventory_path.write_text(
                json.dumps({"live_catalog_release": "release-b", "records": []})
            )
            pin_path = root / "source-version.json"
            pin_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "native_client_sha256": digest,
                        "native_catalog_release": "release-a",
                    }
                )
            )
            output = root / "overrides.properties"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "server/tools/build_dungeon_entry_overrides.py"),
                    "--inventory",
                    str(inventory_path),
                    "--client-jar",
                    str(native_jar),
                    "--source-version",
                    str(pin_path),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("version mismatch", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
