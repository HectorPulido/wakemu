"""Bounded additive public eYk release reconstruction; no DB or client reads."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class RiftCellGroupPublicPackTests(unittest.TestCase):
    def test_original_rows_getters_release_roles_and_cli_idempotence(self):
        from tools.stage_rift_cell_group_catalog import DOCUMENT, encoded

        root = Path(__file__).resolve().parents[1] / "data" / "installation"
        proof_path = root.parent / "native-rift-cell-groups-v1.json"
        proof = json.loads(proof_path.read_bytes())
        public = json.loads((root / "manifest.json").read_bytes())
        baseline_raw = (root / "catalogs/manifest.json").read_bytes()
        baseline = json.loads(baseline_raw)
        historical_raw = (
            root / "catalogs/manifest-rift-cell-groups-v1.json"
        ).read_bytes()
        historical = json.loads(historical_raw)
        historical_active = next(
            row
            for row in historical["releases"]
            if row["revision"] == historical["active_revision"]
        )
        before = next(
            row
            for row in baseline["releases"]
            if row["revision"] == baseline["active_revision"]
        )
        document = next(row for row in before["documents"] if row["path"] == DOCUMENT)
        self.assertEqual(document["sha256"], proof["source_document_sha256"])
        self.assertEqual(proof["exported_references"], [315439, 315771, 315773, 315775])
        self.assertTrue(proof["original_inputs_stable"])
        self.assertEqual(proof["getter"], "bcA.dcX().AH(reference).fKT()!=null")
        with tempfile.TemporaryDirectory(prefix="rift-public-metadata-") as directory:
            target = Path(directory)
            (target / "catalogs").mkdir()
            (target / "catalogs/manifest.json").write_bytes(baseline_raw)
            original_raw = bytearray()
            for part in baseline["blobs"][document["sha256"]]["parts"]:
                src = root / "catalogs" / part["path"]
                dst = target / "catalogs" / part["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                compressed = dst.read_bytes()
                self.assertEqual(
                    hashlib.sha256(compressed).hexdigest(), part["compressed_sha256"]
                )
                original_raw.extend(gzip.decompress(compressed))
            original = json.loads(original_raw)
            self.assertEqual(len(original["effects"]), 1029)
            old_top = deepcopy(public)
            old_top["artifacts"]["native-catalogs"].update(
                path="catalogs/manifest.json",
                sha256=hashlib.sha256(baseline_raw).hexdigest(),
                size=len(baseline_raw),
            )
            old_top["catalogs"]["active_revision"] = baseline["active_revision"]
            for row in old_top["catalogs"]["releases"]:
                if row["revision"] == public["catalogs"]["active_revision"]:
                    row.update(
                        revision=baseline["active_revision"],
                        source_bytes=before["source_bytes"],
                        document_count=before["document_count"],
                    )
            (target / "manifest.json").write_bytes(encoded(old_top))
            command = [
                sys.executable,
                "-S",
                "-m",
                "tools.stage_rift_cell_group_catalog",
                "--pack",
                str(target),
                "--proof",
                str(proof_path),
            ]
            first = subprocess.run(command, capture_output=True, text=True, check=True)
            receipt = json.loads(first.stdout)
            self.assertFalse(receipt["activated"])
            self.assertEqual(
                (receipt["original_rows"], receipt["candidate_rows"]), (1029, 1033)
            )
            self.assertEqual(receipt["added_references"], proof["exported_references"])
            result_top = (target / "manifest.json").read_bytes()
            expected_top = deepcopy(old_top)
            expected_top["artifacts"]["native-catalogs"].update(
                path="catalogs/manifest-rift-cell-groups-v1.json",
                sha256=hashlib.sha256(historical_raw).hexdigest(),
                size=len(historical_raw),
            )
            expected_top["catalogs"]["active_revision"] = historical["active_revision"]
            for release in expected_top["catalogs"]["releases"]:
                if release["revision"] == baseline["active_revision"]:
                    release.update(
                        revision=historical["active_revision"],
                        document_count=historical_active["document_count"],
                        source_bytes=historical_active["source_bytes"],
                    )
            self.assertEqual(json.loads(result_top), expected_top)
            candidate_raw = (target / receipt["candidate_manifest"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(candidate_raw).hexdigest(),
                receipt["candidate_manifest_sha256"],
            )
            self.assertEqual(candidate_raw, historical_raw)
            candidate = json.loads(candidate_raw)
            active = next(
                row
                for row in candidate["releases"]
                if row["revision"] == candidate["active_revision"]
            )
            updated = next(
                row for row in active["documents"] if row["path"] == DOCUMENT
            )
            blob = candidate["blobs"][updated["sha256"]]
            parts = [
                gzip.decompress((target / "catalogs" / row["path"]).read_bytes())
                for row in blob["parts"]
            ]
            new_raw = b"".join(parts)
            self.assertEqual(hashlib.sha256(new_raw).hexdigest(), updated["sha256"])
            merged = json.loads(new_raw)
            self.assertEqual(
                {key: merged["effects"][key] for key in original["effects"]},
                original["effects"],
            )
            self.assertEqual(
                set(merged["effects"]) - set(original["effects"]),
                set(proof["exported_rows"]),
            )
            for reference, row in proof["exported_rows"].items():
                self.assertEqual(merged["effects"][reference], row)
                self.assertIs(row["criterion_present"], True)
                self.assertEqual(row["area_class"], "anH")
                self.assertEqual(row["raw_parameters"], [1, 0, 0, 0, 1, 0])
            # Main identity changes once; mining/fishing remain pinned exactly.
            for role in ("mining_revision", "fishing_revision"):
                self.assertEqual(public["catalogs"][role], old_top["catalogs"][role])
            self.assertEqual(
                candidate["active_revision"], historical["active_revision"]
            )
            self.assertNotEqual(
                candidate["active_revision"], baseline["active_revision"]
            )
            self.assertEqual(
                (target / "catalogs/manifest.json").read_bytes(), baseline_raw
            )
            second = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(second.stdout), receipt)
            self.assertEqual((target / "manifest.json").read_bytes(), result_top)
            corrupt = json.loads(result_top)
            corrupt["artifacts"]["native-catalogs"]["sha256"] = "0" * 64
            (target / "manifest.json").write_bytes(encoded(corrupt))
            rejected = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("manifest checksum mismatch", rejected.stderr)
