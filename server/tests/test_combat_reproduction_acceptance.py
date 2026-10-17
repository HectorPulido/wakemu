"""Exercise acceptance against real bounded stub subprocesses, without engine."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "combat_reproduction_acceptance",
    Path(__file__).resolve().parents[1] / "tools/combat_reproduction_acceptance.py",
)
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)

STUB = """import argparse, json, os, pathlib, sys, time
p=argparse.ArgumentParser()
p.add_argument("command")
p.add_argument("--bundle", type=pathlib.Path)
p.add_argument("--case")
p.add_argument("--output", type=pathlib.Path)
p.add_argument("--allow-source-drift", action="store_true")
a=p.parse_args()
if json.loads((a.bundle/"catalog.json").read_text())["version"] == -1:
    print("Unsupported catalog provenance/version", file=sys.stderr)
    sys.exit(2)
r={"status":"accepted", "matches":True, "catalog_matches":True,
   "source_matches":True, "result_sha256":"a"*64,
   "source_sha256":"b"*64, "catalog_revision":"c"*64}
if a.case == "environment.json":
    forbidden=any(k.startswith(("WAKFU_DATABASE","WAKFU_REDIS","WAKFU_CATALOG","PG")) or k in ("DATABASE_URL","REDIS_URL") for k in os.environ)
    r["matches"]=not forbidden and os.environ.get("PYTHONPATH")==str(pathlib.Path.cwd()/"server")
if a.case == "missing.json":
    print(json.dumps(r), flush=True)
    sys.exit(0)
if a.case == "printed.json":
    print(json.dumps(r), flush=True)
    a.output.write_text("{}")
    sys.exit(0)
if a.case == "repeat-different.json" and a.output.name.startswith("repeat"):
    r["result_sha256"]="d"*64
a.output.write_text(json.dumps(r))
print(json.dumps(r), flush=True)
if a.case == "hang.json":
    time.sleep(30)
if a.case == "nonzero.json":
    sys.exit(1)
"""


class ReproductionAcceptanceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        script = self.root / "server/tools/combat_reproduce.py"
        script.parent.mkdir(parents=True)
        script.write_text(STUB)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        (self.bundle / "catalog.json").write_text(json.dumps({"version": 1}))

    def accept(self, cases, name="result", **kwargs):
        return acceptance.accept(
            self.bundle,
            cases,
            self.root / ".runtime" / name,
            root=self.root,
            timeout=kwargs.pop("timeout", 5),
            **kwargs
        )

    def test_real_exit_repeat_and_manifest_tamper_are_verified(self):
        original = (self.bundle / "catalog.json").read_bytes()
        report = self.accept(["normal.json"], repeat_case="normal.json", tamper=True)
        self.assertTrue(report["complete"])
        self.assertTrue(report["repeat"]["identical_hash"])
        self.assertTrue(report["tamper"]["tamper_rejected"])
        self.assertEqual(report["python"]["version"], list(sys.version_info[:3]))
        self.assertEqual(
            report["python"]["executable"], str(Path(sys.executable).resolve())
        )
        for case in report["cases"]:
            self.assertEqual(case["launcher_python"], report["python"])
        self.assertEqual((self.bundle / "catalog.json").read_bytes(), original)
        output = self.root / ".runtime/result"
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
        for path in output.iterdir():
            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_printed_or_written_match_before_timeout_is_not_success(self):
        report = self.accept(["hang.json"], timeout=1)
        self.assertFalse(report["complete"])
        self.assertEqual(report["cases"][0]["status"], "timeout")
        self.assertTrue(report["cases"][0]["matches"])
        self.assertIsNone(report["cases"][0]["returncode"])

    def test_printed_match_nonzero_exit_and_missing_result_cannot_pass(self):
        report = self.accept(["printed.json", "nonzero.json", "missing.json"])
        self.assertFalse(report["complete"])
        self.assertEqual(
            [case["status"] for case in report["cases"]],
            ["result-mismatch", "nonzero-exit", "missing-or-invalid-result"],
        )
        self.assertTrue(report["cases"][1]["matches"])

    def test_changed_repeat_hash_fails_acceptance(self):
        report = self.accept(
            ["repeat-different.json"], repeat_case="repeat-different.json"
        )
        self.assertTrue(report["cases"][0]["passed"])
        self.assertTrue(report["repeat"]["passed"])
        self.assertFalse(report["repeat"]["identical_hash"])
        self.assertFalse(report["complete"])

    def test_backend_and_catalog_environment_is_removed_without_logging_values(self):
        private_values = {
            key: "private-test-value"
            for key in (
                "WAKFU_DATABASE_URL",
                "WAKFU_DATABASE_PASSWORD_FILE",
                "WAKFU_REDIS_URL",
                "WAKFU_CATALOG_REVISION",
                "DATABASE_URL",
                "REDIS_URL",
                "PGPASSWORD",
            )
        }
        with patch.dict(os.environ, private_values):
            report = self.accept(["environment.json"])
        self.assertTrue(report["complete"])
        output = self.root / ".runtime/result"
        for path in output.iterdir():
            self.assertNotIn("private-test-value", path.read_text())

    def test_invalid_case_repeat_output_and_timeout_are_rejected(self):
        for cases, kwargs in (
            (["../escape.json"], {}),
            (["normal.json"], {"repeat_case": "other.json"}),
            (["normal.json"], {"timeout": 601}),
            (["normal.json", "normal.json"], {}),
        ):
            with self.subTest(cases=cases, kwargs=kwargs), self.assertRaises(
                ValueError
            ):
                self.accept(cases, **kwargs)
        with self.assertRaises(ValueError):
            acceptance.accept(
                self.bundle, ["normal.json"], self.root / "public", root=self.root
            )


if __name__ == "__main__":
    unittest.main()
