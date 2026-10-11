"""Frozen evidence must survive persistence without changing native gameplay."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from normalize_dungeon_configuration_evidence import normalize_configuration
from wakfu_server.dungeon_runtime_config import canonical_hash


class DungeonEvidenceNormalizationTests(unittest.TestCase):
    def test_normalizes_both_affected_routes_without_gameplay_changes(self):
        for identity in (141, 136):
            with self.subTest(identity=identity):
                path = Path(
                    f".runtime/local/hybrid-native-full-room-v7-20261010/native_dungeon_{identity}.json"
                )
                if not path.exists():
                    self.skipTest("Read-only native candidate fixtures unavailable")
                source = json.loads(path.read_text())
                before = copy.deepcopy(source)
                result = normalize_configuration(source, version=15)
                self.assertEqual(source, before)
                self.assertEqual(result["version"], 15)
                for field in ("compiled_plan", "topology", "route", "level_policy"):
                    self.assertEqual(result[field], source[field])
                persisted = json.loads(json.dumps(result))
                for key, field in (
                    ("plan", "compiled_plan"),
                    ("topology", "topology"),
                    ("route", "route"),
                ):
                    self.assertEqual(
                        canonical_hash(persisted[field]),
                        persisted["evidence_hashes"][key],
                    )
                self.assertEqual(canonical_hash(persisted), canonical_hash(result))
                result["topology"]["rooms"][0]["anchor"][0] += 1
                self.assertEqual(source, before)


if __name__ == "__main__":
    unittest.main()
