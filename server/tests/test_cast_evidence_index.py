import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "cast_index",
    Path(__file__).resolve().parents[1] / "tools/build_cast_evidence_index.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CastEvidenceIndexTests(unittest.TestCase):
    def test_critical_observation_does_not_replace_normal_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for critical, stamp in ((False, "01"), (True, "02")):
                (root / ("active-" + stamp + ".json")).write_text(
                    json.dumps(
                        dict(
                            generated_at=f"2026-10-04T{stamp}:00:00+00:00",
                            sources_stable=True,
                            rows=[
                                dict(
                                    spell_id=5033,
                                    level=20,
                                    variant="self",
                                    status="actor_state_changed",
                                    critical=critical,
                                )
                            ],
                        )
                    )
                )
            rows, excluded = module.collect(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["critical"] for row in rows}, {False, True})
            self.assertFalse(excluded)

    def test_new_unstable_or_undated_report_never_replaces_stable_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, stamp, stable, status in (
                ("old", "2026-10-04T01:00:00+00:00", True, "cast_rejected"),
                ("new", "2026-10-04T02:00:00+00:00", True, "actor_state_changed"),
                ("unstable", "2026-10-04T03:00:00+00:00", False, "cast_rejected"),
                ("undated", None, True, "cast_rejected"),
            ):
                (root / ("active-" + filename + ".json")).write_text(
                    json.dumps(
                        dict(
                            generated_at=stamp,
                            sources_stable=stable,
                            rows=[
                                dict(
                                    spell_id=5033,
                                    level=20,
                                    variant="self",
                                    status=status,
                                    gameplay_verified=True,
                                )
                            ],
                        )
                    )
                )
            rows, excluded = module.collect(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["report"], "active-new.json")
            self.assertFalse(rows[0]["client_verified"])
            self.assertFalse(rows[0]["current_source_revalidated"])
            self.assertEqual(
                set(excluded), {"active-unstable.json", "active-undated.json"}
            )
