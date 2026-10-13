import contextlib
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

import qualify_monster_queue_batch as runner
from monster_activation_work_queue import save, load, reusable


class QueueBatchExecutionTests(unittest.TestCase):
    def test_native_once_then_actual_checker_once_warm_context_no_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            candidate = base / "candidate"
            candidate.mkdir()
            manifest = candidate / "manifest.json"
            manifest.write_text("{}")
            native = base / "monsters.json"
            native.write_text("{}")
            validator_path = base / "validator.py"
            validator_path.write_text("# fixture")
            digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
            queue = base / "queue.json"
            save(
                queue,
                dict(
                    schema="monster-activation-work-queue-v1",
                    level_limit=50,
                    jobs=[
                        dict(
                            ref=1,
                            state="pattern_pending",
                            min_level=1,
                            max_level=1,
                            spell_ids=[7],
                            attempts=[],
                        )
                    ],
                ),
            )
            events = []
            module = ModuleType("validate_monster_spell_activation")
            module.__file__ = str(validator_path)

            def main():
                events.append("native")
                self.assertIn("--native-monsters", sys.argv)
                output = Path(sys.argv[sys.argv.index("--output") + 1])
                output.write_text(
                    json.dumps(
                        dict(
                            monsters=[
                                dict(
                                    ref=1,
                                    status="validated",
                                    pending_initialization=False,
                                    cases=[
                                        dict(
                                            level=1,
                                            spell_id=7,
                                            status="validated",
                                            successful_targets=[dict(effectful=True)],
                                        )
                                    ],
                                )
                            ],
                            runtime_code_sha256={},
                            validator_sha256=digest(validator_path),
                            native_monsters_path=str(native),
                            native_monsters_sha256=digest(native),
                            candidate_manifest_sha256=digest(manifest),
                            validator_stable=True,
                            native_monsters_stable=True,
                            elapsed_seconds=0,
                        )
                    )
                )

            def commit(row):
                events.append("ai")
                self.assertEqual(row["ref"], 1)
                return dict(
                    status="validated",
                    packets=1,
                    forecast_source_unchanged=True,
                    serializer_failure_rolled_back=True,
                    committed_state_changed=True,
                    owned_object_identities_preserved=True,
                )

            module.main = main
            module.commit_smoke = commit
            module.source_hashes = lambda: {}
            module.digest = digest
            module.case_qualification_complete = (
                lambda case: case["status"] == "validated"
            )
            offline = ModuleType("offline_monster_catalog")

            class Snapshot:
                def __init__(self, *args):
                    pass

                @contextlib.contextmanager
                def install(self):
                    events.append("install")
                    yield
                    events.append("uninstall")

                def receipt(self):
                    return {"scope": "testdouble"}

            offline.OfflineMonsterCatalog = Snapshot
            output = base / "result.json"
            argv = [
                "runner",
                "--queue",
                str(queue),
                "--candidate",
                str(candidate),
                "--asset-root",
                str(base),
                "--output",
                str(output),
                "--only-ref",
                "1",
                "--native-monsters",
                str(native),
            ]
            with patch.dict(
                sys.modules,
                {
                    "offline_monster_catalog": offline,
                    "validate_monster_spell_activation": module,
                },
            ), patch.object(sys, "argv", argv):
                runner.main()
            self.assertEqual(events, ["install", "native", "ai", "uninstall"])
            job = load(queue)["jobs"][0]
            self.assertEqual(job["state"], "execution_approved")
            self.assertTrue(reusable(job))
            result = json.loads(output.read_text())
            self.assertGreaterEqual(
                result["elapsed_seconds"], result["native_elapsed_seconds"]
            )
            self.assertTrue(Path(result["original_native_proof"]["path"]).is_file())

    def test_wrong_working_directory_rejects_before_catalog_or_execution(self):
        with patch.object(
            sys,
            "argv",
            [
                "runner",
                "--queue",
                "q",
                "--candidate",
                "c",
                "--asset-root",
                "a",
                "--output",
                "o",
                "--only-ref",
                "1",
            ],
        ), patch.object(runner.Path, "cwd", return_value=Path("/not-the-repository")):
            with self.assertRaises(SystemExit):
                runner.main()
